# ============================================================
# SCRIPT: Crear Administrative Unit de Alumnos en Entra ID
# PROPOSITO: Aislar el App Registration del Motor IA para que
#            SOLO pueda modificar cuentas dentro de esta AU.
#            Si el servidor es comprometido, el atacante no
#            puede tocar cuentas de administradores o docentes.
# REQUISITO: Az.Identity + Microsoft.Graph PowerShell SDK
# ============================================================

Connect-MgGraph -Scopes "AdministrativeUnit.ReadWrite.All", "User.Read.All", "RoleManagement.ReadWrite.Directory"

$NombreAU = "AU-Alumnos-UTM"
$DescripcionAU = "Unidad Administrativa restringida - Solo cuentas de alumnos. Gestionada por Motor IA Soporte."

# 1. Crear la Administrative Unit
Write-Host "Creando Administrative Unit: $NombreAU..."
$au = New-MgAdministrativeUnit -DisplayName $NombreAU -Description $DescripcionAU
Write-Host "AU creada con ID: $($au.Id)"

# 2. Identificar todos los alumnos por patron de correo (matricula = inicia con digito o 'utm')
Write-Host "Obteniendo lista de alumnos..."
$alumnos = Get-MgUser -All -Filter "endsWith(mail, '@utmatamoros.edu.mx')" -Property "Id,DisplayName,Mail" | Where-Object {
    $local = $_.Mail.Split("@")[0]
    ($local -match "^\d") -or ($local -match "^utm")
}

Write-Host "Total de alumnos encontrados: $($alumnos.Count)"

# 3. Agregar cada alumno a la AU
$contador = 0
foreach ($alumno in $alumnos) {
    try {
        New-MgAdministrativeUnitMemberByRef -AdministrativeUnitId $au.Id `
            -OdataId "https://graph.microsoft.com/v1.0/users/$($alumno.Id)"
        $contador++
        Write-Host "  [$contador/$($alumnos.Count)] Agregado: $($alumno.Mail)"
    } catch {
        Write-Warning "No se pudo agregar $($alumno.Mail): $_"
    }
}

Write-Host ""
Write-Host "=============================================="
Write-Host "PASO FINAL MANUAL REQUERIDO EN AZURE PORTAL:"
Write-Host "=============================================="
Write-Host "1. Ir a: Entra ID > Administrative Units > '$NombreAU'"
Write-Host "2. Ir a: Roles and Administrators"
Write-Host "3. Agregar el App Registration del Motor IA con el rol:"
Write-Host "   'Authentication Administrator' (SOLO dentro de esta AU)"
Write-Host "4. REVOCAR el permiso global 'User.ReadWrite.All' del App Registration"
Write-Host "   y reemplazarlo con 'User.ReadWrite' con scope de Administrative Unit."
Write-Host ""
Write-Host "RESULTADO: El Motor IA solo podra resetear contrasenas de alumnos."
Write-Host "Si el servidor es comprometido, el atacante NO puede tocar admins ni docentes."
