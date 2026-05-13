$ErrorActionPreference = "Continue"

Write-Host "Iniciando migración de TODOS los grupos faltantes..." -ForegroundColor Cyan
Connect-MgGraph -Scopes "Group.ReadWrite.All", "Team.Create", "Directory.ReadWrite.All" -TenantId "74c39aa3-4db0-45a0-864d-705ac1bd1b90" -ContextScope Process -UseDeviceAuthentication

$gruposPath = "c:\Users\DomingoGH245\Desktop\ia\UTM_Soporte_IA\grupos_clase.txt"
# ¡IMPORTANTE! Leer con UTF8 para no romper los acentos (Física, Química, Cálculo)
$lineas = Get-Content $gruposPath -Encoding UTF8

$backupDir = "c:\Users\DomingoGH245\Desktop\ia\UTM_Soporte_IA\Respaldos"
if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir | Out-Null }

foreach ($linea in $lineas) {
    if ([string]::IsNullOrWhiteSpace($linea)) { continue }
    
    $partes = $linea.Split("`t")
    if ($partes.Count -lt 2) {
        $partes = $linea.Split("  ") | Where-Object { $_.Trim() }
    }
    
    if ($partes.Count -ge 1) {
        $nombre = $partes[0].Trim()
        
        Write-Host "`n===============================================" -ForegroundColor Cyan
        Write-Host "Analizando grupo: $nombre" -ForegroundColor Yellow
        
        $filtro = "DisplayName eq '$($nombre.Replace("'", "''"))'"
        $grupo = Get-MgGroup -Filter $filtro -ErrorAction SilentlyContinue

        if (-not $grupo) {
            Write-Warning "   El grupo no existe en M365. Asegúrate de que el nombre sea exacto."
            continue
        }

        $groupId = $grupo.Id
        $team = Get-MgTeam -TeamId $groupId -ErrorAction SilentlyContinue
        
        if ($team) {
            Write-Host "   [OK] Este grupo YA TIENE un Equipo activado. Se omitirá para no duplicar ni borrar." -ForegroundColor Green
            continue
        }

        Write-Host "   [!] Este grupo NO tiene Team. Iniciando migración a Clase..." -ForegroundColor Red
        
        # 1. Respaldar
        $owners = Get-MgGroupOwner -GroupId $groupId -All | Select-Object -ExpandProperty Id
        $members = Get-MgGroupMember -GroupId $groupId -All | Select-Object -ExpandProperty Id
        $membersOnly = $members | Where-Object { $owners -notcontains $_ }
        
        $backupData = @{ GroupName = $nombre; Owners = $owners; Members = $membersOnly }
        $backupFile = Join-Path $backupDir "Backup_$($groupId).json"
        $backupData | ConvertTo-Json -Depth 3 | Set-Content $backupFile
        Write-Host "   Respaldo listo. Dueños: $($owners.Count), Miembros: $($membersOnly.Count)"
        
        # 2. Borrar grupo defectuoso
        Write-Host "   Borrando grupo estándar..."
        Remove-MgGroup -GroupId $groupId -ErrorAction Stop
        try { Remove-MgDirectoryDeletedItem -DirectoryObjectId $groupId -ErrorAction SilentlyContinue } catch {}
        Start-Sleep -Seconds 3
        
        # 3. Crear Clase Educativa
        Write-Host "   Creando Clase Educativa en Teams..."
        $params = @{
            "template@odata.bind" = "https://graph.microsoft.com/v1.0/teamsTemplates('educationClass')"
            displayName = $nombre
            description = "Grupo de clase: $nombre"
        }
        
        try {
            $nuevoTeam = New-MgTeam -BodyParameter $params -ErrorAction Stop
            Write-Host "   [EXITO] Team creado. Esperando aprovisionamiento..." -ForegroundColor Green
            Start-Sleep -Seconds 12
            
            $nuevoGrupo = Get-MgGroup -Filter $filtro -ErrorAction SilentlyContinue
            if ($nuevoGrupo) {
                # 4. Restaurar Miembros
                Write-Host "   Restaurando miembros..."
                foreach ($o in $owners) { try { New-MgGroupOwner -GroupId $nuevoGrupo.Id -DirectoryObjectId $o -ErrorAction SilentlyContinue } catch {} }
                foreach ($m in $membersOnly) { try { New-MgGroupMember -GroupId $nuevoGrupo.Id -DirectoryObjectId $m -ErrorAction SilentlyContinue } catch {} }
                
                # Quitar a domingo.gonzalez
                $user = Get-MgUser -UserId "domingo.gonzalez@utmatamoros.edu.mx" -ErrorAction SilentlyContinue
                if ($user) {
                    try { Invoke-MgGraphRequest -Method DELETE -Uri "https://graph.microsoft.com/v1.0/groups/$($nuevoGrupo.Id)/owners/$($user.Id)/`$ref" -ErrorAction SilentlyContinue } catch {}
                    try { Invoke-MgGraphRequest -Method DELETE -Uri "https://graph.microsoft.com/v1.0/groups/$($nuevoGrupo.Id)/members/$($user.Id)/`$ref" -ErrorAction SilentlyContinue } catch {}
                }
                Write-Host "   Migración 100% completada." -ForegroundColor Green
            }
        } catch {
            Write-Warning "   Falló la creación del Team: $($_.Exception.Message)"
        }
    }
}
Write-Host "`n====== PROCESO TOTAL FINALIZADO ======" -ForegroundColor Green
