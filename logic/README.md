# 逻辑层

> 实现：`lab/state.py`（状态机 + 重放校验）、`lab/ledger.py`（因果链）
> 测试：`tests/test_lab.py::StateTests`、`::LedgerTests`

## 1. 状态机（已实现）

```
INIT ──► READY ──► RUNNING ──► REVIEWING ──► READY
          │           │            │
          │           ├──► ROLLING_BACK ──► READY
          │           │            └──────► FROZEN
          └───────────┴────────────────────► ARCHIVED
FROZEN（kill switch）：任何非归档状态都可被人工冻结；只能人工 `unfreeze --by <人>` 解冻
```

三条设计决定，都是被原方案的具体漏洞逼出来的：

1. **冻结可以从任何状态进入**。原稿只写了 `ROLLING_BACK → FROZEN`，意味着"跑得好好的
   时候发现异常"反而冻不住。kill switch 必须随时可用。
2. **评审通过回到 READY，不直接回 RUNNING**。否则系统可以自己接着跑下一轮——那就是
   "自启动"，属于我们明确不做的事。下一轮必须由人（或显式调度）发起。
3. **每次转换都落账本**。`{"from","to","actor","reason","ts"}` 五行，事后能回答
   "谁在什么时候因为什么把它冻结了"。

## 2. 重放校验（已实现）

`lab verify` 会从 INIT 重新走一遍 `state.json` 里的 history：任何一条与当时状态不符，
或者转换本身不合法，就报错。这能抓住最朴素的一种作弊——直接手改 `state.json`
把 `FROZEN` 改成 `READY`。

## 3. 因果追踪（已实现，靠账本）

不需要额外的 trace 系统：账本本身是链式的。

- 每条记录有 `seq`（严格递增）与 `prev_hash`（指向上一条）。
- 一次 run 的所有事件 `payload.run_id` 相同，`grep run-002` 就是这次 run 的完整时间线。
- 想知道"为什么回滚"，看该 run 里最后一条 `alert` 与它之前的 `budget` 事件。

## 4. 模块依赖（原则，Issue 0015 收尾）

```
clock ─┬─► budget ─► cli
       ├─► ledger ─► viz / report
       └─► state
policy ─► cli（只读扫描，不依赖运行时状态）
```

规则：

- 依赖单向，禁止循环。需要双向沟通时用账本事件解耦，不要互相 import。
- `policy.py` 不得 import `cli.py`（否则红线扫描会随 CLI 参数变化，失去可测性）。
- 新增模块必须在 PR 里更新本节这张图——这是唯一"文档必须跟代码同步"的硬要求。

## 5. 已知缺口

- 没有跨进程锁：两个 `lab run` 同时跑会互相踩 `state.json`（单人使用可接受，
  多用户场景见 Issue 0016）。
- 没有真正的 trace_id 传播（账本用 `run_id` 近似）。接入模型后需要补。
