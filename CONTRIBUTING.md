# 贡献指南

## 0. 30 秒版本

```bash
git clone https://github.com/xiaoyu123-xiao/open-functional-self-lab.git && cd open-functional-self-lab
python -m lab.cli doctor                          # 应全绿
python -m unittest discover -s tests -v           # 应全过
python -m lab.cli init && python -m lab.cli run --steps 20 && python -m lab.cli verify
```

改代码 → 加测试 → `doctor` + `unittest` + `lint` + `verify` 全绿 → 提 PR。

## 1. 环境

| 项 | 要求 |
|---|---|
| Python | ≥ 3.10（CI 跑 3.10 / 3.11 / 3.12 / 3.13） |
| 第三方依赖 | **核心零依赖**，请不要引入（见第 5 节） |
| GPU | 不需要 |
| Docker | 可选，只在 `docker-compose.yml` 路径需要 |
| 操作系统 | Windows / macOS / Linux 都行；脚本必须是纯 Python |

## 2. 能改什么

| 类型 | 例子 | 需要 |
|---|---|---|
| 文档/错别字/示例 | `docs/`、README | 1 名维护者 |
| 新测试 | `tests/` | 1 名维护者 |
| 新模块（扩展点） | `research/domains/xxx.md`、新任务卡 | 1 名维护者 + 登记 issues |
| 改闸门/规则/账本算法 | `lab/policy.py`、`lab/budget.py`、`lab/ledger.py` | **2 名维护者 + 发起人 + 7 天讨论** |

不确定就开 Issue 问，不要先写 500 行再问。

## 3. 提交规范

```
<type>(<scope>): <subject>

<body: 为什么这么改>

Refs: #<issue>
```

`type`：`feat` `fix` `docs` `test` `chore` `refactor` `sec`。
`sec` 用于安全相关改动（会被单独标红审查）。

一次提交只做一件事。格式调整和逻辑修改不要混在同一个 PR。

## 4. PR 检查清单

- [ ] `python -m lab.cli doctor` 通过
- [ ] `python -m unittest discover -s tests -v` 通过
- [ ] `python -m lab.cli lint` 无高危
- [ ] `python -m lab.cli verify` 通过
- [ ] 新增行为有测试；新增文件有说明用途的 docstring
- [ ] 没提交 `.env`、`state/`、日志、密钥、模型权重
- [ ] 没宣称"意识/觉醒/活过来"，指标写在 `docs/metrics.md` 口径内
- [ ] 若改动涉及预算上限或安全规则，已在 PR 描述里写明回滚方式

## 5. 依赖政策

核心包**只用标准库**。这不是洁癖：

1. 依赖越少，供应链投毒面越小（`SECURITY.md` 第 3 节）。
2. 用户里有大量"只有一台普通电脑"的人——`pip install torch` 就要 2 GB，会把门槛推回"必须有 GPU"。
3. 零依赖让 CI 在 4 个 Python 版本上 40 秒跑完。

确实需要时（例如接真实环境）：放进 `pyproject.toml` 的 `optional-dependencies`，
并在 `THIRD_PARTY_NOTICES.md` 登记许可证与用途。

## 6. 行为与争议

- 技术争议用 ADR（`collab/adr/`）记录，不靠聊天记录。
- 对人的问题遵循 `CODE_OF_CONDUCT.md`。
- 安全问题**不要**开公开 Issue，见 `SECURITY.md` 第 4 节。
