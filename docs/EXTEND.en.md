# Plug in your own environment (20 lines)

> The reusable part of this repo is not the 8×8 grid — it is the **shell**:
> per-step ledger, a hard budget gate, rollback, and held-out scoring.
> You do not need to modify this repo. Provide **an environment** and **a policy**.
> [中文](EXTEND.md) | **English**

---

## 1. Two methods, nothing else

```python
class MyEnv:
    def reset(self):            # called once per episode
        return observation      # any object: number, array, dict

    def step(self, action):     # must return a dict containing "observation"
        return {"observation": ..., "reward": 0.0, "done": False}

class MyPolicy:
    def act(self, observation): # return any hashable object
        return action
```

No base class, no registration — duck typing only. That is deliberate: you can wrap someone
else's library without adapting it.

## 2. A complete example (in this repo)

`examples/lineworld.py` — a number line from 0 to 9; reaching 9 gives +1.

```bash
python -m lab.cli generic \
  --env examples/lineworld.py:make_env \
  --policy examples/lineworld.py:RightPolicy \
  --steps 12 --eval-episodes 3
```

Output:

```
通用回合完成：9 步，总回报 +1.000，提前结束
账本记录 run_id=generic-001（可用 `lab verify` 校验完整性）
留出评测：3 回合，平均回报 +1.000（最好 +1.000，最差 +1.000）
```

Four things you get for free:

| Capability | Where it comes from |
|---|---|
| Per-step ledger entry (tamper-evident) | `lab/core.py` |
| Budget gate (raises instead of silently spending) | `lab/budget.py` |
| Held-out scoring with fixed seeds | `lab/core.py::evaluate_policy` |
| An `alert` record instead of a corrupted ledger when your code raises | `run_generic_episode` |

## 3. Wrapping a model

```python
# my_agent.py
from somewhere import MyModel

class ModelPolicy:
    def __init__(self):
        self.model = MyModel()

    def act(self, observation):
        return self.model.predict(observation)
```

```bash
python -m lab.cli generic --env my_env.py:make_env --policy my_agent.py:ModelPolicy --steps 50
```

If a call is expensive, add a budget category first and `charge` **before** calling.
Charging after the call is how a single runaway request burns an allowance.

## 4. When it refuses you (and why)

| Situation | Behaviour | Reason |
|---|---|---|
| `step()` returns no `observation` | raises `GenericRunError` | without an observation, guessing is worse |
| your policy raises | records an `alert`, then stops | the ledger must never be corrupted |
| budget exceeded | raises `BudgetExceeded`, exit code 3 | designed, not a bug |
| interface mismatch | reports which method is missing | it will not guess your intent |

## 5. Four real uses (none of them "self-improvement")

| Use | For whom | How |
|---|---|---|
| Audit + budget around an existing loop | automation scripts | replace the loop body with `run_generic_episode` |
| Held-out evaluation for your model | people training models | `evaluate_policy` with fixed seeds |
| Experiment records with pre-registered criteria | researchers | copy the format of `docs/experiments/0008` |
| Agent permission flow | teams letting agents act | `lab ask / grant / autonomy` |

None of these requires the "self-improvement" premise. That was the original motivation,
not the only use.
