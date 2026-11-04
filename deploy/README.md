# 在有算力的机器上跑（v0.7）

> 这份文档假设你有一台**能长时间跑**的机器：云 GPU、工作站、或一台闲置的服务器。
> 作者本人的电脑跑不动，所以这个项目按"给有算力的机器用"来设计。

## 最快路径（3 条命令）

```bash
git clone https://github.com/xiaoyu123-xiao/open-functional-self-lab.git
cd open-functional-self-lab
docker compose -f deploy/compose.gpu.yml run --rm lab python -m lab.cli loop --cycles 50 --lethal
```

## 不用 Docker 也可以（任何 Linux 机器）

```bash
sudo apt-get update && sudo apt-get install -y python3.11 python3.11-venv git tmux
git clone https://github.com/xiaoyu123-xiao/open-functional-self-lab.git
cd open-functional-self-lab
python3.11 -m venv .venv && . .venv/bin/activate
python -m lab.cli doctor                       # 10 项全过再继续
python -m lab.cli init
python -m lab.cli loop --cycles 50 --lethal    # 核心：训练 + 留出评测 + 变差回滚
```

## 长时间跑（tmux，断电/断线不中断）

```bash
tmux new -s ofsl
python -m lab.cli loop --cycles 200 --rounds 5 --episodes 200 --lethal > state/loop.log 2>&1
# Ctrl-B D 脱离；tmux attach -t ofsl 回来
```

**注意**：`loop` 每轮都会自己复习"留出分数是否变好"，变差就回滚——所以挂着跑不会越跑越差。

## 想加 GPU 训练（可选，当前版本还用不到）

```bash
pip install -r requirements-train.txt      # torch（CUDA 版按官网选 index-url）
python -c "import torch; print(torch.cuda.is_available())"
```

v0.7 的策略是表格/线性，**不需要 GPU**。GPU 是给 v0.8 的神经网络策略和 LLM 接入准备的，
现在装上也不会有额外收益，别为此多花钱。

## 资源预估（实测）

| 任务 | CPU | 内存 | 时间 |
|---|---|---|---|
| `doctor` + 86 个测试 | 任意 | < 200 MB | ~3 秒 |
| `loop --cycles 50 --lethal` | 1 核 | < 300 MB | ~1–2 分钟 |
| 想跑几百轮做统计 | 1 核 | < 300 MB | 小时级（可并行多进程，各自独立 `--root`） |

**结论**：这个版本对硬件几乎没要求；真正的算力需求会出现在 v0.8（神经网络/LLM）之后。
