# Open Functional Self Lab

> 研究"功能性自我模型"和开放式研究循环。**我们不宣称任何系统拥有意识。**
>
> 📖 **不会写代码？** 直接看 [使用手册 docs/USER-GUIDE.md](docs/USER-GUIDE.md)：装好、跑起来、看懂输出，全程复制粘贴。
> 🗺️ **想了解全貌？** 看 [总册 docs/MASTER.md](docs/MASTER.md)：需求、架构、模块、命令、路线图、边界。

一个**能跑起来**的受控实验台：把最容易被口头承诺、却最难验证的部分——时间、预算、状态机、
审计账本、红线、可视化——先做成可执行、可测试、可回滚的代码。

`Python ≥ 3.10` · 零第三方依赖 · 纯 CPU · 离线可跑 · MIT

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

**已验证**：10 项自检全过 · 92 个 unittest · CI 覆盖 Python 3.10–3.13 · 干净 clone 复验通过。

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
