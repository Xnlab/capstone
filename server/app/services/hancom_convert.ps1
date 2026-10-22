param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Destination,
    [Parameter(Mandatory=$true)][ValidateSet('HWP','HWPX','PDF')][string]$Format
)
$ErrorActionPreference = 'Stop'
$hwpApp = $null
try {
    $previousHwpProcesses = @(Get-Process Hwp -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
    $hwpApp = New-Object -ComObject HWPFrame.HwpObject
    $hwpWindows = $hwpApp.XHwpWindows
    $hwpWindow = $hwpWindows.Item(0)
    $hwpWindow.Visible = ($env:CAPSTONE_HANCOM_VISIBLE -eq '1')
    Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class CapstoneHwpProcess { [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId); }'
    [uint32]$hwpProcessId = 0
    [void][CapstoneHwpProcess]::GetWindowThreadProcessId([IntPtr]$hwpWindow.WindowHandle, [ref]$hwpProcessId)
    if ($hwpProcessId -and $previousHwpProcesses -notcontains $hwpProcessId) {
        $hwpOwnedProcess = Get-Process -Id $hwpProcessId
        Write-Output ('OWNED_PROCESS=' + $hwpProcessId + ',' + $hwpOwnedProcess.StartTime.ToUniversalTime().ToFileTimeUtc())
    }
    Write-Output 'OPENING'
    $inputFormat = ''
    if ([IO.Path]::GetExtension($Source) -eq '.hwpx') { $inputFormat = 'HWPX' }
    if ([IO.Path]::GetExtension($Source) -eq '.hwp') { $inputFormat = 'HWP' }
    if (-not $hwpApp.Open($Source, $inputFormat, 'forceopen:true;versionwarning:false;lock:false')) { throw 'OPEN_FAILED' }
    Write-Output 'SAVING'
    $saveOptions = ''
    if ($Format -eq 'PDF') { $saveOptions = 'export:true' }
    if (-not $hwpApp.SaveAs($Destination, $Format, $saveOptions)) { throw 'SAVE_FAILED' }
    if (-not (Test-Path -LiteralPath $Destination)) { throw 'NO_OUTPUT' }
    Write-Output 'OK'
} catch {
    Write-Output 'HANCOM_CONVERSION_FAILED'
    exit 1
} finally {
    if ($null -ne $hwpApp) {
        $hwpApp.Clear(1)
        $hwpApp.Quit()
        if ($null -ne $hwpWindow) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($hwpWindow) }
        if ($null -ne $hwpWindows) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($hwpWindows) }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($hwpApp)
        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
    }
}
