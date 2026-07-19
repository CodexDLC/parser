Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:UV_CACHE_DIR = Join-Path $repoRoot ".uv-cache"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Push-Location $repoRoot
try {
    Invoke-Checked { uv sync --extra dev } "Dependency sync"
    Invoke-Checked { docker compose config --quiet } "Docker Compose validation"
    Invoke-Checked { docker compose up -d --wait postgres redis } "Infrastructure startup"
    Invoke-Checked { uv run ruff check src tests } "Ruff"
    Invoke-Checked { uv run mypy src/aibot tests } "Mypy"
    Invoke-Checked { uv run pytest --require-infrastructure } "Pytest"
    Invoke-Checked { uv run python -c "from aibot.main import app; assert app" } "App import"
    Invoke-Checked { docker compose ps } "Infrastructure status"
}
finally {
    Pop-Location
}
