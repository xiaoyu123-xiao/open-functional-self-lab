# 软硬件工具清单

> 与旧方案最大的差别：**默认零依赖**。原稿的 `pip install -r sandbox/requirements.txt`
> 里有装不上的包（`pyaif-toolkit`、`soul-agent`）和不存在的版本（`chromadb==1.5.9`），
> clone 下来第一条命令就红。详见 `docs/gap-analysis.md` A2/A3。

## 1. 必需（没有就跑不起来）

| 组件 | 版本 | 用途 | 检查 |
|---|---|---|---|
| Python | ≥ 3.10（CI 覆盖 3.10–3.13） | 运行时 | `python -V` |
| git | 任意较新版本 | 版本管理 / 发布 | `git --version` |

其余**全部标准库**。不需要 numpy、不需要 torch、不需要数据库。

## 2. 可选（按任务再装）

| 组件 | 装法 | 什么时候需要 | 不装的影响 |
|---|---|---|---|
| `gymnasium` | `pip install -e ".[env]"` | Issue 0001 想用现成环境接口 | 自己用标准库写网格世界即可 |
| `chromadb` | `pip install -e ".[memory]"` | Issue 0004 想用向量库 | 用 `sqlite3` 足够（默认建议） |
| Docker + Compose v2 | 官网 | 需要容器隔离（Issue 0016） | 直接本机跑，隔离靠"不联网+不读凭证" |
| GPU / CUDA | — | 只有 Issue 0013 需要 | 其余 18 个任务纯 CPU |

`python sandbox/healthcheck.py` 会把缺的可选组件标 `SKIP`（**不是**失败），
加 `--strict` 才把它们当失败。

## 3. 硬件三档（对应 Issue 0006 的实测）

| 档 | 配置 | 能跑什么 | 实测参考 |
|---|---|---|---|
| 最低 | 4 核 CPU / 8 GB 内存 / 1 GB 磁盘 | 全套检查 + 1000 步 | 20 步约 0.1 秒 |
| 推荐 | 8 核 / 16 GB / 50 GB SSD | + 文献管线、sqlite 记忆 | — |
| 高配 | + RTX 3060 12 GB 以上 | + 一次 LoRA（Issue 0013） | 需要单独预算 |

磁盘：核心 + 测试约 2 MB。真正吃空间的是模型权重（不做）。

## 4. 一键验证（复制粘贴）

```bash
git clone https://github.com/<your-org>/open-functional-self-lab.git
cd open-functional-self-lab
python -m lab.cli doctor
python -m unittest discover -s tests -q
python -m lab.cli init && python -m lab.cli run --steps 20 && python -m lab.cli verify
python sandbox/healthcheck.py
```

四步都应该成功；最后一步会打印几行 `SKIP`，那是正常的。

## 5. 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: lab` | 不在仓库根目录 | `cd` 到有 `lab/` 的目录 |
| `doctor` 的 `stdlib-time` WARN | 仓库根建了 `time/__init__.py` | 删掉它，`time/` 只能是文档目录 |
| macOS 上 `python` 不存在 | 只有 `python3` | 全文换 `python3` |
| Windows 控制台中文乱码 | 代码页 | `chcp 65001`；CLI 已强制 UTF-8 输出 |
| `pip install -e .` 失败 | 没有 pip/setuptools | 本项目**不需要**安装也能跑，直接 `python -m lab.cli` |
