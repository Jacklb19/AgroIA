<#
  Tareas de desarrollo de AgroIA (Windows / PowerShell). Un comando por tarea:

    .\scripts\tasks.ps1 setup      Crea el venv, instala dependencias, levanta Postgres (Docker), migra y siembra datos de EJEMPLO
    .\scripts\tasks.ps1 db-up      Levanta el Postgres local            (db-down lo apaga; db-reset borra sus datos)
    .\scripts\tasks.ps1 migrate    Aplica las migraciones a la base configurada en .env
    .\scripts\tasks.ps1 seed       Vuelve a sembrar datos de ejemplo en la base LOCAL (borra lo que hubiera)
    .\scripts\tasks.ps1 dev        Web en modo desarrollo contra la base local (http://localhost:3000)
    .\scripts\tasks.ps1 test       ruff + pytest (incluye las pruebas con base de datos, contra la base local de pruebas)
    .\scripts\tasks.ps1 lint       Solo ruff
    .\scripts\tasks.ps1 e2e        Build de la web + humo E2E con Playwright (usa el Chrome instalado)
    .\scripts\tasks.ps1 ingest     Un ciclo del job horario de precios contra la base configurada en .env
    .\scripts\tasks.ps1 status     Migraciones aplicadas y pendientes

  Las tareas locales (setup, seed, dev, test, e2e) NUNCA usan la base de .env: fuerzan el Postgres de Docker.
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet("setup", "db-up", "db-down", "db-reset", "migrate", "seed", "dev", "test", "lint", "e2e", "ingest", "status")]
    [string]$Tarea = "setup"
)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz

$Puerto = if ($env:AGROIA_DB_PORT) { $env:AGROIA_DB_PORT } else { "5432" }
$Py = Join-Path $Raiz "venv\Scripts\python.exe"

function Paso($texto) { Write-Host "`n==> $texto" -ForegroundColor Green }

function Invoke-Comando([string]$archivo, [string[]]$argumentos) {
    & $archivo @argumentos
    if ($LASTEXITCODE -ne 0) { throw "Fallo: $archivo $($argumentos -join ' ') (codigo $LASTEXITCODE)" }
}

# Variables que apuntan SOLO al Postgres local de Docker (tienen prioridad sobre .env).
function Usar-BaseLocal([string]$nombre = "agroia") {
    $env:SUPABASE_DB_HOST = "127.0.0.1"; $env:SUPABASE_DB_PORT = $Puerto; $env:SUPABASE_DB_NAME = $nombre
    $env:SUPABASE_DB_USER = "postgres";  $env:SUPABASE_DB_PASSWORD = "postgres"
    $env:DB_HOST = "127.0.0.1"; $env:DB_PORT = $Puerto; $env:DB_NAME = $nombre
    $env:DB_USER = "postgres";  $env:DB_PASSWORD = "postgres"; $env:DB_SSL = "disable"
}

function Asegurar-Venv {
    if (-not (Test-Path $Py)) {
        Paso "Creando el entorno virtual (venv)"
        Invoke-Comando "python" @("-m", "venv", "venv")
    }
}

function Levantar-Db {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker no esta instalado o no esta en el PATH." }
    Paso "Levantando Postgres 16 (Docker, puerto $Puerto)"
    $env:AGROIA_DB_PORT = $Puerto
    Invoke-Comando "docker" @("compose", "up", "-d", "db")
    for ($i = 0; $i -lt 30; $i++) {
        if (Docker-Silencioso @("compose", "exec", "-T", "db", "pg_isready", "-U", "postgres", "-d", "agroia")) { return }
        Start-Sleep -Seconds 2
    }
    throw "Postgres no respondio a tiempo. Revisa: docker compose logs db"
}

# Ejecuta docker sin que su stderr aborte el script; devuelve $true si termino bien.
function Docker-Silencioso([string[]]$argumentos) {
    $previo = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    try { & docker @argumentos *> $null; return ($LASTEXITCODE -eq 0) } finally { $ErrorActionPreference = $previo }
}

function Base-De-Pruebas {
    # Crea agroia_test si no existe (las pruebas con marca `db` recrean su esquema public).
    $previo = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    try {
        $existe = (& docker compose exec -T db psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='agroia_test'" 2>$null) -match "1"
    } finally { $ErrorActionPreference = $previo }
    if (-not $existe) { Invoke-Comando "docker" @("compose", "exec", "-T", "db", "psql", "-U", "postgres", "-c", "CREATE DATABASE agroia_test") }
    $env:TEST_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@127.0.0.1:$Puerto/agroia_test"
}

switch ($Tarea) {
    "setup" {
        Asegurar-Venv
        Paso "Instalando dependencias de Python (requirements-dev.txt)"
        Invoke-Comando $Py @("-m", "pip", "install", "-q", "-r", "requirements-dev.txt")
        Paso "Instalando dependencias de la web (npm ci)"
        Push-Location web; try { Invoke-Comando "npm" @("ci") } finally { Pop-Location }
        if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Se creo .env desde .env.example (completa tus claves cuando las necesites)." }
        Levantar-Db
        Usar-BaseLocal
        Paso "Migrando y sembrando datos de EJEMPLO (sinteticos, solo para ver la interfaz)"
        Invoke-Comando $Py @("scripts/seed_dev.py", "--reset", "--modelo")
        Write-Host "`nListo. Usa: .\scripts\tasks.ps1 dev" -ForegroundColor Green
    }
    "db-up"    { Levantar-Db }
    "db-down"  { Invoke-Comando "docker" @("compose", "down") }
    "db-reset" { Invoke-Comando "docker" @("compose", "down", "-v"); Levantar-Db }
    "migrate"  { Invoke-Comando $Py @("-m", "load.migrate") }
    "status"   { Invoke-Comando $Py @("-m", "load.migrate", "--status") }
    "seed" {
        Levantar-Db; Usar-BaseLocal
        Invoke-Comando $Py @("scripts/seed_dev.py", "--reset", "--modelo")
    }
    "dev" {
        Levantar-Db; Usar-BaseLocal
        Push-Location web
        try { Invoke-Comando "npm" @("run", "dev") } finally { Pop-Location }
    }
    "lint" { Invoke-Comando $Py @("-m", "ruff", "check", ".") }
    "test" {
        Levantar-Db; Base-De-Pruebas; Usar-BaseLocal "agroia_test"
        Invoke-Comando $Py @("-m", "ruff", "check", ".")
        Invoke-Comando $Py @("-m", "pytest", "-q")
    }
    "e2e" {
        Levantar-Db; Usar-BaseLocal
        Invoke-Comando $Py @("scripts/seed_dev.py", "--reset")
        Push-Location web
        try {
            Invoke-Comando "npm" @("run", "build")
            $env:E2E_CHANNEL = "chrome"
            Invoke-Comando "npm" @("run", "e2e")
        } finally { Pop-Location }
    }
    "ingest" { Invoke-Comando $Py @("run_prices.py", "--mode", "hourly") }
}
