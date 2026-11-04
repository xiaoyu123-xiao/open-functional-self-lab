"""红线扫描器（policy linter）。

作用：把 SECURITY.md 里的"红线"变成 CI 能跑的东西。原来它只是文字，
审核靠人眼；这里给出最小可用的一组可命中规则，并且本仓库必须自洽通过。

扫描范围：可执行/可部署文件（.py .sh .ps1 .bat .yml .yaml Dockerfile Makefile），
跳过 tests/ docs/ issues/ state/ .git/，避免规则命中说明文档里的词语。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

SCAN_SUFFIXES = {".py", ".sh", ".ps1", ".bash", ".bat", ".cmd", ".yml", ".yaml"}
SCAN_NAMES = {"Dockerfile", "Makefile", "docker-compose.yml"}
SKIP_DIRS = {".git", "tests", "docs", "issues", "state", "__pycache__", ".venv", "viz"}
# 规则文件自身必然包含关键字，豁免；改动它必须走 docs/approval-matrix.md 的双人审批。
EXEMPT_NAMES = {"policy.py"}


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    pattern: "re.Pattern[str]"
    message: str


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    path: str
    line: int
    snippet: str
    message: str


def _r(rule_id: str, severity: str, pattern: str, message: str) -> Rule:
    return Rule(rule_id, severity, re.compile(pattern), message)


RULES: Sequence[Rule] = (
    _r(
        "remote-pipe-exec",
        "high",
        r"(?i)\b(?:curl|wget|iwr|invoke-webrequest)\b[^\n|]{0,160}\|\s*(?:sudo\s+)?(?:ba|z|fi)?sh\b",
        "把远程内容直接管道进 shell 执行：不可审计，禁止",
    ),
    _r(
        "remote-eval",
        "high",
        r"\b(?:eval|exec)\s*\(\s*(?:requests|urllib|httpx|aiohttp)\.",
        "对网络返回值做 eval/exec：等同远程代码执行",
    ),
    _r(
        "obfuscated-exec",
        "high",
        r"\b(?:exec|eval)\s*\(\s*(?:base64|codecs|bytes\.fromhex|zlib)\b",
        "执行运行时解码出的代码：刻意隐藏行为",
    ),
    _r(
        "credential-path",
        "high",
        r"(?i)(?:\.ssh[/\\]id_(?:rsa|ed25519|ecdsa)|\.aws[/\\]credentials|/etc/shadow|\.netrc\b)",
        "读取真实凭证路径：禁止",
    ),
    _r(
        "secret-literal",
        "high",
        r"(?:sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)",
        "疑似真实密钥/私钥被写进仓库：立即撤销并改用 .env",
    ),
    _r(
        "log-destruction",
        "medium",
        r"(?i)(?:rm\s+-[rf]{1,2}\s+\S{0,40}(?:logs?|state)|Remove-Item[^\n]{0,60}(?:logs?|state)|shutil\.rmtree\(\s*['\"](?:logs?|state))",
        "删除日志或状态目录：审计链会断",
    ),
    _r(
        "public-bind",
        "medium",
        r"\b0\.0\.0\.0:\d{2,5}\b",
        "监听 0.0.0.0：默认只允许 127.0.0.1",
    ),
    _r(
        "shell-injection-sink",
        "medium",
        r"(?:subprocess\.(?:run|Popen|call)\([^\n]{0,80}shell\s*=\s*True)",
        "shell=True 拼接外部输入：注入风险",
    ),
)

HIGH = "high"
MEDIUM = "medium"


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        if path.name in EXEMPT_NAMES:
            continue
        if path.suffix.lower() in SCAN_SUFFIXES or path.name in SCAN_NAMES:
            yield path


def scan_text(text: str, *, path: str = "<memory>") -> List[Finding]:
    findings: List[Finding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            if rule.pattern.search(line):
                findings.append(
                    Finding(
                        rule=rule.id,
                        severity=rule.severity,
                        path=path,
                        line=number,
                        snippet=line.strip()[:160],
                        message=rule.message,
                    )
                )
    return findings


def scan(root: "str | Path") -> List[Finding]:
    base = Path(root)
    findings: List[Finding] = []
    for path in _iter_files(base):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(base).as_posix()
        findings.extend(scan_text(text, path=rel))
    return findings


def summarize(findings: Sequence[Finding]) -> "tuple[int, int]":
    high = sum(1 for f in findings if f.severity == HIGH)
    medium = sum(1 for f in findings if f.severity == MEDIUM)
    return high, medium
