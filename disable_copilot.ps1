# ============================================================
# Run this script AS ADMINISTRATOR (one-time setup)
# It permanently disables the Copilot key from launching Copilot
# ============================================================

Write-Host "=== Disabling Windows Copilot Key ===" -ForegroundColor Cyan

# Method 1: Disable Windows Copilot entirely via Group Policy registry
try {
    $policyPath = "HKLM:\Software\Policies\Microsoft\Windows\WindowsCopilot"
    if (-not (Test-Path $policyPath)) {
        New-Item -Path $policyPath -Force | Out-Null
    }
    Set-ItemProperty -Path $policyPath -Name "TurnOffWindowsCopilot" -Value 1 -Type DWord -Force
    Write-Host "[OK] HKLM Policy: TurnOffWindowsCopilot = 1" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Could not write HKLM policy. Are you running as Administrator?" -ForegroundColor Red
}

# Method 2: User-level policy (backup)
try {
    $userPolicyPath = "HKCU:\Software\Policies\Microsoft\Windows\WindowsCopilot"
    if (-not (Test-Path $userPolicyPath)) {
        New-Item -Path $userPolicyPath -Force | Out-Null
    }
    Set-ItemProperty -Path $userPolicyPath -Name "TurnOffWindowsCopilot" -Value 1 -Type DWord -Force
    Write-Host "[OK] HKCU Policy: TurnOffWindowsCopilot = 1" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Could not write HKCU policy: $_" -ForegroundColor Red
}

# Method 3: Hide the Copilot button from taskbar
try {
    Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "ShowCopilotButton" -Value 0 -Type DWord -Force
    Write-Host "[OK] Taskbar Copilot button hidden" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Could not hide taskbar button: $_" -ForegroundColor Red
}

# Method 4: Disable the Win+Shift+F23 key combo via Scancode Map (nuclear option)
# This blocks the F23 key entirely so the Copilot key combo cannot fire
try {
    $scancodeMap = [byte[]](
        0x00,0x00,0x00,0x00,  # Header (version)
        0x00,0x00,0x00,0x00,  # Header (flags)
        0x02,0x00,0x00,0x00,  # Number of entries (1 remap + 1 null terminator)
        0x00,0x00,0x6B,0x00,  # Map F23 (0x006B) -> Nothing (0x0000)
        0x00,0x00,0x00,0x00   # Null terminator
    )
    Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Keyboard Layout" -Name "Scancode Map" -Value $scancodeMap -Type Binary -Force
    Write-Host "[OK] F23 scancode blocked (Copilot key hardware intercept)" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Could not write scancode map: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Done! Please RESTART your computer for all changes to take effect. ===" -ForegroundColor Yellow
Write-Host "After restart, the Copilot key will do nothing." -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to close"
