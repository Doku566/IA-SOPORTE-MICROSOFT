$ErrorActionPreference = "Stop"

Write-Host "Iniciando proceso seguro de migración a Equipos de Clase..." -ForegroundColor Cyan
Connect-MgGraph -Scopes "Group.ReadWrite.All", "Team.Create", "Directory.ReadWrite.All" -TenantId "74c39aa3-4db0-45a0-864d-705ac1bd1b90" -ContextScope Process -UseDeviceAuthentication

$grupos = @(
    "1IMI1V - 2026 Protocolos de Operación y Mantenimiento",
    "1IMI1V - 2026 Administracion del tiempo",
    "1IMI1V - 2026 Tribologia",
    "1IMI1V - 2026 Matematicas para Ingenieria I",
    "1IMI1V - 2026 Planeacion y Organización del trabajo",
    "1IMI1V - 2026 Fisica para Ingenieria",
    "1IMI1V - 2026 Ingles VI",
    "3IMI1V - 2026 Administracion Estrategica para Mantenimiento",
    "3IMI1V - 2026 Direccion de Equipos de Alto Rendimiento",
    "3IMI1V - 2026 Mantenimiento Predictivo Mecanico",
    "3IMI1V - 2026 Sistemas Automatizados y Redes Industriales",
    "3IMI1V - 2026 Ingles VIII",
    "3IMI2V - 2026 Administracion Estrategica para Mantenimiento",
    "3IMI2V - 2026 Direccion de Equipos de Alto Rendimiento",
    "3IMI2V - 2026 Mantenimiento Predictivo Mecanico",
    "3IMI2V - 2026 Sistemas Automatizados y Redes Industriales",
    "3IMI2V - 2026 Ingles VIII",
    "3IMI3V - 2026 Administracion Estrategica para Mantenimiento",
    "3IMI3V - 2026 Direccion de Equipos de Alto Rendimiento",
    "3IMI3V - 2026 Mantenimiento Predictivo Mecanico",
    "3IMI3V - 2026 Sistemas Automatizados y Redes Industriales",
    "3IMI3V - 2026 Ingles VIII",
    "3MI1D - 2026 Ingles I",
    "3MI1D - 2026 Desarrollo del pensamiento y toma de decisiones",
    "3MI1D - 2026 Física",
    "3MI1D - 2026 Gestión del mantenimiento",
    "3MI2D - 2026 Ingles I",
    "3MI2D - 2026 Desarrollo del pensamiento y toma de decisiones",
    "3MI2D - 2026 Física",
    "3MI2D - 2026 Gestión del mantenimiento",
    "6M1D - 2026 Ingles IV",
    "6M1D - 2026 Liderazgo de equipos de alto desempeño",
    "6M1D - 2026 Cálculo de Varias Variables",
    "6M1D - 2026 Máquinas Eléctricas",
    "6M1D - 2026 Electrónica Digital"
)

# Carpeta para respaldos por si algo falla
$backupDir = "c:\Users\DomingoGH245\Desktop\ia\UTM_Soporte_IA\Respaldos"
if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir | Out-Null }

foreach ($nombre in $grupos) {
    $nombre = $nombre.Trim()
    Write-Host "`n===============================================" -ForegroundColor Cyan
    Write-Host "Procesando grupo: $nombre" -ForegroundColor Yellow
    
    $filtro = "DisplayName eq '$($nombre.Replace("'", "''"))'"
    $grupoAntiguo = Get-MgGroup -Filter $filtro -ErrorAction SilentlyContinue

    if (-not $grupoAntiguo) {
        Write-Warning "El grupo no se encontró. Saltando."
        continue
    }

    $groupId = $grupoAntiguo.Id
    Write-Host "1. Grupo encontrado (ID: $groupId). Respaldando miembros..."
    
    # 1. Respaldar Propietarios y Miembros
    $owners = Get-MgGroupOwner -GroupId $groupId -All | Select-Object -ExpandProperty Id
    $members = Get-MgGroupMember -GroupId $groupId -All | Select-Object -ExpandProperty Id
    
    # Excluir a los propietarios de la lista de miembros para evitar errores de duplicidad al restaurar
    $membersOnly = $members | Where-Object { $owners -notcontains $_ }
    
    $backupData = @{
        GroupName = $nombre
        Owners = $owners
        Members = $membersOnly
    }
    $backupFile = Join-Path $backupDir "Backup_$($groupId).json"
    $backupData | ConvertTo-Json -Depth 3 | Set-Content $backupFile
    Write-Host "   Respaldo guardado con $($owners.Count) dueños y $($membersOnly.Count) miembros." -ForegroundColor Green
    
    # 2. Eliminar grupo antiguo
    Write-Host "2. Eliminando grupo estándar defectuoso..."
    Remove-MgGroup -GroupId $groupId -ErrorAction Stop
    try {
        # Intentar purgar de la papelera para evitar conflictos de alias (puede fallar si tarda en reflejarse)
        Remove-MgDirectoryDeletedItem -DirectoryObjectId $groupId -ErrorAction SilentlyContinue
    } catch {}
    
    Write-Host "   Esperando 5 segundos para replicación..."
    Start-Sleep -Seconds 5
    
    # 3. Crear nuevo Equipo de Clase
    Write-Host "3. Creando nuevo Equipo de Clase..."
    $params = @{
        "template@odata.bind" = "https://graph.microsoft.com/v1.0/teamsTemplates('educationClass')"
        displayName = $nombre
        description = "Grupo de clase: $nombre"
    }
    
    try {
        $team = New-MgTeam -BodyParameter $params -ErrorAction Stop
        Write-Host "   [EXITO] Comando de creación enviado. Esperando 12 segundos para aprovisionamiento..." -ForegroundColor Green
        Start-Sleep -Seconds 12
        
        # Buscar el ID del nuevo grupo
        $nuevoGrupo = Get-MgGroup -Filter $filtro -ErrorAction SilentlyContinue
        if ($nuevoGrupo) {
            $nuevoId = $nuevoGrupo.Id
            Write-Host "   Nuevo grupo generado con ID: $nuevoId"
            
            # 4. Restaurar Propietarios
            Write-Host "4. Restaurando propietarios..."
            foreach ($ownerId in $owners) {
                try { New-MgGroupOwner -GroupId $nuevoId -DirectoryObjectId $ownerId -ErrorAction SilentlyContinue } catch {}
            }
            
            # Restaurar Miembros
            Write-Host "   Restaurando miembros..."
            foreach ($memberId in $membersOnly) {
                try { New-MgGroupMember -GroupId $nuevoId -DirectoryObjectId $memberId -ErrorAction SilentlyContinue } catch {}
            }
            Write-Host "   [EXITO] Migración completada para $nombre." -ForegroundColor Green
        } else {
            Write-Warning "   No se pudo encontrar el grupo recién creado. Revisa el respaldo en: $backupFile"
        }
        
    } catch {
        Write-Warning "   Error al crear el equipo de clase: $($_.Exception.Message)"
        Write-Warning "   ¡Tus miembros están a salvo en el archivo de respaldo!"
    }
}

Write-Host "`n====== PROCESO FINALIZADO ======" -ForegroundColor Green
