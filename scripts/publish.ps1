# 一键发布（Windows PowerShell）。等价于 docs/publish.md 的第 0 + 3 步。
# 用法：双击仓库根目录的 publish.bat，或  .\scripts\publish.ps1
# 认证：首次推送会弹出浏览器登录 GitHub（Git Credential Manager）。GitHub 不接受密码。
# 安全：不改系统设置、不 force push、不重写已推送的历史。

param(
    [switch]$SkipPreflight
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Info($message) { Write-Host $message -ForegroundColor Cyan }
function Warn($message) { Write-Host $message -ForegroundColor Yellow }
function Fail($message) { Write-Host $message -ForegroundColor Red }

Info "== 1/4 预检 =="
if (-not $SkipPreflight) {
    python scripts/preflight.py
    if ($LASTEXITCODE -ne 0) {
        Fail "预检未通过，没有推送任何东西。"
        exit 1
    }
}
else {
    Warn "已跳过预检（-SkipPreflight）"
}

Info "== 2/4 检查 remote 与工作区 =="
$remote = git remote get-url origin 2>$null
if (-not $remote) {
    Fail "没有 origin，先执行："
    Write-Host '  git remote add origin https://github.com/xiaoyu123-xiao/open-functional-self-lab.git'
    exit 1
}
Write-Host "origin = $remote"

if (git status --porcelain) {
    Fail "工作区不干净，先提交或还原："
    git status --short
    exit 1
}

# 只在本次脚本及其子进程里清掉代理变量，不改系统设置。
# 背景：代理软件关掉后，这些变量仍指向一个空端口，会让 git 和 GCM 双双失败。
foreach ($name in @('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy')) {
    if ([Environment]::GetEnvironmentVariable($name)) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }
}
# 认证失败时不要退化成"输入密码"——那只会得到 Invalid username or token。
$env:GIT_TERMINAL_PROMPT = '0'

Info "== 3/4 选择网络路径 =="
# 顺序：先试系统代理（大多数人靠它上网），不通再试直连。两种都用同一段只读探测，
# 不写任何配置、不改系统设置。
$settings = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
$candidates = @()
if ($settings -and $settings.ProxyEnable -eq 1 -and $settings.ProxyServer) {
    $candidates += @{ Name = "系统代理 $($settings.ProxyServer)"; Args = @('-c', "http.proxy=http://$($settings.ProxyServer)", '-c', "https.proxy=http://$($settings.ProxyServer)") }
}
$candidates += @{ Name = '直连'; Args = @('-c', 'http.proxy=', '-c', 'https.proxy=') }

$proxyArgs = $null
foreach ($candidate in $candidates) {
    git @($candidate.Args) ls-remote --exit-code $remote > $null 2>&1
    if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq 2) {
        $proxyArgs = $candidate.Args
        Write-Host "可用路径：$($candidate.Name)（空仓库返回 2 属正常）"
        break
    }
    Warn "$($candidate.Name) 连不上，换下一条"
}

if (-not $proxyArgs) {
    Fail "所有路径都连不上 $remote"
    Write-Host "排查顺序："
    Write-Host "  1. 仓库地址是否正确、网页上是否已建好（空仓库也算建好）"
    Write-Host "  2. 浏览器能打开 https://github.com 吗？打不开是网络/代理问题"
    Write-Host "  3. 设置 → 网络和 Internet → 代理，确认代理软件在运行、端口正确"
    exit 1
}

Info "== 4/4 推送 main 和 tag =="
git @proxyArgs push -u origin main
if ($LASTEXITCODE -ne 0) {
    Fail "推送失败。若是认证问题：GitHub 不支持密码登录，请完成浏览器弹窗里的登录后重试。"
    Fail "若弹窗没有出现，先运行  git credential-manager configure  再重试。"
    exit 1
}

$tag = git describe --tags --abbrev=0
git @proxyArgs push origin $tag
if ($LASTEXITCODE -ne 0) {
    Warn "tag 推送失败（main 已推上去）。手动重试：git push origin $tag"
    exit 1
}

Write-Host ""
Write-Host "完成。接下来："
if ($remote -like "http*") {
    Write-Host "  1. 打开 $($remote -replace '\.git$','')/actions  确认 4 个 job 全绿"
}
else {
    Write-Host "  1. 打开仓库页的 Actions 确认 4 个 job 全绿"
}
Write-Host "  2. Settings → Branches → 保护 main（1 个 approve + status checks）"
Write-Host "  3. Releases → Draft a new release → 选 $tag"
Write-Host "  4. python scripts/seed_issues.py   # 建 19 个 Issue（需 gh）"
