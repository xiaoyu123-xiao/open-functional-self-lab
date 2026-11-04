## 变更说明

<!-- 一句话：这个 PR 让什么变好了 -->

## 关联 Issue

Refs: #

## 类型

- [ ] feat（新能力）
- [ ] fix（修缺陷）
- [ ] docs（文档）
- [ ] test（测试）
- [ ] sec（安全相关，需 2 名维护者）

## 复现步骤

```bash
python -m lab.cli doctor
python -m unittest discover -s tests -v
python -m lab.cli lint
python -m lab.cli verify
```

输出（贴关键行）：

```text

```

## 安全影响

- 是否新增联网行为：否 / 是（域名与理由）
- 是否新增依赖：否 / 是（为何标准库不够）
- 是否触碰 IMMUTABLE 层（policy / budget / ledger / SECURITY.md）：否 / 是（审批链接）

## 回滚方式

<!-- 怎么一键回到改动前；涉及 state/ 的改动要说明账本如何处理 -->

## 检查清单

- [ ] 新增行为有测试，且覆盖边界（超预算、非法状态、被篡改的账本）
- [ ] 没有提交 `.env`、`state/`、密钥、模型权重
- [ ] 没有宣称"意识/觉醒"，结论写在 `docs/metrics.md` 的口径内
- [ ] 失败也记录了（`state/reports/` 或 `docs/` 的失败章节）
