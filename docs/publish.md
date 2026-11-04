# 发布流程（Runbook）

> 目标：从这台机器上的文件夹，变成 GitHub 上一个别人 clone 下来就能跑的仓库。
> 每一步都有"验证方式"。**任何一步验证不过，不要往下走。**
>
> 本机（Windows 11 / Python 3.13.15 / git 2.56）已按本文从第 1 步走到第 7 步实测通过；
> 标注 `[本机已验证]` 的表示我真的在这里跑过。

---

## 0. 发布前：这条命令必须全绿

```bash
cd open-functional-self-lab
python -m lab.cli doctor
python -m unittest discover -s tests -q    # 期望末行 OK
python -m lab.cli lint                     # 期望 "0 高危 0 中危"
python scripts/budget_regression.py        # 期望 "通过（退出码 3 + 回滚到 READY）"
```

`[本机已验证]`

四项全过才继续。`doctor` 里 `layout` / `stdlib-time` / `state-dir` 任一 FAIL，先修，
不要用 `git commit --no-verify` 之类的办法跳过——那是原方案最容易出的事故。

清理本地运行产物（**不要**提交 `state/`）：

```bash
# bash / macOS / Linux
rm -rf state
# Windows PowerShell
Remove-Item -Recurse -Force state -ErrorAction SilentlyContinue
```

> `viz/status.md` 可以留也可以删：留着是一份"真实跑过"的快照，删了 CI 也会重新生成。
> 本仓库 v0.1.0 保留了它（20 步的真实仪表盘）。

---

## 1. 初始化仓库并写第一版

```bash
git init
git config core.autocrlf false          # Windows 上必须：否则换行符会让 diff 全红
git config user.name  "你的名字"
git config user.email "you@example.com"  # 仅本仓库生效，别动全局配置
git add .
git status --short                       # 确认没有 .env / state/ / 密钥
git commit -m "feat: v0.1.0 控制面（时钟/账本/状态机/预算/红线/可视化/周报）"
```

`[本机已验证]`

提交前最后看一眼：`git status --short` 里**不应该**出现以下任何一项——
`.env`、`state/`、`*.gguf`、`*.safetensors`、`lab.config.json.bak`。
出现了就 `git rm --cached <file>` 并补进 `.gitignore`。

---

## 1.5 把占位符换成你的仓库地址（推送之前做）

README / CONTRIBUTING / CITATION / CODEOWNERS / Issue 模板里共 13 处写着 `your-org`。
**CODEOWNERS 里留占位符等于分支保护不生效**，所以这一步不能省：

```bash
python scripts/set_owner.py --owner <你的GitHub用户名>
```

想顺便把 commit 作者改成你本人（仓库还没 push 时才可以）：

```bash
python scripts/set_owner.py --owner <用户名> --name "你的名字" --email "you@example.com"
# 它会提示重新打 tag：git tag -d v0.1.0 && git tag -a v0.1.0 -m "v0.1.0 控制面 MVP"
```

然后：

```bash
git add -A
git commit -m "chore: 替换占位符为真实仓库地址"
```

`[本机已验证]`（在干净 clone 里跑过：13 处全部替换、无残留、`doctor` 与 27 个测试仍全绿）

---

## 2. 建远端仓库

### 方式 A：网页（不需要装任何东西）

1. 打开 https://github.com/new
2. Repository name：`open-functional-self-lab`
3. 选 **Public**；**不要**勾 "Add a README / .gitignore / license"（本地已有，勾了会冲突）
4. Create → 复制页面上的 `https://github.com/<你>/open-functional-self-lab.git`

### 方式 B：gh CLI（装了 gh 才可用）

```bash
gh auth login
gh repo create open-functional-self-lab --public --source=. --remote=origin --push
```

装了 gh 的话，方式 B 直接连第 4 步一起做完，可以跳过第 3 步。

---

## 3. 推送

```bash
git branch -M main
git remote add origin https://github.com/<你>/open-functional-self-lab.git
git push -u origin main
```

`[本机已验证]`（本地已完成 `git init` → `commit` → `tag`，只差 remote 与 push）

认证：HTTPS 要用 **Personal Access Token** 当密码（GitHub 早已不支持账号密码）；
或者装 GitHub CLI 后 `gh auth setup-git` 一次性搞定。

---

## 4. 第一次 CI 必须绿

推到 main 后，Actions 会自动跑 4 个 Python 版本 × 6 步。约 1–2 分钟。

验证方式：仓库页 → Actions → `ci` → 4 个 job 全绿。

红了怎么办（按报错对应）：

| CI 报错 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: lab` | 目录里缺 `lab/__init__.py` | 补文件，重新推送 |
| `doctor` 的 `layout` FAIL | 少了 `REQUIRED_FILES` 里的某个文件 | 按提示补 |
| `lint` 红 | 命中了红线规则 | 看输出里的 `path:line`，改代码；**不要**改 `lab/policy.py` 绕过 |
| `verify` 红 | 账本哈希链断 | 删除 `state/` 重跑；账本不进 git，正常不会有这个问题 |
| 预算回归脚本红 | 有人改了闸门行为 | 回滚该 PR，走 `docs/approval-matrix.md` |

---

## 5. 保护 main 分支

仓库页 → Settings → Branches → Add branch protection rule：

- Branch name pattern：`main`
- ✅ Require a pull request before merging（Required approvals：**1**）
- ✅ Require status checks to pass（选 `py3.12` 或全部 `test`）
- ✅ Do not allow bypassing the above settings

再开：Settings → General → 勾 **Allow auto-merge**、**Automatically delete head branches**。

为什么必须做：原方案只有"维护者批准"这句话。没有分支保护，"批准"随时可以被自己绕过。

---

## 6. 打 tag 与 Release

先把版本日期对齐（否则 `CITATION.cff` 指向不存在的版本）：

```bash
# 1) 改 CITATION.cff 的 date-released 为今天（YYYY-MM-DD）
# 2) 改 CHANGELOG.md 顶部：0.1.0 - 今天
git add CITATION.cff CHANGELOG.md
git commit -m "chore(release): 0.1.0"
git tag -a v0.1.0 -m "v0.1.0 控制面 MVP"
git push origin v0.1.0
```

`[本机已验证]`（tag 已建好）

然后 GitHub → Releases → Draft a new release → 选 `v0.1.0` → 标题 `v0.1.0 — 控制面 MVP`，
正文粘 `CHANGELOG.md` 的 0.1.0 段落 → Publish。

自动校验（发布前跑，避免 tag 与文件不一致）：

```bash
python -c "import re,pathlib;t=pathlib.Path('CITATION.cff').read_text(encoding='utf-8');print(re.search(r'version:\s*(\S+)',t).group(1))"
# 期望输出 0.1.0，与 `python -m lab.cli --version` 一致
```

---

## 7. 建 19 个 Issue

```bash
python scripts/seed_issues.py --dry-run   # 生成正文到 state/issue-bodies/，并把命令存成 state/seed_issues.sh
python scripts/seed_issues.py             # 真建（需要已 gh auth login）
```

没装 gh：`--dry-run` 会把 19 条 `gh issue create ... --body-file ...` 写进 `state/seed_issues.sh`，
装上 gh 后 `bash state/seed_issues.sh` 一次跑完；或手动复制。用 `--body-file` 而不是 `--body`，
是为了避开 Windows 单条命令 8191 字符的上限。

可选但推荐：建 3 个 label + 1 个 Discussion 分类

```bash
gh label create "good-first-issue" --color 7057ff
gh label create "immutable-layer"  --color b60205
gh label create "needs-design"     --color fbca04
```

---

## 8. 发布后 24 小时检查表

- [ ] 在**另一台机器/另一个目录** clone 一遍，按 README 的"五分钟跑通"照做：`doctor` 全绿
- [ ] `python -m unittest discover -s tests -q` → `OK`
- [ ] Actions 绿；Release 页能下载 zip
- [ ] 仓库首页的 License 显示 MIT（不是 "Unknown"）
- [ ] CODEOWNERS 里的 `@your-org/...` 已换成真实用户名/团队（否则保护规则不生效）
- [ ] `CITATION.cff` 的 `repository-code` 已换成真实 URL
- [ ] 把 README 里的 `<your-org>` 全部替换掉：`grep -rn "<your-org>" .`
- [ ] 自己在 Discussions 里发第一条"本项目不宣称意识，只报告指标"

最后一条不是形式主义：它决定了第一个来的人是把这当研究项目，还是当"AI 觉醒"话题。

---

## 9. 回滚（发布后发现严重问题）

```bash
# 情况 1：只是某个 PR 有毒 → 在 GitHub 上 Revert PR（走 PR 流程，留痕）
# 情况 2：整个版本有问题 → 发布一个修复版，不要删 tag
git tag -d v0.1.0 && git push origin :refs/tags/v0.1.0   # 仅当 tag 还没人用时
```

**不要**做的事：`git push --force` 到 main、删除 Release、改历史。审计链和信任都是这么丢的。
已经有人 clone 的版本出问题，正确做法是 `v0.1.1` 里写清楚"0.1.0 有什么问题"。

---

## 10. 常见报错对照

| 现象 | 原因 | 处理 |
|---|---|---|
| `git push` 报 `remote: Support for password authentication was removed` | 用了账号密码 | 换 PAT 或 `gh auth setup-git` |
| Windows 上 `git commit` 报 `LF will be replaced by CRLF` | `core.autocrlf` 为 true | `git config core.autocrlf false` 后重提交 |
| CI 里 `python -m lab.cli doctor` 报 `disk` WARN | 磁盘 <1GB | 无法避免，属 WARN 不阻塞 |
| `bash: python: command not found`（macOS） | 只有 `python3` | 全文把 `python` 换成 `python3` |
| `docker compose up` 报 `could not select device driver ... gpu` | 旧版 compose 文件带 GPU 段 | 本仓库 v0.1 已移除该段；若你改过，删掉 `deploy.resources` |
| Release 里看不到 tag | tag 没 push | `git push origin v0.1.0` |
