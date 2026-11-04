# 推广方案：让陌生人 3 分钟内决定"要不要 star"

> 现状：仓库能跑、CI 绿、文档齐，但**没有描述、没有 Topics、只有一个旧 Release、零曝光**。
> 这份文档只做一件事：把"能跑"变成"有人知道它能跑"。

---

## 一、先做三件 5 分钟的事（不做后面都白搭）

| 动作 | 具体 | 为什么 |
|---|---|---|
| ① 填仓库描述 | Settings → General → Description 填：<br>`受控实验台：审计账本 / 预算闸门 / 可学策略 / 迁移评测。不宣称意识，只报告可测指标。` | 搜索结果里只显示描述，没有描述等于没名字 |
| ② 填 Topics | `research-infrastructure` `audit-ledger` `reinforcement-learning` `reproducibility` `human-in-the-loop` `python` `offline-first` `sandbox` | GitHub 的 Topics 是主要的发现入口之一 |
| ③ 发一个 Release | 用 `?tag=v0.16.0` 直达链接，标题 `v0.16.0 — 多种子复现`，正文粘 CHANGELOG 对应段落 | Release 会出现在仓库首页右侧，是最显眼的"这东西在维护"的证据 |

## 二、加三个"可信度信号"（各 10 分钟）

1. **CI 徽章**：README 顶部加
   ```markdown
   [![ci](https://github.com/xiaoyu123-xiao/open-functional-self-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/xiaoyu123-xiao/open-functional-self-lab/actions/workflows/ci.yml)
   ```
2. **License 徽章**：`![license](https://img.shields.io/badge/license-MIT-blue)`
3. **一行可复现结论**：README 首屏放这张表（别人看完就知道你在做什么）：

   | 任务 | 手写 BFS | 学出来的策略 |
   |---|---|---|
   | 危险区致命（hazards=8） | −1.758 | **+1.597** |
   | 危险区致命（hazards=10） | −2.340 | **+0.573** |

   > 附一句："这只是在单一地图族上成立，别外推。"

## 三、推广渠道（按性价比排序）

| 渠道 | 怎么发 | 注意事项 |
|---|---|---|
| **GitHub Topics + 描述** | 见上 | 零成本，优先级最高 |
| **awesome-lists PR** | 找 3–5 个相关清单：`awesome-machine-learning`、`awesome-rl`、`awesome-audit`、`awesome-reproducibility` | 每个清单的收录标准不同，先读 CONTRIBUTING；**不要群发同一个 PR 文案** |
| **V2EX / 掘金 / 知乎（中文）** | 标题用"我做了一个不宣称意识的 AI 实验台，记录了我三次失败的实验" | 中文社区对"诚实的失败记录"接受度高于"又一个框架" |
| **Hacker News（Show HN）** | 标题：`Show HN: A lab that logs every claim it makes (and fails publicly)` | 英文、短、强调"可复现 + 失败记录"，不要吹 AI |
| **Reddit** | r/MachineLearning 需谨慎（自荐限制严格）；r/reinforcementlearning、r/opensource 更宽松 | 先读版规，很多板块要求"有实质性讨论价值" |
| **论文/预印本** | 若把实验 0006–0008 整理成 4 页短文，投 arXiv cs.LG | 有 Zenodo DOI 会更像"可引用的东西" |

## 四、可直接复制的两段文案

**中文（V2EX / 知乎 / 掘金）**：

> 我做了一个"AI 自我进化"的实验台，但它最值钱的部分是**失败记录**。
>
> 四代方案同一个判据：表格 → 线性 → 多臂 → 加权插值。
> 前两代都输给一个手写的笨规则（最短路径），第三代追平，第四代才赢——赢的原因不是"训得多"，而是
> **换了一种表示**。这些数字全部可用一条命令复跑。
>
> 它不宣称意识，不假装有情绪；它只有审计账本、预算闸门、和一堆被证伪的假设。
> 如果你是那种"想知道它到底怎么变强"的人，这个仓库可能对你有用。

**英文（Show HN / Reddit）**：

> I built a small lab for "self-improving agents" and then spent most of the time **falsifying my own claims**.
>
> Four generations, same criterion (held-out transfer): tabular → linear → multi-head → weighted multi-head.
> The first two **lost** to a hand-written BFS baseline. Only after changing the *representation* (not the data volume)
> did the learned policy win: `+1.60` vs `−1.76` on unseen hazard densities.
>
> Everything is reproducible with one command; every experiment that failed is documented with its numbers.
> No claims about consciousness. Just ledgers, budgets, and falsified hypotheses.

## 五、别做的三件事

1. **别刷 star / 群发链接**——会被举报，且 star 数不解决"没人用"。
2. **别写"AI 觉醒"**——那是这个项目最想避免的误读，也会立刻掉粉。
3. **别在 README 里堆功能列表**——陌生人只看三件事：**它是干什么的、能不能跑、有没有证据**。

## 六、判断推广是否有效的三个指标（比 star 更真实）

| 指标 | 怎么看 | 目标 |
|---|---|---|
| clone 数 | Insights → Traffic（14 天） | 有真实 clone 就说明有人在试 |
| `doctor` 的通过率 | 让人在 Issue 里贴输出 | 若有人报错，说明文档有坑，优先修 |
| 外部 Issue / PR | Issues 列表 | 第一条外部 Issue 是转折点，值得立刻回 |

**一句话**：这个仓库现在的短板不是代码，是"没人知道它存在"；
但"有人知道"之前，先把描述、Topics、Release 补齐——否则来了也留不住。
