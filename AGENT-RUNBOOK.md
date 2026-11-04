# 另一个 AI 接手时该怎么做（Agent Runbook）

> 这份文档不是给人看的，是给**另一个执行型 AI**（Claude Code / Codex / Cursor / DSH / 自建 agent）看的。
> 目标：让它拿到仓库后知道**先做什么、验收标准是什么、什么情况必须停**。

---

## 0. 你的身份与边界

你是"执行者"，不是作者。成功标准只有一条：
**让仓库在这台机器上可复现地跑通，并且不破坏审计链。**

**不要做**：改 `lab/ledger.py` 的哈希算法、改 `lab/budget.py` 的闸门判定、删 `state/ledger.jsonl`、
把 `SECURITY.md` 的红线改松、宣称系统有意识。这些需要人类批准（`docs/approval-matrix.md`）。

## 1. 第一步：只读，不改任何文件

```bash
python -m lab.cli doctor
python -m unittest discover -s tests -q
python -m lab.cli lint
python scripts/check_py310.py
```

四条都要过。把输出原样贴给人类，**不要"顺手修"**。

- `doctor` 失败 → 看它指出的具体项（缺文件 / 状态目录不可写 / 配置不合法）
- 测试失败 → 说明机器环境不同（Python 版本、路径），先报告再动手
- `lint` 命中 → 这是红线扫描命中，**不要改规则，改代码**

## 2. 第二步：跑一轮，看它是否真的工作

```bash
python -m lab.cli init
python -m lab.cli run --steps 20       # 结束会停在 REVIEWING
python -m lab.cli review --pass --by <你的名字>
python -m lab.cli verify
```

验收：`verify` 输出 5 行 OK（账本哈希、状态机重放、状态与账本一致、checkpoint、预算）。

## 3. 第三步：跑一次"有学习"的循环

```bash
python -m lab.cli loop --cycles 3 --rounds 2 --episodes 20 --steps 40 --eval-count 8 --lethal
```

验收：
- 每轮都打印"训练前/训练后/变化/基线"
- 有变好就"保留新策略"，变差就"回滚"
- `state/policy.json` 存在

## 4. 第四步（可选）：跨任务迁移

```bash
python -m lab.cli transfer --algo weighted --rounds 3 --episodes 40 --eval-count 12 --repeats 3
```

验收：打印两个留出配置的分数 + 配对胜率。**这是这个仓库最核心的结论**，但只跑 3 组不能下统计结论。

## 5. 什么时候必须停下来问人

| 情况 | 为什么 |
|---|---|
| 任何一步 `verify` 失败 | 审计链可能断了，不能"重算哈希"掩盖 |
| 想调高 `lab.config.json` 的预算上限 | 属于审批事项 |
| 想联网（`learn --online`） | 需要 `web.fetch` 授权（`lab autonomy` 或 `lab grant`） |
| 想改 `SECURITY.md` / `lab/policy.py` | 属于不可变核 |
| 发现"它好像有意识了" | 去 `docs/metrics.md` 找指标；找不到就是感想，不要写进报告 |

## 6. 输出格式（每轮）

```
目标：
动作：
验证命令与结果：
账本影响（新增事件数 / 预算消耗）：
是否触及红线：否 / 是（说明）
下一步建议（≤3 条）：
```

## 7. 你可以自己做的改进（不需批准）

- 补测试、补文档示例、修错别字
- 在 `docs/experiments/` 增加一次实验记录（照抄 0008 的格式，必须含"复算命令"）
- 把失败写进 `docs/`（失败记录比成功更被需要）

## 8. 环境要求

| 项 | 要求 |
|---|---|
| Python | ≥ 3.10（CI 覆盖 3.10–3.13） |
| 依赖 | **零**（只用标准库） |
| 操作系统 | Linux / macOS / Windows 都可以 |
| 显卡 | 不需要（当前策略是表格/线性） |
| 磁盘 | < 10 MB |

## 9. 如果你跑在容器/CI 里

```bash
python -m lab.cli doctor && python -m lab.cli init \
  && python -m lab.cli run --steps 20 && python -m lab.cli review --pass --by ci \
  && python -m lab.cli verify
```

注意：`review --pass` 是"人"的动作，在 CI 里只是为了让流程闭环，**不要因此假装有人评审过**。
