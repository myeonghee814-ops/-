# Sets up (first run only) and starts the BLIP backend + frontend, waits for
# both to be ready, then opens Chrome pointed at the app. Intended to be run
# hidden via Launch-BLIP.vbs -- do not double-click this file directly on
# systems with the default PowerShell execution policy, it will be blocked.
#
# Runs silently (no window), so anything that goes wrong is written to
# ..\logs\ instead of the screen -- check there first if the app doesn't
# open.

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $root   # desktop/start.ps1 -> repo root
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Wait-ForUrl($url, $timeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) { return $true }
        } catch {}
        Start-Sleep -Seconds 1
    }
    return $false
}

try {
    # --- Backend: create venv + install deps on first run, then start hidden ---
    $venvPython = Join-Path $backend ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        python -m venv (Join-Path $backend ".venv") *> (Join-Path $logDir "venv-create.log")
    }
    & $venvPython -m pip install -q -r (Join-Path $backend "requirements.txt") *> (Join-Path $logDir "pip-install.log")

    if (-not (Test-Path (Join-Path $backend ".env"))) {
        Copy-Item (Join-Path $backend ".env.example") (Join-Path $backend ".env")
    }

    Start-Process -FilePath $venvPython `
        -ArgumentList @("-m", "uvicorn", "main:app", "--port", "8000") `
        -WorkingDirectory $backend `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDir "backend.log") `
        -RedirectStandardError (Join-Path $logDir "backend.err.log") | Out-Null

    # --- Frontend: npm install on first run, then start hidden ---
    if (-not (Test-Path (Join-Path $frontend ".env"))) {
        Copy-Item (Join-Path $frontend ".env.example") (Join-Path $frontend ".env")
    }
    if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
        Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "npm install") `
            -WorkingDirectory $frontend -WindowStyle Hidden -Wait `
            -RedirectStandardOutput (Join-Path $logDir "npm-install.log") `
            -RedirectStandardError (Join-Path $logDir "npm-install.err.log")
    }

    Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "npm run dev") `
        -WorkingDirectory $frontend `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDir "frontend.log") `
        -RedirectStandardError (Join-Path $logDir "frontend.err.log") | Out-Null

    # --- Wait for both servers, then open the app ---
    $backendReady = Wait-ForUrl "http://localhost:8000/api/v1/health" 60
    $frontendReady = Wait-ForUrl "http://localhost:5173" 60
    if (-not $backendReady -or -not $frontendReady) {
        # Best-effort: still try to open the browser -- whichever side didn't
        # respond in time may just be slow, not broken. If it's actually
        # broken, the logs above have the reason.
        Start-Sleep -Seconds 3
    }

    # --- Launch Chrome in app mode (falls back to the default browser) ---
    $chromeCandidates = @()
    if ($env:ProgramFiles) {
        $chromeCandidates += (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe")
    }
    $programFilesX86 = ${env:ProgramFiles(x86)}
    if ($programFilesX86) {
        $chromeCandidates += (Join-Path $programFilesX86 "Google\Chrome\Application\chrome.exe")
    }
    if ($env:LocalAppData) {
        $chromeCandidates += (Join-Path $env:LocalAppData "Google\Chrome\Application\chrome.exe")
    }
    $chrome = $chromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    $url = "http://localhost:5173"
    if ($chrome) {
        # --app hides the address bar/tabs so it reads as a standalone
        # program rather than "a website open in Chrome".
        Start-Process -FilePath $chrome -ArgumentList @("--app=$url", "--new-window")
    } else {
        Start-Process $url
    }
} catch {
    $_ | Out-String | Out-File -FilePath (Join-Path $logDir "launcher-error.log") -Append
}
