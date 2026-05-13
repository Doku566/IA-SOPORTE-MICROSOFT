Import-Module Microsoft.Graph.Applications -ErrorAction SilentlyContinue
Import-Module Microsoft.Graph.Identity.DirectoryManagement -ErrorAction SilentlyContinue

Connect-MgGraph -Scopes "Application.Read.All" -NoWelcome

Write-Host ""
Write-Host "=== APP REGISTRATIONS EN EL TENANT ===" -ForegroundColor Cyan
$apps = Get-MgApplication -All | Select-Object DisplayName, AppId, Id
$apps | Format-Table -AutoSize

Write-Host ""
Write-Host "=== PERMISOS (APP ROLES) POR CADA APP ===" -ForegroundColor Cyan

foreach ($app in $apps) {
    # Obtener el Service Principal correspondiente
    $sp = Get-MgServicePrincipal -Filter "appId eq '$($app.AppId)'" -ErrorAction SilentlyContinue
    if (-not $sp) { continue }

    # Obtener los AppRoleAssignments (permisos de aplicacion)
    $assignments = Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $sp.Id -ErrorAction SilentlyContinue

    if ($assignments.Count -gt 0) {
        Write-Host ""
        Write-Host "APP: $($app.DisplayName) (AppId: $($app.AppId))" -ForegroundColor Yellow
        foreach ($a in $assignments) {
            Write-Host "  Permiso: $($a.PrincipalDisplayName) -> RoleId: $($a.AppRoleId) en $($a.ResourceDisplayName)"
        }
    }
}

Write-Host ""
Write-Host "=== VERIFICACION DE AU: ROLES ASIGNADOS DENTRO DE AU-Alumnos-UTM ===" -ForegroundColor Cyan
$AU_ID = "61618d41-0bab-405c-a3ca-acbfef8d0539"
try {
    $scopedMembers = Get-MgDirectoryAdministrativeUnitScopedRoleMember -AdministrativeUnitId $AU_ID -ErrorAction Stop
    if ($scopedMembers.Count -eq 0) {
        Write-Host "  RESULTADO: Ningun Service Principal tiene rol asignado DENTRO de la AU." -ForegroundColor Red
        Write-Host "  El App Registration del Motor IA NO esta restringido a la AU todavia." -ForegroundColor Red
    } else {
        foreach ($m in $scopedMembers) {
            Write-Host "  Miembro con rol en AU: $($m.RoleId) -> $($m.RoleMemberInfo.DisplayName)"
        }
    }
} catch {
    Write-Host "  Error al consultar roles en AU: $_" -ForegroundColor Red
}
