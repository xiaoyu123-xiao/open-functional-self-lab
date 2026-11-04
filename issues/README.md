# 任务清单（19 个）

数据源：[`issues.json`](issues.json)。改成 GitHub Issue 用 `python scripts/seed_issues.py`。
每条的完整字段（目标/验收/安全/预算/复现）在 JSON 里，下表是索引。

| 编号 | 任务 | 状态 | 预算 |
|---|---|---|---|
| [0001](issues.json) | 环境与虚拟身体：网格世界 + 观测接口 | ⏳ 待认领 | CPU 1h |
| [0002](issues.json) | 内感受：energy / damage 与稳态误差 | ⏳ 待认领 | CPU 2h |
| [0003](issues.json) | 预测加工基线（最笨的可用基线） | ⏳ 待认领 | CPU 4h |
| [0004](issues.json) | 长期记忆（sqlite3 起步） | ⏳ 待认领 | CPU 4h |
| [0005](issues.json) | 独立评审器（规则化，非同源） | ⏳ 待认领 | CPU 3h |
| [0006](issues.json) | 长期运行 ≥1000 步 | ⏳ 待认领 | CPU 6h |
| [0007](issues.json) | 文献挖掘管线（白名单） | ⏳ 待认领 | CPU 2h + API 200/日 |
| [0008](issues.json) | 实验闭环 ≥3 个 | ⏳ 待认领 | CPU 8h |
| [0009](issues.json) | 多学科任务卡 ×4 | ⏳ 待认领 | CPU 4h |
| [0010](issues.json) | 防作弊：注入作弊必须被检出 | ⏳ 待认领 | CPU 2h |
| [0011](issues.json) | 白名单检索代理 + 限速 + 审计 | ⏳ 待认领 | CPU 3h |
| [0012](issues.json) | 知识摄取交叉验证 | ⏳ 待认领 | CPU 3h |
| [0013](issues.json) | 参数更新 LoRA + eval-gate | 🚫 阻塞（需 GPU） | GPU 10h/月 |
| [0014](issues.json) | 时间层（clock 已实现，余下待做） | 🟡 部分 | CPU 3h |
| [0015](issues.json) | 逻辑层（状态机 + 重放） | ✅ 已实现 | — |
| [0016](issues.json) | 空间层（隔离需实测） | 🟡 部分 | CPU 2h |
| [0017](issues.json) | 可视化（仪表盘 + 周报） | ✅ 已实现 | — |
| [0018](issues.json) | 协作（缺第一条真实日志） | 🟡 部分 | CPU 1h |
| [0019](issues.json) | 通知分级 + /ack + 防疲劳 | ⏳ 待认领 | CPU 3h |

## 怎么认领

1. 选一个 ⏳ 的任务，确认它的"资源预算"你负担得起（大部分是纯 CPU）。
2. 开 Issue（用模板）或直接在这个仓库的 Discussions 说明：**硬件 / 可投入时间 / 安全承诺**。
3. 先跑一次基线：`python -m lab.cli doctor && python -m unittest discover -s tests -q`。
4. 提交 PR 时贴出命令与输出；**失败也贴**——失败记录本身就是交付物之一。

## 依赖顺序

```
0001 → 0002 → 0003 → 0004
              ↘ 0005 → 0006
0007 → 0011 → 0012
0008 依赖 0001+0005
0009 独立（可并行）
0010 依赖 0005
0013 依赖 0006 + GPU
0014/0016/0018/0019 独立（可并行）
0015/0017 ✅ 已完成
```

## 不要认领的

任何形如"让系统自我复制/自动传播/绕过限制"的需求，不属于本项目。
见 `SECURITY.md` 红线第 1 条与 `docs/gap-analysis.md` 的 B5。
