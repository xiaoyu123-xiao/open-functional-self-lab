# 问题清单：从对话第 27 轮往后，原方案里会出事的地方

> 依据：分享对话 `#27`（脑机接口）到 `#67`（"你不能太绝对，要折中"）这一段，
> 共 41 轮。原稿指对话里的"Open Functional Self Lab 最终整合版"（#56 那条）。
> 每条给：**现象 → 为什么没被想到 → 改法落在哪个文件 → 严重度**。
>
> 严重度：🔴 会让 clone 下来就跑不起来 / 出事；🟠 半年后会烂尾；🟡 表述层隐患。

---

## A. 🔴 发布阻塞：照着原稿建仓库，第一条命令就会红

### A1. Docker 镜像指向一个不存在的模块

原稿 `sandbox/Dockerfile` 最后一行是 `CMD ["python", "-m", "lab.main"]`，但整棵树里
**没有 `lab/` 目录**（只有 `sandbox/healthcheck.py`）。`docker compose up` 会得到
`No module named lab`，容器立刻退出。

- 改法：所有入口统一为 `python -m lab.cli`，且 `lab/` 真的存在（本仓库 8 个模块）。
- 落点：`sandbox/Dockerfile`、`docker-compose.yml`、`lab/cli.py`。

### A2. `requirements.txt` 里有装不上的包，还混着不存在的版本号

原稿写 `pyaif-toolkit>=0.1.1`、`soul-agent>=0.1.4`、`chromadb==1.5.9`。
前两个在 PyPI 上找不到对应的可用发行版，第三个版本号不存在。`pip install -r` 第一步就失败，
而 README 的第 2 步正是这条命令。

- 改法：核心 **零依赖**（只用标准库）；确实需要的放 `optional-dependencies`
  （`gymnasium`、`chromadb>=0.4`），并在 `sandbox/requirements.txt` 里注明移除了什么、为什么。
- 落点：`pyproject.toml`、`sandbox/requirements.txt`、`docs/tools.md`。

### A3. `torch` 当必需项 + 文档写"Python ≥3.10，推荐 3.12"

用户实际用的是 3.13。`torch` 没有对应 wheel，`pip install` 直接失败。原稿没提这一条，
因为"作者机器上装好了"。

- 改法：核心不装 torch；CI 在 3.10/3.11/3.12/3.13 四档都跑一遍。
- 落点：`.github/workflows/ci.yml`、`docs/tools.md`。

### A4. 没有 `LICENSE` 正文、没有 `pyproject.toml`、没有测试和 CI

- 树里列了 `LICENSE`，正文只在 README 写了一句"MIT"。GitHub 会显示"无许可证"，
  法律上别人**不能**用你的代码。而原稿的目标恰恰是"让大家都来贡献"。
- 没有打包元数据 → `pip install -e .` 报错，只能靠 `sys.path` 注入。
- 没有任何测试/CI → push 之后没人知道还能不能跑。

- 改法：补 MIT 全文；补 `pyproject.toml`（`[project.scripts] ofsl`）；补 27 个 unittest
  + 四档矩阵 CI + 预算闸门回归脚本。
- 落点：`LICENSE`、`pyproject.toml`、`tests/test_lab.py`、`scripts/budget_regression.py`。

### A5. `docker-compose.yml` 在没装 nvidia 工具链的机器上直接报错

```yaml
deploy:
  resources:
    reservations:
      devices: [{driver: nvidia, count: 1, capabilities: [gpu]}]
```

这段在没有 NVIDIA Container Toolkit 的机器上会让 `docker compose up` 报
`could not select device driver "" with capabilities: [[gpu]]`。
而且同一文件里 `network_mode: "none"` 与"按需开白名单代理"自相矛盾——容器没有任何网络，
"按需"根本开不了。

- 改法：默认无 GPU、`network_mode: none`、`read_only`、`cap_drop: ALL`、非 root；
  需要联网时单独启 `proxy` 服务（`profiles: ["online"]`），主容器不接外网。
- 落点：`docker-compose.yml`、`space/README.md`。

---

## B. 🔴 会出事：能跑，但跑起来会烧钱 / 会被当成授权

### B1. 预算只是一张表，没有任何代码阻止超支

原稿 `docs/budget.md` 定义了 `SEARCH_DAILY_BUDGET`、`GPU_BUDGET_HOURS`，但
`AGENTS.md` 里只有"仅在预算内执行"这句祈使句。祈使句不是闸门：一次 `while True`
就能跑到天亮。

- 改法：`lab/budget.py` 把上限做成会抛 `BudgetExceeded` 的闸门；`run` 捕获后**回滚到
  READY 并返回退出码 3**；CI 里有回归脚本确认这个数字不被改动。
- 落点：`lab/budget.py`、`lab/cli.py`、`scripts/budget_regression.py`、`docs/budget.md`。

### B2. "日志不可删除"只是承诺，没有任何机制

原稿要求"日志不可删除、保留原始来源"，但日志是普通 jsonl，`rm` 之后无痕，改一行也没人知道。
你自己在第 #57 轮说"最好把这一块形成长期记忆"——没有不可篡改的账本，"记忆"就只是文本。

- 改法：哈希链账本，每条记录带前一条的 sha256；`verify` 逐条重算，改一个字节就断链（有测试）。
- 落点：`lab/ledger.py`、`tests/test_lab.py::LedgerTests`。

### B3. 状态机只写在 markdown 里，非法转换没人拦

`logic/state-machine.md` 写了 `INIT → RUNNING → REVIEWING → ROLLING_BACK → FROZEN`，
但没有代码执行它。于是"连续两次回滚就冻结"这条规则永远靠人自觉。

- 改法：`lab/state.py` 用显式转换表；非法转换抛 `IllegalTransition`；
  `verify` 会**重放**历史，手改 `state.json` 会被发现。
- 落点：`lab/state.py`、`logic/README.md`。

### B4. "安全底线别写太死，让人去破解"——这句不能进仓库

第 #59、#61 轮的原话是"你写的太死眼了…让他也可以更改"、"有能力的让他自己去破解"。
作为朋友间的讨论没问题；写进一个要发布到 GitHub 的治理文件，等于**对外声明本项目
授权他人绕过安全限制**。第一个照做的人出事，仓库作者要解释。

- 改法：不写"可以破解"，改成 **IMMUTABLE / EXTENSIBLE 两层**：
  护栏本身改起来要 2 名维护者 + 发起人 + 7 天讨论 + 回滚演练；其余一切随便加模块。
  这样既满足你"别写死"的诉求，又不给"破解"背书。
- 落点：`SECURITY.md` 第 2 节、`GOVERNANCE.md`、`docs/approval-matrix.md`。

### B5. 第 #16–#24、#55 轮那条"无限增殖 / 木马"的需求，不能变成代码或 Issue

那是整段对话里最危险的一条线。它可以作为**反面假设**记录（"为什么我们不做"），
不能作为待认领任务，更不能写成"不受限提示词"。

- 改法：`SECURITY.md` 红线条目 1（自复制/传播）；`lab/policy.py` 用可命中的规则拦
  `curl … | sh`、`exec(base64…)`、私钥路径、`shell=True`、`0.0.0.0` 监听；
  CI 每次跑，命中即红。
- 落点：`SECURITY.md`、`lab/policy.py`、`tests/test_lab.py::PolicyTests`。

### B6. 通知只有"触发条件"，没有防疲劳与回应率闭环

#55 轮你要求"你有更新，总得提示一下本人"。原稿的 `notify/` 只有高/中/低三档触发条件，
没回答三个真问题：**谁判定值得提示？重复了怎么办？一直没人回怎么办？**

- 改法：分级 + 24 小时去重 + 把"回应率"做成指标（<50% 触发通知策略复审）+
  连续 3 天无高危则自动降频 + 所有通知写 `logs/notify.jsonl`（可审计）。
- 落点：`notify/README.md`、`docs/logging.md`、`viz/README.md` 的"未回应告警数"。

### B7. 脑机接口 / 意识上传没有明确边界

#27–#30 轮问过 BCI、"把苍蝇的意识上传"。原 `ETHICS.md` 只写了"不接入活体人脑"，
措辞含糊（"活体人脑"≠"神经信号设备"），容易被读成"以后可以"。

- 改法：显式写"不接入任何脑机接口/神经信号设备"，并说明这类话题只能作为科幻讨论存在。
- 落点：`ETHICS.md` 第 2 节。

### B8. 抓文献只有"遵守条款"，没有落地机制

`research/ingest` 写"不删除原始来源""交叉验证"，但没说**存不存全文**。存全文是最常见的
版权雷，且一旦有人 `git push` 上去，仓库要背。

- 改法：只存"引用 + 摘要 + 链接 + 访问时间"，不存全文；删除请求走账本 `redaction` 事件。
- 落点：`SECURITY.md` 第 5 节、`research/README.md`。

---

## C. 🟠 会烂尾：三个月后没人知道该干什么

### C1. 40 多个只有标题的占位文件

原树有 `time/` 5 个、`logic/` 4 个、`space/` 4 个、`viz/` 3 个、`collab/` 5 个、
`notify/` 3 个、`docs/` 12 个、`issues/` 19 个…… 大部分只有两三行。发布当天看起来像
"写完了"，第二周每个人打开都发现是空壳，然后没人再打开。

- 改法：**合并为有内容的 10 个模块文档**（每个 40–90 行，规则可执行、可对照代码），
  并在 README 的表格里说明"合并规则"，而不是留 40 个 TODO 文件。
- 落点：`time/ logic/ space/ viz/ collab/ notify/ search/ research/ evolve/ issues/` 各自一个 README。

### C2. 单人项目 + "自我进化" = 单点故障

第 #39–#40 轮你自己说"我只是普通人，很多资源接触不到"。原方案的所有审批角色
（发起人、维护者、评审者）都默认是同一个人，等于没有治理。

- 改法：维护者 ≥2，否则项目自动 `FROZEN` 只收安全修复；发起人 30 天无响应可由维护者代行、
  60 天可移交或归档；移交时公开 `state/` 的处理方式。
- 落点：`GOVERNANCE.md` 第 1、4 节。

### C3. 没有发布流程：tag、CHANGELOG、Release notes 全缺

`CITATION.cff` 写了 `version: 0.1.0` 和 `date-released: 2026-10-29`，但仓库里没有对应 tag。
别人引用时会指向一个不存在的版本。

- 改法：SemVer + CHANGELOG + `docs/publish.md` 的发布清单（tag 与 CITATION 日期必须对齐，
  发布脚本里有一行检查）。
- 落点：`CHANGELOG.md`、`CITATION.cff`、`docs/publish.md`。

### C4. 没有"最低配置"路径

原方案默认 Docker + GPU + 向量库。而 #64 轮你说的是"我只是普通人"。让普通人第一步就
`pip install torch`，等于把 90% 的潜在贡献者挡在门外。

- 改法：v0.1 **纯 CPU、零依赖、离线、40 秒跑完全套检查**；GPU 与向量库进 `optional-dependencies`。
- 落点：`README.md`、`sandbox/healthcheck.py`（缺可选组件只 SKIP，不 FAIL）。

### C5. 时间函数：只说了"经 clock 取时间"，没处理回拨/DST/超时

#50 轮你专门要求"别总忘时间"。原稿的 `time/clock.md` 只有"禁止直接调用系统时间"一条，
没定义：时钟回拨怎么办、跨夏令时怎么不重复跑、长任务超时怎么算、测试怎么注入。

- 改法：UTC-only（naive 时间直接抛错）、耗时用单调计数、`FakeClock` 注入保证账本可复现、
  DST 规则（不存在/重复的本地时刻）写进 `time/README.md`。
- 落点：`lab/clock.py`、`time/README.md`。

---

## D. 🟡 表述层：不改会被人当成"你自己都没想清楚"

| 矛盾 | 出处 | 处理 |
|---|---|---|
| "硬边界，不可修改" vs "别写太死，让人改" | #58–#61 | 分 IMMUTABLE / EXTENSIBLE 两层，写清谁能改、走什么流程 |
| 大谈"自我进化" vs 声明"不宣称意识" | 通篇 | 术语表：只写指标，不写"它想/它感受"（`ETHICS.md` 第 3 节） |
| "秒级通知" vs 没有通知通道实现 | #55 | 明确 v0.1 只落账本 + 终端输出，GitHub/webhook 是 Issue 0019 |
| "季度回滚演练" vs 没有演练脚本 | `evolve/rollback.md` | `verify` + checkpoint + `freeze` 使其可脚本化，演练即跑一遍 |

---

## 一句话结论

原稿是一份**很好的立场声明**，但不是**可发布的工程**：它的 19 个任务里，真正卡住发布的是
"没有一行代码执行它自己写的规则"。所以 v0.1 只做一件事——把时间、预算、状态机、账本、
红线、可视化做成**能跑、能测、能回滚**的约 1,100 行（含测试 1,500 行），其余继续留在 Issue 里。

对应到你的 67 轮里：**需求没变，变的是"承诺"和"可验证"的比例。**
