$ErrorActionPreference = "Stop"

Write-Host "Iniciando proceso para eliminar usuario creador de los grupos..." -ForegroundColor Cyan
Connect-MgGraph -Scopes "Group.ReadWrite.All", "User.Read.All", "Directory.ReadWrite.All" -TenantId "74c39aa3-4db0-45a0-864d-705ac1bd1b90" -ContextScope Process -UseDeviceAuthentication

$userEmail = "domingo.gonzalez@utmatamoros.edu.mx"
Write-Host "Buscando ID del usuario: $userEmail"
$user = Get-MgUser -UserId $userEmail -ErrorAction SilentlyContinue

if (-not $user) {
    Write-Warning "No se pudo encontrar el usuario $userEmail. Verifica el correo."
    exit
}

$userId = $user.Id
Write-Host "Usuario encontrado con ID: $userId" -ForegroundColor Green

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

foreach ($nombre in $grupos) {
    $nombre = $nombre.Trim()
    $filtro = "DisplayName eq '$($nombre.Replace("'", "''"))'"
    $grupo = Get-MgGroup -Filter $filtro -ErrorAction SilentlyContinue

    if ($grupo) {
        $groupId = $grupo.Id
        Write-Host "Procesando: $nombre"
        
        # Eliminar de Propietarios usando la API Graph directamente para mayor compatibilidad
        try {
            Invoke-MgGraphRequest -Method DELETE -Uri "https://graph.microsoft.com/v1.0/groups/$groupId/owners/$userId/`$ref" -ErrorAction Stop
            Write-Host "  [-] Removido de Propietarios" -ForegroundColor Cyan
        } catch {
            # Silently continue if not owner
        }

        # Eliminar de Miembros
        try {
            Invoke-MgGraphRequest -Method DELETE -Uri "https://graph.microsoft.com/v1.0/groups/$groupId/members/$userId/`$ref" -ErrorAction Stop
            Write-Host "  [-] Removido de Miembros" -ForegroundColor Cyan
        } catch {
            # Silently continue if not member
        }
    }
}

Write-Host "`nProceso finalizado. Tu cuenta ha sido removida de los equipos." -ForegroundColor Green
