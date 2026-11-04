# Open Functional Self Lab

> **We study functional self-models and open-ended research loops. We do not claim consciousness.**
> 我们研究"功能性自我模型"和开放式研究循环；我们不宣称、不证明任何系统拥有意识。

一个**可运行**的受控实验台：把"自律研究循环"里最容易被口头承诺、却最难验证的那部分
——时间、预算、状态机、审计账本、红线、可视化、告警——先做成能跑、能测、能回滚的代码。

- 版本：`0.1.0`（控制面 MVP，纯 CPU、零第三方依赖、离线可跑）
- 依赖：Python ≥ 3.10，其余全部标准库
- 状态：所有检查在本机实跑通过（见下方"已验证"）

## 这是什么

| 你得到 | 在哪 |
|---|---|
| 统一时钟（UTC + 单调计数 + 可注入） | `lab/clock.py` · `time/README.md` |
| 只追加哈希链账本（改一条就断链） | `lab/ledger.py` |
| 显式状态机（非法转换直接拒） | `lab/state.py` · `logic/README.md` |
| 预算硬闸门（超限抛异常并回滚） | `lab/budget.py` · `docs/budget.md` |
| 红线扫描（SECURITY.md 的可执行版） | `lab/policy.py` · `SECURITY.md` |
| 仪表盘自动生成 | `lab/viz.py` → `viz/status.md` |
| 周报自动生成 | `lab/report.py` → `state/reports/` |
| 紧急冻结开关 | `lab freeze` / `lab unfreeze --by <你>` |
| 19 个可认领任务 | `issues/README.md` |
| 发布流程（含回滚） | `docs/publish.md` |

## 这不是什么

- ❌ 不是"会自我进化/觉醒"的程序。仓库里**没有**自复制、网络传播、权限提升、隐藏行为的代码，红线扫描器会拦住这类 PR。
- ❌ 不是大模型部署教程。要部署模型请看 `docs/tools.md` 的"模型侧可选项"，本项目默认**不下载任何权重**。
- ❌ 不是论文。任何"涌现""意识"的说法在本仓库都只作为**待验证假设**记录，不作为结论。

## 五分钟跑通

```bash
git clone https://github.com/<your-org>/open-functional-self-lab.git
cd open-functional-self-lab

python -m lab.cli doctor          # 环境与仓库自检，应全绿
python -m lab.cli init            # 建 state/
python -m lab.cli run --steps 20  # 跑一次受控循环（模拟芯，不联网）
python -m lab.cli verify          # 校验哈希链/状态机重放/checkpoint/预算
python -m lab.cli lint            # 红线扫描
python -m lab.cli viz             # 生成 viz/status.md
python -m lab.cli report          # 生成周报
```

Windows、macOS、Linux 命令相同（没有 `make`、没有 `sh` 脚本依赖）。
想完全复现某次运行的账本哈希：加 `--fake-now 2026-01-01T00:00:00Z`。

### 自测

```bash
python -m unittest discover -s tests -v
```

### 已验证（本机 2026-11-04，Windows 11 / Python 3.13.15）

```
doctor  9 项检查全通过
init    → state/state.json + state/ledger.jsonl
run     → 20 步，checkpoint 落盘，账本 +65 条（合计 67 条）
verify  哈希链完整 / 状态机重放 4 次 / checkpoint 带锚点 / 预算未超限
lint    0 高危 0 中危
healthcheck  必需项全过，可选组件 4 项 SKIP（正常）
unittest 27 项通过
```

并且把仓库 clone 到另一个空目录后重跑上面全部命令，结果一致——没有依赖任何本地未提交的文件。

## 为什么先做控制面

原方案的 19 个 Issue 里，真正会让项目"看起来在动、实际上不可复用"的，不是缺模型，
而是**缺约束的可执行实现**：预算只写在表格里、状态机只写在文档里、日志只写"不可删除"、
"红线"只靠人眼审。没有这些，跑三周以后没人说得清发生了什么。

所以 v0.1 用约 1,100 行标准库代码把这些变成可测试的断言；模型侧（哪怕只是 Ollama 上的
一个 7B）在 `docs/tools.md` 里作为**可选**接入点，接进来也不能绕过 `lab run` 的预算与状态机。

## 目录

```
lab/        控制面实现（clock · ledger · state · budget · policy · viz · report · cli）
tests/      unittest，零依赖
time/       时间规则（时钟/衰减/TTL/调度/窗口/时区与 DST）
logic/      依赖图/调用链/状态机/因果追踪
space/      资源布局/权限边界/数据流/沙箱隔离
viz/        仪表盘规范 + 自动生成的 status.md
collab/     人机分工/进步日志/ADR
notify/     触发规则/渠道/模板/防疲劳
search/     白名单代理与限速
research/   文献→假设→实验→验证 闭环规范
evolve/     LoRA/eval-gate/回滚（v0.1 不启用，仅规范）
docs/       工具、流程、发布、预算、指标、审批矩阵、问题清单
issues/     19 个可认领任务（含验收标准与预算）
sandbox/    Dockerfile、零依赖 healthcheck
scripts/    建 Issue / 预检 辅助脚本
```

## 参与方式

1. 先读 `SECURITY.md`、`ETHICS.md`、`GOVERNANCE.md`（15 分钟）
2. `python -m lab.cli doctor` 确认环境；`python -m unittest discover -s tests` 确认基线
3. 到 `issues/README.md` 挑一个 `good-first-issue`，按 `CONTRIBUTING.md` 提 PR
4. 高风险改动（安全模块、预算上限、评测器）必须走 `docs/approval-matrix.md`

## 已知边界

- `lab run` 目前跑的是**确定性模拟芯**（伪随机噪声 + 单调衰减），用途是验证闭环基础设施，
  不代表任何模型能力。接入真实模型是 Issue 0003 / 0007 的工作。
- 未做多用户鉴权；`state/` 只适合单机单人。
- 不收集任何个人数据；如需接入人类反馈，先读 `ETHICS.md` 的知情同意条款。

## 许可证

MIT，见 `LICENSE`。安全与治理条款见 `SECURITY.md` / `GOVERNANCE.md`；它们不是法律条款，
而是**合并条件**——违反即拒绝合入。

## 引用

见 `CITATION.cff`。
