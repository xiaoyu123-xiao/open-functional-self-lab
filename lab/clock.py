"""统一时钟。

硬规则（与 docs/time.md 一致）：
1. 只接受 UTC aware 时间；naive datetime 直接抛错，不允许进日志。
2. 对外一律 `YYYY-MM-DDTHH:MM:SSZ`，秒级，便于账本哈希稳定复现。
3. 耗时用单调计数计算，系统时钟回拨不会产生负时长。
4. 测试用 FakeClock 注入时间，账本哈希可完全复现。
"""

from __future__ import annotations

import datetime as _dt
import time as _monotonic

UTC = _dt.timezone.utc
ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def to_iso(when: _dt.datetime) -> str:
    """转成 UTC ISO 8601 字符串；naive 时间视为程序错误。"""
    if when.tzinfo is None:
        raise ValueError("naive datetime 不允许进入记录：请使用 UTC aware 时间")
    return when.astimezone(UTC).strftime(ISO_FMT)


def parse_iso(text: str) -> _dt.datetime:
    """解析 ISO 8601；缺时区按 UTC 处理，返回 aware UTC。"""
    cleaned = text.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    parsed = _dt.datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def elapsed_seconds(start_ns: int, end_ns: int) -> float:
    """用单调计数算耗时；回退视为错误，避免负数污染指标。"""
    delta = int(end_ns) - int(start_ns)
    if delta < 0:
        raise ValueError("单调计数回退：传入的不是 monotonic 值")
    return delta / 1_000_000_000


class Clock:
    """生产时钟。"""

    def now(self) -> _dt.datetime:
        return _dt.datetime.now(UTC)

    def now_iso(self) -> str:
        return to_iso(self.now())

    def monotonic_ns(self) -> int:
        return _monotonic.monotonic_ns()


class FakeClock(Clock):
    """测试时钟：可注入起点、可推进，保证同一输入得到同一账本。"""

    def __init__(self, start: "str | _dt.datetime" = "2026-01-01T00:00:00Z") -> None:
        self._now = parse_iso(start) if isinstance(start, str) else start.astimezone(UTC)
        self._mono = 0

    def now(self) -> _dt.datetime:
        return self._now

    def now_iso(self) -> str:
        return to_iso(self._now)

    def monotonic_ns(self) -> int:
        return self._mono

    def advance(self, seconds: float) -> _dt.datetime:
        step = float(seconds)
        if step < 0:
            raise ValueError("FakeClock 只能向前推进")
        self._now = self._now + _dt.timedelta(seconds=step)
        self._mono += int(step * 1_000_000_000)
        return self._now
