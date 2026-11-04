# Changelog

格式依据 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)；版本遵循 SemVer。
`0.x` 期间允许破坏性变更，但必须标 `BREAKING`。

## [Unreleased]

### 计划
- v0.2 第二块：`lab loop`（自驱循环，每轮过预算闸门，到 REVIEWING 就停）
- v0.2 第三块：插件接口 `lab/plugins/*.py`（manifest 声明能力与预算，加载时过红线扫描）


### 计划
- Issue 0014：decay / TTL / 调度器（含 DST 规则）
- Issue 0008：实验闭环（更复杂的任务，才看得出预测器的真实差距）
- Issue 0013 / 0016：真实 checkpoint 恢复、并发锁

## [0.2.0] - 2026-11-04

v0.2 的第一块：**自我模型**。也是"能不能不重复别人"这个问题的落点（`docs/positioning.md`）。

### Added
- `lab/selfmodel.py`：结构化自我描述，五段——`identity`（身份+边界，运行时不可改写）、
  `capabilities`（能力自评，数字必须能从账本复算）、`failure_patterns`（同一错误重复才算模式）、
  `goals`（可被人工干预的目标栈）、`continuity`（会话连续次数）
- `lab self`：查看 / `self init --name --purpose` / `self goal-add --text` / `self goal-done --id`
- `lab run` 结束自动更新自我模型（会话数、上一轮步数与平均误差）
- `lab review --pass|--fail` 把评审结果回写：通过 → 成功率 +1；不通过 → `review_failed` 失败模式 +1
- `docs/positioning.md`：与 LangGraph / CrewAI / AutoGen / AutoGPT 的差异说明，
  并引用业内公认的五条失败模式，说明我们冲的是"持久状态、每步预算、eval harness"这三条
- `docs/metrics.md` 第 7 节：自我指涉的 5 个可测代理指标（不宣称意识，但不关门）
- 6 个新测试：初始化、未初始化时拒绝记录、评审回写成功率、失败模式、目标生命周期、CLI 端到端

### Changed
- 测试数 57 → 63
- 版本进入 `0.2.x`：从"控制面"转向"自驱循环"（下一块是 `lab loop`，再下一块是插件接口）

### Notes
- 关于"主观意识"：本项目**不宣称**，也**不判死**。做法是把它拆成可积累的中间指标，
  并且明确写清"指标上升 ≠ 意识出现"。

## [0.3.0] - 2026-11-04

补上"自己去网上找东西 → 内化成知识"这条主线，并交出**总册**。

### Added
- `lab/web.py`：白名单取样。`OfflineFetcher`（读 `docs/catalog`，默认）/ `LiveFetcher`（真联网，
  必须显式 `--online` + 域名在白名单，否则抛 `NotAllowed`）。只留标题+摘要（≤400 字），不存全文
- `lab/knowledge.py`：声明入库。同一主张同一域名去重；**≥2 个独立域名才算 verified**；
  到期 `review` 降级为 pending 并延长周期；逐条哈希，篡改可发现
- `lab learn` / `lab knowledge [stats|list|review|check]`
- `docs/MASTER.md`：**总册**——需求总表（#27 之后逐条对应落点）、架构图、模块地图、
  命令全集与退出码、`state/` 每个文件的用途、指标、已实现/未实现、路线图、边界、术语表
- `docs/catalog/*.json`：3 条离线样本（内容取自本项目自己的实测结论，不伪造外部研究）
- 8 个新测试：白名单闸门、离线/在线 fetcher、去重、独立性判定、到期复审、哈希篡改、CLI 端到端

### Changed
- 测试数 63 → 71
- README 顶部直接指向总册

### Notes
- 取样 ≠ 爬虫：域名白名单 + 预算计费 + 不存全文 + 默认离线
- 知识库目前**还没有影响决策**（"下一轮做什么"仍由人定），这是 v0.3 的关键一步

## [0.6.0] - 2026-11-04

加了第二种学习算法，**结论是它也没能超过手写基线**——但这次弄清了为什么。

### Added
- `lab/linear.py`：线性函数逼近 Q（17 维特征：方向/距离档/能量档/损伤档/四方向墙体位），
  `--algo linear` 可切换；权重存 `state/policy.json`，与表格版靠 `algo` 字段隔离，绝不混用
- `state_of()` 支持 `with_walls=True`；`tasks/loop` 全线透传
- `docs/experiments/0003-why-bfs-wins.md`：为什么打不过 BFS —— 三种方法实测对比 +
  **"我原来的假设错了"**的说明 + v0.7 的改向（改任务而不是改算法）

### Measured（留出 seed 9000–9019，60 步）
| 方法 | 最好留出分数 |
|---|---|
| 表格 Q（2000 回合） | +2.450 |
| 线性 Q（13 维） | +2.345 |
| 线性 Q + 墙体（17 维） | +0.990 |
| BFS 基线 | **+3.565** |

### Changed
- 测试数 79 → 82
- 判断修正：**在这个玩具任务上 BFS 近似最优**，继续调算法是刷天花板；v0.7 改任务设计
  （危险区挡路 + 食物移动），判据改为 M1'（≥ 基线 ×1.05）

## [0.5.0] - 2026-11-04

两件事：修好"越练越差"，以及**给不读代码的人写了一份能照着用的手册**。

### Added
- `docs/USER-GUIDE.md`：使用手册——装好、跑起来、看懂每个数字、出错怎么办、
  你的数据在哪、不会写代码怎么参与。全程复制粘贴，不需要编程基础
- `docs/experiments/0002-negative-results.md`：两个负结果
  A) 给状态加"四方向墙体"特征后状态数 126→948，留出分数 +2.6→−0.4（状态爆炸，已撤回）
  B) 固定学习率下继续训练会把策略冲垮（连续 6 轮全部回滚）
- 课程机制：追上基线就自动加难（危险区 +1，上限 8）；追不上维持难度，不许降难度刷分
- 知识影响行为（v0.5 唯一一处）：知识库里有 `hazard` 标签的声明时，循环起始难度 +1

### Fixed
- **学习率衰减**：`alpha = 0.2 / √(1 + updates/500)`。修完不再自毁：
  `−4.495 → +2.200` 后稳定在 +2.2（每轮 −0.03 属噪声，正确回滚）

### Changed
- 测试数 77 → 79；`GridWorld` 支持 `walls/food/hazards` 参数；`tasks/loop` 全部支持难度
- 仍**未**达成 M1（留出 ≥ BFS 基线 3.565）。当前最好 +2.2

## [0.4.0] - 2026-11-04

**第一次让系统真的变强**（在自己身上），并且如实公布它仍然打不过手写基线。

### Added
- `lab/agent.py`：表格 Q-learning 策略（零依赖、纯 CPU），状态 =（食物方向 / 距离档 / 能量档 / 损伤档），
  参数存 `state/policy.json`，可审计、可复算
- `lab/tasks.py`：训练 seed（1000–1999）与评测 seed（9000–9999）**严格不重叠**；
  `evaluate()` 是唯一允许用来宣称"变强"的分数；`baseline_score()` 提供 BFS 对照
- `lab/loop.py`：自驱循环一轮 = 评测 → 训练 → 再评测 → **只有变好才保存策略，否则回滚**，
  每轮写账本 `cycle` 事件（before / after / baseline / delta / 是否保留）
- 命令：`lab train`、`lab eval`、`lab loop --cycles N`
- `docs/experiments/0001-learnability.md`：实验记录 —— 方法、数字、结论、**以及"我明确不调参凑数"的声明**
- 6 个新测试：seed 不重叠、训练后留出分数上升、策略存取一致、循环落账并保留、参数校验、REVIEWING 时拒绝运行

### 实测（写进实验文档，不粉饰）
| 阶段 | 留出分数 |
|---|---|
| 训练前 | −4.495 |
| 循环 3 轮后 | +1.925 |
| BFS 基线 | **+3.565** |

**还没追上基线。** 里程碑 M1（≥ +3.565 连续 3 轮）未达成；状态表示太粗、表太小导致抖动。
下一版要么升级特征，要么在这个方向上认输——见实验文档的"可证伪的下一步"。

### Changed
- 测试数 71 → 77

## [0.1.4] - 2026-11-04

一次**针对自己代码**的逻辑审计（`docs/logic-audit.md`）。修掉 6 个"看起来在守规矩、实际没守"的问题。

### Fixed
1. **统计口径错误**：三个预测器的"单步最优占比"加起来 168.2%（并列都算赢）。
   改为严格最优 + 单独统计并列，报告里直接打印"合计必须 100%"的校验行。
2. **仪表盘预算恒为 0**：`run` 窗口拿不到 `run_id`，所有扣费都匹配不上。
   改为回落到"账本里最近一次 run"，现在显示真实用量。
3. **评审是自己宣布的**：`run` 结束时写 `REVIEWING → READY，reason="独立评审通过（占位规则）"`，
   等于程序自评自过。改为**停在 REVIEWING**，必须 `lab review --pass|--fail` 才回到 READY；
   未评审就再跑会被拒绝。
4. **"单次上限"冒充"总量上限"**：`steps_per_run` 只限一次 run，连续 run 等于无约束。
   新增 `steps_per_day`（UTC 日），run 前同时校验，每步同时扣两个账。
5. **通知回应率自我放大**：`notify-health` 自己也想 `needs_action=True`，越提醒分母越大。
   改为 `needs_action=False` 并在统计中显式排除。
6. **`verify` 不比对账本**：state.json 与账本两个写入点，中间崩溃无人发现。
   新增交叉校验，逐条比对转换序列。

### Added
- `python -m lab.cli review --pass|--fail --by <人> --reason "..."`：显式评审入口
- `docs/logic-audit.md`：审计方法、6 个已修问题、6 个**仍在**的设计边界、原稿被判定不可照做的 5 条
- 8 个回归测试（每个修复都有一条，防止回退）

### Changed
- 测试数 49 → 57；`lab run` 的输出结尾改为"等待评审"

## [0.1.3] - 2026-11-04

把"有事要提示本人"做成会记录、会去重、会自我诊断的机制。

### Added
- `lab/notify.py`：`Notifier` —— 分级（高/中/低）、24 小时去重（同一 `kind + dedupe_key`）、
  `ack()` 回应写账本、回应率统计、回应率过低时自动追加 `notify-health` 提醒
- 三个命令：`lab notify --kind ... --message ...`、`lab ack <编号> --action ...`、`lab inbox`
- 渠道：终端即时打印 + 账本 `alert` 事件 + `state/notify.jsonl`（每行一条，便于 grep）
- `lab run` 的预算拦截、`lab freeze` 现在都走 Notifier（前者 24h 去重，后者每次都响）
- 8 个新测试：去重/过期、`ack` 后回应率、样本太小不下结论、非法级别与动作、CLI 端到端

### Changed
- `issues/0019` 标记为已完成；`notify/README.md` 状态从"待实现"改为已实现
- 仪表盘的"已回应"改为**只统计回应了真实存在的告警**（原来把 `ack` 记录数当回应数，会刷虚）
- 测试数 41 → 49

### Notes
- 刻意**不联网**：webhook / GitHub Issue 渠道留到以后，保持"默认离线"这条承诺

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
