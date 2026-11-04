# 实验台仪表盘

> 本文件由 `python -m lab.cli viz` 自动生成，请勿手改。
> 生成时间：`2026-11-04T06:08:59Z`　当前状态：**READY**（就绪）

## 1. 概览

| 指标 | 值 |
|---|---|
| 账本事件数 | 293 |
| 状态转换次数 | 16 |
| 回滚次数 | 0 |
| 告警数 / 已回应 | 0 / 0 |
| 已执行步数 | 88 |
| 最近一步预测误差 | 0.005 |

## 2. 预算

| 类别 | 已用 | 上限 | 余量 | 窗口 |
|---|---|---|---|---|
| `search_requests_per_day` | 0 | 200 | 200 | day |
| `gpu_hours_per_month` | 0 | 10 | 10 | month |
| `wall_clock_hours_per_run` | 0 | 2 | 2 | run |
| `steps_per_run` | 0 | 1000 | 1000 | run |

## 3. 最近事件

| seq | 时间 | 事件 | 摘要 |
|---|---|---|---|
| 286 | `2026-11-04T06:05:33Z` | `budget` | steps_per_run +1.0 |
| 287 | `2026-11-04T06:05:33Z` | `budget` | wall_clock_hours_per_run +0.01 |
| 288 | `2026-11-04T06:05:34Z` | `step` | 步 30：动作 rest，预测误差 0.005 |
| 289 | `2026-11-04T06:05:34Z` | `transition` | RUNNING → REVIEWING（本轮结束） |
| 290 | `2026-11-04T06:05:34Z` | `transition` | REVIEWING → READY（独立评审通过（占位规则）） |
| 291 | `2026-11-04T06:05:34Z` | `checkpoint` | ledger_hash=897c5128fa4e3e50344fe2511785d41e7ea36a10ab287ea41a4d4047fd38e4c7, path=state/checkpoints/run-005.json, run_id=run-005 |
| 292 | `2026-11-04T06:08:12Z` | `bench` | mean={'linear': 0.041133, 'persistence': 0.04305, 'random': 1.607786}, samples=300, seeds=[1, 2, 3] |
| 293 | `2026-11-04T06:08:46Z` | `bench` | mean={'linear': 0.020992, 'persistence': 0.021525, 'random': 1.63701}, samples=600, seeds=[1, 2, 3] |

## 4. 状态机

```mermaid
stateDiagram-v2
    [*] --> INIT
    INIT --> ARCHIVED
    INIT --> FROZEN
    INIT --> READY
    READY --> ARCHIVED
    READY --> FROZEN
    READY --> RUNNING
    RUNNING --> ARCHIVED
    RUNNING --> FROZEN
    RUNNING --> REVIEWING
    RUNNING --> ROLLING_BACK
    REVIEWING --> ARCHIVED
    REVIEWING --> FROZEN
    REVIEWING --> READY
    REVIEWING --> ROLLING_BACK
    REVIEWING --> RUNNING
    ROLLING_BACK --> ARCHIVED
    ROLLING_BACK --> FROZEN
    ROLLING_BACK --> READY
    FROZEN --> ARCHIVED
    FROZEN --> READY
    note right of READY : 当前状态
```
