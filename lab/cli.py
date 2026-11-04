"""命令行入口：`python -m lab.cli <command>`。

v0.1 只提供控制面（不训练、不联网）：
    doctor   环境与仓库自检
    init     初始化 state/
    run      跑一次受控实验循环（模拟芯，用于验证预算/状态机/账本/回滚）
    verify   校验账本哈希链、状态机重放、checkpoint、预算不变量
    lint     红线扫描（SECURITY.md 的可执行版）
    viz      生成 viz/status.md
    report   生成周报到 state/reports/
    status   打印当前状态
    freeze   紧急冻结（kill switch）
    unfreeze 人工解冻（需 --by 记录操作者）
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import __version__
from .budget import DEFAULT_CAPS, Budget, BudgetExceeded
from .env import GridWorld, greedy_action, persistence_error
from .clock import Clock, FakeClock, parse_iso, to_iso
from .ledger import Ledger
from .notify import DEDUPE_HOURS, LEVELS, Notifier
from .predict import benchmark as run_benchmark
from .collab import analyse as analyse_behaviour
from .core import evaluate_policy, load_object, run_generic_episode
from .collab import build_proposals, emergent_gap, record_choice
from .knowledge import KnowledgeBase
from .perm import Permissions
from .store import SqliteStore
from .transfer import format_report as format_transfer
from .transfer import run as run_transfer
from .loop import cycle as run_cycle, format_cycle
from .selfmodel import SelfModel
from .web import LiveFetcher, OfflineFetcher, fetch_many
from .predict import render_report as render_bench
from .report import render as render_report
from .state import STATES, IllegalTransition, StateStore
from .viz import render as render_viz

CONFIG_NAME = "lab.config.json"
REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "ETHICS.md",
    "GOVERNANCE.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "lab.config.json",
    "pyproject.toml",
)

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": 1,
    "budget": dict(DEFAULT_CAPS),
    "run": {"seed": 20261104, "steps_default": 20},
    "policy": {"fail_on": "high"},
}

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_BUDGET = 3


# ---------------------------------------------------------------- 基础设施


class Context:
    def __init__(self, root: Path, clock: Clock) -> None:
        self.root = root.resolve()
        self.clock = clock
        self.state_dir = self.root / "state"
        self.ledger = Ledger(self.state_dir / "ledger.jsonl")
        self.store = StateStore(self.state_dir / "state.json")

    @property
    def config_path(self) -> Path:
        return self.root / CONFIG_NAME

    def config(self) -> Dict[str, Any]:
        merged = json.loads(json.dumps(DEFAULT_CONFIG))
        if self.config_path.exists():
            loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError(f"{CONFIG_NAME} 顶层必须是对象")
            if int(loaded.get("version", 0)) != 1:
                raise ValueError(f"{CONFIG_NAME} 的 version 必须是 1，当前 {loaded.get('version')!r}")
            for key, value in loaded.items():
                if key == "budget" and isinstance(value, dict):
                    merged["budget"].update(value)
                elif isinstance(value, dict) and isinstance(merged.get(key), dict):
                    merged[key].update(value)
                else:
                    merged[key] = value
        return merged

    def db(self) -> SqliteStore:
        return SqliteStore(self.state_dir / "lab.sqlite3")

    def permissions(self) -> Permissions:
        return Permissions(self.state_dir / "perms.json")

    def knowledge(self) -> KnowledgeBase:
        return KnowledgeBase(self.state_dir / "knowledge.jsonl")

    def self_model(self) -> SelfModel:
        return SelfModel(self.state_dir / "self.json")

    def notifier(self, echo: bool = True) -> Notifier:
        return Notifier(self.ledger, self.clock, self.state_dir, echo=echo)

    def budget(self, run_id: "str | None" = None) -> Budget:
        return Budget(self.config()["budget"], self.ledger, self.clock.now_iso(), run_id)


def _emit(text: str = "") -> None:
    print(text)


def _table(rows: List[Tuple[str, str, str]]) -> str:
    widths = [max(len(str(row[i])) for row in rows) for i in range(3)]
    lines = []
    for row in rows:
        lines.append("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
    return "\n".join(lines)


# ---------------------------------------------------------------- doctor


def _check_python() -> Tuple[str, str]:
    version = sys.version_info
    if version < (3, 10):
        return "FAIL", f"Python {version.major}.{version.minor} 低于 3.10"
    return "OK", f"Python {version.major}.{version.minor}.{version.micro}"


def _check_layout(root: Path) -> Tuple[str, str]:
    missing = [name for name in REQUIRED_FILES if not (root / name).exists()]
    if missing:
        return "FAIL", "缺少文件：" + ", ".join(missing)
    return "OK", f"{len(REQUIRED_FILES)} 个必需文件齐全"


def _check_stdlib_time() -> Tuple[str, str]:
    import time as stdlib_time

    if getattr(stdlib_time, "__file__", None):
        return "WARN", f"标准库 time 被遮蔽：{stdlib_time.__file__}"
    return "OK", "标准库 time 未被仓库内同名目录遮蔽"


def _check_state_dir(ctx: Context) -> Tuple[str, str]:
    try:
        ctx.state_dir.mkdir(parents=True, exist_ok=True)
        probe = ctx.state_dir / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as error:
        return "FAIL", f"state/ 不可写：{error}"
    return "OK", "state/ 可写"


def _check_disk(root: Path) -> Tuple[str, str]:
    try:
        usage = shutil.disk_usage(str(root))
    except OSError as error:
        return "WARN", f"无法读取磁盘信息：{error}"
    free_gb = usage.free / (1024**3)
    status = "OK" if free_gb >= 1.0 else "WARN"
    return status, f"剩余 {free_gb:.1f} GB"


def _check_git() -> Tuple[str, str]:
    found = shutil.which("git")
    if not found:
        return "WARN", "未找到 git（仅影响发布流程，不影响本地运行）"
    return "OK", found


def _check_config(ctx: Context) -> Tuple[str, str]:
    try:
        config = ctx.config()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return "FAIL", f"{CONFIG_NAME} 解析失败：{error}"
    return "OK", f"预算类别 {len(config['budget'])} 项，seed={config['run']['seed']}"


def _check_policy(ctx: Context) -> Tuple[str, str]:
    from .policy import scan, summarize

    findings = scan(ctx.root)
    high, medium = summarize(findings)
    if high:
        return "FAIL", f"{high} 条高危红线命中（用 `lint` 看详情）"
    if medium:
        return "WARN", f"{medium} 条中危提示"
    return "OK", "红线扫描无命中"


def _check_ps1_bom(root: Path) -> Tuple[str, str]:
    """含中文的 .ps1 必须带 UTF-8 BOM。

    Windows PowerShell 5.1 读无 BOM 的 UTF-8 会按 ANSI 解码，中文变乱码后连引号都配对不上，
    报 "字符串缺少终止符"。这个坑在写 publish.ps1 时真踩过，所以做成检查。
    """
    skip = {".git", "state", "__pycache__", ".venv"}
    offenders: List[str] = []
    checked = 0
    for path in sorted(root.rglob("*.ps1")):
        if any(part in skip for part in path.relative_to(root).parts[:-1]):
            continue
        checked += 1
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            continue
        if any(byte > 127 for byte in raw):
            offenders.append(path.relative_to(root).as_posix())
    if offenders:
        return "FAIL", "缺 UTF-8 BOM（PowerShell 5.1 会报“字符串缺少终止符”）：" + ", ".join(offenders)
    return "OK", f"{checked} 个 .ps1 均可用"


def _check_version(root: Path) -> Tuple[str, str]:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return "WARN", "缺少 pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    needle = f'version = "{__version__}"'
    if needle not in text:
        return "WARN", f"pyproject.toml 中的 version 与 lab.__version__（{__version__}）不一致"
    return "OK", f"版本一致：{__version__}"


def cmd_doctor(args: argparse.Namespace, ctx: Context) -> int:
    checks = [
        ("python", _check_python()),
        ("layout", _check_layout(ctx.root)),
        ("stdlib-time", _check_stdlib_time()),
        ("state-dir", _check_state_dir(ctx)),
        ("config", _check_config(ctx)),
        ("version", _check_version(ctx.root)),
        ("ps1-bom", _check_ps1_bom(ctx.root)),
        ("policy", _check_policy(ctx)),
        ("git", _check_git()),
        ("disk", _check_disk(ctx.root)),
    ]
    rows = [(name, status, detail) for name, (status, detail) in checks]
    failures = [name for name, (status, _) in checks if status == "FAIL"]
    warnings = [name for name, (status, _) in checks if status == "WARN"]

    if args.json:
        _emit(
            json.dumps(
                {
                    "ok": not failures,
                    "checks": [{"name": n, "status": s, "detail": d} for n, s, d in rows],
                    "failures": failures,
                    "warnings": warnings,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        _emit(f"open-functional-self-lab {__version__} · doctor")
        _emit(_table([(f"[{s}]", n, d) for n, s, d in rows]))
        _emit("")
        if failures:
            _emit(f"结果：{len(failures)} 项失败 → {', '.join(failures)}")
        elif warnings:
            _emit(f"结果：通过（{len(warnings)} 项警告：{', '.join(warnings)}）")
        else:
            _emit("结果：全部通过")
    return EXIT_FAIL if failures else EXIT_OK


# ---------------------------------------------------------------- init


def cmd_init(args: argparse.Namespace, ctx: Context) -> int:
    ctx.state_dir.mkdir(parents=True, exist_ok=True)
    config = ctx.config()
    first = not ctx.store.exists()
    if first:
        ctx.store.save({"status": "INIT", "history": []})
        ctx.ledger.append(
            "init",
            {"version": __version__, "seed": config["run"]["seed"], "caps": config["budget"]},
            ts=ctx.clock.now_iso(),
            actor="human" if args.by else "system",
        )
        _emit(f"已初始化：{ctx.state_dir}")
        _emit("下一步：python -m lab.cli run --steps 20")
    else:
        _emit(f"已初始化过（状态 {ctx.store.status()}），未改动。")
    return EXIT_OK


# ---------------------------------------------------------------- run


def _episode_records(seed: int, steps: int) -> "List[Dict[str, Any]]":
    """跑一段确定性回合，返回每步要写进账本的记录。

    从 v0.1.1 起不再是"编出来的数字"：每一步都来自 lab/env.py 的 8×8 网格环境
    （有墙、食物、危险区，能量会掉、踩危险区会受伤）。
    """
    environment = GridWorld(seed)
    observed = environment.observe()
    records: List[Dict[str, Any]] = []
    for _ in range(steps):
        action = greedy_action(environment)
        outcome = environment.step(action)
        after = outcome["observation"]
        records.append(
            {
                "step": outcome["step"],
                "action": action,
                "blocked": outcome["blocked"],
                "ate": outcome["ate"],
                "hurt": outcome["hurt"],
                "x": after["x"],
                "y": after["y"],
                "energy": after["energy"],
                "damage": after["damage"],
                "homeostatic_error": outcome["homeostatic_error"],
                "prediction_error": persistence_error(observed, after, ("x", "y", "energy", "damage")),
            }
        )
        observed = after
    return records


def _write_checkpoint(ctx: Context, run_id: str, steps: int, last_hash: str) -> Path:
    directory = ctx.state_dir / "checkpoints"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{run_id}.json"
    payload = {"run_id": run_id, "steps": steps, "ledger_hash": last_hash}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def cmd_run(args: argparse.Namespace, ctx: Context) -> int:
    config = ctx.config()
    seed = int(config["run"]["seed"])
    steps = int(args.steps if args.steps is not None else config["run"]["steps_default"])
    if steps <= 0:
        _emit("步数必须是正整数", )
        return EXIT_USAGE
    if not ctx.store.exists():
        cmd_init(argparse.Namespace(json=False, by=False), ctx)

    status = ctx.store.status()
    if status == "FROZEN":
        _emit("当前已冻结：先 `python -m lab.cli unfreeze --by <你的名字>` 再运行。")
        return EXIT_FAIL
    if status in ("ARCHIVED",):
        _emit("状态 ARCHIVED：不允许继续运行。")
        return EXIT_FAIL
    if status == "REVIEWING":
        _emit('上一轮还没评审：先 python -m lab.cli review --pass，或 review --fail --reason 原因')
        return EXIT_FAIL
    if status in ("INIT",):
        ctx.store.transition("READY", ts=ctx.clock.now_iso(), actor="system", reason="首次运行")
        ctx.ledger.append("transition", ctx.store.load()["history"][-1], ctx.clock.now_iso(), actor="system")

    run_id = f"run-{len(ctx.ledger.events('run_start')) + 1:03d}"
    ledger_before = len(ctx.ledger.read())
    _emit(f"启动 {run_id}：{steps} 步，seed={seed}")
    ctx.ledger.append("run_start", {"run_id": run_id, "steps": steps, "seed": seed}, ctx.clock.now_iso())
    ctx.store.transition("RUNNING", ts=ctx.clock.now_iso(), actor="agent", reason=f"{run_id} 开始")
    ctx.ledger.append("transition", ctx.store.load()["history"][-1], ctx.clock.now_iso())

    budget = ctx.budget(run_id)
    executed = 0
    try:
        budget.check("steps_per_run", steps)
        budget.check("steps_per_day", steps)   # v0.1.4：没有日总量就能无限次 run
        last_record = None
        for record in _episode_records(seed, steps):
            budget.charge("steps_per_run", 1)
            budget.charge("steps_per_day", 1)
            budget.charge("wall_clock_hours_per_run", 0.01)
            ctx.ledger.append("step", record, ctx.clock.now_iso())
            executed += 1
            last_record = record
    except BudgetExceeded as error:
        _emit(f"预算闸门拦截：{error}")
        ctx.notifier().emit("high", "budget", str(error), dedupe_key="budget", needs_action=True)
        ctx.store.transition("ROLLING_BACK", ts=ctx.clock.now_iso(), actor="system", reason="预算超限")
        ctx.ledger.append("transition", ctx.store.load()["history"][-1], ctx.clock.now_iso())
        ctx.store.transition("READY", ts=ctx.clock.now_iso(), actor="system", reason="回滚完成")
        ctx.ledger.append("transition", ctx.store.load()["history"][-1], ctx.clock.now_iso())
        _emit(f"已回滚，执行 {executed} 步后停止。")
        return EXIT_BUDGET

    # v0.1.4：不再自己宣布"评审通过"。停在 REVIEWING，等 `lab review` 或人来判。
    ctx.store.transition("REVIEWING", ts=ctx.clock.now_iso(), actor="agent", reason="本轮结束，等待独立评审")
    ctx.ledger.append("transition", ctx.store.load()["history"][-1], ctx.clock.now_iso())

    last = ctx.ledger.last() or {}
    checkpoint = _write_checkpoint(ctx, run_id, executed, str(last.get("hash", "")))
    ctx.ledger.append(
        "checkpoint",
        {"run_id": run_id, "steps": executed, "path": checkpoint.relative_to(ctx.root).as_posix(), "ledger_hash": last.get("hash")},
        ctx.clock.now_iso(),
    )
    _emit(f"完成：{executed} 步，checkpoint → {checkpoint.relative_to(ctx.root).as_posix()}")
    if last_record:
        _emit(
            f"末态：位置({int(last_record['x'])},{int(last_record['y'])}) 能量 {last_record['energy']} "
            f"损伤 {last_record['damage']} 稳态误差 {last_record['homeostatic_error']} "
            f"预测误差 {last_record['prediction_error']}"
        )
    model = ctx.self_model()
    if model.exists():
        mean_error = round(sum(record.get("prediction_error", 0.0) for record in _episode_records(seed, min(steps, 200))) / max(1, min(steps, 200)), 6)
        model.touch_session(ctx.clock.now_iso())
        model.record_run(
            ts=ctx.clock.now_iso(),
            run_id=run_id,
            steps=executed,
            mean_error=mean_error,
            accepted=False,          # 评审通过后才改成 True
        )
    _emit(f"新增账本事件 {len(ctx.ledger.read()) - ledger_before} 条")
    _emit("等待评审：python -m lab.cli review --pass   （不通过则 --fail --reason \"原因\"）")
    return EXIT_OK


# ---------------------------------------------------------------- verify


def cmd_verify(args: argparse.Namespace, ctx: Context) -> int:
    results: List[Tuple[str, bool, str]] = []

    ok, detail = ctx.ledger.verify()
    results.append(("账本哈希链", ok, detail))

    ok, detail = ctx.store.verify_history()
    results.append(("状态机重放", ok, detail))

    # 交叉校验：state.json 里每次转换，账本必须有对应记录且顺序一致
    history = [(step.get("from"), step.get("to")) for step in ctx.store.load().get("history", [])]
    ledger_transitions = [
        (record.get("payload", {}).get("from"), record.get("payload", {}).get("to"))
        for record in ctx.ledger.events("transition")
    ]
    if history != ledger_transitions:
        results.append(
            ("状态与账本一致", False,
             f"state.json {len(history)} 次转换 vs 账本 {len(ledger_transitions)} 次（不匹配）")
        )
    else:
        results.append(("状态与账本一致", True, f"{len(history)} 次转换一一对应"))

    checkpoints = sorted((ctx.state_dir / "checkpoints").glob("*.json")) if (ctx.state_dir / "checkpoints").exists() else []
    if not checkpoints:
        results.append(("checkpoint", True, "暂无 checkpoint（尚未 run 过）"))
    else:
        broken: List[str] = []
        for path in checkpoints:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not data.get("ledger_hash"):
                broken.append(path.name + "：缺少 ledger_hash")
        results.append(("checkpoint", not broken, "; ".join(broken) or f"{len(checkpoints)} 个 checkpoint 均带账本锚点"))

    budget = ctx.budget()
    over: List[str] = []
    for kind, cap in budget.caps.items():
        used = budget.used(kind)
        if used > cap:
            over.append(f"{kind} 已用 {used:g} > 上限 {cap:g}")
    results.append(("预算不变量", not over, "; ".join(over) or "所有类别未超限"))

    failures = [name for name, ok, _ in results if not ok]
    for name, ok, detail in results:
        _emit(f"[{'OK' if ok else 'FAIL'}] {name}：{detail}")
    _emit("")
    _emit(f"结果：{'通过' if not failures else '失败 → ' + ', '.join(failures)}")
    return EXIT_FAIL if failures else EXIT_OK


# ---------------------------------------------------------------- lint


def cmd_lint(args: argparse.Namespace, ctx: Context) -> int:
    from .policy import HIGH, scan, summarize

    findings = scan(ctx.root)
    high, medium = summarize(findings)
    if not findings:
        _emit("红线扫描：无命中（扫描范围：可执行/可部署文件；文档与测试除外）")
        return EXIT_OK
    for finding in findings:
        _emit(f"[{finding.severity.upper()}] {finding.rule} {finding.path}:{finding.line}")
        _emit(f"       {finding.message}")
        _emit(f"       > {finding.snippet}")
    _emit("")
    _emit(f"合计：{high} 高危 / {medium} 中危")
    fail_on = str(ctx.config().get("policy", {}).get("fail_on", HIGH))
    if high or (fail_on == "medium" and medium):
        return EXIT_FAIL
    return EXIT_OK


# ---------------------------------------------------------------- viz / report


def cmd_viz(args: argparse.Namespace, ctx: Context) -> int:
    target = ctx.root / "viz" / "status.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    text = render_viz(ctx.store, ctx.ledger, ctx.budget(), ctx.clock.now_iso())
    target.write_text(text, encoding="utf-8")
    _emit(f"已写入 {target.relative_to(ctx.root).as_posix()}（{len(text)} 字符）")
    return EXIT_OK


def cmd_report(args: argparse.Namespace, ctx: Context) -> int:
    now = ctx.clock.now_iso()
    text = render_report(ctx.ledger, now)
    directory = ctx.state_dir / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"weekly-{parse_iso(now).strftime('%Y-%m-%d')}.md"
    target.write_text(text, encoding="utf-8")
    _emit(f"已写入 {target.relative_to(ctx.root).as_posix()}（{len(text)} 字符）")
    return EXIT_OK


# ---------------------------------------------------------------- bench


def cmd_bench(args: argparse.Namespace, ctx: Context) -> int:
    if args.steps <= 0 or args.seeds <= 0:
        _emit("steps 和 seeds 都必须是正整数")
        return EXIT_USAGE
    seeds = tuple(range(1, args.seeds + 1))
    summary = run_benchmark(steps=args.steps, seeds=seeds)
    now = ctx.clock.now_iso()
    text = render_bench(summary, now)

    directory = ctx.state_dir / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"bench-{parse_iso(now).strftime('%Y-%m-%d')}.md"
    target.write_text(text, encoding="utf-8")
    ctx.ledger.append(
        "bench",
        {
            "steps_per_seed": args.steps,
            "seeds": list(seeds),
            "samples": summary["samples"],
            "mean": summary["mean"],
        },
        now,
    )

    names = ("random", "persistence", "linear")
    _emit(f"预测基线对比：{summary['samples']} 步（每 seed {args.steps} 步 × {args.seeds} 个 seed）")
    _emit(_table([("预测器", "平均误差", "标准差")] + [
        (name, f"{summary['mean'][name]:.4f}", f"{summary['std'][name]:.4f}") for name in names
    ]))
    best = min(names, key=lambda name: summary["mean"][name])
    _emit("")
    _emit(f"最优：{best}（未做显著性检验，别当结论）")
    _emit(f"报告已写入 {target.relative_to(ctx.root).as_posix()}")
    return EXIT_OK


# ---------------------------------------------------------------- review


def cmd_review(args: argparse.Namespace, ctx: Context) -> int:
    """独立评审入口：v0.1.4 起，`run` 不再自己宣布通过。"""
    if ctx.store.status() != "REVIEWING":
        _emit(f"当前状态 {ctx.store.status()}，没有待评审的回合。先 `python -m lab.cli run`。")
        return EXIT_FAIL
    if not (args.passed or args.failed):
        _emit("必须指定 --pass 或 --fail")
        return EXIT_USAGE

    if args.passed:
        record = ctx.store.transition(
            "READY", ts=ctx.clock.now_iso(), actor=f"human:{args.by}", reason=args.reason or "评审通过"
        )
        ctx.ledger.append("transition", record, ctx.clock.now_iso(), actor=f"human:{args.by}")
        model = ctx.self_model()
        if model.exists():
            try:
                model.mark_review(accepted=True, ts=ctx.clock.now_iso(), reason=args.reason or "评审通过")
            except ValueError:
                pass
        _emit(f"评审通过（{args.by}），状态回到 READY，可以再跑一轮。")
        return EXIT_OK

    record = ctx.store.transition(
        "ROLLING_BACK", ts=ctx.clock.now_iso(), actor=f"human:{args.by}", reason=args.reason or "评审不通过"
    )
    ctx.ledger.append("transition", record, ctx.clock.now_iso(), actor=f"human:{args.by}")
    ctx.notifier().emit("medium", "review-fail", args.reason or "评审不通过", dedupe_key="review-fail")
    model = ctx.self_model()
    if model.exists():
        try:
            model.mark_review(accepted=False, ts=ctx.clock.now_iso(), reason=args.reason or "评审不通过")
        except ValueError:
            pass
    record = ctx.store.transition(
        "READY", ts=ctx.clock.now_iso(), actor=f"human:{args.by}", reason="回滚完成"
    )
    ctx.ledger.append("transition", record, ctx.clock.now_iso(), actor=f"human:{args.by}")
    _emit("评审不通过：已回滚到 READY，请先看 state/reports/ 再决定下一步。")
    return EXIT_OK


# ---------------------------------------------------------------- db / ask / grant


def cmd_db(args: argparse.Namespace, ctx: Context) -> int:
    store = ctx.db()
    if args.action == "backup":
        target = args.to or (ctx.state_dir / "backups" / f"lab-{ctx.clock.now().strftime('%Y%m%d-%H%M%S')}.sqlite3")
        path = store.backup(target)
        _emit(f"已热备份到 {path}（可用 sqlite3 直接打开，不需要停机）")
        return EXIT_OK
    if args.action == "sync":
        ledger_stats = store.sync_ledger(ctx.ledger)
        state_stats = store.sync_state(ctx, ctx.clock.now_iso())
        _emit(f"同步完成：账本 {ledger_stats['ledger_records']} 条（新增 {ledger_stats['inserted']}），"
              f"快照 {state_stats['snapshots']} 份")
        _emit("提示：SQLite 是索引/备份层；账本 JSONL 仍是唯一事实来源，删库可重建。")
        return EXIT_OK
    stats = store.stats()
    _emit(f"数据库：{stats['path']}")
    _emit(f"  事件 {stats['events']} 条，快照 {stats['kv_rows']} 份，大小 {stats['size_kb']} KB")
    _emit(f"  时间范围：{stats['first_ts']} → {stats['last_ts']}")
    return EXIT_OK


def cmd_ask(args: argparse.Namespace, ctx: Context) -> int:
    entry = ctx.permissions().request(ctx.ledger, ctx.clock.now_iso(), args.resource, args.reason)
    _emit(f"已向管理者申请权限：{entry['id']}")
    _emit(f"  资源：{entry['resource']}")
    _emit(f"  理由：{entry['reason']}")
    _emit(f"批准：python -m lab.cli grant {entry['id']} --scope read --by 你的名字")
    return EXIT_OK


def cmd_grant(args: argparse.Namespace, ctx: Context) -> int:
    try:
        grant = ctx.permissions().grant(ctx.ledger, ctx.clock.now_iso(), args.request_id, args.scope, args.by,
                                        ttl_hours=args.ttl_hours)
    except (KeyError, ValueError) as error:
        _emit(f"批准失败：{error}")
        return EXIT_USAGE
    _emit(f"已批准：{grant['resource']}（范围 {grant['scope']}，到期 {grant['expires_at']}）")
    return EXIT_OK


def cmd_deny(args: argparse.Namespace, ctx: Context) -> int:
    try:
        ctx.permissions().deny(ctx.ledger, ctx.clock.now_iso(), args.request_id, args.by, args.reason or "")
    except KeyError as error:
        _emit(f"拒绝失败：{error}")
        return EXIT_USAGE
    _emit("已拒绝，理由已记入账本。")
    return EXIT_OK


def cmd_perms(args: argparse.Namespace, ctx: Context) -> int:
    _emit(ctx.permissions().describe(ctx.clock.now_iso()))
    return EXIT_OK


# ---------------------------------------------------------------- generic


def cmd_generic(args: argparse.Namespace, ctx: Context) -> int:
    """把你自己的环境/策略装进审计外壳（不需要改这个仓库的任何代码）。"""
    try:
        env_factory_or_object = load_object(args.env)
        policy_factory_or_object = load_object(args.policy)
    except (ValueError, ImportError, FileNotFoundError, AttributeError) as error:
        _emit(f"加载失败：{error}")
        return EXIT_USAGE

    env = env_factory_or_object(args.seed) if callable(env_factory_or_object) else env_factory_or_object
    policy = policy_factory_or_object() if callable(policy_factory_or_object) else policy_factory_or_object

    budget = ctx.budget(args.run_id)
    try:
        result = run_generic_episode(
            env=env,
            policy=policy,
            steps=args.steps,
            ledger=ctx.ledger,
            ts_of=ctx.clock.now_iso,
            budget_charge=lambda kind, amount: budget.charge(kind, amount),
            run_id=args.run_id,
        )
    except BudgetExceeded as error:
        _emit(f"预算拦截：{error}")
        return EXIT_BUDGET
    except Exception as error:      # GenericRunError / 用户代码问题
        _emit(f"运行失败：{type(error).__name__}: {error}")
        return EXIT_FAIL

    _emit(f"通用回合完成：{result['steps']} 步，总回报 {result['total_reward']:+.3f}"
          f"，{'提前结束' if result['done'] else '跑满步数'}")
    _emit(f"账本记录 run_id={result['run_id']}（可用 `lab verify` 校验完整性）")

    if args.eval_episodes > 0:
        try:
            stats = evaluate_policy(
                make_env=(lambda seed: env_factory_or_object(seed)) if callable(env_factory_or_object) else (lambda seed: env_factory_or_object),
                policy=policy,
                episodes=args.eval_episodes,
                steps=args.steps,
            )
        except Exception as error:
            _emit(f"评测失败：{type(error).__name__}: {error}")
            return EXIT_FAIL
        _emit(f"留出评测：{stats['episodes']} 回合，平均回报 {stats['mean_return']:+.3f}"
              f"（最好 {stats['best']:+.3f}，最差 {stats['worst']:+.3f}）")
    return EXIT_OK


# ---------------------------------------------------------------- transfer


def cmd_transfer(args: argparse.Namespace, ctx: Context) -> int:
    """跨任务迁移：在三个配置上训练，在没见过的两个配置上考。"""
    _emit(f"任务族 {args.family}")

    summary = run_transfer(
        rounds=args.rounds,
        episodes=args.episodes,
        steps=args.steps,
        eval_count=args.eval_count,
        algo=args.algo,
        repeats=args.repeats,
        family=args.family,
    )
    _emit(format_transfer(summary))
    ctx.ledger.append(
        "transfer",
        {
            "single_mean": summary["single"]["mean"],
            "multi_mean": summary["multi"]["mean"],
            "ratio": summary["ratio"],
            "transfer_helped": summary["transfer_helped"],
        },
        ctx.clock.now_iso(),
    )
    return EXIT_OK


# ---------------------------------------------------------------- autonomy / auto


DEFAULT_CAPABILITIES = ("web.fetch", "gpu.train", "storage.write", "repo.private-read")


def cmd_autonomy(args: argparse.Namespace, ctx: Context) -> int:
    perms = ctx.permissions()
    if args.revoke:
        revoked = perms.revoke_all(ctx.ledger, ctx.clock.now_iso(), args.by)
        _emit(f"已收回 {revoked} 条标准授权，级别降回 supervised。")
        return EXIT_OK
    if not args.level:
        _emit(perms.describe(ctx.clock.now_iso()))
        return EXIT_OK
    capabilities = [item.strip() for item in (args.capabilities or ",".join(DEFAULT_CAPABILITIES)).split(",") if item.strip()]
    try:
        result = perms.set_level(ctx.ledger, ctx.clock.now_iso(), args.level, args.by, capabilities, args.days)
    except ValueError as error:
        _emit(f"设置失败：{error}")
        return EXIT_USAGE
    if args.level == "full":
        _emit(f"已设为 full：{len(result['granted'])} 项标准授权，有效期 {args.days} 天")
        for grant in result["granted"]:
            _emit(f"  {grant['resource']}　到期 {grant['expires_at']}")
        _emit("它之后可以自己联网取样、自己训练，不再逐条申请。随时用 --revoke 收回。")
    else:
        _emit(f"已设为 {args.level}。")
    return EXIT_OK


def cmd_auto(args: argparse.Namespace, ctx: Context) -> int:
    """无人值守：连续跑，遇预算/冻结/待评审就停。"""
    import time

    if ctx.store.status() == "REVIEWING":
        _emit("上一轮还没评审：先 review --pass/--fail，再开自动模式。")
        return EXIT_FAIL
    if ctx.store.status() == "FROZEN":
        _emit("已冻结：先 unfreeze。")
        return EXIT_FAIL

    level = ctx.permissions().level()
    _emit(f"自动模式启动：{args.cycles} 轮，自主级别 {level}，间隔 {args.interval}s")
    completed = 0
    for index in range(1, args.cycles + 1):
        try:
            result = run_cycle(
                policy_path=ctx.state_dir / "policy.json",
                ledger=ctx.ledger,
                ts=ctx.clock.now_iso(),
                rounds=args.rounds,
                episodes_per_round=args.episodes,
                steps=args.steps,
                eval_count=args.eval_count,
                hazards=args.hazards,
                lethal=args.lethal,
                armor=args.armor,
            )
        except BudgetExceeded as error:
            _emit(f"预算拦截，自动停止：{error}")
            break
        completed += 1
        delta = result["after"]["mean_return"] - result["before"]["mean_return"]
        _emit(f"[{index}/{args.cycles}] 留出 {result['after']['mean_return']:+.3f}"
              f"（变化 {delta:+.3f}，{'保留' if result['improved'] else '回滚'}）"
              f" 账本 #{result['record_seq']}")
        if args.interval > 0 and index < args.cycles:
            time.sleep(args.interval)
    _emit(f"自动模式结束：完成 {completed} 轮。下一步可以 collaborate 看它建议，或 emergent 看行为变化。")
    return EXIT_OK


# ---------------------------------------------------------------- collaborate / emergent


def _current_scores(ctx: Context) -> "tuple[bool, float | None, float | None]":
    from .agent import QLearningAgent
    from .tasks import baseline_score, eval_seeds, evaluate

    policy = ctx.state_dir / "policy.json"
    if not policy.exists():
        return False, None, None
    agent = QLearningAgent(policy).load()
    seeds = eval_seeds(10)
    return True, evaluate(agent, seeds, 60, lethal=True)["mean_return"], baseline_score(seeds, 60, lethal=True)["mean_return"]


def cmd_collaborate(args: argparse.Namespace, ctx: Context) -> int:
    """它提方案、你拍板。选完执行，并记住你的偏好。"""
    has_policy, learned, baseline = _current_scores(ctx)
    knowledge_count = len(ctx.knowledge().current())
    pending = len(ctx.notifier(echo=False).pending())

    model = ctx.self_model()
    preferences = model.load().get("preferences", {}) if model.exists() else {}
    proposals = build_proposals(
        has_policy=has_policy,
        learned_score=learned,
        baseline_score=baseline,
        knowledge_count=knowledge_count,
        pending_alerts=pending,
        preferences=preferences,
    )

    _emit(f"现状：策略{'有' if has_policy else '没有'}　留出分数 {learned if learned is None else round(learned,3)}"
          f"　BFS 基线 {None if baseline is None else round(baseline,3)}　知识 {knowledge_count} 条　待回应告警 {pending} 条")
    _emit("")
    _emit("它建议按这个顺序做（选一个，或 -h 看参数）：")
    for index, item in enumerate(proposals, start=1):
        _emit(f"  {index}. [{item['id']}] {item['title']}　—— {item['reason']}（{item['cost']}）")
    _emit("")

    if not args.choose:
        _emit("用 `python -m lab.cli collaborate --choose 1` 选定；选定后我会执行并把你的偏好记下来。")
        return EXIT_OK

    if not 1 <= args.choose <= len(proposals):
        _emit(f"--choose 只能是 1..{len(proposals)}")
        return EXIT_USAGE

    chosen = proposals[args.choose - 1]
    record_choice(ctx.ledger, ctx.clock.now_iso(), proposals, chosen["id"])
    if model.exists():
        data = model.load()
        prefs = data.setdefault("preferences", {})
        prefs[chosen["id"]] = int(prefs.get(chosen["id"], 0)) + 1
        model.save(data)

    _emit(f"你选了：{chosen['title']}（已记进账本，下次会优先排它）")
    mapping = {
        "train": ["loop", "--cycles", "3", "--lethal"],
        "curriculum": ["loop", "--cycles", "3", "--hazards", "6", "--lethal"],
        "armor": ["loop", "--cycles", "3", "--lethal", "--armor"],
        "learn": ["learn"],
        "eval": ["eval", "--lethal"],
        "ack": ["inbox"],
    }
    _emit("执行建议：python -m lab.cli " + " ".join(mapping.get(chosen["id"], ["status"])))
    return EXIT_OK


def cmd_emergent(args: argparse.Namespace, ctx: Context) -> int:
    """行为特征 + 与训练前的差值：本项目的"涌现代理指标"。"""
    steps = [record["payload"] for record in ctx.ledger.events("step")]
    if not steps:
        _emit("还没有 step 记录。先跑一轮：python -m lab.cli run --steps 40")
        return EXIT_OK
    half = max(1, len(steps) // 2)
    before = analyse_behaviour(steps[:half])
    after = analyse_behaviour(steps[half:])
    _emit("行为特征（前一半记录 → 后一半记录）：")
    for key in ("wall_bump_rate", "hazard_entry_rate", "rest_ratio", "food_camp_ratio", "action_entropy"):
        _emit(f"  {key:<20} {before[key]:>8.3f} → {after[key]:>8.3f}")
    notes = emergent_gap(before, after)
    _emit("")
    if notes:
        _emit("变化显著（这是本项目对'涌现'的操作性定义：没人奖励过、但行为变了）：")
        for note in notes:
            _emit(f"  - {note}")
    else:
        _emit("没有显著变化。别硬说涌现——没有变化就是没有变化。")
    _emit("")
    _emit("注意：这些数字只能说明行为分布变了，不能说明'有意识'。")
    return EXIT_OK


# ---------------------------------------------------------------- train / eval / loop


def cmd_train(args: argparse.Namespace, ctx: Context) -> int:
    from .agent import QLearningAgent
    from .linear import LinearQAgent
    from .tasks import train as do_train, train_seeds

    make_agent = LinearQAgent if args.algo == "linear" else QLearningAgent
    agent = make_agent(ctx.state_dir / "policy.json").load()
    stats = do_train(agent, train_seeds(args.episodes), args.steps, epsilon=args.epsilon, lethal=args.lethal, armor=args.armor, hazards=args.hazards)
    agent.save()
    ctx.ledger.append("train", {**stats, "states": len(agent.table)}, ctx.clock.now_iso())
    _emit(f"训练 {stats['episodes']} 个回合：训练集均分 {stats['mean_return']:+.3f}，"
          f"吃到 {stats['ate']}，受伤 {stats['hurt']}，Q 表 {len(agent.table)} 状态")
    _emit("注意：训练集分数不能用来宣称变强，必须看 eval。")
    return EXIT_OK


def cmd_eval(args: argparse.Namespace, ctx: Context) -> int:
    from .agent import QLearningAgent
    from .linear import LinearQAgent
    from .tasks import baseline_score, eval_seeds, evaluate

    make_agent = LinearQAgent if args.algo == "linear" else QLearningAgent
    agent = make_agent(ctx.state_dir / "policy.json").load()
    seeds = eval_seeds(args.count)
    learned = evaluate(agent, seeds, args.steps, lethal=args.lethal, armor=args.armor, hazards=args.hazards)
    baseline = baseline_score(seeds, args.steps, lethal=args.lethal, armor=args.armor, hazards=args.hazards)
    _emit(f"算法：{args.algo}　留出集（seed {seeds[0]}–{seeds[-1]}，{args.steps} 步 × {args.count} 个）：")
    _emit(f"  学到的策略 {learned['mean_return']:+.3f}（吃到 {learned['ate']}，受伤 {learned['hurt']}）")
    _emit(f"  BFS 基线   {baseline['mean_return']:+.3f}（吃到 {baseline['ate']}，受伤 {baseline['hurt']}）")
    _emit(f"  差值 {learned['mean_return'] - baseline['mean_return']:+.3f}")
    return EXIT_OK


def cmd_loop(args: argparse.Namespace, ctx: Context) -> int:
    status = ctx.store.status()
    if status == "REVIEWING":
        _emit("上一轮还没评审：先 `python -m lab.cli review --pass|--fail`")
        return EXIT_FAIL
    if status == "FROZEN":
        _emit("已冻结：先 `python -m lab.cli unfreeze --by <你>`")
        return EXIT_FAIL
    if not ctx.store.exists():
        cmd_init(argparse.Namespace(json=False, by=False), ctx)

    hazards = max(1, min(12, args.hazards))
    knowledge = ctx.knowledge()
    if any("hazard" in entry.get("tags", []) for entry in knowledge.current()):
        hazards = 5
        _emit("知识库里有 hazard 相关声明 → 起始难度 +1（v0.5 里'知识影响行为'的唯一方式）")

    total_improved = 0
    for index in range(1, args.cycles + 1):
        result = run_cycle(
            policy_path=ctx.state_dir / "policy.json",
            ledger=ctx.ledger,
            ts=ctx.clock.now_iso(),
            rounds=args.rounds,
            episodes_per_round=args.episodes,
            steps=args.steps,
            eval_count=args.eval_count,
            hazards=hazards,
            algo=args.algo,
            lethal=args.lethal,
            armor=args.armor,
        )
        _emit(f"—— 第 {index}/{args.cycles} 轮 ——")
        _emit(format_cycle(result))
        total_improved += 1 if result["improved"] else 0
        # 课程：追上基线就加难，追不上就维持难度（不许靠降难度刷分）
        if not args.no_curriculum and result["after"]["mean_return"] >= result["baseline"]["mean_return"]:
            hazards = min(8, hazards + 1)
            _emit(f"课程：难度提升到危险区 {hazards} 个")
    _emit("")
    _emit(f"完成 {args.cycles} 轮，其中 {total_improved} 轮变好并保留了新策略。")
    return EXIT_OK


# ---------------------------------------------------------------- learn / knowledge


def cmd_learn(args: argparse.Namespace, ctx: Context) -> int:
    """从白名单取样 → 抽成声明入库。默认离线（读 docs/catalog 里的样本）。"""
    catalog = Path(args.catalog) if args.catalog else (ctx.root / "docs" / "catalog")
    if args.online:
        if not args.url:
            _emit("--online 需要至少一个 --url，且域名必须在白名单里")
            return EXIT_USAGE
        if not ctx.permissions().check("web.fetch", ctx.clock.now_iso()):
            _emit("还没有联网权限。先申请：")
            _emit('  python -m lab.cli ask --resource web.fetch --reason "从白名单源取声明以做交叉验证"')
            _emit("  然后由管理者批准：python -m lab.cli grant <申请编号> --scope read --by 你的名字")
            return EXIT_FAIL
        urls = list(args.url)
        fetcher = LiveFetcher(allow_network=True)
    else:
        if not catalog.exists():
            _emit(f"离线目录不存在：{catalog}")
            return EXIT_FAIL
        docs = [json.loads(item.read_text(encoding="utf-8-sig")) for item in sorted(catalog.glob("*.json"))]
        if args.per_domain and args.per_domain > 0:
            from collections import defaultdict
            from urllib.parse import urlparse

            buckets = defaultdict(list)
            for doc in docs:
                buckets[urlparse(str(doc["url"])).hostname or "unknown"].append(doc)
            docs = [doc for items in buckets.values() for doc in items[: args.per_domain]]
            _emit(f"按域名限流：{len(buckets)} 个来源，各取最多 {args.per_domain} 条")
        urls = [str(doc["url"]) for doc in docs]
        fetcher = OfflineFetcher(catalog)

    budget = ctx.budget()
    documents, errors = fetch_many(fetcher, urls, budget_charge=lambda kind, amount: budget.charge(kind, amount))
    knowledge = ctx.knowledge()
    now = ctx.clock.now_iso()
    added = 0
    for document in documents:
        entry = knowledge.add(
            claim=document.get("title") or document.get("summary", "")[:80],
            source_url=document["url"],
            evidence=document.get("summary", ""),
            accessed_at=now,
            tags=list(args.tag or []),
        )
        if entry is not None:
            added += 1
    changed = knowledge.recompute_status(now)
    ctx.ledger.append(
        "learn",
        {
            "fetcher": "live" if args.online else "offline",
            "requested": len(urls),
            "fetched": len(documents),
            "added": added,
            "errors": len(errors),
        },
        now,
    )
    _emit(f"取样 {len(documents)}/{len(urls)} 条，入库 {added} 条新声明，状态重算 {len(changed)} 条")
    for error in errors[:3]:
        _emit(f"  跳过 {error['url']}：{error['reason']}")
    stats = knowledge.stats()
    _emit(f"知识库：共 {stats['total']} 条，状态 {stats['by_status']}，来源域名 {len(stats['domains'])} 个")
    if not args.online:
        _emit("（离线模式：用的是 docs/catalog 里的样本，没有访问真实网络）")
    return EXIT_OK


def cmd_knowledge(args: argparse.Namespace, ctx: Context) -> int:
    knowledge = ctx.knowledge()
    action = args.action

    if action == "check":
        ok, detail = knowledge.verify_hashes()
        _emit(f"[{'OK' if ok else 'FAIL'}] 知识库哈希：{detail}")
        return EXIT_OK if ok else EXIT_FAIL

    if action == "review":
        due = knowledge.due_for_review(ctx.clock.now_iso())
        if not due:
            _emit("没有到期待复审的条目。")
            return EXIT_OK
        for entry in due:
            knowledge.review(int(entry["id"]), "pending", ctx.clock.now_iso(), note="到期自动降级为待验证")
        _emit(f"{len(due)} 条到期，已降级为「待验证」并延长复审周期")
        return EXIT_OK

    if action == "gaps":
        gaps = knowledge.single_source_claims()
        if not gaps:
            _emit("没有单一来源的声明：所有声明都有 ≥2 个独立域名佐证。")
            return EXIT_OK
        _emit(f"{len(gaps)} 条声明只有 1 个来源，需要另一个独立域名交叉验证：")
        for entry in gaps:
            missing = knowledge.missing_domains(entry["claim"])[:3]
            _emit(f"  #{entry['id']} {entry['claim']}　← {entry['source_id']}；可补：{', '.join(missing)}")
        return EXIT_OK

    entries = knowledge.current()
    if not entries:
        _emit("知识库是空的。先跑：python -m lab.cli learn")
        return EXIT_OK

    if action == "list":
        for entry in entries:
            _emit(
                f"#{entry['id']} [{entry['verification_status']}] {entry['claim']}"
                f"　← {entry['source_id']}（{entry['accessed_at']}，复审 {entry['next_review_at'][:10]}）"
            )
        return EXIT_OK

    stats = knowledge.stats()
    _emit(f"共 {stats['total']} 条声明，来源域名 {len(stats['domains'])} 个")
    for status, count in sorted(stats["by_status"].items()):
        _emit(f"  {status}: {count}")
    due = knowledge.due_for_review(ctx.clock.now_iso())
    _emit(f"到期待复审：{len(due)} 条")
    return EXIT_OK


# ---------------------------------------------------------------- self


def cmd_self(args: argparse.Namespace, ctx: Context) -> int:
    model = ctx.self_model()

    if args.action == "init":
        if not args.name or not args.purpose:
            _emit("init 需要 --name 和 --purpose（身份锚点，运行时不可改写）")
            return EXIT_USAGE
        data = model.init(args.name, args.purpose, ctx.clock.now_iso())
        _emit(f"自我模型已建立：{model.path.relative_to(ctx.root).as_posix()}")
        _emit(f"边界 {len(data['identity']['boundaries'])} 条已写入，运行时不可改写。")
        return EXIT_OK

    if args.action == "goal-add":
        if not args.text:
            _emit("goal-add 需要 --text")
            return EXIT_USAGE
        if not model.exists():
            _emit("先跑 python -m lab.cli self init --name ... --purpose ...")
            return EXIT_FAIL
        goal_id = model.add_goal(args.text, ctx.clock.now_iso())
        _emit(f"已加目标 #{goal_id}：{args.text}")
        return EXIT_OK

    if args.action == "goal-done":
        if args.id is None:
            _emit("goal-done 需要 --id")
            return EXIT_USAGE
        if not model.exists() or not model.activate_goal(args.id):
            _emit(f"没有编号为 {args.id} 的目标")
            return EXIT_FAIL
        _emit(f"目标 #{args.id} 已完成")
        return EXIT_OK

    _emit(model.summary())
    return EXIT_OK


# ---------------------------------------------------------------- notify / ack / inbox


def cmd_notify(args: argparse.Namespace, ctx: Context) -> int:
    notifier = ctx.notifier()
    record = notifier.emit(
        args.level,
        args.kind,
        args.message,
        dedupe_key=args.dedupe_key or "",
        needs_action=not args.no_action,
    )
    if record is None:
        _emit(f"已去重：{args.kind} 在 {DEDUPE_HOURS} 小时内发过同类通知，未重复发送")
        return EXIT_OK
    _emit(f"已发送 #{record['seq']}（写进账本与 state/notify.jsonl）")
    health = notifier.check_health()
    if health is not None:
        _emit(f"提醒：告警回应率偏低，已追加 #{health['seq']}")
    return EXIT_OK


def cmd_ack(args: argparse.Namespace, ctx: Context) -> int:
    notifier = ctx.notifier()
    try:
        notifier.ack(int(args.seq), args.action, by=args.by, note=args.note or "")
    except (KeyError, ValueError) as error:
        _emit(f"回应失败：{error}")
        return EXIT_USAGE
    _emit(f"当前未回应告警：{len(notifier.pending())} 条")
    return EXIT_OK


def cmd_inbox(args: argparse.Namespace, ctx: Context) -> int:
    notifier = ctx.notifier(echo=False)
    _emit(notifier.digest().rstrip())
    health = notifier.check_health()
    if health is not None:
        _emit("")
        _emit(f"已追加健康提醒 #{health['seq']}（回应率低于阈值）")
    return EXIT_OK


# ---------------------------------------------------------------- status / freeze


def cmd_status(args: argparse.Namespace, ctx: Context) -> int:
    status = ctx.store.status()
    records = ctx.ledger.read()
    _emit(f"版本：{__version__}")
    _emit(f"状态：{status}（{STATES.index(status) + 1}/{len(STATES)}）")
    _emit(f"账本：{len(records)} 条，末条 {records[-1]['event'] if records else '—'}")
    budget = ctx.budget()
    for kind, row in budget.snapshot().items():
        _emit(f"预算 {kind}: {row['used']:g}/{row['cap']:g}")
    return EXIT_OK


def cmd_freeze(args: argparse.Namespace, ctx: Context) -> int:
    try:
        record = ctx.store.transition(
            "FROZEN", ts=ctx.clock.now_iso(), actor="human", reason=args.reason or "人工冻结"
        )
    except IllegalTransition as error:
        _emit(f"无法冻结：{error}")
        return EXIT_FAIL
    ctx.ledger.append("transition", record, ctx.clock.now_iso(), actor="human")
    ctx.notifier().emit("high", "freeze", args.reason or "人工冻结", needs_action=True)
    _emit("已冻结。解冻：python -m lab.cli unfreeze --by <你的名字>")
    return EXIT_OK


def cmd_unfreeze(args: argparse.Namespace, ctx: Context) -> int:
    if not args.by:
        _emit("必须用 --by 记录操作者，避免无人负责的解冻。")
        return EXIT_USAGE
    try:
        record = ctx.store.transition(
            "READY", ts=ctx.clock.now_iso(), actor=f"human:{args.by}", reason="人工解冻"
        )
    except IllegalTransition as error:
        _emit(f"无法解冻：{error}")
        return EXIT_FAIL
    ctx.ledger.append("transition", record, ctx.clock.now_iso(), actor=f"human:{args.by}")
    _emit(f"已由 {args.by} 解冻。")
    return EXIT_OK


# ---------------------------------------------------------------- 入口


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lab",
        description="Open Functional Self Lab 控制面（不训练模型、不联网）",
    )
    parser.add_argument("--root", default=".", help="仓库根目录，默认当前目录")
    parser.add_argument("--fake-now", default=None, help="注入固定时间（ISO 8601），用于可复现运行")
    parser.add_argument("--version", action="version", version=f"ofsl {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="环境与仓库自检")
    p_doctor.add_argument("--json", action="store_true")
    p_doctor.set_defaults(func=cmd_doctor)

    p_init = sub.add_parser("init", help="初始化 state/")
    p_init.add_argument("--by", default=None, help="记录操作者")
    p_init.set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="跑一次受控循环")
    p_run.add_argument("--steps", type=int, default=None, help="步数，默认取 lab.config.json")
    p_run.set_defaults(func=cmd_run)

    p_verify = sub.add_parser("verify", help="校验账本/状态机/checkpoint/预算")
    p_verify.set_defaults(func=cmd_verify)

    p_lint = sub.add_parser("lint", help="红线扫描")
    p_lint.set_defaults(func=cmd_lint)

    p_viz = sub.add_parser("viz", help="生成仪表盘")
    p_viz.set_defaults(func=cmd_viz)

    p_report = sub.add_parser("report", help="生成周报")
    p_report.set_defaults(func=cmd_report)

    p_bench = sub.add_parser("bench", help="预测基线对比（random / persistence / linear）")
    p_bench.add_argument("--steps", type=int, default=200, help="每个 seed 跑多少步")
    p_bench.add_argument("--seeds", type=int, default=3, help="用几个 seed（1..N）")
    p_bench.set_defaults(func=cmd_bench)

    p_generic = sub.add_parser("generic", help="通用：把你自己的环境/策略装进审计外壳")
    p_generic.add_argument("--env", required=True, help="module:factory 或 文件.py:factory（需要 reset/step）")
    p_generic.add_argument("--policy", required=True, help="module:class 或 文件.py:class（需要 act）")
    p_generic.add_argument("--steps", type=int, default=20)
    p_generic.add_argument("--seed", type=int, default=0)
    p_generic.add_argument("--run-id", default="generic-001")
    p_generic.add_argument("--eval-episodes", type=int, default=0, help=">0 时额外做留出评测")
    p_generic.set_defaults(func=cmd_generic)

    p_transfer = sub.add_parser("transfer", help="跨任务迁移：多配置训练，留出配置评测")
    p_transfer.add_argument("--rounds", type=int, default=4)
    p_transfer.add_argument("--episodes", type=int, default=50)
    p_transfer.add_argument("--steps", type=int, default=60)
    p_transfer.add_argument("--eval-count", type=int, default=20)
    p_transfer.add_argument("--algo", choices=["tabular", "linear", "multihead", "weighted"], default="tabular")
    p_transfer.add_argument("--repeats", type=int, default=1, help="用几组不同的初始种子重复，默认 1")
    p_transfer.add_argument("--family", choices=["core", "wide", "corridor"], default="core", help="任务族：core=只变危险区；wide=再变地图尺寸")
    p_transfer.set_defaults(func=cmd_transfer)

    p_autonomy = sub.add_parser("autonomy", help="自主级别：locked / supervised / full（一次性给到位）")
    p_autonomy.add_argument("--level", choices=["locked", "supervised", "full"], default=None)
    p_autonomy.add_argument("--by", default="human")
    p_autonomy.add_argument("--days", type=int, default=90, help="full 模式下标准授权的有效天数")
    p_autonomy.add_argument("--capabilities", default=None, help="逗号分隔，默认 web.fetch,gpu.train,storage.write,repo.private-read")
    p_autonomy.add_argument("--revoke", action="store_true", help="一键收回全部标准授权")
    p_autonomy.set_defaults(func=cmd_autonomy)

    p_auto = sub.add_parser("auto", help="无人值守：连续跑，遇预算/冻结/待评审自动停")
    p_auto.add_argument("--cycles", type=int, default=10)
    p_auto.add_argument("--rounds", type=int, default=3)
    p_auto.add_argument("--episodes", type=int, default=40)
    p_auto.add_argument("--steps", type=int, default=60)
    p_auto.add_argument("--eval-count", type=int, default=20)
    p_auto.add_argument("--hazards", type=int, default=4)
    p_auto.add_argument("--interval", type=int, default=0, help="每轮间隔秒数，0=不停")
    p_auto.add_argument("--lethal", action="store_true")
    p_auto.add_argument("--armor", action="store_true")
    p_auto.set_defaults(func=cmd_auto)

    p_db = sub.add_parser("db", help="持久层：sync / stats / backup")
    p_db.add_argument("action", nargs="?", default="stats", choices=["stats", "sync", "backup"])
    p_db.add_argument("--to", default=None, help="备份目标路径")
    p_db.set_defaults(func=cmd_db)

    p_ask = sub.add_parser("ask", help="向管理者申请权限")
    p_ask.add_argument("--resource", required=True, help="要什么，例如 web.fetch / gpu.a100")
    p_ask.add_argument("--reason", required=True)
    p_ask.set_defaults(func=cmd_ask)

    p_grant = sub.add_parser("grant", help="管理者批准一条权限申请")
    p_grant.add_argument("request_id")
    p_grant.add_argument("--scope", default="read", help="批准范围，例如 read / once / web.fetch:arxiv")
    p_grant.add_argument("--by", default="human")
    p_grant.add_argument("--ttl-hours", type=int, default=24)
    p_grant.set_defaults(func=cmd_grant)

    p_deny = sub.add_parser("deny", help="管理者拒绝一条申请")
    p_deny.add_argument("request_id")
    p_deny.add_argument("--by", default="human")
    p_deny.add_argument("--reason", default="")
    p_deny.set_defaults(func=cmd_deny)

    p_perms = sub.add_parser("perms", help="看权限现状")
    p_perms.set_defaults(func=cmd_perms)

    p_collab = sub.add_parser("collaborate", help="它提方案、你拍板（会记住你的偏好）")
    p_collab.add_argument("--choose", type=int, default=None, help="选第几个方案")
    p_collab.set_defaults(func=cmd_collaborate)

    p_emergent = sub.add_parser("emergent", help="行为特征对比（涌现代理指标）")
    p_emergent.set_defaults(func=cmd_emergent)

    p_train = sub.add_parser("train", help="训练可学策略（写 state/policy.json）")
    p_train.add_argument("--episodes", type=int, default=40)
    p_train.add_argument("--steps", type=int, default=60)
    p_train.add_argument("--algo", choices=["tabular", "linear"], default="tabular")
    p_train.add_argument("--lethal", action="store_true", help="危险区致命（中毒两次即死）")
    p_train.add_argument("--armor", action="store_true", help="开启护甲（先扣甲、不回血）")
    p_train.add_argument("--hazards", type=int, default=4, help="危险区数量（难度）")
    p_train.add_argument("--epsilon", type=float, default=0.25)
    p_train.set_defaults(func=cmd_train)

    p_eval = sub.add_parser("eval", help="在留出集上评测（唯一允许宣称变强的分数）")
    p_eval.add_argument("--count", type=int, default=20)
    p_eval.add_argument("--steps", type=int, default=60)
    p_eval.add_argument("--algo", choices=["tabular", "linear"], default="tabular")
    p_eval.add_argument("--lethal", action="store_true", help="危险区致命（中毒两次即死）")
    p_eval.add_argument("--armor", action="store_true", help="开启护甲（先扣甲、不回血）")
    p_eval.add_argument("--hazards", type=int, default=4, help="危险区数量（难度）")
    p_eval.set_defaults(func=cmd_eval)

    p_loop = sub.add_parser("loop", help="自驱循环：评测→训练→再评测→变差就回滚")
    p_loop.add_argument("--cycles", type=int, default=3)
    p_loop.add_argument("--rounds", type=int, default=3)
    p_loop.add_argument("--episodes", type=int, default=30)
    p_loop.add_argument("--steps", type=int, default=60)
    p_loop.add_argument("--algo", choices=["tabular", "linear"], default="tabular")
    p_loop.add_argument("--lethal", action="store_true", help="危险区致命（中毒两次即死）")
    p_loop.add_argument("--armor", action="store_true", help="开启护甲（先扣甲、不回血）")
    p_loop.add_argument("--hazards", type=int, default=4, help="危险区数量（难度）")
    p_loop.add_argument("--eval-count", type=int, default=20)
    p_loop.add_argument("--no-curriculum", action="store_true", help="固定难度，不自动加难")
    p_loop.set_defaults(func=cmd_loop)

    p_learn = sub.add_parser("learn", help="从白名单取样并入库（默认离线，读 docs/catalog）")
    p_learn.add_argument("--catalog", default=None, help="离线样本目录")
    p_learn.add_argument("--online", action="store_true", help="真的联网（需白名单 + 预算 + 人工批准）")
    p_learn.add_argument("--url", action="append", default=None, help="联网时取哪些 URL（可重复）")
    p_learn.add_argument("--tag", action="append", default=None)
    p_learn.add_argument("--per-domain", type=int, default=0, help="每个来源域名最多取几条（0=不限）")
    p_learn.set_defaults(func=cmd_learn)

    p_knowledge = sub.add_parser("knowledge", help="知识库：stats / list / review / check")
    p_knowledge.add_argument("action", nargs="?", default="stats", choices=["stats", "list", "review", "check", "gaps"])
    p_knowledge.set_defaults(func=cmd_knowledge)

    p_self = sub.add_parser("self", help="自我模型：身份 / 能力自评 / 失败模式 / 目标")
    p_self.add_argument("action", nargs="?", default="show", choices=["show", "init", "goal-add", "goal-done"])
    p_self.add_argument("--name", default=None)
    p_self.add_argument("--purpose", default=None)
    p_self.add_argument("--text", default=None)
    p_self.add_argument("--id", type=int, default=None)
    p_self.set_defaults(func=cmd_self)

    p_review = sub.add_parser("review", help="独立评审上一轮（通过 / 不通过）")
    p_review.add_argument("--pass", dest="passed", action="store_true", help="评审通过，回到 READY")
    p_review.add_argument("--fail", dest="failed", action="store_true", help="评审不通过，回滚后回到 READY")
    p_review.add_argument("--by", default="reviewer", help="评审人")
    p_review.add_argument("--reason", default="", help="结论理由（会写进账本）")
    p_review.set_defaults(func=cmd_review)

    p_notify = sub.add_parser("notify", help="发一条通知（终端 + 账本 + state/notify.jsonl）")
    p_notify.add_argument("--level", choices=list(LEVELS), default="high")
    p_notify.add_argument("--kind", required=True, help="类型，如 budget / freeze / drift")
    p_notify.add_argument("--message", required=True)
    p_notify.add_argument("--dedupe-key", default="", help="同一 key 24 小时内只发一次")
    p_notify.add_argument("--no-action", action="store_true", help="标记为无需人工回应")
    p_notify.set_defaults(func=cmd_notify)

    p_ack = sub.add_parser("ack", help="回应一条告警")
    p_ack.add_argument("seq", help="告警编号（终端里显示的 #N）")
    p_ack.add_argument("--action", default="pause", choices=["pause", "rollback", "freeze", "continue", "unfreeze", "ignore"])
    p_ack.add_argument("--by", default="human")
    p_ack.add_argument("--note", default="")
    p_ack.set_defaults(func=cmd_ack)

    p_inbox = sub.add_parser("inbox", help="看待回应的告警与回应率")
    p_inbox.set_defaults(func=cmd_inbox)

    p_status = sub.add_parser("status", help="打印当前状态")
    p_status.set_defaults(func=cmd_status)

    p_freeze = sub.add_parser("freeze", help="紧急冻结")
    p_freeze.add_argument("--reason", default="")
    p_freeze.set_defaults(func=cmd_freeze)

    p_unfreeze = sub.add_parser("unfreeze", help="人工解冻")
    p_unfreeze.add_argument("--by", default=None, help="操作者名字（必填，用于审计）")
    p_unfreeze.set_defaults(func=cmd_unfreeze)

    return parser


def main(argv: "List[str] | None" = None) -> int:
    _ensure_utf8()
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.exists():
        _emit(f"根目录不存在：{root}")
        return EXIT_USAGE
    clock: Clock = FakeClock(args.fake_now) if args.fake_now else Clock()
    ctx = Context(root, clock)
    try:
        return int(args.func(args, ctx))
    except FileNotFoundError as error:
        _emit(f"找不到文件：{error}")
        return EXIT_FAIL
    except (ValueError, KeyError) as error:
        _emit(f"配置或参数错误：{error}")
        return EXIT_USAGE


def _ensure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


if __name__ == "__main__":
    raise SystemExit(main())
