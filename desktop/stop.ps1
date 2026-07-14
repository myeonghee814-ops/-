# Stops the BLIP backend + frontend dev servers by killing whatever is
# listening on their ports. Port-based rather than PID-based because
# `uvicorn --reload` and `npm run dev` both spawn a child process, and
# killing only the parent PID would leave the actual listener running.

$ports = @(8000, 5173)
foreach ($port in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}
