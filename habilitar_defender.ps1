# habilitar_defender.ps1
# Activa el "Standard Preset Security Policy" de Microsoft Defender

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host " Activando Microsoft Defender (Safe Links/Attachments)   " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

Write-Host "`nConectando a Exchange Online (Microsoft 365)..." -ForegroundColor Yellow
Write-Host "Se abrirá la ventana de inicio de sesión de Microsoft." -ForegroundColor Yellow
Connect-ExchangeOnline -ShowProgress $false

Write-Host "`n1. Activando Protección Estándar (EOP)..." -ForegroundColor Cyan
try {
    Enable-EOPProtectionPolicyRule -Identity "Standard Preset Security Policy" -ErrorAction Stop
    Write-Host "-> Regla de Exchange Online Protection activada." -ForegroundColor Green
} catch {
    Write-Host "-> Error o ya estaba activada: $_" -ForegroundColor Yellow
}

Write-Host "`n2. Activando Protección Avanzada (Safe Links / ATP)..." -ForegroundColor Cyan
try {
    Enable-ATPProtectionPolicyRule -Identity "Standard Preset Security Policy" -ErrorAction Stop
    Write-Host "-> Regla de Defender (Safe Links y Anti-Phishing) activada." -ForegroundColor Green
} catch {
    Write-Host "-> Error o ya estaba activada: $_" -ForegroundColor Yellow
}

Write-Host "`nCerrando sesión..." -ForegroundColor Cyan
Disconnect-ExchangeOnline -Confirm:$false

Write-Host "`n=========================================================" -ForegroundColor Green
Write-Host "¡Proceso terminado! La IA Anti-Phishing está encendida." -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
