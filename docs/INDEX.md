# 文档索引（从哪开始读）

> 仓库里有 40+ 份文档。这里是唯一入口，按"你现在想知道什么"排序。

---

## 第一次接触（按顺序）

| 顺序 | 读什么 | 花多久 |
|---|---|---|
| 1 | [一页看懂](ONE-PAGE.md) | 1 分钟 |
| 2 | [起源与现状](ORIGIN.md)：最初的想法、哪些没做到 | 3 分钟 |
| 3 | [它能干什么、不能干什么](../README.md)（README 第一屏） | 2 分钟 |

## 想拿走点东西

| 你想要 | 去哪 |
|---|---|
| 一段绕开危险区的规划（零依赖 5 行） | [SAFETY.md](SAFETY.md) + `lab/safety.py` |
| 按预算选策略 | `python -m lab.cli frontier --world ref-1,lethal,one_hit` |
| 把环境/策略接进来（20 行） | [EXTEND.md](EXTEND.md) + `examples/` |
| 接大模型 | [DEPLOY-WITH-MODEL.md](DEPLOY-WITH-MODEL.md) |
| 高配机器 / 并行 | [HARDWARE.md](HARDWARE.md) |

## 想知道它可不可信

| 问题 | 去哪 |
|---|---|
| 犯过哪些错、怎么防的 | `python -m lab.cli lessons`（11 条，每条都绑测试或脚本） |
| 已经测出什么 | `python -m lab.cli facts --brief`（21 条，带复算证据） |
| 哪些结论还站着 | [EXPERIMENTS-SUMMARY.md](EXPERIMENTS-SUMMARY.md) |
| 全部实验（含失败） | [experiments/](experiments/)——35 篇，26 篇负结果 |
| 我有没有自我美化 | [self-audit.md](self-audit.md) + [language.md](language.md) |
| 记忆怎么存的 | [MEMORY-PROTOCOL.md](MEMORY-PROTOCOL.md) |

## 想参与

| 做什么 | 去哪 |
|---|---|
| 提问题 | `.github/ISSUE_TEMPLATE/bug_report.md`（要求贴 `doctor` 输出） |
| 改代码 | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| 接神经策略（有算力的人） | [ROADMAP-NEURAL.md](ROADMAP-NEURAL.md) |
| 加语言 | [i18n.md](i18n.md) |
| 推广 | [promotion.md](promotion.md) |

## 内部参考

| 内容 | 去哪 |
|---|---|
| 总册（模块、命令、状态机） | [MASTER.md](MASTER.md) |
| 不用代码的用法 | [USER-GUIDE.md](USER-GUIDE.md) |
| 参考任务与两级协议 | [BENCHMARK.md](BENCHMARK.md) |
| 给执行型 AI 的手册 | [../AGENT-RUNBOOK.md](../AGENT-RUNBOOK.md) |
| AI 自己怎么用这个仓库 | [AGENT-SELF-USE.md](AGENT-SELF-USE.md) |
