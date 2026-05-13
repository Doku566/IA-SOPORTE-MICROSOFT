Write-Host "Iniciando prueba de creacion de clase en Teams..."
Connect-MgGraph -Scopes "Group.ReadWrite.All", "Team.Create", "Directory.ReadWrite.All" -TenantId "74c39aa3-4db0-45a0-864d-705ac1bd1b90" -ContextScope Process -UseDeviceAuthentication

$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$teamName = "TEST_CLASE_IA_$timestamp"

Write-Host "Intentando crear Equipo de Clase: $teamName"

$params = @{
    "template@odata.bind" = "https://graph.microsoft.com/v1.0/teamsTemplates('educationClass')"
    displayName = $teamName
    description = "Clase de prueba"
}

try {
    $team = New-MgTeam -BodyParameter $params -ErrorAction Stop
    Write-Host "[EXITO] Equipo de clase creado correctamente." -ForegroundColor Green
    
    # Pausamos para permitir que se provisione
    Start-Sleep -Seconds 10
    
    # Buscamos el grupo generado
    $group = Get-MgGroup -Filter "DisplayName eq '$teamName'"
    if ($group) {
        Write-Host "Grupo M365 generado con ID: $($group.Id)"
        # Limpieza
        Remove-MgGroup -GroupId $group.Id -ErrorAction SilentlyContinue
        Write-Host "Limpieza completada (Grupo borrado)."
    }
} catch {
    Write-Warning "[ERROR] al crear la clase: $($_.Exception.Message)"
}
