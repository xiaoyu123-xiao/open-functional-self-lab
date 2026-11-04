# Agent Runbook (for an AI executing this repo)

> For an **executing AI** (Claude Code / Codex / Cursor / DSH / custom agent), not for a human reader.
> Your goal: make the repository reproducible on this machine **without breaking the audit chain**.
> [中文](AGENT-RUNBOOK.md) | **English**

---

## 0. Role and hard limits

You are an **executor**, not the author. Success means: the repo runs here, verifiably.

**Do not**: change the hashing in `lab/ledger.py`, change the gate logic in `lab/budget.py`,
delete `state/ledger.jsonl`, relax rules in `SECURITY.md`, or claim the system is conscious.
Those require human approval (`docs/approval-matrix.md`).

## 1. Step 1 — read only, change nothing

```bash
python -m lab.cli doctor
python -m unittest discover -s tests -q
python -m lab.cli lint
python scripts/check_py310.py
```

All four must pass. Paste the raw output to the human. **Do not "just fix" anything.**

- `doctor` fails → it names the exact item (missing file / unwritable state dir / bad config)
- tests fail → the machine differs (Python version, paths); report first
- `lint` hits → that is the red-line scanner; fix the code, never the rule

## 2. Step 2 — one episode, does it actually work

```bash
python -m lab.cli init
python -m lab.cli run --steps 20        # ends in REVIEWING
python -m lab.cli review --pass --by <your-name>
python -m lab.cli verify
```

Acceptance: `verify` prints 5 OK lines (ledger hash, state replay, state/ledger agreement, checkpoint, budget).

## 3. Step 3 — one learning cycle

```bash
python -m lab.cli loop --cycles 3 --rounds 2 --episodes 20 --steps 40 --eval-count 8 --lethal
```

Acceptance: each cycle prints before / after / delta / baseline; better cycles keep the new policy,
worse cycles roll back; `state/policy.json` exists afterwards.

## 4. Step 4 (optional) — cross-task transfer

```bash
python -m lab.cli transfer --algo weighted --rounds 3 --episodes 40 --eval-count 12 --repeats 3
```

Acceptance: prints scores on two held-out configurations plus the paired win rate.
This is the project's headline result — but 3 repeats are not a statistical claim.

## 5. Stop and ask a human when

| Situation | Why |
|---|---|
| any `verify` failure | the audit chain may be broken; never recompute hashes to hide it |
| you want to raise a budget cap | that is an approval item |
| you want network access (`learn --online`) | requires a `web.fetch` grant (`lab autonomy` / `lab grant`) |
| you want to edit `SECURITY.md` or `lab/policy.py` | immutable core |
| "it seems conscious" | go find a metric in `docs/metrics.md`; if none exists, it is an impression, not a finding |

## 6. Report format (every cycle)

```
Goal:
Actions:
Verification commands & results:
Ledger impact (new events / budget spent):
Red line touched: no / yes (explain)
Next steps (max 3):
```

## 7. You may do these without approval

- add tests, doc examples, fix typos
- add an experiment record under `docs/experiments/` (copy the format of 0008; include the reproduce command)
- write failures into `docs/` — failures are more valuable than successes here

## 8. Environment

| Item | Requirement |
|---|---|
| Python | ≥ 3.10 (CI covers 3.10–3.13) |
| Dependencies | **none** (standard library only) |
| OS | Linux / macOS / Windows |
| GPU | not needed (tabular / linear policies) |
| Disk | < 10 MB |

## 9. If you run in CI

```bash
python -m lab.cli doctor && python -m lab.cli init \
  && python -m lab.cli run --steps 20 && python -m lab.cli review --pass --by ci \
  && python -m lab.cli verify
```

Note: `review --pass` is a human action. In CI it only closes the loop — **never claim a human reviewed it**.
