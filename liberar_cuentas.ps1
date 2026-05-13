# liberar_cuentas.ps1
# Script para otorgar límites máximos de envío a cuentas de servicio/administrativas

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host " Liberador de Límites de Envío (Outbound Spam) - UTM     " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

Write-Host "`nConectando a Exchange Online..." -ForegroundColor Yellow
Connect-ExchangeOnline -ShowProgress $false

# Cuentas que tendrán privilegios máximos
$cuentas = @(
    "servicios.administrativos@utmatamoros.edu.mx",
    "soporte@utmatamoros.edu.mx",
    "servicios.escolares@utmatamoros.edu.mx",
    "atencion.alumnos@utmatamoros.edu.mx"
)

$policyName = "Bypass_Spam_Salida_Administracion"
$ruleName = "Regla_Bypass_Spam_Salida"

Write-Host "`n1. Configurando Política con límites máximos permitidos (10,000 diarios)..." -ForegroundColor Cyan
try {
    $policy = Get-HostedOutboundSpamFilterPolicy -Identity $policyName -ErrorAction SilentlyContinue
    if (!$policy) {
        # Creamos política con el tope de M365 y que solo avise (Alert), pero no bloquee (BlockUser)
        New-HostedOutboundSpamFilterPolicy -Name $policyName -RecipientLimitExternalPerHour 5000 -RecipientLimitInternalPerHour 5000 -RecipientLimitPerDay 10000 -ActionWhenThresholdReached Alert | Out-Null
        Write-Host "-> Política de alto volumen creada." -ForegroundColor Green
    } else {
        Set-HostedOutboundSpamFilterPolicy -Identity $policyName -RecipientLimitExternalPerHour 5000 -RecipientLimitInternalPerHour 5000 -RecipientLimitPerDay 10000 -ActionWhenThresholdReached Alert | Out-Null
        Write-Host "-> Política de alto volumen actualizada." -ForegroundColor Green
    }
} catch {
    Write-Host "-> Error configurando política: $_" -ForegroundColor Red
}

Write-Host "`n2. Aplicando la política a las 4 cuentas solicitadas..." -ForegroundColor Cyan
try {
    $rule = Get-HostedOutboundSpamFilterRule -Identity $ruleName -ErrorAction SilentlyContinue
    if (!$rule) {
        New-HostedOutboundSpamFilterRule -Name $ruleName -HostedOutboundSpamFilterPolicy $policyName -From $cuentas | Out-Null
        Write-Host "-> Cuentas asignadas y liberadas." -ForegroundColor Green
    } else {
        Set-HostedOutboundSpamFilterRule -Identity $ruleName -From $cuentas | Out-Null
        Write-Host "-> Cuentas actualizadas exitosamente." -ForegroundColor Green
    }
} catch {
    Write-Host "-> Error asignando cuentas: $_" -ForegroundColor Red
}

Write-Host "`nCerrando conexiones..." -ForegroundColor Cyan
Disconnect-ExchangeOnline -Confirm:$false

Write-Host "`n=========================================================" -ForegroundColor Green
Write-Host "¡PROCESO COMPLETADO!" -ForegroundColor Green
Write-Host "Tus 4 cuentas ahora tienen el permiso de mandar hasta 10,000 correos al día."
Write-Host "=========================================================" -ForegroundColor Green
