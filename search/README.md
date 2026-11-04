# 检索（白名单）

> 状态：v0.1 **没有联网代码**。本文件是 Issue 0011 的规范与验收依据。

## 1. 允许

| 源 | 端点 | 用途 | 注意 |
|---|---|---|---|
| arXiv | `export.arxiv.org/api/query` | 预印本 | 遵守 3 秒间隔，不批量镜像 |
| OpenAlex | `api.openalex.org` | 开放元数据 | CC0，但需署名来源 |
| Semantic Scholar | `api.semanticscholar.org` | 跨领域 | 免费额度有限，429 要退避 |
| PubMed E-utilities | `eutils.ncbi.nlm.nih.gov` | 生物医学 | 高频需 API key |
| GitHub API | `api.github.com` | 仅公开仓库只读 | 不要拿它做代码搜索的替代品 |

## 2. 禁止

- 任意网页抓取、绕过登录/付费墙、模拟登录、自动注册。
- 抓取个人隐私、通讯录、任何凭证类端点。
- 白名单外域名：**拒绝并记录，不重试**。
- 把抓到的全文存进仓库（版权 + 体积）。只存：引用、摘要、URL、访问时间。

## 3. 接口约定（Issue 0011 实现时照此写）

```python
search(query: str, sources: list[str], max_results: int) -> list[dict]
# 返回：[{"title", "url", "snippet", "source", "accessed_at"}]
# 失败：返回 []，并把原因写进账本（不允许抛异常静默吞掉）
```

## 4. 速率

| 项 | 默认 | 来源 |
|---|---|---|
| 单域名每分钟 | ≤10 | 各 API 条款取最严 |
| 全局并发 | ≤3 | 避免把自己打成爬虫 |
| 每日请求 | 200（`lab.config.json`） | 由 `lab/budget.py` 硬拦截 |
| 重试 | 指数退避，最多 3 次 | 429/5xx；4xx 不重试 |

预算闸门会先扣额度再发请求：`budget.charge("search_requests_per_day", 1)`。
超了直接抛 `BudgetExceeded` —— 不是"发到限额再停"，而是"发之前就知道不行"。

## 5. 失败模式

| 情况 | 行为 |
|---|---|
| 白名单外域名 | 拒绝 + 账本 `denied` 事件 + 告警（中） |
| 429 限流 | 退避重试；仍失败则本次降级为空 + 告警（低） |
| 解析失败 | 保留原始响应哈希，标记 `parse_failed`，不猜内容 |
| 预算耗尽 | 立即停止，返回已得结果，账本 `budget` 事件 |

## 6. 为什么默认离线

因为"能联网"是最容易被忽略的风险放大器：一个 bug 会变成对第三方站点的压力，
一个提示注入会变成数据外传。v0.1 刻意不含任何 `urllib.request` / `socket` 调用，
`lab lint` 也会拦下 `curl … | sh` 这类写法（见 `SECURITY.md`）。
