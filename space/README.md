# 空间层

> 实现：`docker-compose.yml`（默认隔离）、`sandbox/Dockerfile`
> 未完成部分：Issue 0016（权限实测）

## 1. 资源布局

| 资源 | 位置 | 进 git | 备份 |
|---|---|---|---|
| 代码 | 仓库根 | ✅ | git |
| 运行产物（账本、状态、checkpoint、周报） | `state/` | ❌ | 需要时手动导出 |
| 仪表盘（生成物） | `viz/status.md` | ✅ | git（可重新生成） |
| 模型权重 | 仓库外，路径写进 `.env` | ❌ | 不备份，只记哈希 |
| 抓取的文献 | 只存引用+摘要 → `state/` | ❌ | 随 state |

规则：**`state/` 永远不进 git**。理由不是"脏"，是"账本一旦进 git，就会有人为了 diff 干净
去改写它"——那正是审计链最怕的事。

## 2. 权限边界

| 角色 | 可写 | 只读 | 禁止 |
|---|---|---|---|
| 主流程（`lab run`） | `state/` | 仓库代码 | 改 `lab/policy.py`、`lab/budget.py` 的判定 |
| 验证器（Issue 0005） | `state/validator/` | 运行产出 | 主流程目录 |
| 人类 | 全部 | 全部 | — |
| 容器内进程 | 仅 `/workspace/state` | `/workspace`（只读挂载） | 宿主文件系统 |

`lab/` 里的模块没有"运行时改自己"的能力：没有 `importlib.reload`、没有写 `.py` 的代码。
想改规则只能提 PR——这是故意的。

## 3. 数据流向

```
 输入(可选, 白名单) ──► run ──► 账本(state/ledger.jsonl)
                      │            ├──► viz/status.md
                      │            └──► state/reports/*.md
                      └──► checkpoint(state/checkpoints/*.json)
```

三条不变量（`verify` 会检查）：

1. 账本只追加，不改写；任何改写都会被哈希链发现。
2. checkpoint 必须带 `ledger_hash`，能指回账本某一条。
3. 预算用量只能从账本的 `budget` 事件推导，不允许有"第二个账本"。

## 4. 沙箱隔离（Docker，可选）

`docker-compose.yml` 的默认值：

- `read_only: true` + 只挂 `./state` → 容器不能改代码，改了也不生效。
- `cap_drop: ALL` + `no-new-privileges` → 没有提权路径。
- `network_mode: none` → 默认完全离线。
- `user: "1000:1000"` → 非 root。

要联网时必须**另起** `proxy` 服务（`profiles: ["online"]`），主容器仍然离线。
"在同一个容器里按需开网"是原方案的矛盾点，已改掉（见 `docs/gap-analysis.md` A5）。

## 5. 本机（无 Docker）怎么办

不需要 Docker 也能跑：`state/` 就是当前目录下的文件夹。此时"隔离"靠两点——
不联网（v0.1 没有网络代码）、不读凭证（`lab/policy.py` 扫描私钥/`.ssh` 路径）。
这比容器弱，但对"只在自己电脑上跑 20 步"的场景够用，且门槛低得多。
