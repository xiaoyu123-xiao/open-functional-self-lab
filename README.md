# Open Functional Self Lab

> [中文](README.md) | [English](README.en.md)

**这个仓库是什么**：一份**零依赖的可复现实验模板** + 一份**诚实的失败档案** + 一条**被验证过的小结论**。

**它不是什么**：不是自我进化系统，不是安全 RL 框架，不是通用 agent 库。**技术上也不新颖**——
"把危险区纳入规划"属于 safe RL / shielding 一类成熟方法（[Alshiekh et al., AAAI 2018](https://aaai.org/papers/11797-safe-reinforcement-learning-via-shielding/)）。
**想找现成安全 RL 库的人，请优先用 shielding 的官方实现；这个仓库不适合你。**

> **起源**：这个项目最初的想法（自我进化、连续记忆、人机协作、左脚踩右脚）原样记在
> [`docs/ORIGIN.md`](docs/ORIGIN.md)，包括哪些没做到。**那一页不要删。**

## 唯一可拿走的结论

> 在有危险区的环境里，**把危险区纳入规划**比只走最短路更好：
> **受伤从未更高**；在伤害致命（碰即死）或环境会变（危险区漂移）时，吃食不减少而严格更好。
> 7 个世界、2 种地图生成规则都成立。

五行就能用（不需要训练、不需要本仓库其它部分）：

```python
from lab.safety import hazard_aware_path
step = hazard_aware_path(env)      # 无路可走返回 None
if step:
    env.step(step)
```

详见 [`docs/SAFETY.md`](docs/SAFETY.md)。

## 它可能对你有用的三个地方

| 你可能想要 | 这里有什么 |
|---|---|
| 一段零依赖的"绕开危险区"规划 | `lab/safety.py`（BFS，标准库，5 行用法） |
| 一套"不骗自己"的实验流程 | 判据先写后跑、≥20 组才可声称显著、奖励一改旧分数作废、结论必须引用已核实事实 |
| 一份失败档案 | 31 篇实验，**26 篇是负结果**，每篇带复算命令 |

## 一句话劝退

如果你要的是"能自我进化的 AI"——**这个仓库没有，而且我们 31 篇实验里 26 篇负结果正是它做不到的证据。**
如果你要的是"一个小而干净的审计/自检模板，附一份真实的失败记录"——你可以从这里拿走。

## 证据（可复算）

`python -m lab.cli frontier --world ref-1,lethal,one_hit,slippery,drift`（单位：份/回合、次/回合）

| 世界 | 最短路 BFS | 安全规划（危险区当墙） | 判定 |
|---|---|---|---|
| 非致命 | **5.00** / 2.50 | 2.17 / **0.00** | 权衡 |
| 致命 | **3.50** / 1.33 | 2.17 / **0.00** | 权衡 |
| **碰即死** | 2.00 / 0.83 | **2.17 / 0.00** | **支配** |
| 打滑 30% | **5.00** / 10.00 | 3.67 / 4.50 | 权衡 |
| **危险区漂移** | 5.00 / 2.50 | **5.00 / 0.17** | **支配** |
| 房间式 | **3.33** / 0.67 | 3.17 / **0.00** | 权衡 |
| **房间式·碰即死** | 2.67 / 0.50 | **3.17 / 0.00** | **支配** |

**结论**：把危险区纳入规划后，**受伤从未高于 BFS**（7 个世界全部成立）；
在伤害致命（碰即死）或环境会变（漂移）时，它在吃食不减少的情况下**严格更好**，
且该结论在**两种地图生成规则**（走廊、房间）上重复出现。学习器在所有世界里都没进前沿。
**局限**：只测一张 10×10 走廊地图族，不要外推。

## 五分钟跑通

```bash
git clone https://github.com/xiaoyu123-xiao/open-functional-self-lab.git
cd open-functional-self-lab
python -m lab.cli doctor          # 10 项自检
python -m lab.cli init
python -m lab.cli run --steps 20  # 跑一轮受控循环（结束停在 REVIEWING）
python -m lab.cli review --pass    # 评审通过才回到 READY
python -m lab.cli self             # 看它对自己的描述（能力/失败模式/目标）
python -m lab.cli learn            # 离线取样入知识库（不联网）；--online 才真的取
python -m lab.cli loop --cycles 3  # 自驱循环：评测→训练→再评测→变差就回滚
python -m lab.cli verify          # 校验账本/状态机/checkpoint/预算
python -m lab.cli lint            # 红线扫描
python -m lab.cli bench --steps 200  # 预测基线对比（random/persistence/linear）
python -m lab.cli inbox           # 看待回应的告警与回应率
python -m lab.cli viz             # 生成仪表盘 viz/status.md
```

Windows / macOS / Linux 命令相同。想完全复现某次运行：加 `--fake-now 2026-01-01T00:00:00Z`。

## 这不是什么

- ❌ 不是"会自我进化/觉醒"的程序。仓库里**没有**自复制、网络传播、权限提升、隐藏行为的代码，
  `lab/policy.py` 会拦住这类 PR。
- ❌ 不是大模型部署教程。默认不下载任何权重。
- ❌ 不是论文。"涌现""意识"只作为**待验证假设**记录，不作为结论。

`lab run` 跑的是**8×8 网格环境**（墙 / 食物 / 危险区，能量会掉、踩危险区会受伤）。它是玩具环境、不是模型，但状态是真的：同一个 seed 下逐字节可复现。

## 它到底做了什么

| 你会得到 | 文件 |
|---|---|
| 统一时钟（UTC-only，naive 时间直接抛错） | `lab/clock.py` · `time/README.md` |
| 只追加哈希链账本（改一个字节就断链） | `lab/ledger.py` |
| 显式状态机（非法转换拒绝，手改 state.json 会被抓） | `lab/state.py` · `logic/README.md` |
| 预算硬闸门（超限抛异常 → 回滚 → 退出码 3） | `lab/budget.py` · `docs/budget.md` |
| 红线扫描（CI 每次跑） | `lab/policy.py` · `SECURITY.md` |
| 仪表盘 / 周报自动生成 | `lab/viz.py` · `lab/report.py` |
| 预测基线对比（random / persistence / linear） | `lab/predict.py` · `lab bench` |
| 可学策略（表格 / 线性）+ 训练留出分离 | `lab/agent.py` · `lab/linear.py` · `lab loop` |
| 在有算力的机器上跑 | `deploy/README.md`（Docker / tmux / GPU 可选） |
| 通知：分级 / 24h 去重 / `ack` 回应 / 回应率 | `lab/notify.py` · `lab notify` · `lab inbox` |
| **自我模型**：身份锚点 / 能力自评 / 失败模式 / 目标 | `lab/selfmodel.py` · `lab self` |
| **取样入库**：白名单 → 声明 → 独立性 → 复审 | `lab/web.py` · `lab/knowledge.py` · `lab learn` |
| 紧急冻结开关 | `lab freeze` / `lab unfreeze --by <你>` |

**已验证**：10 项自检全过 · 108 个 unittest · CI 覆盖 Python 3.10–3.13 · 干净 clone 复验通过。

## 参与

1. 读 `SECURITY.md`、`ETHICS.md`、`GOVERNANCE.md`（15 分钟）
2. `issues/README.md` 挑一个标 ⏳ 的任务认领，大部分是纯 CPU
3. 按 `CONTRIBUTING.md` 提 PR

红线、预算闸门、账本算法属于不可变核，改动要走 `docs/approval-matrix.md` 的双人审批。

## 文档

`docs/publish-first-time.md` 发布指南 · `docs/gap-analysis.md` 设计取舍 · `docs/process.md` 日常流程
`docs/metrics.md` 指标口径 · `docs/logging.md` 日志规范 · `docs/tools.md` 环境与硬件

## 已知边界

- `lab run` 的环境是玩具级（8×8 网格），不是真实任务
- 未做多用户鉴权，单机单人
- 不收集个人数据；不接入任何脑机接口/神经信号设备

## 许可

MIT（见 `LICENSE`）。安全与治理条款是**合并条件**，不是法律条款——违反即拒绝合入。
