param(
    [Parameter(Mandatory = $true)][ValidateSet('slice', 'full', 'gated')][string]$Scope,
    [Parameter(Mandatory = $true)][ValidateRange(0.1, 64.0)][double]$RamGiB,
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_-]*$')][string]$RunId,
    [string]$DryOutputDirectory,
    [ValidateRange(1, 30)][int]$Minutes = 10
)

$ErrorActionPreference = 'Stop'
$Python = (Get-Command python -CommandType Application).Source
$Slots = 'C:/Users/rajul/.looptools/slots.py'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
$Stamp = "$(Get-Date -Format yyyyMMdd-HHmmss-fff).$PID"
if ($Scope -eq 'gated') {
    if (-not $RunId -or $DryOutputDirectory) { throw 'Use -RunId for gated runs.' }
    $OutDir = Join-Path $Root "gates/g108/runs/$RunId"
    $Scores = Join-Path $OutDir 'scores.json'
    $Log = Join-Path $OutDir "launch.$Stamp.log"
    $Arguments = @('-B', '-u', 'gates/g108/run.py', ('"{0}"' -f $OutDir))
    $Job = 'g108-gated'
} else {
    if ($RunId) { throw 'Use -DryOutputDirectory for an alternate dry output.' }
    $OutDir = if ($DryOutputDirectory) { $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($DryOutputDirectory) } else { $PSScriptRoot }
    $Stem = if ($Scope -eq 'slice') { 'slice' } else { 'keepout' }
    $Scores = Join-Path $OutDir "$Stem.json"
    $Log = Join-Path $OutDir "$Stem.log"
    if (Test-Path -LiteralPath $Log) { $Log = Join-Path $OutDir "$Stem.$Stamp.log" }
    $Arguments = @('-B', '-u', 'gates/g108/dry/keepout.py', $Scope, '--out', ('"{0}"' -f $Scores))
    $Job = 'g108-dry'
}
[void][IO.Directory]::CreateDirectory($OutDir)
$Stderr = "$Log.stderr"
$env:OPENBLAS_NUM_THREADS = '2'
$env:OMP_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
$Slot = (& $Python -B $Slots acquire $Job medium $RamGiB $Minutes $PID | Select-Object -Last 1)
if ($LASTEXITCODE -ne 0 -or $Slot -cnotmatch '^[0-9a-f]{8}$') {
    "No slot granted: $Slot" | Set-Content -LiteralPath $Log
    exit 1
}

$Child = $null
$Code = 1
$Failure = $null
$ScoreHash = $null
try {
    $Clock = [Diagnostics.Stopwatch]::StartNew()
    $Start = @{
        FilePath = $Python
        WorkingDirectory = $Root
        WindowStyle = 'Hidden'
        ArgumentList = $Arguments
        RedirectStandardOutput = $Log
        RedirectStandardError = $Stderr
    }
    $Child = Start-Process @Start -PassThru
    $null = $Child.Handle                      # cache the handle now, or ExitCode stays empty after exit (slice v1: rc=)
    while (-not $Child.WaitForExit(500)) {
        $Child.Refresh()
        if ($Child.HasExited) { break }
        if ($Clock.Elapsed.TotalMinutes -ge $Minutes -or $Child.PeakWorkingSet64 -gt $RamGiB * 1GB) {
            throw 'G108 run exceeded its wall-time or peak working-set budget.'
        }
    }
    # After exit the process snapshot can lose PeakWorkingSet64 (null compares as below any budget), so the final
    # peak is the child's own measurement in its record; missing telemetry or exit code fails closed
    if ($null -eq $Child.ExitCode) { throw 'The G108 run left no exit code.' }
    if ($Clock.Elapsed.TotalMinutes -ge $Minutes) { throw 'G108 run exceeded its wall-time budget (found after it exited).' }
    if ($Child.ExitCode -eq 0) {
        $Line = Select-String -LiteralPath $Log -Pattern '^final_peak_working_set_bytes=(\d+)$' | Select-Object -Last 1
        if ($null -eq $Line) { throw 'G108 run printed no final peak working set.' }
        $Peak = [double]$Line.Matches[0].Groups[1].Value
        if ($Peak -le 0 -or $Peak -gt $RamGiB * 1GB) { throw "G108 run peak working set invalid or over budget: $Peak bytes." }
        if ($Scope -eq 'gated') { $ScoreHash = (Get-FileHash -LiteralPath $Scores -Algorithm SHA256).Hash.ToLowerInvariant() }
    }
    $Code = $Child.ExitCode
} catch {
    $Failure = $_.Exception.Message
} finally {
    if ($null -ne $Child -and -not $Child.HasExited) {
        Stop-Process -InputObject $Child
        $Child.WaitForExit()
    }
    & $Python -B $Slots release $Slot
    $ReleaseCode = $LASTEXITCODE
    if (Test-Path -LiteralPath $Stderr) {
        Get-Content -LiteralPath $Stderr | Add-Content -LiteralPath $Log
        Remove-Item -LiteralPath $Stderr
    }
    if ($Failure) { "launcher error: $Failure" | Add-Content -LiteralPath $Log }
    if ($ScoreHash) { "scores_sha256=$ScoreHash" | Add-Content -LiteralPath $Log }
    if ($ReleaseCode -ne 0) { $Code = 1 }
    "rc=$Code slot=$Slot release_rc=$ReleaseCode" | Add-Content -LiteralPath $Log
}
exit $Code
