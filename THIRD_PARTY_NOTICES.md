# 第三方组件与许可证

## 运行时必需

**无。** v0.1 只使用 Python 标准库（`json` `hashlib` `datetime` `argparse` `pathlib` `random`
`math` `shutil` `subprocess` `tempfile` `unittest`）。标准库随 Python 分发（PSF License），
不属于本项目再分发范围。

## 可选（`optional-dependencies`，不装也能跑）

| 组件 | 来源 | 许可证 | 用途 | 修改 |
|---|---|---|---|---|
| gymnasium | Farama Foundation | MIT | Issue 0001 可选的现成环境接口 | 无 |
| chromadb | Chroma | Apache-2.0 | Issue 0004 可选的向量库 | 无 |

## 已移除（旧方案的依赖问题）

| 组件 | 问题 | 处理 |
|---|---|---|
| `pyaif-toolkit` | PyPI 上无可用发行版 | 移除（Issue 0003 用标准库实现基线） |
| `soul-agent` | PyPI 上无可用发行版 | 移除 |
| `chromadb==1.5.9` | 版本号不存在 | 改为 `chromadb>=0.4` 并降级为可选 |
| `torch>=2.0`（必需） | Python 3.13 无 wheel，且 2 GB | 移除；Issue 0013 需要时再作为可选安装 |
| `numpy` `pyyaml` `requests` `apscheduler` | 核心用不到 | 移除（`json` 替代 yaml，`urllib` 需要时再引入） |

## 规则

- 新增依赖必须：在本表登记 + 说明为何标准库不够 + 锁版本。
- GPL/AGPL 依赖不得并入 MIT 项目；确需使用时隔离为独立进程并通过接口调用。
- 模型权重与数据集不入库，只记来源、许可证与哈希。
