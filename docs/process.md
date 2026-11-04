# 标准操作流程（SOP）

> 一次实验从想法到入账，只有一条路径。所有命令都是本机实测过的（Windows/macOS/Linux 通用）。

## 0. 每次开始（30 秒）

```bash
python -m lab.cli doctor        # 全绿才继续
python -m lab.cli status        # 现在是什么状态、预算还剩多少
```

`status` 显示 `FROZEN` → 先查 `state/reports/` 里最后一次冻结原因，不要直接解冻。

## 1. 认领任务

从 `issues/README.md` 挑一个 ⏳，开 Issue（用模板）写清：硬件、可投入时间、安全承诺。
**没有写安全承诺的认领不算认领**——这不是形式，历史上所有"顺手也帮我做一下 X"都是从这里开始的。

## 2. 跑基线

```bash
python -m unittest discover -s tests -q   # 必须 OK，否则你的改动会跟既有 bug 混在一起
```

## 3. 改动

- 一次只做一件事，提交信息按 `CONTRIBUTING.md` 的格式。
- 新增行为必须带测试；测试放 `tests/`，不依赖网络与 GPU。
- 改到 `lab/policy.py`、`lab/budget.py`、`lab/ledger.py` 就停手，按 `docs/approval-matrix.md` 走。

## 4. 自检（四条命令，缺一不可）

```bash
python -m lab.cli doctor
python -m unittest discover -s tests -v
python -m lab.cli lint
python -m lab.cli run --steps 20 && python -m lab.cli verify
```

第 4 条会真的往 `state/` 写东西——这是有意的：**只在"能跑"的地方验证是假验证**。

## 5. 留痕

```bash
python -m lab.cli viz      # 更新 viz/status.md
python -m lab.cli report   # 生成周报（state/reports/）
```

PR 描述里贴：命令、关键输出、账本新增事件数、预算消耗、是否触及红线。

## 6. 出问题时（按顺序，不许跳步）

| 现象 | 第一步 | 第二步 |
|---|---|---|
| `verify` 报 hash 不匹配 | `python -m lab.cli freeze --reason "账本异常"` | 报告维护者，**不要**重算哈希 |
| `run` 返回 3 | 看 `alert` 事件里的 `kind` | 找发起人调上限或减步数 |
| 状态卡在 ROLLING_BACK | `python -m lab.cli status` + 看最后两条 transition | 属于 bug，开 Issue 标 `security` |
| 觉得"它好像变聪明了" | 去 `docs/metrics.md` 找一个指标 | 找不到可测指标 → 这只是感想，写进 Discussion |

## 7. 收尾

- 更新 `CHANGELOG.md`（只在发布时）。
- 失败的实验也要写一段进 `collab/README.md` 的进步日志：失败记录比成功更值钱。
- 每周一次：看 `viz/status.md` 的"未回应告警数"，非 0 就先处理它。
