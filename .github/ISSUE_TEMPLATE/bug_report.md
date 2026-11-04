---
name: 报告问题
about: 跑不通、结果对不上、文档有错
title: "[问题] "
labels: bug
---

## 你做了什么

```bash
# 贴完整命令
```

## 你看到了什么

```
# 贴完整输出（不要只贴最后一行）
```

## 你期望什么

## 环境

| 项 | 值 |
|---|---|
| 系统 | Windows / macOS / Linux |
| Python | `python --version` 的输出 |
| 来源 | 官方仓库 / 某个 fork（fork 请给链接） |

## 自检结果（重要）

```bash
python -m lab.cli doctor
python -m unittest discover -s tests -q
```

> 这两条的输出能省掉一半来回。**请不要修改 SECURITY.md 或 lab/policy.py 来"绕过"问题。**
