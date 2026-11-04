# What it actually does (for people who don't code)

> Two minutes: read §1 and §3. [中文](WHAT-IS-IT.md) | **English**

---

## 1. One sentence

It is a small program that **runs experiments on itself and keeps an auditable record of every step**.

Not a chatbot. Not an AI assistant. Not a language model. No GPU, no network, no API key.

## 2. What it is doing, concretely

Picture an 8×8 room:

```
. . . . . . . .      F = food
. F . . # . . .      # = wall
. . # . . . F .      H = hazard (two hits and it dies)
. . . H . . . .
. . . . . F . .
```

Each step it may move up, down, left, right, or rest. A policy must collect food and avoid hazards
within 60 steps. **It learns from scratch** (tabular Q-learning), is trained on one batch of maps,
and is scored on a **different, unseen** batch. Every score goes into a ledger.

## 3. How it differs from most "agent" projects

**It documents what it got wrong more carefully than what it got right.**

`docs/experiments/` holds 8 records; 4 of them are failures:

| Experiment | Outcome |
|---|---|
| 0001 | it learns, but loses to a hand-written rule |
| 0002 | adding features made it worse (state explosion) |
| 0003 | why it lost: the task was too friendly to the rule |
| 0006 | multi-task transfer failed (interference) |
| 0008 | after changing the criterion, 5 paired runs won 5/5 |

Each record ends with a one-line command you can run to reproduce or refute it.
**That is the point of the project.**

## 4. What you get

1. **A working lab**: `lab run` / `lab loop` / `lab eval`, results in seconds
2. **An auditable record**: hash-chained ledger; budget overruns are refused, not warned
3. **Honest experiment notes**: failures included, criteria registered before running

## 5. Boundaries: commitments ≠ limitations

| Kind | Content |
|---|---|
| **Commitment** | no consciousness claims, no "general intelligence" claims; every number reproducible. Not negotiable |
| **Default** | one 8×8 example world, CPU-only, offline. **All replaceable** |
| **Extension points** | environment, policy, evaluation, tasks |

**Do not read it as "a grid toy"**: `lab generic` accepts any environment with `reset`/`step`
and any policy with `act(observation)`, and gives you the ledger, the budget gate, rollback and
held-out scoring. See [EXTEND.en.md](EXTEND.en.md); the example is `examples/lineworld.py` (a number line, 20 lines).

## 6. Three minutes to run

```bash
git clone https://github.com/xiaoyu123-xiao/open-functional-self-lab.git
cd open-functional-self-lab
python -m lab.cli doctor          # expect "all checks passed"
python -m lab.cli loop --cycles 3 --lethal
```

The third command prints four lines: score before, score after, kept or rolled back, and how it
compares with the hand-written baseline.

## 7. If you only want the conclusion

With lethal hazards (`--lethal`), on **unseen maps**:

| Hazards | Hand-written rule | Learned policy |
|---|---|---|
| 8 | −1.758 | **+1.597** |
| 10 | −2.340 | **+0.573** |

**Do not extrapolate**: this holds for one 8×8 map family with varying hazard density.
