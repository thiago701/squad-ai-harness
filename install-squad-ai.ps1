# Wrapper fino (Windows): localiza Python e chama o instalador real.
# Toda a lógica vive em install-squad-ai.py (DRY). Repassa os argumentos.
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) { Write-Error "Python 3 nao encontrado no PATH."; exit 1 }
& $py.Source (Join-Path $dir "install-squad-ai.py") @args
exit $LASTEXITCODE
