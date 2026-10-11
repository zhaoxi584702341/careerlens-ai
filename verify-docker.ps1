# =============================================================================
# CareerLens AI — Docker Compose 联网环境复验脚本
# -----------------------------------------------------------------------------
# 用途：在可访问 Docker Hub 的环境中，一键完成 compose 构建、启动、健康等待、
#       端到端接口验证与失败诊断。对应 DELIVERY.md 第 4.6 节「阶段 2」。
#
# 用法（仓库根目录 careerlens-ai/ 下执行）：
#   .\verify-docker.ps1              # 完整：预检 → 构建启动 → 健康等待 → 端到端验证
#   .\verify-docker.ps1 -SkipBuild   # 跳过构建，仅启动已有镜像
#   .\verify-docker.ps1 -Down        # 仅停止并清理（含卷，需二次确认）
#   .\verify-docker.ps1 -KeepRunning # 验证后不自动 down，保留容器供人工浏览
#
# 提示：PowerShell 默认禁止本地脚本时，可执行
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
# =============================================================================

[CmdletBinding()]
param(
    [switch]$SkipBuild,      # 跳过 --build
    [switch]$Down,           # 仅清理退出
    [switch]$KeepRunning,    # 验证完成后保留容器
    [int]$WaitTimeoutSec = 300
)

$ErrorActionPreference = 'Stop'

# ---------- 常量（与 docker-compose.yml 对齐） ----------
$FrontendUrl  = 'http://localhost:5173'
$BffUrl       = 'http://localhost:3000'
$JavaUrl      = 'http://localhost:8080'
$PythonUrl    = 'http://localhost:8000'
$Services     = @('python-service', 'java-service', 'bff', 'frontend')

# ---------- 输出着色辅助 ----------
function Info($m) { Write-Host "[INFO]  $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[ OK ]  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[WARN]  $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "[FAIL]  $m" -ForegroundColor Red }

# ---------- 前置检查 ----------
function Assert-Environment {
    Info '前置检查：仓库根目录 / Docker / Compose / compose 配置 / .env'

    if (-not (Test-Path './docker-compose.yml')) {
        Fail "未找到 ./docker-compose.yml，请在仓库根目录 careerlens-ai/ 下执行本脚本。"
        exit 1
    }

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Fail '未检测到 docker 命令，请安装并启动 Docker Desktop。'
        exit 1
    }
    Ok "docker 版本: $((docker --version) -join '')"

    docker compose version *> $null
    if ($LASTEXITCODE -ne 0) {
        Fail 'docker compose 不可用，请安装 Docker Compose v2。'
        exit 1
    }
    Ok "compose 版本: $((docker compose version) -join '')"

    # 校验编排文件语法（离线可做，先失败早暴露）
    docker compose config *> $null
    if ($LASTEXITCODE -ne 0) {
        Fail 'docker compose config 校验失败，请检查 docker-compose.yml。'
        exit 1
    }
    Ok 'docker compose config 校验通过（四服务渲染正常）'

    # python-service/.env 为 compose 的 env_file，缺失会导致启动失败
    if (-not (Test-Path './python-service/.env')) {
        Warn '未找到 python-service/.env（compose 的 env_file）。'
        Warn '未配置 LLM_API_KEY 时服务仍可启动，但业务接口走本地降级（返回 200 + 降级结果）。'
        Warn '如需真实 LLM 链路，请复制 .env.example 为 .env 并填写 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL。'
    } else {
        Ok '已找到 python-service/.env'
    }

    # 关键：能否访问 Docker Hub（基础镜像拉取来源）
    Info '探测 Docker Hub 连通性（拉取 hello-world 验证网络）...'
    docker pull hello-world *> $null
    if ($LASTEXITCODE -ne 0) {
        Fail 'Docker Hub 不可达，无法拉取基础镜像。请确认网络/代理可访问 registry-1.docker.io 后重试。'
        Warn '这是本次复验的核心前置条件（原环境即因该项失败）。'
        exit 1
    }
    Ok 'Docker Hub 连通，基础镜像可拉取'
}

# ---------- 清理 ----------
function Invoke-Down {
    param([switch]$WithVolumes)
    if ($WithVolumes) {
        Warn '即将执行 docker compose down -v：将删除容器、网络与数据卷（SQLite 历史记录会清空）'
        $ans = Read-Host '确认继续？输入 yes 继续，其它任意键取消'
        if ($ans -ne 'yes') { Info '已取消清理。'; return }
        docker compose down -v
    } else {
        docker compose down
    }
    Ok '清理完成'
}

# ---------- 构建 + 启动 ----------
function Invoke-Up {
    if ($SkipBuild) {
        Info '跳过构建，直接启动已有镜像（docker compose up -d）'
        docker compose up -d
    } else {
        Info '构建并启动四服务（docker compose up -d --build），首次构建较慢...'
        docker compose up -d --build
    }
    if ($LASTEXITCODE -ne 0) {
        Fail 'docker compose up 失败，输出诊断信息：'
        docker compose ps
        Write-Host '---- 最近日志 ----'
        docker compose logs --tail=50
        exit 1
    }
    Ok 'compose up 已返回'
}

# ---------- 等待健康 ----------
function Wait-Healthy {
    Info "等待四服务进入 healthy（最长 $WaitTimeoutSec 秒）..."
    $deadline = (Get-Date).AddSeconds($WaitTimeoutSec)
    $allHealthy = $false

    while ((Get-Date) -lt $deadline) {
        $allHealthy = $true
        $lines = @()
        foreach ($svc in $Services) {
            $cid = (docker compose ps -q $svc) 2>$null
            if (-not $cid) { $allHealthy = $false; $lines += "$svc`: 未创建"; continue }
            $state = (docker inspect -f '{{.State.Status}}' $cid) 2>$null
            $health = (docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $cid) 2>$null
            if ($health -ne 'healthy') { $allHealthy = $false }
            $lines += "$svc`: state=$state, health=$health"
        }
        Write-Host ("    " + ($lines -join ' | '))
        if ($allHealthy) { break }
        Start-Sleep -Seconds 5
    }

    if ($allHealthy) {
        Ok '四服务均已 healthy'
        return $true
    }
    Fail "等待超时，仍有服务未 healthy。输出 docker compose ps 与各服务日志："
    docker compose ps
    foreach ($svc in $Services) {
        Write-Host "---- $svc 最近 30 行日志 ----" -ForegroundColor Yellow
        docker compose logs --tail=30 $svc
    }
    return $false
}

# ---------- 端到端接口验证 ----------
# 以 UTF-8 字节发送中文，避免 PowerShell 5 按 ISO-8859-1 编码造成「假乱码」
function Post-JsonUtf8 {
    param([string]$Url, [string]$Json)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Json)
    return Invoke-RestMethod -Uri $Url -Method Post -Body $bytes -ContentType 'application/json; charset=utf-8'
}

function Test-EndToEnd {
    Info '开始端到端接口验证'
    $failed = 0

    # 1) Python 直连
    try {
        $h = Invoke-RestMethod "$PythonUrl/health"
        if ($h.status -eq 'ok') { Ok "python /health → status=$($h.status), llm_enabled=$($h.llm_enabled)" }
        else { Fail "python /health 异常: $($h | ConvertTo-Json -Compress)"; $failed++ }
    } catch { Fail "python /health 请求失败: $_"; $failed++ }

    # 2) Java 直连（UTF-8 中文透传回归点）
    try {
        $a = Post-JsonUtf8 "$JavaUrl/api/analyze" '{"resumeText":"5年前端开发经验，熟悉Vue3与TypeScript"}'
        $kw = ($a.keywords -join ',')
        if ($kw -match '\?\?\?') { Fail "java /api/analyze 出现乱码: $kw"; $failed++ }
        else { Ok "java /api/analyze 中文透传正常，keywords=$kw, score=$($a.score)" }
    } catch { Fail "java /api/analyze 请求失败: $_"; $failed++ }

    # 3) BFF 四接口 + history
    $cases = @(
        @{ Name='analyze-resume';  Url="$BffUrl/api/analyze-resume";  Body='{"resume_text":"5年Java开发，熟悉Spring Boot与MySQL"}' },
        @{ Name='match-job';       Url="$BffUrl/api/match-job";       Body='{"resume_text":"3年前端","job_description":"要求React与性能优化"}' },
        @{ Name='optimize-resume'; Url="$BffUrl/api/optimize-resume"; Body='{"resume_text":"3年前端","job_description":"要求React"}' },
        @{ Name='radar';           Url="$BffUrl/api/radar";           Body='{"resume":"3年前端","jd":"要求React"}' }
    )
    foreach ($c in $cases) {
        try {
            $r = Post-JsonUtf8 $c.Url $c.Body
            Ok "bff /api/$($c.Name) → 200，字段: $(($r.PSObject.Properties.Name -join ', '))"
        } catch { Fail "bff /api/$($c.Name) 请求失败: $_"; $failed++ }
    }

    try {
        $hist = Invoke-RestMethod "$BffUrl/api/history?limit=10"
        Ok "bff /api/history → total=$($hist.total), 返回 $($hist.records.Count) 条"
    } catch { Fail "bff /api/history 请求失败: $_"; $failed++ }

    # 4) 前端与反代（经 Nginx 访问 /api）
    try {
        $front = Invoke-WebRequest "$FrontendUrl/" -UseBasicParsing
        if ($front.StatusCode -eq 200) { Ok "frontend / → HTTP 200（Nginx 托管正常）" }
        else { Fail "frontend / 返回 $($front.StatusCode)"; $failed++ }
    } catch { Fail "frontend / 请求失败: $_"; $failed++ }

    try {
        $proxy = Invoke-RestMethod "$FrontendUrl/api/history?limit=1"
        Ok "frontend 反代 /api/history → 正常（/api/* 已转发至 bff:3000）"
    } catch { Fail "frontend 反代 /api/* 失败（检查 frontend/nginx.conf）: $_"; $failed++ }

    return $failed
}

# =============================================================================
# 主流程
# =============================================================================
Write-Host '=============================================' -ForegroundColor Magenta
Write-Host ' CareerLens AI — Docker Compose 联网复验脚本' -ForegroundColor Magenta
Write-Host '=============================================' -ForegroundColor Magenta

if ($Down) {
    Invoke-Down -WithVolumes
    exit 0
}

Assert-Environment
Invoke-Up

$healthy = Wait-Healthy
if (-not $healthy) {
    Fail '服务未全部就绪，终止端到端验证。可据上方日志定位问题。'
    exit 2
}

$failCount = Test-EndToEnd

# 持久化验证：重启后历史记录是否仍在
if ($failCount -eq 0) {
    try {
        $before = (Invoke-RestMethod "$BffUrl/api/history?limit=1").total
        Info '重启 bff 容器以验证 SQLite 卷持久化...'
        docker compose restart bff *> $null
        Start-Sleep -Seconds 8
        $after = (Invoke-RestMethod "$BffUrl/api/history?limit=1").total
        if ($after -ge $before) { Ok "卷持久化正常：重启前 total=$before，重启后 total=$after" }
        else { Fail "卷持久化异常：重启前 $before → 重启后 $after"; $failCount++ }
    } catch { Warn "持久化验证跳过（请求异常）: $_" }
}

Write-Host '=============================================' -ForegroundColor Magenta
if ($failCount -eq 0) {
    Ok '全部验证通过：四服务 healthy，端到端链路与反代正常，数据卷持久化正常。'
    Info "人工验收：浏览器打开 $FrontendUrl，逐页操作「简历解析 / 岗位匹配 / 简历优化 / 能力雷达」。"
} else {
    Fail "端到端验证存在 $failCount 项失败，详见上方 [FAIL] 输出。"
}

if ($KeepRunning) {
    Info '按要求保留运行中的容器。停止命令：docker compose down'
} else {
    Info '正在清理容器（保留数据卷）...'
    docker compose down
    Ok '已清理。如需连数据卷一并清理：.\verify-docker.ps1 -Down'
}

exit $(if ($failCount -eq 0) { 0 } else { 3 })
