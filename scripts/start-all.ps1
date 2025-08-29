param(
    [int]$BackendPort = 8010,
    [int]$FrontendPort = 8000,
    [string]$ListenHost = "127.0.0.1",
    [switch]$Reload,
    [switch]$StartDocker
)

$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERR ] $msg" -ForegroundColor Red }

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot    = Resolve-Path (Join-Path $ScriptDir "..")
$DockerDir   = Join-Path $RepoRoot "infra\docker"
$ServerDir   = Join-Path $RepoRoot "server"
$FrontendDir = Join-Path $RepoRoot "frontend"
$VenvDir     = Join-Path $RepoRoot ".venv"
$Activate    = Join-Path $VenvDir "Scripts\Activate.ps1"

function Kill-Port {
    param([int]$Port)
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        if ($null -ne $conns) {
            $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
            foreach ($procId in $pids) {
                Write-Warn "Killing process PID=$procId bound to port $Port"
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        } else {
            Write-Info "No process currently bound to port $Port"
        }
    } catch {
        Write-Warn ("Unable to inspect/kill port {0}: {1}" -f $Port, $_)
    }
}

function Ensure-DockerVehiclesDB {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Warn "Docker CLI is not installed or not in PATH. Skipping DB container startup."
        return
    }
    if (-not (Test-Path $DockerDir)) {
        Write-Warn "Docker directory not found: $DockerDir. Skipping Docker startup."
        return
    }
    try {
        $container = docker ps -a --filter "name=vehicles-db" --format '{{.ID}} {{.Status}}'
        $needsStart = $true
        if ($container) {
            $status = ($container -split ' ',2)[1]
            if ($status -match 'Up') { $needsStart = $false }
        }
        if ($needsStart) {
            Write-Info "Starting Docker Compose (vehicles DB)"
            Push-Location $DockerDir
            docker compose up -d | Out-Null
            Pop-Location
        } else {
            Write-Info "Docker container 'vehicles-db' already running"
        }
        # Wait for healthy
        Write-Info "Waiting for 'vehicles-db' to be healthy..."
        $maxWait = 60
        $elapsed = 0
        while ($true) {
            $health = docker inspect --format '{{.State.Health.Status}}' vehicles-db 2>$null
            if ($health -eq 'healthy') { Write-Info "vehicles-db is healthy"; break }
            Start-Sleep -Seconds 2
            $elapsed += 2
            if ($elapsed -ge $maxWait) { Write-Warn "Timed out waiting for vehicles-db to be healthy"; break }
        }
    } catch {
        Write-Warn "Docker startup check failed: $_"
    }
}

function Backend-CommandString {
    param([string]$BHost, [int]$Port, [bool]$ReloadFlag)
    $reloadArg  = if ($ReloadFlag) { '--reload' } else { '' }
    $reloadText = if ($ReloadFlag) { 'True' } else { 'False' }
    @"
`$ErrorActionPreference = 'Stop'
function Info([string]`$m){ Write-Host "[INFO] `$m" -ForegroundColor Cyan }
Info "Activating venv and installing server deps"
if (-not (Test-Path "$VenvDir")) { python -m venv "$VenvDir" }
. "$Activate"
`$packages = @(
  'fastapi','uvicorn[standard]','pydantic','pydantic-settings','sqlalchemy','alembic',
  'cryptography','python-multipart','python-jose[cryptography]','passlib[bcrypt]',
  'httpx','tenacity','openai','psycopg2-binary'
)
pip install --disable-pip-version-check --quiet @packages | Out-Null
Set-Location "$ServerDir"
Write-Host "[INFO] Starting FastAPI at $env:TTDB_URL reload=$env:TTDB_RELOAD"
uvicorn app.main:app --host $BHost --port $Port $reloadArg
"@
}

function Frontend-CommandString {
    param([int]$Port)
    @"
`$ErrorActionPreference = 'Stop'
function Info([string]`$m){ Write-Host "[INFO] `$m" -ForegroundColor Cyan }
Set-Location "$FrontendDir"
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Write-Host "Node.js not found" -ForegroundColor Red; Read-Host; exit }
if (-not (Test-Path (Join-Path "$FrontendDir" 'node_modules'))) { Info 'Installing frontend deps'; npm install --no-audit --no-fund }
Info "Starting Next.js at http://localhost:$Port"
npm run dev -- -p $Port
"@
}

try {
    Write-Info "Repository root: $RepoRoot"

    # Ensure Docker DB
    Ensure-DockerVehiclesDB

    # Proactively free ports before launching services
    Kill-Port -Port $BackendPort
    Kill-Port -Port $FrontendPort

    Write-Info "Launching backend window..."
    # Pass URL/reload via environment so child block logging is safe
    $env:TTDB_URL = "http://$ListenHost`:$BackendPort"
    $env:TTDB_RELOAD = if ($Reload.IsPresent) { 'True' } else { 'False' }

    $backendCmd = Backend-CommandString -BHost $ListenHost -Port $BackendPort -ReloadFlag:$($Reload.IsPresent)
    $backendProc = Start-Process powershell -PassThru -ArgumentList @('-NoExit','-ExecutionPolicy','Bypass','-Command', $backendCmd)

    Write-Info "Launching frontend window..."
    $frontendCmd = Frontend-CommandString -Port $FrontendPort
    $frontendProc = Start-Process powershell -PassThru -ArgumentList @('-NoExit','-ExecutionPolicy','Bypass','-Command', $frontendCmd)

    Write-Host ""
    Write-Info "Backend:  http://${ListenHost}:$BackendPort"
    Write-Info "Frontend: http://localhost:$FrontendPort"
    Write-Warn "Ensure frontend proxy in frontend/next.config.js points to http://${ListenHost}:$BackendPort (already set)."

    Write-Host ""
    Write-Info "Waiting for child windows to close (backend PID=$($backendProc.Id), frontend PID=$($frontendProc.Id))..."
    Wait-Process -Id $backendProc.Id,$frontendProc.Id

    Write-Host ""
    Write-Warn "Press ENTER to close this window"
    Read-Host | Out-Null
}
catch {
    Write-Err "Startup failed: $_"
    Write-Host ""; Write-Warn "Press ENTER to close this window"
    Read-Host | Out-Null
}
