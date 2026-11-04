# 安全体检：这个东西能不能碰到我的电脑？

> 结论先给：**默认情况下不能。** 它不联网、不执行系统命令、只写自己目录下的 `state/`。
> 只有两个口子能"出去"，而且都必须由你显式触发。下面是证据与自查方法。

---

## 一、它能做什么（全部清单）

| 能力 | 代码位置 | 默认 | 触发条件 |
|---|---|---|---|
| 访问网络 | `lab/web.py:96-97`（唯一的 `urlopen`） | **关闭** | 三条同时成立：`learn --online` + 域名在 `ALLOWLIST` + 已授予 `web.fetch` 权限 |
| 执行你自己的 Python 文件 | `lab/core.py:51,55`（`exec_module`） | 不触发 | `lab generic --env 某文件.py:x` |
| 写文件 | `lab/*.py` 共 17 处 | 开启 | 都写在 `state/` 下（账本、状态、知识、通知、权限、策略、checkpoint、报告、`viz/status.md`） |
| 读文件 | 只读自己写过的那些 + `docs/catalog/*.json` | 开启 | 不读家目录、不读凭证 |

## 二、它**不能**做什么（也是查过的）

```bash
# 这三条在仓库里都搜不到（除了规则字符串本身）
grep -rn "subprocess\|os.system\|popen\|shell=True" lab/      # 空
grep -rn "\beval(\|\bexec(" lab/                              # 空
grep -rn "expanduser\|Path.home\|\.ssh\|\.aws/credentials" lab/  # 空
```

- 不能开子进程、不能执行 shell 命令
- 不能读 `~/.ssh`、`~/.aws`、浏览器密码库（`lab/policy.py` 里的 `.ssh` 只是**扫描别人代码**的规则）
- 不能修改仓库以外的文件（除非你用 `--root` 指到别处）
- 不能自己联网（除非你给权限并显式 `--online`）

## 三、两个口子的详细说明

### 口子 A：`learn --online`

```bash
python -m lab.cli learn --online --url https://export.arxiv.org/api/query
# 没有权限时会直接拒绝：
#   还没有联网权限。先申请：
#     python -m lab.cli ask --resource web.fetch --reason "..."
```

**三道闸门**：域名白名单（`lab/web.py::ALLOWLIST`，5 个学术源）→ 权限授予（24 小时或 `autonomy full`）→ 预算扣费。

即使三道全过，它也只做一件事：**取回标题 + 摘要（≤400 字）+ URL**，不存全文、不执行返回内容。

### 口子 B：`lab generic --env 文件.py:x`

**这条要特别小心，因为它等于 `python 那个文件.py`。**

- 你跑自己的文件 → 没问题
- 你跑**别人给你的**文件 → 等于运行他的任意代码，包括删文件、联网、读凭证

所以规则只有一条：**只对你信任的 `.py` 使用 `--env` / `--policy`。**
这跟"不要运行陌生脚本"是同一条规矩，不是这个仓库能替你挡的。

## 四、怎么自己验证（三条命令，30 秒）

```bash
# 1. 断网也能跑完整套
python -m lab.cli doctor && python -m lab.cli run --steps 20

# 2. 搜索所有可能"出去"的调用
grep -rn "urlopen\|socket\|subprocess" lab/

# 3. 看它到底写了哪些文件（跑完后对比目录）
ls -R state/
```

第 2 条应该只返回 `lab/web.py` 里那一行；第 3 条应该全是 `state/` 下的东西。

## 五、威胁模型（谁需要担心什么）

| 场景 | 风险 | 缓解 |
|---|---|---|
| 你自己 clone 官方仓库并运行 | 极低（纯标准库、无网络、无系统命令） | 不用处理 |
| 你运行**别人 fork 的版本** | 风险来自那份代码，不来自本仓库 | 先 `git diff` 看改了什么；或用容器跑 |
| 你把 `--env` 指向陌生 `.py` | 等价于运行陌生脚本 | 不要这么做 |
| 你把 `state/` 放在共享目录 | 别人能读你的账本 | 账本不含凭证，但含实验记录 |
| 你给 `autonomy --level full --days 365` | 长期授权，无人复核 | 用 `--revoke`；或用 `supervised` |

## 六、加固建议（按成本从低到高）

1. **不联网也能用**：默认就是离线，`lab run` / `loop` / `transfer` 都不需要网络
2. **只给短期授权**：`autonomy --level full --days 7`，到期自动失效
3. **用独立目录**：`--root ./sandbox-a`，不碰你的其他文件
4. **容器里跑**：`deploy/Dockerfile`，默认无网络、只挂 `state/`
5. **`--env` 只用自己写的文件**

## 七、一条诚实的提醒

**"默认安全"不等于"绝对安全"**：这个仓库没有做沙箱、没有做权限隔离、没有防恶意依赖
（因为它零依赖）。它的安全边界是"**只做你让它做的事，并且全部记账**"——
如果你让它做危险的事（指向危险的文件、给出长期联网权限），它不会拦你。

想让它拦你，就把 `supervised` 模式开着，每次都要你批。
