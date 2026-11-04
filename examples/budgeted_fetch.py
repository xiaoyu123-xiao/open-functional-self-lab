"""示例 3：带预算的取样器——白名单 + 先扣费 + 只存摘要。

它演示三件在真实抓取里最容易出事的事：
    1. 域名不在白名单 → 直接拒绝，不重试
    2. 先扣预算再请求（超了就不发）
    3. 只保留标题/摘要/URL，不存全文

跑法：
    python examples/budgeted_fetch.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab.budget import Budget, BudgetExceeded  # noqa: E402
from lab.knowledge import KnowledgeBase  # noqa: E402
from lab.ledger import Ledger  # noqa: E402
from lab.web import OfflineFetcher, fetch_many  # noqa: E402


def demo(cap: float = 2.0, workdir: Path | None = None) -> dict:
    base = Path(workdir) if workdir else Path("state")
    base.mkdir(parents=True, exist_ok=True)
    catalog = ROOT / "docs" / "catalog"
    ledger = Ledger(base / "demo-fetch-ledger.jsonl")
    budget = Budget({"search_requests_per_day": cap}, ledger, "2026-01-01T00:00:00Z", run_id="demo-fetch")

    # 用离线目录当"互联网"（不联网也能演示全部逻辑）
    urls = [json.loads(item.read_text(encoding="utf-8"))["url"] for item in sorted(catalog.glob("*.json"))]
    print(f"候选 {len(urls)} 条，预算上限 {cap} 次")

    documents, errors = fetch_many(
        OfflineFetcher(catalog), urls, budget_charge=lambda kind, amount: budget.charge(kind, amount)
    )
    print(f"取回 {len(documents)} 条，跳过 {len(errors)} 条")
    for error in errors[:2]:
        print(f"  跳过原因：{error['reason'][:80]}")

    kb = KnowledgeBase(base / "demo-knowledge.jsonl")
    added = 0
    for document in documents:
        entry = kb.add(
            claim=document["title"],
            source_url=document["url"],
            evidence=document["summary"],
            accessed_at="2026-01-01T00:00:00Z",
        )
        added += 1 if entry else 0
    print(f"入库 {added} 条新声明（只存标题+摘要+URL，不存全文）")

    # 演示白名单拒绝
    try:
        fetch_many(OfflineFetcher(catalog), ["https://example.com/secret"], budget_charge=None)
    except Exception as error:  # OfflineFetcher 找不到时会报 FileNotFound，真实场景是 NotAllowed
        print(f"非白名单/不存在的地址会被拒绝：{type(error).__name__}")
    print("提示：真实联网需要 `lab ask --resource web.fetch` + 人工批准。")
    return {"fetched": len(documents), "skipped": len(errors), "added": added}


if __name__ == "__main__":
    try:
        demo()
    except BudgetExceeded as error:
        print(f"预算拦截（这是设计）：{error}")
