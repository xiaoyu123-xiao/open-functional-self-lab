# 预算与成本

> 实现：`lab/budget.py`　配置：`lab.config.json`　回归：`scripts/budget_regression.py`
> 这是本项目与旧方案差别最大的一处：**预算不是表格，是会抛异常的闸门。**

## 1. 四类上限

| 类别 | 默认 | 窗口 | 计量点 |
|---|---|---|---|
| `steps_per_run` | 1000 | 每次 run | 每步 +1 |
| `wall_clock_hours_per_run` | 2 | 每次 run | 每步 +0.01（占位） |
| `search_requests_per_day` | 200 | UTC 日 | 每次检索请求 +1 |
| `gpu_hours_per_month` | 10 | UTC 月 | 训练/推理 +实际小时 |

窗口口径写死在代码里（`WINDOWS` 字典），不接受运行时传入，避免"临时改窗口"这种操作。

## 2. 超限时会发生什么（不许"警告后继续"）

```
$ python -m lab.cli run --steps 5000
启动 run-001：5000 步，seed=20261104
预算闸门拦截：steps_per_run 超限：已用 0 + 本次 5000 > 上限 1000（窗口=run）。
已回滚，执行 0 步后停止。
$ echo $?
3
```

三件事同时发生：①抛 `BudgetExceeded`；②状态走 `RUNNING → ROLLING_BACK → READY`；
③账本写 `alert`（高优先级）。退出码 `3` 是契约，CI 里有脚本守着它不被改成 0。

## 3. 怎么改上限

改 `lab.config.json` 的 `budget` 字段，**并经 `docs/approval-matrix.md` 的"调整预算上限"**：
发起人 + 1 名维护者。单人改上限等于没有上限。

```json
{ "budget": { "steps_per_run": 2000 } }
```

只写要改的键即可，其余沿用默认（`lab/cli.py::DEFAULT_CONFIG`）。

## 4. 账本里的成本记录

每次扣费写一条：

```json
{"seq": 12, "ts": "2026-11-04T04:31:12Z", "event": "budget", "actor": "system",
 "payload": {"kind": "steps_per_run", "amount": 1.0, "run_id": "run-001"}}
```

`lab verify` 会重算"按窗口求和 ≤ 上限"，所以**手改账本少记一笔**会被发现（哈希链断），
**少写一条**也会被发现（下一条的 `prev_hash` 对不上）。

## 5. 周报里的成本段

`python -m lab.cli report` 会输出本周各 `kind` 的累计用量。周报不自动折算成钱：
单价因地区/供应商差异太大，写死一个汇率只会误导。要算钱自己乘。

## 6. 明确不做

- 不做"超限后自动续费/自动扩容"。超限就该停下并找人。
- 不做跨机器共享预算池（单机单人场景，跨机器一致性成本高于收益）。
- 不用预算去限制"想法"，只限制**执行**。写文档、提假设不花钱。
