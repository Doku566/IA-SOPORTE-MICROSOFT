$ErrorActionPreference = "Continue"

Write-Host "Iniciando proceso para agregar soporte@utmatamoros.edu.mx a los grupos..." -ForegroundColor Cyan
Connect-MgGraph -Scopes "Group.ReadWrite.All", "User.Read.All" -TenantId "74c39aa3-4db0-45a0-864d-705ac1bd1b90" -ContextScope Process -UseDeviceAuthentication

$soporteEmail = "soporte@utmatamoros.edu.mx"
$soporteUser = Get-MgUser -UserId $soporteEmail -ErrorAction SilentlyContinue

if (-not $soporteUser) {
    Write-Warning "No se pudo encontrar el usuario $soporteEmail. Verifica que el correo esté bien escrito."
    exit
}

$soporteId = $soporteUser.Id
Write-Host "Usuario soporte encontrado con ID: $soporteId" -ForegroundColor Green

$gruposPath = "c:\Users\DomingoGH245\Desktop\ia\UTM_Soporte_IA\grupos_clase.txt"
$lineas = Get-Content $gruposPath -Encoding UTF8

foreach ($linea in $lineas) {
    if ([string]::IsNullOrWhiteSpace($linea)) { continue }
    
    $partes = $linea.Split("`t")
    if ($partes.Count -lt 2) {
        $partes = $linea.Split("  ") | Where-Object { $_.Trim() }
    }
    
    if ($partes.Count -ge 1) {
        $nombre = $partes[0].Trim()
        $filtro = "DisplayName eq '$($nombre.Replace("'", "''"))'"
        $grupo = Get-MgGroup -Filter $filtro -ErrorAction SilentlyContinue

        if ($grupo) {
            Write-Host "Procesando: $nombre"
            
            # Intentar agregar como Propietario
            try {
                New-MgGroupOwner -GroupId $grupo.Id -DirectoryObjectId $soporteId -ErrorAction Stop
                Write-Host "  [+] Cuenta de soporte agregada como Propietario." -ForegroundColor Green
            } catch {
                if ($_.Exception.Message -match "already exist") {
                    Write-Host "  [~] La cuenta de soporte ya estaba agregada como propietario." -ForegroundColor Cyan
                } else {
                    Write-Warning "  [-] Error al agregar: $($_.Exception.Message)"
                }
            }
        }
    }
}

Write-Host "`nProceso finalizado. La cuenta de soporte tiene acceso a todos los equipos." -ForegroundColor Green
