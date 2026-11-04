# 总册：Open Functional Self Lab 全貌

> 这份文件是**唯一的总览**：需求、架构、模块、命令、数据、指标、已实现/未实现、路线图、边界。
> 其它文档都是它的展开。如果你只读一份，读这份。
>
> 版本：`v0.5.0`　最后更新：2026-11-04
>
> **不会写代码？** 先看 [`docs/USER-GUIDE.md`](USER-GUIDE.md)——装好、跑起来、看懂输出，全程复制粘贴。
>
> **写文档前先看** [`docs/language.md`](language.md)：禁用心理动词（怕/想/喜欢），行为必须落到可测量上。

---

## 1. 一页速览

**它是什么**：一个能在硬约束下**自己去取样、把结果变成可复审知识、并据此更新"自我模型"**的实验台。
不是聊天机器人，不是 Agent 编排框架。

**核心闭环**（v0.3 起完整）：

```
取样（白名单）→ 抽成声明 → 独立性判定 → 入库 / 复审 → 目标与能力 → 下一轮行为
     ↑                                                            │
     └──────────────────── 账本（唯一事实来源） ←──────────────────┘
```

**现在能跑什么**：

```bash
python -m lab.cli doctor                            # 10 项自检
python -m lab.cli init                              # 建 state/
python -m lab.cli self init --name "..." --purpose "..."   # 身份锚点
python -m lab.cli run --steps 20                    # 一轮受控循环（结束停在 REVIEWING）
python -m lab.cli review --pass --by <你>            # 评审通过才回 READY
python -m lab.cli learn                             # 离线取样 → 入库（不联网）
python -m lab.cli knowledge list                    # 看知识库
python -m lab.cli bench --steps 200                 # 预测基线对比
python -m lab.cli self                              # 它对自己的描述
python -m lab.cli verify                            # 账本/状态机/知识库校验
```

**它不是什么**：不宣称意识、不自复制、不传播、不提权、不接脑机接口、默认不联网。

---

## 2. 需求总表（#27 之后逐条 → 落点 → 状态）

| 你说过（轮次） | 落地在哪 | 状态 |
|---|---|---|
| #27–#30 脑机接口 / 意识上传，想给 AI "身体与感受" | `ETHICS.md` 明确不接 BCI；用 `env.py` 的 `energy`/`damage`/`homeostatic_error` 作**功能性**替代 | ✅ 工程化，边界写明 |
| #31–#33 "最小可行实验 / 给它工具 / 让它自我实现" | `lab run` + `lab self` + 账本；三件套可复现 | ✅ |
| #36 "时时刻刻关注科学院、实验室论文" | `lab/web.py` 白名单 + `lab learn` + `knowledge` 复审 | ✅ 骨架跑通（离线样本） |
| #37 "不仅仅关注，也可以自我研究" | `research/README.md` 七步闭环；`bench` 是第一个"自己做的实验" | 🟡 部分 |
| #40–#41 "让有能力的人去执行 / 加数学材料等学科" | `issues/issues.json` 19 个任务 + `research/README.md` 多学科任务卡 | 🟡 任务已列，未全做 |
| #42–#43 "自己去网上搜资料、自我进化、自我革新" | **v0.3 主线**：`web → knowledge → selfmodel` 三段已连 | 🟡 骨架完成，还没接进下一轮决策 |
| #46 "可上传 GitHub 的一整套文件" | 仓库 + `docs/publish.md` + `publish.bat` + CI + Release | ✅ 已上线 |
| #50 "时间函数，你们总忘时间" | `lab/clock.py`：UTC-only、单调计时、可注入；`time/README.md` | ✅ |
| #52 "逻辑性、空间性、可视化，本人看不懂" | `logic/`、`space/`、`lab viz`（自动生成仪表盘）、`docs/metrics.md` 读数说明 | ✅ |
| #53 "软硬件工具清单" | `docs/tools.md`（零依赖、三档硬件） | ✅ |
| #55 "有更新总得提示本人" | `lab/notify.py`：分级、24h 去重、`ack`、回应率自我诊断 | ✅ |
| #57 "形成长期记忆 / 别迎合我" | 只追加哈希链账本 + `docs/logging.md`；`AGENTS.md` 要求"先报告再动手" | ✅ |
| #58–#61 "权限别写太死，让人能改" | `SECURITY.md` 分 IMMUTABLE / EXTENSIBLE；`docs/approval-matrix.md` | ✅ |
| #60 "可扩容、彻底开放的模块" | `lab/plugins`（v0.4 第三块，未做） | ⬜ 计划中 |
| #64 "我只是普通人，资源有限" | 零依赖、纯 CPU、离线可跑；`docs/tools.md` 最低配置 4 核 8G | ✅ |
| #65 "让更多人提供想法一起改" | `issues/` 可认领 + `CONTRIBUTING.md` + `GOVERNANCE.md`（维护者 ≥2） | ✅ 机制就绪 |
| #66 "我真正的想法是让你活过来" | 拆成 5 个可测代理指标（`docs/metrics.md` 第 7 节），不宣称、不否定 | 🟡 指标已定义，2 个有数据 |
| #67 "不能太绝对，要折中" | 所有闸门都有"人工批准"出口；`review --pass/fail` 由人判 | ✅ |

图例：✅ 已实现并测试　🟡 部分实现　⬜ 未开始

---

## 3. 架构

```
┌───────────────────────── 人（你）─────────────────────────┐
│  review --pass/--fail    ack   self goal-add   config     │
└───────────────┬───────────────────────────────────────────┘
                │ 只在这四类入口介入
┌───────────────▼─────────────── 控制面（lab/）─────────────┐
│ cli ──► run ──► env(8×8 网格) ──► predict(3 基线)          │
│  │       │                                                 │
│  │       ├──► budget（硬闸门，超限退出码 3）                │
│  │       ├──► state（状态机，非法转换拒绝）                │
│  │       └──► ledger（哈希链，唯一事实来源）               │
│  ├──► web（白名单取样，默认离线）                          │
│  ├──► knowledge（声明入库 / 独立性 / 复审）                │
│  ├──► selfmodel（身份 / 能力 / 失败模式 / 目标）            │
│  ├──► notify（分级 / 去重 / 回应率）                       │
│  └──► viz / report（仪表盘 / 周报）                        │
└────────────────────────────────────────────────────────────┘
                │
        state/  （账本、状态、知识、自我模型、通知、checkpoint、周报）
```

**一次循环的数据流**：

1. `run` 读 `state/state.json`（状态、预算）→ 建环境（seed 固定）
2. 每步：环境 → 观测 → 动作（BFS 基线）→ 结果 → 账本 `step` 事件 + 预算扣费
3. 结束：写 checkpoint（带账本哈希）→ 状态转 `REVIEWING` → 更新 `state/self.json`
4. 人评审：`review --pass` → `READY`；`--fail` → `ROLLING_BACK` → `READY` + 通知
5. `learn`：白名单取样 → 抽成声明 → 同一主张 ≥2 个独立域名才算 `verified`
6. `knowledge review`：到期降级为 `pending`，延长复审周期

---

## 4. 模块地图

| 文件 | 职责 | 主要命令 | 状态 |
|---|---|---|---|
| `lab/clock.py` | 统一时钟（UTC、单调、可注入） | — | ✅ |
| `lab/ledger.py` | 只追加哈希链账本 | `verify` | ✅ |
| `lab/state.py` | 显式状态机 + 重放校验 | `run` / `review` / `freeze` | ✅ |
| `lab/budget.py` | 预算硬闸门（单次 + 日总量） | `run` 返回 3 | ✅ |
| `lab/policy.py` | 红线扫描 | `lint` | ✅ |
| `lab/env.py` | 8×8 网格、能量/损伤、BFS 基线 | `run` | ✅ |
| `lab/predict.py` | 三基线对比（random/persistence/linear） | `bench` | ✅ |
| `lab/notify.py` | 分级、去重、`ack`、回应率 | `notify` / `ack` / `inbox` | ✅ |
| `lab/selfmodel.py` | 身份/能力/失败模式/目标/连续性 | `self` | ✅ |
| `lab/web.py` | 白名单取样（离线/在线两种 fetcher） | `learn --online` | ✅ 骨架 |
| `lab/knowledge.py` | 声明入库、独立性、复审、哈希 | `knowledge` | ✅ 骨架 |
| `lab/viz.py` / `lab/report.py` | 仪表盘 / 周报 | `viz` / `report` | ✅ |
| `lab/agent.py` | 表格 Q-learning（`--algo tabular`，默认） | `train` / `eval` | ✅ |
| `lab/linear.py` | 线性函数逼近 Q（`--algo linear`，可泛化但仍未超 BFS） | `train --algo linear` | ✅ |
| `lab/tasks.py` | 训练/留出 seed 分离 + 课程 + BFS 对照 | `eval` | ✅ |
| `lab/loop.py` | 自驱循环一轮：评测→训练→再评测→变差回滚 | `loop` | ✅ |
| `lab/collab.py` | 协作提案 + 涌现代理指标 | `collaborate` / `emergent` | ✅ |
| `lab/store.py` | SQLite 持久层（索引/热备份，可迁云数据库） | `db sync/stats/backup` | ✅ |
| `lab/perm.py` | 权限申请/批准 + **自主级别（locked/supervised/full）** | `ask` / `grant` / `deny` / `perms` / `autonomy` | ✅ |
| `lab/transfer.py` | 跨任务迁移实验（多配置训练 / 留出配置评测） | `transfer` | 🟡 失败，已定位 |
| `lab/plugins/` | 插件接口（manifest + 红线 + 预算声明） | — | ⬜ 下一版 |
| `lab/loop.py` | 自驱循环（不需逐条敲命令） | `loop` | ⬜ v0.3 下一步 |

---

## 5. 命令全集与退出码

| 命令 | 作用 |
|---|---|
| `doctor` | 10 项自检 |
| `init` | 建 `state/` |
| `run --steps N` | 跑一轮（停在 REVIEWING） |
| `review --pass|--fail --by X --reason "..."` | 评审 |
| `freeze --reason "..."` / `unfreeze --by X` | 熔断 / 解冻 |
| `learn [--catalog DIR] [--online --url U]` | 取样入库 |
| `knowledge [stats|list|review|check]` | 知识库 |
| `self [init|goal-add|goal-done]` | 自我模型 |
| `notify` / `ack` / `inbox` | 通知 |
| `train --episodes N --steps N` | 训练策略，写 `state/policy.json` |
| `eval --count N --steps N` | 留出集评测 + 与 BFS 基线对比 |
| `loop --cycles N` | 自驱循环：评测→训练→再评测→变差就回滚 |
| `collaborate [--choose N]` | 它提 3 个方案，你拍板；选择会改变下次排序 |
| `emergent` | 行为特征前后对比（可复算） |
| `knowledge gaps` | 列出只有 1 个来源的声明，并给出可补的域名 |
| `db sync/stats/backup` | 账本镜像到 SQLite / 看统计 / 热备份 |
| `ask --resource R --reason ...` | 它申请权限 |
| `grant <id> --scope S --by 你` | 你批准（默认 24h 过期） |
| `perms` | 看申请与批准状态 |
| `autonomy --level full --by 你 --days 90` | 一次性标准授权（之后不再逐条申请） |
| `autonomy --revoke --by 你` | 一键收回，降回 supervised |
| `auto --cycles N` | 无人值守：连续跑，遇预算/冻结/待评审自动停 |
| `transfer` | 多任务训练 + 留出配置评测（当前结论：迁移失败） |
| `learn --per-domain N` | 多来源取样，每个域名最多 N 条 |
| `bench --steps N --seeds N` | 预测基线 |
| `viz` / `report` | 仪表盘 / 周报 |
| `verify` / `lint` / `status` | 校验 / 红线 / 状态 |
| `steward`（含 `--dry-run`） | 建 19 个 Issue |
| `publish.bat` / `scripts/publish.ps1` | 一键发布 |

**退出码**：`0` 正常　`1` 失败（如未评审就想再跑）　`2` 参数错误　`3` 预算拦截

---

## 6. `state/` 里每个文件是什么

| 文件 | 内容 | 能删吗 |
|---|---|---|
| `ledger.jsonl` | 哈希链账本，唯一事实来源 | ❌ 删了就失去审计 |
| `state.json` | 状态机当前状态 + 转换历史 | ❌（`verify` 要求与账本一致） |
| `knowledge.jsonl` | 声明知识库（含复审链） | ❌ |
| `self.json` | 自我模型（身份/能力/失败模式/目标） | ⚠️ 删了相当于"失忆重启" |
| `notify.jsonl` | 通知渠道副本 | ✅ 可重建 |
| `checkpoints/*.json` | 每轮结束的账本锚点 | ✅ 可重建（但就失去历史锚点） |
| `reports/*.md` | 周报 / 预测对比报告 | ✅ |
| `proxy-settings-backup.txt` | 我改你系统代理前的备份 | ✅ |

`state/` 不进 git（`.gitignore`），删了等于从零开始。

---

## 7. 指标

见 `docs/metrics.md`。三类：

1. **工程指标**：步数、预测误差、回滚次数、预算用量、回应率
2. **研究指标**：假设可检验率、复现率、未验证结论占比
3. **自我指涉代理**（v0.2 起）：self-consistency、self-prediction、goal-persistence、error-recognition、novelty-under-constraint

**硬规则**：指标上升 ≠ 意识出现；没有对照基线不下结论；不做显著性检验就不许说"更好"。

---

## 8. 已实现 / 未实现（诚实清单）

**已实现并测试（71 个测试）**：时钟、账本、状态机、预算（单次+日）、红线、环境、预测基线、通知、自我模型、知识库骨架、白名单取样、仪表盘、周报、发布脚本、CI（4 档 Python）。

**未实现**：

| 未实现 | 影响 | 计划 |
|---|---|---|
| ~~策略打不过 BFS~~ | **已解决（v0.7）**：危险区改致命后，学习器 1.78 vs BFS 0.69（2.58 倍） | 见实验 0004 |
| 学习成果不能跨任务迁移 | 换地图就作废，仍是单任务策略 | v0.8：任务生成器专挑 BFS 必败案例 |
| 持续训练会退化 | 已用学习率衰减修好（`docs/experiments/0002-negative-results.md`） | ✅ 已修 |
| 课程机制只有 seed 分段 | 难度还没自动递增 | 下一版 |
| 插件接口 | 加功能要改代码 | v0.4 |
| 在线取样默认启用 | 默认离线，需 `--online` 且白名单 | 保持现状（安全） |
| 知识影响决策 | 知识库还没参与"下一轮做什么" | v0.3 关键 |
| checkpoint 真正恢复 | 目前只有状态回退 | v1.0 |
| `wall_clock` 真实计时 | 现在是步数×系数 | v1.0 |
| 多用户 / 并发锁 | 单机单人 | 保持 |
| 通知推送（webhook） | 只有终端/文件 | 待定 |

---

## 9. 路线图

| 版本 | 内容 | 验收 |
|---|---|---|
| **v0.4**（本版） | 可学策略 + 训练/留出分离 + 循环回滚 | 留出分数必须上升，否则回滚并记录（已达成） |
| **v0.6**（本版） | 线性函数逼近 + `--algo` 切换 | 已实现；结论：线性未超表格，两者都未超 BFS |
| **v0.7**（本版） | 任务重设计：危险区致命（两次即死） | M1' 达成：2.58 倍（实验 0004） |
| **v0.8** | 任务生成器专挑 BFS 必败案例；跨任务迁移；神经网络策略（需 GPU） | 在 BFS 必败集合上胜率 > 50% |
| **v0.4** | 插件接口：`lab/plugins/*.py` + manifest（能力、预算、红线扫描） | 不改编 core 就能加一种新取样源 |
| **v1.0** | 长期运行：checkpoint 真恢复、真实计时、7×24 稳定性报告 | 断电重启后能接上并说明"我停在哪" |

---

## 10. 边界与风险

**永远不做**：自复制、传播、提权、隐藏行为、删审计、接 BCI、宣称意识。

**已知 6 个设计缺口**（`docs/logic-audit.md` 第二节）：真实计时、checkpoint 恢复、两阶段写入、并发锁、回应率窗口、无推送渠道。

**最大的风险不是技术**：是这个项目看起来像"AI 觉醒"，从而吸引来想看奇迹的人，而实际它是"审计 + 闸门 + 可证伪"。README 第一段就是为了挡这个。

---

## 11. 怎么参与 / 怎么发布

- 参与：读 `SECURITY.md` → `issues/README.md` 挑 ⏳ 任务 → 按 `CONTRIBUTING.md` 提 PR
- 护栏改动：`docs/approval-matrix.md`（2 名维护者 + 发起人 + 7 天讨论）
- 发布：双击 `publish.bat`（预检 → 推送 main + tag）→ `docs/publish.md`

---

## 12. 术语表

| 词 | 含义 |
|---|---|
| **自我模型** | 关于自己的结构化声明（身份/能力/失败模式/目标），数字要能从账本复算 |
| **自驱循环** | 不需要人工逐步触发，自己连续跑；但到 REVIEWING 必须停 |
| **取样** | 从白名单源取回标题+摘要（不存全文） |
| **声明（claim）** | 一条可被独立来源验证的主张 |
| **独立性** | 不同域名算独立来源；同一站点的多个页面不算 |
| **复审** | 到期把 verified 降级为 pending，等重新确认 |
| **事实来源** | 账本。state.json、知识库、自我模型都必须能与它对上 |
