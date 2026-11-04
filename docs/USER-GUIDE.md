# 使用手册（不需要会编程）

> 这份文档给"想用这个东西、但不打算读代码"的人。
> 全程只需要：一个命令行窗口 + 复制粘贴几条命令。
> 读不完也没关系，只看第 1、2、3、6 节就够用。

---

## 1. 它能干什么（60 秒版）

**一句话**：它是一个能自己跑实验、自己记笔记、自己被评测的"小型研究台"。

| 它会做 | 什么意思 |
|---|---|
| 跑一轮实验 | 在一个 8×8 的小世界里走 20~60 步，找食物、躲危险，每一步都记账 |
| 学一件事 | 用 Q-learning 从零学"怎么走"，学完在**没见过的地图**上考它 |
| 记笔记 | 把"它学到了什么、在哪摔倒"写进 `state/self.json` |
| 收资料 | 从白名单网站取样、存成"待验证的声明"，到期提醒复审 |
| 提醒你 | 出问题（超预算、评审不过）时分级通知，并且记录你是否回应过 |

**它不会做**（这些是我刻意做的边界，不是还没写完）：

- ❌ 不会自称有意识，也不会假装"我想活下去"
- ❌ 不会自己复制、传播、去别人的电脑上跑
- ❌ 默认不联网（要开必须手动加 `--online` 且网站在白名单里）
- ❌ **目前还打不过一个手写的笨规则**（见第 5 节，这是真话）

---

## 2. 五分钟装好并跑起来

### 你需要什么

- Windows 10/11（macOS、Linux 也一样，命令只差 `python3` 和 `python`）
- Python 3.10 或更新（装的时候**记得勾选** "Add python.exe to PATH"）
- 一个文件夹放它

### 第一步：拿到代码

```powershell
cd D:\下载\储存东西用的
git clone https://github.com/xiaoyu123-xiao/open-functional-self-lab.git
cd open-functional-self-lab
```

没有 git 也行：在 GitHub 页面点 **Code → Download ZIP**，解压后进入那个文件夹。

### 第二步：自检（10 秒）

```powershell
python -m lab.cli doctor
```

**应该看到**（10 项全 OK）：

```
[OK] python      Python 3.13.15
[OK] layout      9 个必需文件齐全
...
结果：全部通过
```

只要最后一句话是"全部通过"，就可以继续。出现 `FAIL` 就看第 6 节。

### 第三步：让它跑起来（20 秒）

```powershell
python -m lab.cli init
python -m lab.cli run --steps 20
```

**应该看到**：

```
启动 run-001：20 步，seed=20261104
完成：20 步，checkpoint → state/checkpoints/run-001.json
末态：位置(6,4) 能量 0.98 损伤 0.25 稳态误差 0.0 预测误差 0.25
等待评审：python -m lab.cli review --pass
```

**注意最后一行**：它跑完会**停下来等你评审**——这是故意的，它不许自己给自己打分。

```powershell
python -m lab.cli review --pass --by 你的名字
```

### 第四步：让它"学会走路"（1~2 分钟）

```powershell
python -m lab.cli loop --cycles 3
```

**会看到**（数字每次略有不同，但结构一样）：

```
—— 第 1/3 轮 ——
训练前留出分数：-4.495（吃到 25，受伤 103）
训练后留出分数：+2.200（吃到 70，受伤 17）
变化 +6.695 → 保留新策略
BFS 基线 +3.565，当前策略与之差 -1.365（负数表示还没追上）
```

这段是**这个项目最核心的输出**，第 4、5 节专门解释怎么读。

---

## 3. 五个最常用的操作

| 你想干什么 | 命令 | 大概耗时 |
|---|---|---|
| 看它现在什么状态 | `python -m lab.cli status` | 1 秒 |
| 跑一轮实验 | `python -m lab.cli run --steps 20` 然后 `review --pass` | 2 秒 |
| 训练 + 考试 | `python -m lab.cli loop --cycles 3` | 1~2 分钟 |
| 训练 + 考试（致命危险区） | `python -m lab.cli loop --cycles 3 --lethal` | 同上 |
| 只考试（致命） | `python -m lab.cli eval --lethal` | 5 秒 |
| 单独考试（不训练） | `python -m lab.cli eval` | 5 秒 |
| 看它对自己的描述 | `python -m lab.cli self` | 1 秒 |
| 看知识库里有什么 | `python -m lab.cli knowledge list` | 1 秒 |
| **给它开权限**（一次性给到位） | `python -m lab.cli autonomy --level full --by 你 --days 90` | 3 秒 |
| 收回权限 | `python -m lab.cli autonomy --revoke --by 你` | 1 秒 |
| **让它自己跑一段时间** | `python -m lab.cli auto --cycles 20` | 视轮数 |
| 备份数据到 SQLite | `python -m lab.cli db sync && python -m lab.cli db backup` | 2 秒 |
| 收一批资料 | `python -m lab.cli learn` | 1 秒 |
| 看有没有事需要你处理 | `python -m lab.cli inbox` | 1 秒 |
| 和它一起决定下一步 | `python -m lab.cli collaborate` 然后 `--choose 1` | 2 秒 |
| 看它的行为有没有变化 | `python -m lab.cli emergent` | 1 秒 |

**全部命令**在 `docs/MASTER.md` 第 5 节，命令后加 `-h` 可以看参数，例如 `python -m lab.cli loop -h`。

---

## 4. 那些数字是什么意思

用 `loop` 的输出举例：

```
训练前留出分数：-4.495   ← 还没学时，它在"没见过的地图"上的得分
训练后留出分数：+2.200   ← 学完之后，同一批地图上的得分
变化 +6.695 → 保留新策略 ← 变好了才保留，变差会回滚到旧策略
BFS 基线 +3.565          ← 一个手写的笨规则在同一批地图上的得分
```

**四个词**：

- **留出分数**：在一批**训练时从没见过**的地图上考出来的分数。只有这个分数能说明"它变强了"。
- **训练分数**：训练时见过的地图上的分数。**这个数字再高也没意义**，等于背答案。
- **BFS 基线**：人类写死的"朝最近食物走"的规则。至今它还比学出来的强，见第 5 节。
- **回滚**：学完变差了，就把新学的东西扔掉，恢复上次的。所以它不会越练越差。

**分数的组成**：吃到食物 +1、踩到危险 −1、每步 −0.01、靠近食物 +0.1×距离。

---

## 5. 现在它能到什么程度（诚实版）

我按"能不能超过手写规则"做了实验，结果写在 `docs/experiments/0001-learnability.md`：

| 阶段 | 分数 |
|---|---|
| 完全不学 | −4.5（乱撞，受伤 103 次） |
| 学 3 轮后（表格） | **+2.2**（受伤降到 17 次） |
| 学 6 轮后（线性） | +2.3（换算法也没超过） |
| 手写规则 | **+3.6** |

**注意**：上面是普通任务（危险区只扣分）。把危险区改成致命（`--lethal`）后结论反过来了：
学习器 **1.78**，手写规则 **0.69**（2.58 倍，见实验 0004）。

**结论**：普通任务上追不上手写规则；致命任务上它赢了，因为手写规则根本不知道疼。
我试过给它加"看得见墙"的能力，结果更差（状态爆炸），所以撤回了。

**我没有做的事**：调参数把数字弄好看。这条写进了文档，任何人都能复算上面每一个数字。

**下一步的判据**（我先立flag）：留出分数连续 3 轮 ≥ 3.565 才算追上；做不到就换方法。

---

## 6. 出错了怎么办

| 你看到的 | 什么意思 | 怎么办 |
|---|---|---|
| `ModuleNotFoundError: lab` | 不在项目文件夹里 | `cd` 到有 `lab` 文件夹的那一层 |
| `[FAIL] layout` | 文件不全 | 重新下载 ZIP，别只拷一半 |
| `[FAIL] python` | Python 太旧 | 装 3.10 以上 |
| `上一轮还没评审` | 上一轮没打分就想再跑 | `python -m lab.cli review --pass` |
| `预算闸门拦截`（退出码 3） | 超过步数上限 | 改 `lab.config.json` 的 `steps_per_day`，或减少 `--steps` |
| `状态 FROZEN` | 被冻结了 | `python -m lab.cli unfreeze --by 你的名字` |
| 中文变乱码 | Windows 终端编码 | `chcp 65001` 后再跑 |
| `git` 推不上去 | 网络/代理 | 见 `docs/publish.md` 第 10 节 |

**万能一条**：先跑 `python -m lab.cli doctor`，它会把问题指到具体文件。

---

## 7. 你的数据在哪

全部在 `state/` 文件夹里（不进 git，删了就从头开始）：

| 文件 | 是什么 | 能删吗 |
|---|---|---|
| `ledger.jsonl` | 所有事情的流水账（防篡改） | ❌ 删了就没有审计 |
| `state.json` | 现在跑到哪一步 | ❌ |
| `self.json` | 它对自己的描述 | ⚠️ 删了等于失忆 |
| `knowledge.jsonl` | 收来的资料（待验证的声明） | ❌ |
| `policy.json` | 它学到的策略参数 | ✅ 删了等于重新学 |
| `reports/` | 周报、对比报告 | ✅ |

**备份**：整个 `state/` 文件夹复制走就行。
**重来**：删掉 `state/`，重跑 `python -m lab.cli init`。

---

## 8. 不会写代码也能参与

| 你能做的 | 怎么做 |
|---|---|
| 报告"我看不懂这里" | 开 Issue，标 `docs` |
| 提一个你想验证的问题 | 开 Issue，用"任务"模板，写清判据 |
| 跑一次评测并把结果贴出来 | 跑 `python -m lab.cli eval`，把输出粘到 Issue |
| 记录一次失败 | `docs/experiments/` 里加一份，格式照抄 0001 |
| 纠错 | 任何一个数字不对，直接说，我改 |

**不需要**：会 Python、有显卡、懂机器学习。

---

## 9. 一页速查

```powershell
python -m lab.cli doctor                 # 自检，出问题先跑这个
python -m lab.cli init                   # 第一次用
python -m lab.cli run --steps 20         # 跑一轮（会停在评审）
python -m lab.cli review --pass --by 我   # 评审通过
python -m lab.cli loop --cycles 3        # 训练 + 考试（核心功能）
python -m lab.cli eval                   # 只考试
python -m lab.cli self                   # 它对自己的描述
python -m lab.cli learn                  # 收资料（离线样本）
python -m lab.cli knowledge list          # 看资料库
python -m lab.cli inbox                  # 有没有事等我处理
python -m lab.cli verify                 # 账本有没有被改过
```

**看不明白任何一处，都可以只跑第一条命令（doctor），然后把输出发给维护者。**
