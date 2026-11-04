# 时间层

> 实现：`lab/clock.py`　测试：`tests/test_lab.py::ClockTests`

第 #50 轮你专门要求"别总忘时间"。这件事在代码里有四个具体含义，缺一个都会出错：

## 1. 只用 UTC，禁止 naive 时间

```python
to_iso(datetime.now())          # ❌ ValueError：naive datetime 不允许进入记录
to_iso(datetime.now(timezone.utc))  # ✅
```

为什么不能"允许但警告"：naive 时间一旦进账本，哈希链在不同时区的机器上就不一致，
`verify` 会误报"账本被改"。宁可在入口处崩，也不要在三个月后查不出原因。

## 2. 输出格式固定

`YYYY-MM-DDTHH:MM:SSZ`，秒级。不带微秒：微秒会让同一动作在两台机器上产生不同哈希，
而秒级对本项目的时间分辨率已经足够（步长以分钟计）。

## 3. 耗时用单调计数，不用时钟差

```python
start = clock.monotonic_ns()
... 
elapsed_seconds(start, clock.monotonic_ns())   # ✅ 系统时钟回拨也不会出现负数
now - start                                     # ❌ NTP 校正后可能是负的
```

长跑实验（Issue 0006 的 1000 步）几乎一定会遇到 NTP 回拨。

## 4. 可注入的 FakeClock

```python
clock = FakeClock("2026-01-01T00:00:00Z")
clock.advance(90)              # now_iso() == 2026-01-01T00:01:30Z
```

同一条命令 `python -m lab.cli --fake-now 2026-01-01T00:00:00Z run --steps 20`
在任何机器上产出**完全相同**的账本哈希——这是"可复现"的最低要求。

## 5. 调度与 DST（尚未实现，属 Issue 0014）

规则先定下来，实现按此验收：

- 调度一律按 UTC 判定触发，本地时区只用于展示。
- 夏令时"不存在的本地时刻"（如 02:30 跳过）：映射到该日 UTC 同一时刻，**只跑一次**。
- 夏令时"重复的本地时刻"（如 02:30 出现两次）：只跑**第一次**，第二次不跑。
- 错过触发（机器休眠/停机）：启动时补跑**最近一次**，更早的不补，只记一条 `missed` 事件。
- 每个任务必须有 `last_run_at`，据此幂等；没有幂等键的定时任务不允许合并。

## 6. 超时

- `wall_clock_hours_per_run` 是硬上限，由 `lab/budget.py` 计量；超了就走回滚。
- 单步超时在接入真实模型（Issue 0003）后再定，届时必须写进 `lab.config.json`。

## 7. 衰减与 TTL（尚未实现，属 Issue 0014）

`confidence(t) = confidence_0 × exp(−λ·Δt)`，λ 按学科配置（数学 ≈ 0，生物医学中等，
快速变化领域较大）。衰减到阈值只标"待复审"，**不删除**；连续两次复审失败标"争议"。
