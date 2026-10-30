# wave-runner.ps1 - orquestrador de uma wave do Squad AI spec-kit.
# ASCII-ONLY (instinto-0004: PowerShell 5.1 le .ps1 BOM-less como ANSI; acento quebra parsing).
#
# O QUE FAZ (deterministico; o build/audit/fix em si e do agente via /squad-wave):
#   - Le um WAVE-SPEC.yaml e imprime o PLANO (sub_tasks em ordem de dependencia: owner|gate|budget).
#   - Modo -Record: grava metricas reais (tokens/duracao/tools) e o resultado de volta no YAML.
#   - Se o resultado != GREEN: imprime DEFERRED/FAILED em destaque e sai != 0 (NAO silencia o gate).
#   - Modo -FixPattern: registra um padrao de fix no ReasoningBank (.claude/banco-padroes/).
#
# Uso:
#   ./wave-runner.ps1 WAVE-SPEC.yaml                              # imprime o plano (read-only)
#   ./wave-runner.ps1 WAVE-SPEC.yaml -Record -Resultado GREEN -TokensReais 71 -DuracaoMin 18 -ToolsCalls 42
#   ./wave-runner.ps1 WAVE-SPEC.yaml -Record -Resultado DEFERRED -FailedTask W1-S3
#   ./wave-runner.ps1 WAVE-SPEC.yaml -FixPattern "insert-first em processed_messages" -FixTaskId W1-S4

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$SpecPath,
    [switch]$Record,
    [switch]$DryRun,
    [ValidateSet('GREEN', 'DEFERRED', 'FAILED')]
    [string]$Resultado,
    [int]$TokensReais = -1,
    [int]$DuracaoMin = -1,
    [int]$ToolsCalls = -1,
    [string]$FailedTask = '',
    [string]$FixPattern = '',
    [string]$FixTaskId = '',
    [string]$BancoPadroes = '.claude/banco-padroes'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $SpecPath)) {
    Write-Output "ERRO: WAVE-SPEC nao encontrado: $SpecPath"
    exit 2
}

$lines = Get-Content -LiteralPath $SpecPath
$text = ($lines -join "`n")

function Clean([string]$s) {
    # remove comentario inline (' #...') e aspas/espacos das pontas
    $s = [regex]::Replace($s, '\s+#.*$', '')
    return $s.Trim().Trim('"').Trim()
}

function Get-Scalar([string]$key) {
    $m = [regex]::Match($text, "(?m)^\s*$key`:\s*(.*)$")
    if ($m.Success) { return (Clean $m.Groups[1].Value) }
    return ''
}

$waveId = Get-Scalar 'id'
$waveName = Get-Scalar 'name'
$waveObj = Get-Scalar 'objetivo'
$milestone = Get-Scalar 'milestone_pai'

# --- parse das sub_tasks (line scan; schema canonico fixo) ---
$tasks = @()
$cur = $null
$inSub = $false
foreach ($ln in $lines) {
    if ($ln -match '^\s*sub_tasks:\s*$') { $inSub = $true; continue }
    if ($ln -match '^\s*metricas:\s*$') { if ($cur) { $tasks += , $cur; $cur = $null }; $inSub = $false; continue }
    if (-not $inSub) { continue }
    if ($ln -match '^\s*-\s*id:\s*(.*)$') {
        if ($cur) { $tasks += , $cur }
        $cur = [ordered]@{ id = (Clean $matches[1]); owner = ''; gate = ''; budget = '0'; dep = '[]' }
        continue
    }
    if (-not $cur) { continue }
    if ($ln -match '^\s*owner:\s*(.*)$') { $cur.owner = (Clean $matches[1]) }
    elseif ($ln -match '^\s*gate:\s*(.*)$') { $cur.gate = (Clean $matches[1]) }
    elseif ($ln -match '^\s*token_budget:\s*(.*)$') { $cur.budget = ((Clean $matches[1]) -replace '[^\d].*$', '') }
    elseif ($ln -match '^\s*depende_de:\s*(.*)$') { $cur.dep = (Clean $matches[1]) }
}
if ($cur) { $tasks += , $cur }

# --- ordem de dependencia: tarefas sem dependencia primeiro (estavel) ---
$semDep = @($tasks | Where-Object { $_.dep -eq '[]' -or $_.dep -eq '' })
$comDep = @($tasks | Where-Object { -not ($_.dep -eq '[]' -or $_.dep -eq '') })
$ordem = @($semDep) + @($comDep)

# --- imprime o plano ---
Write-Output "=== WAVE $waveId : $waveName ==="
Write-Output "objetivo : $waveObj"
Write-Output "milestone: $milestone (fase SPARC)"
Write-Output "sub_tasks: $($tasks.Count) (em ordem de dependencia)"
Write-Output "-----------------------------------------------------------------------"
$totBudget = 0
foreach ($t in $ordem) {
    $totBudget += [int]$t.budget
    Write-Output ("  {0,-7} owner={1,-18} budget={2,3}k  gate: {3}" -f $t.id, $t.owner, $t.budget, $t.gate)
    if ($t.dep -ne '[]' -and $t.dep -ne '') { Write-Output ("          depende_de: {0}" -f $t.dep) }
}
Write-Output "-----------------------------------------------------------------------"
Write-Output ("budget total estimado: {0}k tokens" -f $totBudget)

# -DryRun: modo plan explicito (alias do default sem flag) - NUNCA escreve.
# Sem nenhuma flag o comportamento ja e plan/read-only; -DryRun deixa isso explicito e
# tem precedencia: mesmo com -Record/-FixPattern, nada e gravado.
if ($DryRun) {
    Write-Output "[dry-run] modo plan: nenhuma escrita (metricas/resultado/ReasoningBank ignorados)."
}

# --- ReasoningBank: registra padrao de fix (owner=fix) ---
if ($FixPattern -ne '' -and -not $DryRun) {
    $bankDir = $BancoPadroes
    if (-not (Test-Path -LiteralPath $bankDir)) { New-Item -ItemType Directory -Path $bankDir -Force | Out-Null }
    $bankFile = Join-Path $bankDir 'spec-kit-fixes.md'
    if (-not (Test-Path -LiteralPath $bankFile)) {
        Set-Content -LiteralPath $bankFile -Value "# ReasoningBank - padroes de fix do spec-kit (wave-runner)" -Encoding ASCII
    }
    $stamp = (Get-Date -Format 'yyyy-MM-dd')
    $entry = "- [$stamp][$waveId/$FixTaskId] $FixPattern"
    Add-Content -LiteralPath $bankFile -Value $entry -Encoding ASCII
    Write-Output "ReasoningBank: padrao de fix registrado em $bankFile"
    Write-Output "  (RETRIEVE futuro: grep '$bankDir' antes de re-resolver o mesmo beco)"
}

# --- modo -Record: grava metricas + resultado de volta no YAML (ignorado em -DryRun) ---
if ($Record -and -not $DryRun) {
    if ($TokensReais -ge 0) { $text = [regex]::Replace($text, '(?m)^(\s*tokens_reais:\s*).*$', "`${1}$TokensReais") }
    if ($DuracaoMin -ge 0) { $text = [regex]::Replace($text, '(?m)^(\s*duracao_min:\s*).*$', "`${1}$DuracaoMin") }
    if ($ToolsCalls -ge 0) { $text = [regex]::Replace($text, '(?m)^(\s*tools_calls:\s*).*$', "`${1}$ToolsCalls") }
    if ($Resultado -ne '') { $text = [regex]::Replace($text, '(?m)^(\s*resultado:\s*).*$', "`${1}`"$Resultado`"") }
    Set-Content -LiteralPath $SpecPath -Value $text -Encoding UTF8
    Write-Output "-----------------------------------------------------------------------"
    Write-Output "Registrado: tokens_reais=$TokensReais duracao_min=$DuracaoMin tools_calls=$ToolsCalls resultado=$Resultado"
}

# --- gate: resultado != GREEN nao e silenciado (sai != 0) ---
if ($Resultado -eq 'DEFERRED' -or $Resultado -eq 'FAILED') {
    Write-Output "***********************************************************************"
    Write-Output "*  $Resultado  -  gate da wave $waveId NAO passou."
    if ($FailedTask -ne '') { Write-Output "*  sub_task que barrou: $FailedTask" }
    Write-Output "*  O loop PARA aqui. Trate o finding (owner=fix