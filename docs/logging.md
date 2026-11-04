# 日志与审计

> 实现：`lab/ledger.py`　校验：`python -m lab.cli verify`

## 1. 为什么不是普通日志

普通 `app.log` 有三个问题：可以改、可以删、看不出"少了一条"。而这个项目的历史里，
最需要的恰恰是"证明某事发生过 / 没发生过"。所以用**只追加 + 哈希链**：

```json
{"seq": 7, "ts": "2026-11-04T04:31:12Z", "event": "step", "actor": "agent",
 "payload": {"step": 7, "action": "rest", "prediction_error": 0.4712},
 "prev_hash": "9f2c…", "hash": "a41b…"}
```

- `hash` = 本条（去掉 `hash` 字段）规范 JSON 的 sha256。
- `prev_hash` = 上一条的 `hash`；首条为 64 个 `0`。
- 改任何一个字节 → 该条 hash 不匹配 → `verify` 报第几条；删一条 → 下一条 `prev_hash` 断链。

## 2. 事件类型（v0.1）

| event | 何时 | 关键字段 |
|---|---|---|
| `init` | 首次 `lab init` | version, seed, caps |
| `run_start` | 每次 `run` | run_id, steps, seed |
| `step` | 每步 | step, action, prediction_error |
| `budget` | 每次扣费 | kind, amount, run_id |
| `transition` | 状态变化 | from, to, actor, reason |
| `checkpoint` | run 结束 | run_id, path, ledger_hash |
| `alert` | 异常 | level, kind, detail |
| `ack` | 人回应告警 | event_id, action |

新增事件类型要在 PR 里更新本表——否则 `report` 的统计会漏。

## 3. 字段规范

- `ts`：UTC ISO 8601 秒级，来自 `lab/clock.py`。**不允许** naive 时间（会抛错）。
- `actor`：`agent` / `system` / `human` / `human:<名字>`。谁解冻的必须写清楚。
- `payload`：只放结构化数据；不放长文本（长文本进 `state/reports/`，账本只存路径）。
- 不记录：密钥、token、个人数据、完整网页正文。

## 4. 脱敏与删除（redaction）

需要删除某条内容时，**不删账本记录**（那会断链），而是追加：

```json
{"event": "redaction", "payload": {"target_seq": 42, "reason": "含个人数据"}}
```

`verify` 允许 `redaction` 存在；`report` 统计时跳过被 redact 的条目。
这样既满足"可删除"，又保住"曾经存在过"的证明。

## 5. 保留策略

| 数据 | 保留 | 位置 |
|---|---|---|
| 账本 | 永久（体积极小，每步约 300 字节） | `state/ledger.jsonl` |
| checkpoint | 最近 30 个，更早的归档为 tar | `state/checkpoints/` |
| 周报 | 永久（人写的部分有长期价值） | `state/reports/` |
| 通知日志 | 90 天 | `state/notify.jsonl` |

`state/` 不进 git。要长期保存就自己备份——**不要**为了让 CI 能看待就把账本提交进仓库。

## 6. 排查顺序（出事时照这个走）

1. `python -m lab.cli verify` —— 先确认账本没坏。
2. `python -m lab.cli status` —— 现在什么状态、预算还剩多少。
3. 看该 run 的 `alert` 事件：`grep -n '"run_id":"run-002"' state/ledger.jsonl`。
4. 看 `state/reports/` 最近一期周报的"风险与待办"。
5. 都不行 → `freeze`，再开 Issue 附上账本片段（**不要**附整份账本）。
