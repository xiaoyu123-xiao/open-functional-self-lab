# 把你自己东西接进来（20 行）

> 这个仓库最有用的部分不是那个 8×8 网格，而是**外面那层壳**：
> 每一步都记账、预算超了立刻停、变差能回滚、事后能复算。
>
> 你不需要改这个仓库的任何代码，只需要提供两个东西：**一个环境**、**一个策略**。

---

## 1. 最小约定（就两个方法）

```python
class MyEnv:
    def reset(self):            # 每回合开始调用一次
        return observation      # 任意对象都行：数字、数组、字典

    def step(self, action):     # 返回至少包含 observation 的字典
        return {"observation": ..., "reward": 0.0, "done": False}

class MyPolicy:
    def act(self, observation): # 返回任何可哈希对象
        return action
```

不需要继承基类，不需要注册，鸭子类型即可——**这样你可以直接包别人的库**。

## 2. 一个完整例子（仓库里就有）

`examples/lineworld.py`：一条数轴，走到 9 得 +1。它跟 8×8 网格毫无关系。

```bash
python -m lab.cli generic \
  --env examples/lineworld.py:make_env \
  --policy examples/lineworld.py:RightPolicy \
  --steps 12 --eval-episodes 3
```

输出：

```
通用回合完成：9 步，总回报 +1.000，提前结束
账本记录 run_id=generic-001（可用 `lab verify` 校验完整性）
留出评测：3 回合，平均回报 +1.000（最好 +1.000，最差 +1.000）
```

**你立刻得到的四样东西**（不需要写一行额外代码）：

| 能力 | 来自哪里 |
|---|---|
| 每步落账本（可校验，改一个字节就发现） | `lab/core.py` |
| 预算闸门（步数超限抛异常，不会静默烧钱） | `lab/budget.py` |
| 留出评测（固定 seed，别人可复算） | `lab/core.py::evaluate_policy` |
| 出错时记 alert 而不是写坏账本 | `run_generic_episode` 的异常分支 |

## 3. 接你自己的模型/库

```python
# my_agent.py
from somewhere import MyModel

class ModelPolicy:
    def __init__(self):
        self.model = MyModel()
        self.history = []

    def act(self, observation):
        self.history.append(observation)
        return self.model.predict(observation)   # 返回动作即可
```

```bash
python -m lab.cli generic --env my_env.py:make_env --policy my_agent.py:ModelPolicy --steps 50
```

如果模型一次调用很贵，先在 `lab.config.json` 里加预算项，再在策略里 `charge`——
**先付钱再调用**，这是唯一能防"一次失控调用烧穿额度"的顺序。

## 4. 什么时候会拒绝你（以及为什么）

| 情况 | 行为 | 说明 |
|---|---|---|
| `step()` 没返回 `observation` | 抛 `GenericRunError` | 没有观测就没法继续，硬猜会更糟 |
| 策略抛异常 | 记一条 `alert` 后停止 | 账本不会被写坏 |
| 超预算 | 抛 `BudgetExceeded`，退出码 3 | 这是设计，不是 bug |
| 环境/策略不是鸭子类型 | 加载时提示缺哪个方法 | 不猜你的意图 |

## 5. 你现在可以拿它做的四件事（都不是"自我进化"）

| 用途 | 用户是谁 | 怎么用 |
|---|---|---|
| 给已有脚本加"审计 + 预算" | 写自动化脚本的人 | 把循环体换成 `run_generic_episode` |
| 给自己训练的模型做评测台 | 调模型的人 | 用 `evaluate_policy` + 固定 seed |
| 记录实验并预注册判据 | 做实验/写论文的人 | 照 `docs/experiments/0008` 的格式写 |
| 给 agent 加"申请权限"流程 | 想让 AI 干活的团队 | `lab ask / grant / autonomy` |

**这四件事都不需要"自我进化"这个前提。** 那只是这个项目最初的动机，不是它唯一的用途。
