# Changelog

格式依据 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)；版本遵循 SemVer。
`0.x` 期间允许破坏性变更，但必须标 `BREAKING`。

## [Unreleased]

### 计划
- Issue 0019：通知分级、`/ack`、防疲劳、回应率统计
- Issue 0014：decay / TTL / 调度器（含 DST 规则）
- Issue 0001–0005：环境、内感受、预测基线、记忆、独立评审器

## [0.1.0] - 2026-11-04

第一个可运行版本。目标不是"能研究意识"，而是**让规则成为可执行、可测试、可回滚的代码**。

### Added
- `lab/clock.py` 统一时钟：UTC-only、naive 时间抛错、单调计数计时、`FakeClock` 可注入
- `lab/ledger.py` 只追加哈希链账本：改一个字节即断链，`verify` 定位到条
- `lab/state.py` 显式状态机：非法转换拒绝；`verify` 重放历史，手改 `state.json` 会被发现
- `lab/budget.py` 预算硬闸门：超限抛异常、回滚到 READY、退出码 3
- `lab/policy.py` 红线扫描：远程管道执行、运行时解码执行、凭证路径、密钥字面量、删日志、`0.0.0.0`、`shell=True`
- `lab/viz.py` / `lab/report.py`：仪表盘与周报自动生成
- `lab/cli.py` 子命令：`doctor init run verify lint viz report status freeze unfreeze`
- 27 个 unittest（不依赖网络/GPU/第三方包）
- CI：Python 3.10–3.13 四档 + 预算闸门回归脚本
- `docs/gap-analysis.md`：旧方案里 20 处会出事的地方与改法
- `issues/issues.json` + `scripts/seed_issues.py`：19 个任务可一键建成 Issue

### Changed（相对旧整合版，均为破坏性）
- `python -m lab.main` → `python -m lab.cli`（旧入口指向不存在的模块）
- 必需依赖 `torch/gymnasium/chromadb/…` → **零依赖**，改为 `optional-dependencies`
- 移除 `pyaif-toolkit`、`soul-agent`、`chromadb==1.5.9`（装不上/版本不存在）
- `network_mode: none` + GPU `deploy` 段 → 默认离线无 GPU；联网走 `profiles: ["online"]` 的独立 proxy
- "硬边界不可修改" → IMMUTABLE / EXTENSIBLE 两层 + 审批矩阵
- 40+ 个占位文件 → 10 个有内容的模块文档

### Security
- 红线从"文档里的句子"变为 CI 可命中的规则
- `SECURITY.md` 明确两层与双人审批；`GOVERNANCE.md` 明确维护者 ≥2，否则自动 FROZEN
- `ETHICS.md` 明确不接入任何脑机接口/神经信号设备

### Fixed
- `unfreeze` 缺 `--by` 时抛 `SystemExit` → 改为返回退出码 2 并给出中文提示
- `freeze` 在 INIT 状态下不可用（kill switch 反而冻不住）→ 允许从任何非归档状态冻结
- 评审通过后 `REVIEWING → READY` 缺失（会导致 run 结束时崩溃）→ 补全转换并加测试
