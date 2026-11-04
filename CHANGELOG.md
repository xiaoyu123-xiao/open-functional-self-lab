# Changelog

格式依据 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)；版本遵循 SemVer。
`0.x` 期间允许破坏性变更，但必须标 `BREAKING`。

## [Unreleased]

### 计划
- Issue 0019：通知分级、`/ack`、防疲劳、回应率统计
- Issue 0014：decay / TTL / 调度器（含 DST 规则）
- Issue 0008：实验闭环（更复杂的任务，才看得出预测器的真实差距）

## [0.1.2] - 2026-11-04

第一次能回答"这个 `prediction_error` 到底算好还是算差"。

### Added
- `lab/predict.py`：三个预测器 + 统一误差定义（x / y / energy / damage 的平均绝对偏差）
  - `random`：合法范围内随机猜（固定 seed，可复现），当下界用
  - `persistence`：假设"下一步 = 上一步"，主基线
  - `linear`：假设"下一步 = 上一步 + 最近一次位移"，速度外推
- `python -m lab.cli bench --steps 200 --seeds 3`：跑同一批 seed，输出对比表，
  写 `state/reports/bench-YYYY-MM-DD.md`，并向账本追加 `bench` 事件
- 报告含 ASCII 误差曲线（无绘图依赖）、单步最优占比、明确的「未做显著性检验」说明
- 6 个新测试：静态序列零误差、匀速序列下线性优于持久性、benchmark 可复现、random 更差、sparkline 形状

### Changed
- 测试数 35 → 41；`issues/0003` 标记为已完成
- `docs/metrics.md` 增加实测章节（600 步的真实数字与读数方法）

### Fixed
- `Linear` 预测器的位移只在收到两个观测后才生效，导致前两步白错：改为记录"本次预测出发的观测"，
  第一步之后即可正确外推

## [0.1.1] - 2026-11-04

`lab run` 从"编造的数字"换成**真的会失败的环境**。这是项目从"控制面"迈向"实验台"的第一步。

### Added
- `lab/env.py`：8×8 网格环境——随机布置墙 / 食物 / 危险区，`energy` 每步 -0.02、
  进食 +0.20、踩危险区 +0.25 `damage`；`homeostatic_error()` 把"偏离舒适区"变成一个数字
- `greedy_action()`：BFS 朝最近食物走一步的**基线策略**（不知道危险区在哪，所以会受伤）
- `persistence_error()`：持久性预测基线（假设"下一步=上一步"），供 Issue 0003 做对照
- `lab run` 结束打印末态：位置 / 能量 / 损伤 / 稳态误差 / 预测误差
- 8 个环境测试：同 seed 逐字节复现、撞墙、能量下降、进食回能、受伤累积、基线能吃到食物

### Changed
- 账本 `step` 记录不再只有 `action` 和 `prediction_error`，新增 `x` `y` `energy` `damage`
  `homeostatic_error` `blocked` `ate` `hurt`
- `prediction_error` 定义改变：从"0.9×0.93^step 衰减 + 噪声"的占位值，改为真正的持久性基线误差
- 测试数 27 → 35；`issues/0001` 标记为已完成

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
