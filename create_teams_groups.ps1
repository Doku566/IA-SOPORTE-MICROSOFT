# create_teams_groups.ps1
# Script para crear grupos en Teams usando la cuenta de soporte@utmatamoros.edu.mx

# 1. Conectar a Microsoft Graph
Write-Host "Iniciando conexión. Se abrirá una ventana para iniciar sesión." -ForegroundColor Cyan
Write-Host "IMPORTANTE: Elige la cuenta de soporte@utmatamoros.edu.mx" -ForegroundColor Yellow

# Forzamos una sesión limpia
Connect-MgGraph -Scopes "Group.ReadWrite.All", "Team.Create", "User.Read.All", "Directory.ReadWrite.All" -TenantId "74c39aa3-4db0-45a0-864d-705ac1bd1b90" -ContextScope Process

$context = Get-MgContext
if (-not $context -or [string]::IsNullOrEmpty($context.Account)) {
    Write-Error "No se detectó una sesión activa."
    exit
}

# 2. Cargar el directorio
$directorioPath = "c:\Users\DomingoGH245\Desktop\ia\UTM_Soporte_IA\directorio_utm_completo.csv"
if (Test-Path $directorioPath) {
    Write-Host "Cargando base de datos de usuarios..."
    $usuarios = Import-Csv $directorioPath
}

# 3. Leer la lista de grupos
$gruposPath = "c:\Users\DomingoGH245\Desktop\ia\UTM_Soporte_IA\grupos_clase.txt"
$lineas = Get-Content $gruposPath

# 4. Obtener el ID del usuario actual
$currentUser = Get-MgUser -UserId $context.Account
$currentUserId = $currentUser.Id

# Validar cuenta de soporte
if ($context.Account -notlike "*soporte*") {
    Write-Host "`n⚠️ ATENCIÓN: Estás conectado como: $($context.Account)" -ForegroundColor Red
    $confirm = Read-Host "¿Deseas CERRAR esta sesión e intentar con soporte? (S/N)"
    if ($confirm -eq "S") {
        Disconnect-MgGraph
        exit
    }
}

Write-Host "Iniciando creación de grupos como: $($context.Account)" -ForegroundColor Green

foreach ($linea in $lineas) {
    if ([string]::IsNullOrWhiteSpace($linea)) { continue }
    
    $partes = $linea.Split("`t")
    if ($partes.Count -lt 3) {
        $partes = $linea.Split("  ") | Where-Object { $_.Trim() }
    }

    if ($partes.Count -ge 3) {
        $nombreGrupo = $partes[0].Trim()
        $nombreDocente = $partes[1].Trim()
        $correoPrefecto = $partes[2].Trim()

        Write-Host "`n--- Procesando: $nombreGrupo ---" -ForegroundColor Yellow

        # A. Buscar Docente
        $docenteId = $null
        if ($usuarios) {
            $match = $usuarios | Where-Object { $_.displayName -like "*$nombreDocente*" } | Select-Object -First 1
            if ($match) { $docenteId = $match.id }
        }
        
        if (-not $docenteId) {
            $matchLive = Get-MgUser -Filter "displayName eq '$($nombreDocente.Replace("'", "''"))'" -ErrorAction SilentlyContinue
            if ($matchLive) { $docenteId = $matchLive.Id }
        }

        # B. Buscar Prefecto
        $prefecto = Get-MgUser -UserId $correoPrefecto -ErrorAction SilentlyContinue
        $prefectoId = if ($prefecto) { $prefecto.Id } else { $null }

        # C. Crear/Obtener Grupo
        $nickname = ($nombreGrupo -replace '[^a-zA-Z0-9]', '').ToLower()
        if ($nickname.Length -gt 64) { $nickname = $nickname.Substring(0, 64) }

        $existe = Get-MgGroup -Filter "DisplayName eq '$($nombreGrupo.Replace("'", "''"))'"
        if ($existe) {
            $groupId = $existe.Id
        } else {
            $params = @{
                DisplayName = $nombreGrupo
                Description = "Grupo de clase: $nombreGrupo"
                MailEnabled = $true
                MailNickname = $nickname
                SecurityEnabled = $false
                GroupTypes = @("Unified")
            }
            $nuevoGrupo = New-MgGroup @params
            $groupId = $nuevoGrupo.Id
        }

        # D. Asignar Propietarios
        $propietarios = @($docenteId, $prefectoId, $currentUserId) | Where-Object { $_ }
        foreach ($oId in $propietarios) {
            try {
                New-MgGroupOwner -GroupId $groupId -DirectoryObjectId $oId -ErrorAction SilentlyContinue
            } catch { }
        }

        # E. Activar Team
        Write-Host "  Activando Teams..."
        try {
            New-MgTeam -GroupId $groupId -TemplateBind "https://graph.microsoft.com/v1.0/teamsTemplates('standard')" -ErrorAction Stop
            Write-Host "  [OK] Team activado." -ForegroundColor Green
        } catch {
            Write-Warning "  Info: $($_.Exception.Message)"
        }
        Start-Sleep -Seconds 1
    }
}
Write-Host "`nProceso finalizado." -ForegroundColor Green
