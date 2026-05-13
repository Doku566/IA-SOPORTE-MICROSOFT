Import-Module Microsoft.Graph.Identity.SignIns -ErrorAction SilentlyContinue
Import-Module Microsoft.Graph.Users -ErrorAction SilentlyContinue

Connect-MgGraph -Scopes "Policy.ReadWrite.AuthenticationMethod","UserAuthenticationMethod.ReadWrite.All","User.Read.All" -NoWelcome

# Leer correo del .env
$envLines = Get-Content "c:\Users\DomingoGH245\Desktop\ia\UTM_Soporte_IA\.env"
$SOPORTE_UPN = ($envLines | Where-Object { $_ -match "^SUPPORT_EMAIL=" }) -replace "SUPPORT_EMAIL=",""
Write-Host "Cuenta objetivo: $SOPORTE_UPN" -ForegroundColor Cyan

# Obtener el usuario
$user = Get-MgUser -Filter "userPrincipalName eq '$SOPORTE_UPN'" -ErrorAction Stop
Write-Host "Usuario encontrado: $($user.DisplayName) (ID: $($user.Id))" -ForegroundColor Green

# Revisar metodos de autenticacion actuales
Write-Host ""
Write-Host "=== Metodos de autenticacion actuales ===" -ForegroundColor Yellow
$methods = Get-MgUserAuthenticationMethod -UserId $user.Id
foreach ($m in $methods) {
    $type = $m.AdditionalProperties["@odata.type"]
    Write-Host "  - $type"
}

# Verificar si ya tiene metodo de telefono registrado
$phoneMethod = Get-MgUserAuthenticationPhoneMethod -UserId $user.Id -ErrorAction SilentlyContinue
if ($phoneMethod) {
    Write-Host ""
    Write-Host "Metodo de telefono registrado: $($phoneMethod.PhoneNumber) ($($phoneMethod.PhoneType))" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "AVISO: No hay metodo de telefono registrado para esta cuenta." -ForegroundColor Yellow
    Write-Host "Se recomienda registrar Microsoft Authenticator o un numero de telefono." -ForegroundColor Yellow
}

# Habilitar MFA usando la politica de autenticacion por usuario via Graph
Write-Host ""
Write-Host "=== Aplicando politica de autenticacion fuerte ===" -ForegroundColor Cyan

# Actualizar el perfil del usuario para requerir MFA en el proximo inicio de sesion
Update-MgUser -UserId $user.Id -PasswordPolicies "None" -ErrorAction SilentlyContinue

# Registrar numero de telefono MFA si no existe (solo si el admin lo desea)
Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "ESTADO ACTUAL:" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host "La cuenta $SOPORTE_UPN requiere configuracion manual de MFA." -ForegroundColor White
Write-Host ""
Write-Host "PASOS PARA COMPLETAR (2 minutos en el portal):" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Ir a: https://aka.ms/mfasetup"
Write-Host "   (Iniciar sesion con $SOPORTE_UPN)"
Write-Host "2. Agregar 'Microsoft Authenticator' como metodo principal"
Write-Host "3. Escanear el codigo QR con el telefono del administrador"
Write-Host ""
Write-Host "PROTECCION ADICIONAL INMEDIATA:" -ForegroundColor Cyan
Write-Host "Para forzar MFA en la cuenta ahora mismo via portal:"
Write-Host "1. Ir a: https://entra.microsoft.com"
Write-Host "2. Identity > Users > Soporte-IA > Authentication methods"  
Write-Host "3. Require re-register MFA = ON"
Write-Host ""

# Verificar si el tenant tiene Security Defaults habilitados
$secDefaults = Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/policies/identitySecurityDefaultsEnforcementPolicy"
Write-Host "=== Estado de Security Defaults ===" -ForegroundColor Yellow
Write-Host "  Habilitados: $($secDefaults.isEnabled)"
if (-not $secDefaults.isEnabled) {
    Write-Host "  RECOMENDACION: Habilitar Security Defaults fuerza MFA en TODAS las cuentas." -ForegroundColor Yellow
    Write-Host "  Ejecutar para habilitar:"
    Write-Host '  Invoke-MgGraphRequest -Method PATCH -Uri "https://graph.microsoft.com/v1.0/policies/identitySecurityDefaultsEnforcementPolicy" -Body @{isEnabled=$true} -ContentType "application/json"'
}
