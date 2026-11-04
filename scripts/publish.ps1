# 一键发布（Windows PowerShell）。等价于 docs/publish.md 的第 0 + 3 步。
# 用法：右键"使用 PowerShell 运行"，或在仓库目录执行  .\scripts\publish.ps1
# 认证：首次推送会弹出 Git Credential Manager 的浏览器登录，登录你的 GitHub 账号即可。
# 注意：不做 force push；已存在的 commit 不会被改写。

param(
    [switch]$SkipPreflight
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== 1/4 预检 ==" -ForegroundColor Cyan
if (-not $SkipPreflight) {
    python scripts/preflight.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "预检未通过，已停止（没有推送任何东西）。" -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "已跳过预检（-SkipPreflight）" -ForegroundColor Yellow
}

Write-Host "== 2/4 检查 remote ==" -ForegroundColor Cyan
$remote = git remote get-url origin 2>$null
if (-not $remote) {
    Write-Host "没有 origin。先执行：" -ForegroundColor Red
    Write-Host '  git remote add origin https://github.com/xiaoyu123-xiao/open-functional-self-lab.git'
    exit 1
}
Write-Host "origin = $remote"

$dirty = git status --porcelain
if ($dirty) {
    Write-Host "工作区不干净，先提交或还原：" -ForegroundColor Red
    git status --short
    exit 1
}

# 很多人装过代理软件，关闭后系统里仍留着 HTTP_PROXY / HTTPS_PROXY 之类的环境变量，
# git 会去连一个死端口，甚至解析不了域名（Could not resolve host）。
# 处理方式：不改你的系统设置，只在本次 git 调用上加 `-c http.proxy=` 强制直连。
# 注意：不能枚举 Env: 提供程序——环境里同时存在 HTTP_PROXY 与 http_proxy 时它会直接抛异常。
$proxyHint = @()
foreach ($name in @('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY')) {
    $value = [System.Environment]::GetEnvironmentVariable($name)
    if ($value) { $proxyHint += "$name=$value" }
}
if ($proxyHint.Count -gt 0) {
    Write-Host "检测到代理环境变量（本次推送强制直连，不改系统设置）：$($proxyHint -join '; ')" -ForegroundColor Yellow
}

Write-Host "== 3/4 探测能否访问仓库 ==" -ForegroundColor Cyan
$probe = git -c http.proxy= -c https.proxy= ls-remote --exit-code $remote 2>&1
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 2) {
    Write-Host "连不上 $remote" -ForegroundColor Red
    Write-Host ($probe | Out-String)
    Write-Host "排查顺序（docs/publish.md 第 10 节）："
    Write-Host "  1. 仓库地址是否正确、是否已在网页建好（空仓库也算建好）"
    Write-Host "  2. 浏览器能打开 https://github.com 吗？打不开就是网络/代理问题"
    Write-Host "  3. 如果你在用代理软件，请确认它正在运行；或临时关闭系统代理再试"
    exit 1
}
Write-Host "可以访问（空仓库会返回 2，属正常；0 表示已有提交）"

Write-Host "== 4/4 推送 main 和 tag ==" -ForegroundColor Cyan
git -c http.proxy= -c https.proxy= push -u origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "推送失败。常见原因：认证被取消 / 网络抖动 / 远端已有提交。见 docs/publish.md 第 10 节。" -ForegroundColor Red
    exit 1
}

$tag = git describe --tags --abbrev=0
git -c http.proxy= -c https.proxy= push origin $tag
if ($LASTEXITCODE -ne 0) {
    Write-Host "tag 推送失败（main 已推上去）。手动重试：git -c http.proxy= -c https.proxy= push origin $tag" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "完成。接下来："
if ($remote -like "http*") {
    Write-Host "  1. 打开 $($remote -replace '\.git$','')/actions  确认 4 个 job 全绿"
}
else {
    Write-Host "  1. 打开仓库页的 Actions 确认 4 个 job 全绿（当前 remote 不是 http 地址，跳过自动拼接）"
}
Write-Host "  2. Settings → Branches → 保护 main（1 个 approve + status checks）"
Write-Host "  3. Releases → Draft a new release → 选 $tag"
Write-Host "  4. python scripts/seed_issues.py   # 建 19 个 Issue（需 gh）"
