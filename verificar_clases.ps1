$ErrorActionPreference = "Continue"

Write-Host "Verificando estado de los grupos en Microsoft Teams..." -ForegroundColor Cyan
Connect-MgGraph -Scopes "Group.Read.All", "Team.ReadBasic.All" -TenantId "74c39aa3-4db0-45a0-864d-705ac1bd1b90" -ContextScope Process -UseDeviceAuthentication

$gruposPath = "c:\Users\DomingoGH245\Desktop\ia\UTM_Soporte_IA\grupos_clase.txt"
$grupos = Get-Content $gruposPath

$resultados = @()

foreach ($linea in $grupos) {
    if ([string]::IsNullOrWhiteSpace($linea)) { continue }
    
    $partes = $linea.Split("`t")
    if ($partes.Count -lt 2) {
        $partes = $linea.Split("  ") | Where-Object { $_.Trim() }
    }
    
    if ($partes.Count -ge 1) {
        $nombre = $partes[0].Trim()
        $filtro = "DisplayName eq '$($nombre.Replace("'", "''"))'"
        
        # Obtenemos las propiedades extendidas para verificar si es clase
        $grupo = Get-MgGroup -Filter $filtro -Property "Id,DisplayName,CreationOptions,ResourceProvisioningOptions" -ErrorAction SilentlyContinue

        $obj = [PSCustomObject]@{
            Nombre = $nombre
            M365Group = "❌"
            Team = "❌"
            ClaseEducativa = "❌"
        }

        if ($grupo) {
            $obj.M365Group = "✅"
            
            # Verificamos si tiene el Team activado
            $team = Get-MgTeam -TeamId $grupo.Id -ErrorAction SilentlyContinue
            if ($team) {
                $obj.Team = "✅"
            }

            # Si en sus opciones de creacion tiene TeamClass o banderas de educación
            $opciones = $grupo.CreationOptions -join ","
            if ($opciones -match "TeamClass" -or $opciones -match "ExchangeProvisioningFlags:481") {
                $obj.ClaseEducativa = "✅"
            } elseif ($opciones) {
                $obj.ClaseEducativa = "Estándar"
            } else {
                $obj.ClaseEducativa = "Estándar"
            }
        }
        $resultados += $obj
    }
}

Write-Host "`n--- RESULTADOS DEL REPORTE ---" -ForegroundColor Yellow
$resultados | Format-Table -AutoSize

# Separar los que necesitan corrección
$malos = $resultados | Where-Object { $_.ClaseEducativa -eq "Estándar" -or $_.ClaseEducativa -eq "❌" }
if ($malos.Count -gt 0) {
    Write-Host "`nATENCIÓN: Hay $($malos.Count) grupos que NO están configurados correctamente como clase." -ForegroundColor Red
} else {
    Write-Host "`n¡TODOS LOS GRUPOS ESTÁN CONFIGURADOS COMO CLASE CORRECTAMENTE!" -ForegroundColor Green
}
