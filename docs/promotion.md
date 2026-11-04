# 推广：六步，每步都写清"点哪里、粘什么"

> 目标：让一个陌生人在 30 秒内判断"这东西值不值得点开"。
> 现在的问题不是代码，是**没人知道它存在，也没人看懂它是干什么的**。

---

## 第 1 步：填仓库信息（3 分钟）

**先打开** → `https://github.com/xiaoyu123-xiao/open-functional-self-lab/settings`

1. 页面顶部「General」
2. **Description** 框里粘：

   ```
   受控实验台：审计账本 / 预算闸门 / 可学策略 / 迁移评测。不宣称意识，只报告可测指标。
   ```

3. **Topics** 框里逐个输入（每输一个按回车）：

   ```
   research-infrastructure
   audit-ledger
   reinforcement-learning
   reproducibility
   human-in-the-loop
   python
   offline-first
   sandbox
   ```

4. 点绿色 **Save changes**
5. 验证：打开仓库首页，右侧应该出现这段描述 + 一排 Topics 标签

---

## 第 2 步：发一个 Release（2 分钟）

**直接打开**（标签会自动选好）：

```
https://github.com/xiaoyu123-xiao/open-functional-self-lab/releases/new?tag=v0.16.0
```

1. **Release title** 填：`v0.16.0 — 多种子复现`
2. 大文本框粘 `CHANGELOG.md` 里 `## [0.16.0]` 那一整段（从标题到 `### Notes` 结束）
3. 拉到最底，点 **Publish release**
4. 验证：仓库首页右侧出现 "Releases → v0.16.0"

> 之前版本不用补。历史 tag 都在，Release 只是门面。

---

## 第 3 步：加两个徽章（1 分钟）

编辑 `README.md`，在**第一行标题下面**插入：

```markdown
[![ci](https://github.com/xiaoyu123-xiao/open-functional-self-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/xiaoyu123-xiao/open-functional-self-lab/actions/workflows/ci.yml)
![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)
```

**为什么**：陌生人扫一眼就知道"有 CI、有许可证、支持多版本"。这三个标签比一段介绍更有说服力。

---

## 第 4 步：在 README 首屏放"证据表"（3 分钟，你问的就是这一步）

**这一步为什么关键**：陌生人不会读代码，只会看"你有没有真东西"。

在 README 的「这是什么」下面，粘这段：

```markdown
## 证据（可复算）

| 任务 | 手写 BFS 规则 | 学出来的策略 |
|---|---|---|
| 危险区致命，8 个 | −1.758 | **+1.597** |
| 危险区致命，10 个 | −2.340 | **+0.573** |

复算：`python -m lab.cli transfer --algo weighted --repeats 5`

> 只在单一地图族上成立（只变危险区数量），不要外推。5 组复现胜率 100%，但没做统计检验。
```

**为什么这么写**：
- 有具体数字（不是"效果很好"）
- 有复算命令（别人能推翻你）
- 有局限声明（反而增加可信度）

---

## 第 5 步：分发（每次 10 分钟，按顺序做）

| 顺序 | 渠道 | 具体怎么做 | 注意 |
|---|---|---|---|
| 1 | **GitHub Topics** | 第 1 步已做 | 这是最主要的发现入口之一 |
| 2 | **awesome-lists PR** | 搜 `awesome reinforcement learning`、`awesome reproducibility`、`awesome audit`，进去读 CONTRIBUTING，按它的格式加一行 | 一次只提一个；被拒是常态，别争 |
| 3 | **V2EX / 掘金 / 知乎** | 标题：`我做了一个"AI 自我进化"实验台，最值钱的部分是 8 篇失败记录` | 中文社区对"诚实失败"接受度高于"又一个框架" |
| 4 | **Show HN** | 标题：`Show HN: A lab that logs every claim it makes, including the failed ones` | 英文、短、别提"意识" |
| 5 | **Reddit** | 先读版规；`r/reinforcementlearning`、`r/opensource` 比 `r/MachineLearning` 宽松 | 很多板块禁止纯自荐，先参与讨论再发 |

---

## 第 6 步：看三个真实指标（不是 star）

| 指标 | 在哪看 | 目标 |
|---|---|---|
| clone 次数 | 仓库 → Insights → Traffic（14 天） | 有非 0 就说明有人在试 |
| 外部 Issue | Issues 列表 | 第一条外部 Issue = 转折点，务必当天回 |
| `doctor` 报错反馈 | Issue 里的输出 | 有报错就修，那是文档的坑 |

---

## 别做

1. 刷 star、群发链接——会被举报，且不解决"没人用"
2. 写"AI 觉醒"——这是本项目最想避免的误读
3. 在 README 堆功能列表——陌生人只看三件事：**干什么、能不能跑、有没有证据**
