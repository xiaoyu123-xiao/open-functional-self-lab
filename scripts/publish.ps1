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

Write-Host "== 3/4 推送 main ==" -ForegroundColor Cyan
git push -u origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "推送失败。常见原因：仓库还没建 / 网络 / 认证被取消。见 docs/publish.md 第 10 节。" -ForegroundColor Red
    exit 1
}

Write-Host "== 4/4 推送 tag ==" -ForegroundColor Cyan
$tag = git describe --tags --abbrev=0
git push origin $tag
if ($LASTEXITCODE -ne 0) {
    Write-Host "tag 推送失败（main 已推上去）。手动重试：git push origin $tag" -ForegroundColor Yellow
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
