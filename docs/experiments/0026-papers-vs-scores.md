# 实验 0026：按论文改奖励塑形，行为一分没变——分数却在变

> 日期：2026-11-04　版本：v0.38.0
> 起因：委托人提醒"自我进化应该靠外部论文与学术"，而我一直在原地自己推。

---

## 一、先修取样器（它之前等于没取）

`lab learn --online` 抓 arXiv 时，只把**整份 feed 的标题**当成一条声明（存进去的是 `export.arxiv.org`）。
等于什么都没取到。

已修：新增 `parse_atom_entries()`，把 Atom 的 `<entry>` 拆成逐篇（标题/摘要/链接），
`fetch_many` 遇到多篇时会逐条入库。

修完后，一次取样入库 6 篇：

| # | 标题 | 来源 |
|---|---|---|
| 5 | A new Potential-Based Reward Shaping for Reinforcement Learning Agent | arxiv.org |
| 6 | Improving the Effectiveness of Potential-Based Reward Shaping in RL | arxiv.org |
| 7 | Hierarchical Potential-based Reward Shaping from Task Specifications | arxiv.org |
| 8 | Automating Potential-based Reward Shaping with Vision Language Model Guidance | arxiv.org |
| 9 | Potential-Based Reward Shaping For Intrinsic Motivation | arxiv.org |
| 10 | On the Sample Efficiency of Abstractions and Potential-Based Reward Shaping | arxiv.org |

知识库现在共 10 条声明、3 个来源域名。`python -m lab.cli knowledge gaps` 可以看哪些还只有单一来源。

## 二、按论文改代码

Ng, Harada & Russell (1999) 的结论是：**只有势能式塑形** `F(s,s') = γΦ(s') − Φ(s)`
才保证不改变最优策略。我们原来的写法是 `0.1 × (d − d')`，**少了 γ 因子**。

已实现三种模式（`shaping=`）：

| 模式 | 公式 |
|---|---|
| `none` | 不塑形 |
| `legacy`（默认，兼容旧结论） | `0.1 × (d − d')` |
| `potential`（严格势能式） | `γΦ(s') − Φ(s)`，`Φ(s) = −0.1·d(s)`，γ=0.95 |

另外按第 9 篇（Intrinsic Motivation）加了**计数式探索奖励**：`bonus / sqrt(1 + 访问次数)`。

## 三、结果：行为一模一样，分数差 4 分

**走廊 10×10，非致命：**

| 组 | 分数 | 吃到 | 受伤 |
|---|---|---|---|
| ① 无塑形 | −0.42 | 9.8 | 5.0 |
| ② 旧塑形 | −0.42 | 9.8 | 5.0 |
| ③ 严格势能式 | **+1.67** | 9.8 | 5.0 |
| ④ 势能式 + 探索奖励 | **+3.62** | 9.8 | 5.0 |

**碰即死：**

| 组 | 分数 | 吃到 | 受伤 |
|---|---|---|---|
| ① 无塑形 | −1.20 | 0.0 | 0.0 |
| ③ 严格势能式 | **+0.80** | 0.0 | 0.0 |
| ④ 势能式 + 探索奖励 | **+2.36** | 0.0 | 0.0 |

## 四、这说明了什么（比数据重要）

1. **塑形改的是"分数怎么算"，不是"策略怎么做"**。四组行为完全一致（吃到 9.8 / 受伤 5.0）。
2. 严格势能式的分数变高，是因为 `γΦ(s_T) − Φ(s_0)` 在回合结束时**不平**：
   终点离食物更近，`Φ` 更大，于是整条轨迹的白送分变多。**这正是文献说的"策略不变、返回值变"。**
3. 所以过去几轮里我那些"分数变好了"，**大部分是这一类记账差异**，不是能力提升。

## 五、正式确立的规矩（从本轮起）

> **主指标只看与奖励无关的量：吃到份数、受伤次数、存活步数。**
> 分数只作参考，且**跨奖励版本不可比较**。

这不再是建议，是硬规矩——本轮就是它揭穿了四次"看起来的进步"。

## 六、下一步

1. **"不动"是任务设计问题**：食物远、死亡 −5 → 不动是理性的。把食物放进 12–20 步内，
   让"不动"必然输给探索。
2. 用新主指标重跑 0022 那张 2×2 表，看结论是否变化。
3. 知识库里的 6 篇论文还没读完摘要，下一步应逐篇提取"具体做法"，而不是只看标题。
