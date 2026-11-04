"""联网检索（白名单 + 默认离线）。

对应你对话里的原话：
    #36 "时时刻刻关注生物化学物理方面的科学院，实验室学术论文"
    #42 "做那种自己去网上搜索资料，然后自我进化、自我革新的功能"

设计原则（都是硬约束，不是建议）：
1. **默认离线**：不显式传 `allow_network=True` 时，任何 URL 都不会被访问。
2. **白名单**：域名不在表里 → 直接拒绝并记录，不重试。
3. **不存全文**：只保留标题、摘要（≤400 字）、URL、访问时间；正文即弃。
4. **有预算**：每次请求前先扣 `search_requests_per_day`，超了就不发。
5. **可替换**：`OfflineFetcher` 用本地目录当"互联网"，测试和演示都跑它。

一句话：这不是爬虫，是**受限取样器**。
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# 只放公开、允许机器读取的学术/开放数据源；每条都要能说清条款。
ALLOWLIST: Dict[str, str] = {
    "export.arxiv.org": "arXiv API，遵守 3 秒间隔，不批量镜像",
    "api.openalex.org": "OpenAlex，CC0 元数据，需署名来源",
    "api.semanticscholar.org": "Semantic Scholar，免费额度有限，429 需退避",
    "eutils.ncbi.nlm.nih.gov": "PubMed E-utilities，高频需 API key",
    "api.github.com": "GitHub，仅公开仓库只读",
}

MAX_SUMMARY_CHARS = 400
MAX_BYTES = 256 * 1024
TIMEOUT_SECONDS = 10


class NotAllowed(RuntimeError):
    """域名不在白名单，或未开启联网。"""


def host_of(url: str) -> str:
    return urllib.parse.urlparse(url).hostname or ""


def is_allowed(url: str) -> bool:
    host = host_of(url).lower()
    return any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWLIST)


def parse_atom_entries(text: str, limit: int = 10) -> List[Dict[str, str]]:
    """把 arXiv/Atom 的返回拆成逐条论文（title / summary / url）。

    v0.38：之前只取整份 feed 的标题，等于什么都没取到——这是取样器的缺陷。
    """
    import re

    entries: List[Dict[str, str]] = []
    for block in re.findall(r"<entry>(.*?)</entry>", text, flags=re.S)[:limit]:
        title = re.search(r"<title>(.*?)</title>", block, flags=re.S)
        summary = re.search(r"<summary>(.*?)</summary>", block, flags=re.S)
        link = re.search(r"<id>(.*?)</id>", block, flags=re.S)
        if not title:
            continue
        entries.append(
            {
                "title": " ".join(title.group(1).split())[:200],
                "summary": " ".join(summary.group(1).split())[:MAX_SUMMARY_CHARS] if summary else "",
                "url": link.group(1).strip() if link else "",
            }
        )
    return entries


def check_url(url: str, allow_network: bool) -> str:
    if not allow_network:
        raise NotAllowed("默认离线：本次没有开启联网（需要 allow_network=True 且经人工批准）")
    if not is_allowed(url):
        raise NotAllowed(f"域名不在白名单：{host_of(url)}（见 lab/web.py 的 ALLOWLIST）")
    return host_of(url)


class OfflineFetcher:
    """把本地目录当"互联网"：`catalog/<name>.json` 里有 url / title / summary。"""

    name = "offline"

    def __init__(self, catalog: Path) -> None:
        self.catalog = Path(catalog)

    def fetch(self, url: str) -> Dict[str, Any]:
        if not self.catalog.exists():
            raise FileNotFoundError(f"离线目录不存在：{self.catalog}")
        for item in sorted(self.catalog.glob("*.json")):
            data = json.loads(item.read_text(encoding="utf-8-sig"))
            if data.get("url") == url:
                return {
                    "url": url,
                    "title": str(data.get("title", ""))[:200],
                    "summary": str(data.get("summary", ""))[:MAX_SUMMARY_CHARS],
                    "fetched_at": "",
                    "bytes": len(str(data.get("summary", "")).encode("utf-8")),
                    "fetcher": self.name,
                }
        raise FileNotFoundError(f"离线目录里没有这个 URL：{url}")


class LiveFetcher:
    """真实网络。默认不会被构造——必须显式 allow_network=True 且 URL 在白名单。"""

    name = "live"

    def __init__(self, allow_network: bool = False, timeout: int = TIMEOUT_SECONDS) -> None:
        self.allow_network = allow_network
        self.timeout = timeout

    def fetch(self, url: str) -> Dict[str, Any]:
        check_url(url, self.allow_network)
        request = urllib.request.Request(url, headers={"User-Agent": "ofsl/0.3 (+research; contact in repo)"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - 白名单已校验
            raw = response.read(MAX_BYTES)
        text = raw.decode("utf-8", errors="replace")
        entries = parse_atom_entries(text)
        if entries:
            return {
                "url": url,
                "title": f"{len(entries)} 篇",
                "summary": "",
                "entries": entries,
                "fetched_at": "",
                "bytes": len(raw),
                "fetcher": self.name,
            }
        summary = " ".join(text.split())[:MAX_SUMMARY_CHARS]
        return {
            "url": url,
            "title": host_of(url),
            "summary": summary,
            "fetched_at": "",
            "bytes": len(raw),
            "fetcher": self.name,
        }


def fetch_many(
    fetcher: Any, urls: Sequence[str], budget_charge: Optional[Any] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """批量取：逐条计费，失败不抛给调用方，收集到 errors 里。"""
    documents: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for url in urls:
        if budget_charge is not None:
            try:
                budget_charge("search_requests_per_day", 1)
            except Exception as error:  # BudgetExceeded
                errors.append({"url": url, "reason": f"预算拦截：{error}"})
                break
        try:
            document = fetcher.fetch(url)
        except Exception as error:  # 单条失败不影响其它
            errors.append({"url": url, "reason": f"{type(error).__name__}: {error}"})
            continue
        entries = document.get("entries") if isinstance(document, dict) else None
        if entries:                      # v0.38：Atom/arXiv 一次返回多篇，逐篇入库
            for entry in entries:
                documents.append(
                    {
                        "url": entry.get("url") or url,
                        "title": entry.get("title", "")[:200],
                        "summary": entry.get("summary", "")[:MAX_SUMMARY_CHARS],
                        "fetched_at": document.get("fetched_at", ""),
                        "bytes": len(entry.get("summary", "").encode("utf-8")),
                        "fetcher": document.get("fetcher", "live"),
                    }
                )
        else:
            documents.append(document)
    return documents, errors
