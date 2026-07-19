param(
    [switch]$KeepStack
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$projectName = "m4_container_acceptance"
$envFile = ".env.example"

$env:APP_ENV_FILE = $envFile
$env:APP_IMAGE_TAG = "acceptance"
$env:API_BIND_PORT = "58000"
$env:POSTGRES_DB = "m4"
$env:POSTGRES_USER = "m4"
$env:POSTGRES_PASSWORD = "m4"
$env:CONTAINER_DATABASE_URL = "postgresql+asyncpg://m4:m4@postgres:5432/m4"
$env:CONTAINER_REDIS_URL = "redis://redis:6379/0"
$env:COMPOSE_BAKE = "false"

function Invoke-Compose {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & docker compose --project-name $projectName --env-file $envFile @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

Push-Location $repoRoot
try {
    Invoke-Compose @("config", "--quiet")
    & docker build --tag "m4-aibot:acceptance" .
    if ($LASTEXITCODE -ne 0) {
        throw "docker build failed with exit code $LASTEXITCODE"
    }
    Invoke-Compose @("up", "-d", "--wait", "--wait-timeout", "60", "postgres", "redis")
    Invoke-Compose @("up", "--no-log-prefix", "migrate")
    Invoke-Compose @(
        "up",
        "-d",
        "--no-deps",
        "--wait",
        "--wait-timeout",
        "60",
        "api",
        "worker"
    )
    Invoke-Compose @("up", "-d", "--no-deps", "beat")

    $health = Invoke-RestMethod -Uri "http://127.0.0.1:58000/api/health"
    if ($health.status -ne "ok") {
        throw "API healthcheck returned an unexpected status"
    }

    Invoke-Compose @(
        "exec",
        "-T",
        "api",
        "python",
        "-c",
        "import os; from pathlib import Path; assert os.geteuid() != 0; assert not Path('/app/.env').exists()"
    )
    Invoke-Compose @("run", "--rm", "--no-deps", "migrate", "alembic", "current")
    Invoke-Compose @(
        "exec",
        "-T",
        "worker",
        "celery",
        "-A",
        "celery_worker.celery_app",
        "inspect",
        "ping",
        "--timeout",
        "5"
    )
    Invoke-Compose @("ps")
}
catch {
    & docker compose --project-name $projectName --env-file $envFile ps
    & docker compose --project-name $projectName --env-file $envFile logs `
        --no-color --tail 100 api worker beat migrate
    throw
}
finally {
    if (-not $KeepStack) {
        & docker compose --project-name $projectName --env-file $envFile down `
            --volumes --remove-orphans
    }
    Pop-Location
}
