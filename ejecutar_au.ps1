# Script de ejecucion directa - AU Alumnos UTM
# Ejecutar desde PowerShell con: .\ejecutar_au.ps1

Import-Module Microsoft.Graph.Identity.DirectoryManagement
Import-Module Microsoft.Graph.Users

# Conectar con los permisos necesarios
Connect-MgGraph -Scopes "AdministrativeUnit.ReadWrite.All","User.Read.All" -NoWelcome

$ctx = Get-MgContext
if (-not $ctx.Account) {
    Write-Error "No se pudo autenticar. Intenta de nuevo."
    exit 1
}
Write-Host "Autenticado como: $($ctx.Account)" -ForegroundColor Green

# Verificar si ya existe la AU
$auExistente = Get-MgDirectoryAdministrativeUnit -Filter "displayName eq 'AU-Alumnos-UTM'" -ErrorAction SilentlyContinue
if ($auExistente) {
    Write-Host "La AU 'AU-Alumnos-UTM' ya existe (ID: $($auExistente.Id)). Usando la existente." -ForegroundColor Yellow
    $au = $auExistente
} else {
    Write-Host "Creando Administrative Unit AU-Alumnos-UTM..."
    $au = New-MgDirectoryAdministrativeUnit `
        -DisplayName "AU-Alumnos-UTM" `
        -Description "Unidad Administrativa - Solo cuentas de alumnos UTM. Scope del Motor IA Soporte."
    Write-Host "AU creada con ID: $($au.Id)" -ForegroundColor Green
}

# Obtener alumnos por patron de matricula
Write-Host "`nObteniendo usuarios del dominio utmatamoros.edu.mx..."
$todosUsuarios = Get-MgUser -All -Property "Id,DisplayName,Mail" | Where-Object {
    $_.Mail -like "*@utmatamoros.edu.mx"
}

$alumnos = $todosUsuarios | Where-Object {
    $local = $_.Mail.Split("@")[0]
    ($local -match "^\d") -or ($local -match "^utm")
}

Write-Host "Total alumnos encontrados: $($alumnos.Count)" -ForegroundColor Cyan

# Obtener miembros ya existentes en la AU
$miembrosActuales = Get-MgDirectoryAdministrativeUnitMemberAsUser -AdministrativeUnitId $au.Id -All -ErrorAction SilentlyContinue
$idsActuales = $miembrosActuales.Id

$agregados = 0
$omitidos = 0

foreach ($alumno in $alumnos) {
    if ($idsActuales -contains $alumno.Id) {
        $omitidos++
        continue
    }
    try {
        New-MgDirectoryAdministrativeUnitMemberByRef `
            -AdministrativeUnitId $au.Id `
            -OdataId "https://graph.microsoft.com/v1.0/users/$($alumno.Id)"
        $agregados++
        Write-Host "  [+] $($alumno.Mail)" -ForegroundColor Green
    } catch {
        Write-Warning "  Error al agregar $($alumno.Mail): $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "RESUMEN" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "AU ID       : $($au.Id)"
Write-Host "Agregados   : $agregados"
Write-Host "Ya existian : $omitidos"
Write-Host ""
Write-Host "PASO FINAL (Manual en Azure Portal):" -ForegroundColor Yellow
Write-Host "1. Ir a: Entra ID > Administrative Units > 'AU-Alumnos-UTM'"
Write-Host "2. Roles and Administrators > Add Assignment"
Write-Host "3. Rol: 'Authentication Administrator'"
Write-Host "4. Asignar el App Registration del Motor IA SOLO dentro de esta AU"
Write-Host "5. En App Registrations > Motor IA > API Permissions:"
Write-Host "   - REVOCAR: User.ReadWrite.All (global)"
Write-Host "   - Este paso lo hace el aislamiento de la AU automaticamente"
Write-Host ""
Write-Host "LISTO: El Motor IA ahora solo podra operar sobre cuentas de alumnos." -ForegroundColor Green
