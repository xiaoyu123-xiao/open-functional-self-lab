# 示例：这个壳能装什么

> 三个示例，都不用联网、不用显卡，`python examples/xxx.py` 直接跑。
> 它们证明一件事：**这个仓库不是只能玩 8×8 网格**。

| 示例 | 演示什么 | 跑法 |
|---|---|---|
| `eval_harness.py` | 给**你自己的模型**算留出分数（训练 seed 与评测 seed 不重叠） | `python examples/eval_harness.py` |
| `llm_wrapper.py` | 包一个"模型"：先扣预算 → 调用 → 非法输出降级 → 全进账本 | `python examples/llm_wrapper.py` |
| `budgeted_fetch.py` | 带预算的取样：白名单 → 先扣费 → 只存摘要 | `python examples/budgeted_fetch.py` |

---

## 1. `eval_harness.py`：评测台

```python
from lab.core import evaluate_policy

stats = evaluate_policy(
    make_env=MyEnv, policy=MyPolicy,
    episodes=20, steps=1, seeds=range(9000, 9020),   # 留出 seed
)
print(stats["mean_return"])   # 别人可以用同一批 seed 复算
```

实测输出：

```
训练集上调出的阈值：0.5
留出集准确率：1.000（20 题）
随机猜的准确率：0.450
```

**关键点**：训练用 1000–1019，评测用 9000–9019，两段不重叠。
这就是"分数能不能信"的分界线。

## 2. `llm_wrapper.py`：把模型包成策略

```python
class ModelPolicy:
    def act(self, observation):
        self.budget.charge("calls_per_day", 1)      # 先付钱
        reply = self.model.chat(prompt)
        if reply.strip().lower() not in ACTIONS:
            return "rest"                          # 非法输出降级，不猜
        return reply.strip().lower()
```

实测输出（预算 8 次）：

```
结果：5 步，总回报 +1.0
模型调用 5 次，其中非法输出 1 次（已降级为 rest）
```

换成真实模型：把 `MockModel.chat` 换成你的 API 调用，其余不动。

## 3. `budgeted_fetch.py`：带预算的取样

实测输出（预算 2 次）：

```
候选 3 条，预算上限 2 次
取回 2 条，跳过 1 条
  跳过原因：预算拦截：search_requests_per_day 超限…
入库 2 条新声明（只存标题+摘要+URL，不存全文）
```

三件事一起演示：**白名单拒绝、先扣费再请求、只存摘要**。

---

## 自己写一个

1. 环境只需要两个方法：`reset()` / `step(action)`
2. 策略只需要一个方法：`act(observation)`
3. 跑：`python -m lab.cli generic --env 你的文件.py:make_env --policy 你的文件.py:Policy --steps 50`

细节见 [`docs/EXTEND.md`](../docs/EXTEND.md)。

## 注意

`--env` 指向的文件**会被真的执行**（等于 `python 那个文件.py`）。
只对你信任的文件用它。这一点在 [`docs/security-audit.md`](../docs/security-audit.md) 第五节写明了。
