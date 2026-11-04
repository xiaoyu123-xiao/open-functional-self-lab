# 第一次发布：从零到 GitHub（图文级步骤）

> 给"从来没建过仓库"的人。手机和电脑都行，但**必须在有代码的那台电脑上推**。
> 全程不需要给我账号密码；GitHub 的登录在你自己的浏览器里完成。

---

## 第 1 步：建一个空仓库（2 分钟，手机也能做）

1. 打开 **https://github.com/new**
   （手机浏览器同样可用；如果没登录，先登录你的 `xiaoyu123-xiao` 账号）

2. **Repository name** 填：

   ```
   open-functional-self-lab
   ```

   ⚠️ 一字不差。因为 `CITATION.cff`、`README`、`.github/` 里的链接都已经写成这个名字了。

3. **Description** 随便填或留空，例如：

   ```
   受控实验台：时钟/审计账本/状态机/预算闸门/红线扫描（不宣称意识）
   ```

4. 选 **Public**（公开）。
   Private 也能跑，但 Actions 只有 2000 分钟/月，而且别人看不到你的 Issue。

5. ⚠️ **三个勾选框全部保持不勾**：

   | 不要勾 | 因为 |
   |---|---|
   | Add a README file | 我们本地已经有，勾了会让第一次 push 被拒（非空仓库） |
   | Add .gitignore | 同上，本仓库已有 60 行定制版 |
   | Choose a license | 同上，本仓库已有 MIT 全文 |

6. 点绿色的 **Create repository**。

建完后出现的页面会显示一堆 `git remote add origin …` 之类的命令——**不要照着敲**，那是给空仓库用的，我们的 remote 已经配好了。直接去第 2 步。

---

## 第 2 步：回到电脑，双击一个文件（30 秒）

打开文件夹：

```
D:\下载\储存东西用的\Distilly_hub\open-functional-self-lab
```

双击 **`publish.bat`**。

窗口会依次做四件事：

1. 跑预检（doctor / 27 个测试 / 红线扫描 / 预算回归 / 账本校验）
2. 检查工作区是否干净、remote 是否指向你的仓库
3. `git push -u origin main`
4. `git push origin v0.1.0`

**第一次会弹出一个浏览器窗口让你登录 GitHub**（这是 Git Credential Manager，
登录完它会记住，以后再也不用登）。登录后窗口自己继续跑。

看到这两行就是成功：

```
 * [new branch]      main -> main
 * [new tag]         v0.1.0 -> v0.1.0
[完成] 已推送到 GitHub。
```

窗口最后停在"按任意键继续"，不会一闪而过。

---

## 第 3 步：确认东西真的上去了（1 分钟）

打开：

```
https://github.com/xiaoyu123-xiao/open-functional-self-lab
```

应该看到：

- 根目录有 `README.md`、`lab/`、`tests/`、`docs/`、`.github/`
- 右侧 **Releases** 显示 `v0.1.0`
- 页面底部/侧边 **License: MIT**（不是 Unknown）
- 顶部 **Actions** 标签 → 有 4 个 job（py3.10 / 3.11 / 3.12 / 3.13），1–2 分钟后全绿

如果 Actions 提示 *"Workflows aren't being run"*，点一下 **I understand my workflows, go ahead and enable them**。

---

## 第 4 步：开保护（3 分钟）

**Settings → Branches → Add branch protection rule**

- Branch name pattern：`main`
- ✅ Require a pull request before merging（Approvals 填 `1`）
- ✅ Require status checks to pass（勾 `py3.12`）
- ✅ Do not allow bypassing the above settings
- 点 **Create**

---

## 第 5 步：发版本 + 建任务（5 分钟）

**发版本**：仓库页右侧 **Releases → Draft a new release** → Tag 选 `v0.1.0` →
标题填 `v0.1.0 — 控制面 MVP` → 正文粘 `CHANGELOG.md` 里 `[0.1.0]` 那一整段 → **Publish release**。

**建 19 个任务 Issue**（二选一）：

- 想在网页上一个个建：打开 `issues/README.md` 照表复制，用 "New issue" 的模板填
- 想自动建：先装 GitHub CLI `winget install --id GitHub.cli`，然后

  ```powershell
  gh auth login
  python scripts/seed_issues.py
  ```

---

## 出错了怎么办

| 屏幕上的字 | 意思 | 怎么办 |
|---|---|---|
| `Repository not found` | 仓库还没建，或名字拼错 | 回第 1 步；名字必须一字不差 |
| `Authentication failed` / 弹窗被关掉 | 登录没完成 | 重新双击 `publish.bat`，这次把浏览器窗口登录完 |
| `Updates were rejected … non-fast-forward` | 建仓库时勾了 README/LICENSE | 最省事：删掉那个仓库，重新建一个**全空**的；或执行 `git pull --rebase origin main` 再跑一次 |
| `refusing to allow a Personal Access Token … workflow` | 你用了 token 而不是弹窗登录 | token 要同时勾 `repo` + `workflow` 两个范围；或者改用弹窗登录 |
| `git: command not found` | 没装 Git | 装 Git for Windows，装完重开窗口 |
| 窗口一闪就没了 | 极少见 | 用 PowerShell 进入仓库目录，手动执行 `.\publish.bat` 看报错 |

任何一步卡住，把**窗口里的文字**发给我（不要发密码），我按报错定位。

---

## 手机上之后能做什么

推送必须在电脑上（commit 在你电脑的 `.git` 里）。推上去以后，手机上什么都能做：

- 看 Actions 是否绿、看仪表盘 `viz/status.md`
- 提 Issue（有模板，会自动带你填目标/验收/安全/预算）
- 改 README、发 Release、开 Discussions（Settings → General → 勾 Discussions）
- 把仓库链接发给朋友，别人 `git clone` 就能跑
