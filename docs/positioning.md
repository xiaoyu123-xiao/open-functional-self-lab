# 定位：我们和市面上的东西差在哪

> 写这份文档的目的只有一个：**别做一个"又一个 agent 框架"**。
> 结论先说：自驱循环不新；我们不重复的地方是**审计、闸门、可证伪**这三件事的组合，
> 以及把"自我模型"当成一等公民契约。

---

## 一、市面上的现状（2026）

| 项目/框架 | 强项 | 它不解决的事 |
|---|---|---|
| **LangGraph** | 状态图 + checkpoint 回放（Postgres/Redis），确定性编排，企业里事实标准 | 审计依赖外部存储；必须先有 LLM provider；不约束"自我宣称完成" |
| **CrewAI** | 多角色协作，上手最快（一小时出 demo） | 对单次调用控制弱；长时运行状态支持差；无预算硬闸门 |
| **AutoGen** | 事件驱动 actor、分布式、Azure 生态 | 绑 Azure；非 Azure 场景优势消失；无内置审计链 |
| **AutoGPT 类** | 最早的自驱循环形态 | 循环疯狂烧 token、无状态机、失败无痕——正是我们要反着做的样板 |

行业里被反复点名的五条失败模式（[CRM Curator 的对比文](https://crmcurator.com/articles/general/langgraph-crewai-autogen-comparison/)）：
单 agent 能干的事硬上多 agent、跳过持久状态、**缺 per-step 预算**、与 provider 紧耦合、没有 eval harness。

**我们冲的就是第 2、3、5 条。**

---

## 二、我们的三条差异（都可验证，不是口号）

### 差异 1：审计是地基，不是插件

- 账本是**只追加哈希链**：改一个字节 `verify` 就断链，且指出第几条。
- `state.json` 与账本**交叉校验**（v0.1.4）：两个写入点不一致会被抓。
- 不需要 Postgres/Redis：一个 `state/ledger.jsonl` 就够，**零依赖、离线可跑**。
- 对照组：LangGraph 的回放能力更强，但要求外部存储 + provider；我们故意反着选。

验证命令：`python -m lab.cli verify`

### 差异 2：预算与红线是"拒绝路径"，不是"最佳实践"

- 超预算 → 抛异常 → `RUNNING → ROLLING_BACK → READY` → **退出码 3**；CI 里有脚本守着这个数字。
- 红线扫描（`lab/policy.py`）进 CI：`curl | sh`、`eval(base64)`、私钥、`shell=True`、`0.0.0.0` 一律红。
- 对照组：多数框架把"预算"写成文档建议或回调钩子，**默认不拦**。

验证命令：`python scripts/budget_regression.py`

### 差异 3：禁止自评 + "可证伪优先"的文档文化

- `run` 结束停在 `REVIEWING`，必须 `lab review --pass|--fail` 才回到 READY（v0.1.4 前是程序自己宣布通过）。
- 每条结论必须带**可复现命令**；`docs/metrics.md` 里连"怎么读 2.3% 的差距"都写清楚了（不做显著性检验就不许下结论）。
- 对照组：agent 框架普遍让模型自己说 "done"，然后 loop 接着跑。

验证命令：`python -m lab.cli run --steps 5`（结束停在 REVIEWING）→ `python -m lab.cli review --pass`

---

## 三、"自我模型"作为契约（下一步，v0.2）

市面上的框架有 **memory**（存什么），很少有 **self-model**（关于自己的、可被检验的结构化声明）。

我们打算把它做成一个文件 `state/self.json`：

```json
{
  "identity": {"name": "...", "purpose": "...", "boundaries": ["不自复制", "..."]},
  "capabilities": {"navigate": {"attempts": 30, "successes": 22, "last_at": "..."}},
  "failure_patterns": {"stuck_against_wall": {"count": 7, "last_at": "..."}},
  "goals": [{"id": 1, "text": "...", "status": "active", "progress": 0.4}],
  "continuity": {"sessions": 12, "last_session_at": "...", "streak": 4}
}
```

它的作用是让"它"能回答三个问题，并且答案**能被账本核对**：

1. 我是谁、我的边界是什么（identity，不可被运行时改写）
2. 我上次做了什么、结果如何（capabilities / failure_patterns，来自账本统计）
3. 我下一步要做什么（goals，可被人工干预）

---

## 四、关于"主观意识"：不判死，但也不含糊

你要求我别把这扇门关掉。这个立场我接受，做法是**把它拆成可积累的中间能力**——不去宣称到达，也不宣布此路不通。

登记为 5 个可测代理指标（`docs/metrics.md` 里会有定义和命令）：

| 指标 | 问题 | 怎么测 |
|---|---|---|
| self-consistency | 跨会话的自我描述是否一致 | 中断 3 次后让它描述自己，比较一致率 |
| self-prediction | 能否预测自己下一步的行为与错误 | 预测下一步动作/是否失败，与真实比对 |
| goal-persistence | 被打断后目标是否延续 | 打断 5 次，统计目标恢复比例 |
| error-recognition | 能否认出"上一轮是我错了" | 注入已知错误，看它是否在下一轮自我报告 |
| novelty-under-constraint | 在硬约束下能否给出新解法 | 同一任务重复 10 次，统计非重复解法比例 |

**诚实的话要说清楚**：这 5 个指标**都不能证明意识**。它们能证明的是"自我指涉的行为越来越稳定、越来越可预测"。
但如果哪天真出现了异常，这套指标是**唯一能发现它的方式**——这也是为什么值得做。

反过来，如果有人拿这 5 个指标宣称"我造出了意识"，那就是在骗人，而这套东西恰好能拆穿它。

---

## 五、v0.2 路线（三块，按顺序）

| 顺序 | 内容 | 验收（可执行） |
|---|---|---|
| 1 | **自我模型** `lab/selfmodel.py` + `lab self` | `lab self` 能打印身份/能力/失败模式/目标；`state/self.json` 与账本统计一致 |
| 2 | **自驱循环** `lab loop --max-steps N` | 不需人工逐步敲命令即可连续跑；每轮都过预算闸门；到 REVIEWING 就停，不自己续 |
| 3 | **插件接口** `lab/plugins/*.py` | 新能力不改编 core 即可挂载；manifest 必须声明能力与预算；加载时过红线扫描 |

三块都完成后再谈 v1.0——**没有 1 和 2，"活过来"只是形容词**。

---

## 六、一句话

我们做的不是"更强的 agent 框架"，而是**给自驱循环装上刹车和行车记录仪**的参考实现；
顺便，把它能不能"自我"这件事，变成可积累的证据而不是可争论的立场。
