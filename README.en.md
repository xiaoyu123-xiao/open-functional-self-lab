# Open Functional Self Lab

> We study functional self-models and open-ended research loops. **We do not claim any system is conscious.**
>
> [中文](README.md) | **English**

> **👉 One page is enough:** [docs/ONE-PAGE.en.md](docs/ONE-PAGE.en.md) — one diagram, three commands, two numbers.

## What it is

A small lab that **runs experiments on itself and keeps an auditable ledger of every step**.
Not a chatbot. Not an LLM. No GPU, no network, no API keys.

It ships with one example world (an 8×8 grid with food, walls and lethal hazard zones) and a
learning policy, so you can see the whole loop run in seconds. The part worth reusing is the
**shell around it**: append-only hash-chained ledger, hard budget gate, explicit state machine,
held-out evaluation, and a rollback that keeps the last good policy.

## Evidence (reproducible)

Run: `python -m lab.cli transfer --algo weighted --repeats 5`

| Task | Hand-written BFS baseline | Learned policy |
|---|---|---|
| lethal hazards = 8 | −1.758 | **+1.597** |
| lethal hazards = 10 | −2.340 | **+0.573** |

The hand-written rule walks the shortest path and **cannot feel pain**; the learned policy is shaped by
`hurt = −1`, `death = −5`. This holds **only** for one 8×8 map family with varying hazard density.
Five paired runs won 5/5. No statistical test was performed. Do not extrapolate.

## Quick start (3 commands)

```bash
git clone https://github.com/xiaoyu123-xiao/open-functional-self-lab.git
cd open-functional-self-lab
python -m lab.cli doctor          # expect "all checks passed"
python -m lab.cli loop --cycles 3 --lethal
```

Requirements: Python ≥ 3.10, nothing else. Linux / macOS / Windows. ~0.5 MB.

## Use it with your own environment (20 lines)

```python
class MyEnv:
    def reset(self): return observation
    def step(self, action): return {"observation": ..., "reward": 0.0, "done": False}

class MyPolicy:
    def act(self, observation): return action
```

```bash
python -m lab.cli generic --env my_env.py:make_env --policy my_agent.py:MyPolicy --steps 50
```

You immediately get: per-step ledger, budget enforcement, held-out scoring, and an `alert` record
instead of a corrupted ledger when your code raises. Details: [docs/EXTEND.en.md](docs/EXTEND.en.md).

## What you get for your own work (no "self-improvement" required)

| Use | For whom |
|---|---|
| Audit + budget + rollback around an existing loop | anyone scripting automation |
| A held-out evaluation harness for your own model | people training models |
| Experiment records with pre-registered acceptance criteria | researchers / students |
| A permission-request flow for agents (`ask → grant → revoke`) | teams letting agents act |

## Boundaries: commitments vs defaults

| Kind | Content | Changeable |
|---|---|---|
| **Commitment** | no consciousness claims, no "general intelligence" claims, every number reproducible | ❌ |
| **Default** | one 8×8 example world, CPU-only, offline | ✅ replace via `lab generic` |
| **Extension points** | environment, policy, evaluation, tasks | ✅ without touching core |

Three things are deliberately *not* configurable: the ledger, the budget gate, and rollback.
They constrain **how** work happens, not **what** you can build.

## Documentation

| Read | For |
|---|---|
| [docs/ONE-PAGE.en.md](docs/ONE-PAGE.en.md) | the whole thing on one page |
| [docs/WHAT-IS-IT.en.md](docs/WHAT-IS-IT.en.md) | plain-language introduction |
| [docs/EXTEND.en.md](docs/EXTEND.en.md) | plug in your environment / policy |
| [AGENT-RUNBOOK.en.md](AGENT-RUNBOOK.en.md) | if you are an AI agent executing this repo |
| [docs/MASTER.md](docs/MASTER.md) | full picture (Chinese) |
| [docs/experiments/](docs/experiments/) | 8 experiment records, 4 of them failures |
| [examples/](examples/README.md) | three runnable integrations (eval harness / model wrapper / budgeted fetch) |
| [docs/security-audit.md](docs/security-audit.md) | what it can and cannot touch on your machine |

## Status

`v0.18.0` · 108 tests · CI on Python 3.10–3.13 · MIT · zero third-party dependencies.

Translation status and how to add a language: [docs/i18n.md](docs/i18n.md).

## License

MIT. Security and governance rules are **merge conditions**, not legal terms.
