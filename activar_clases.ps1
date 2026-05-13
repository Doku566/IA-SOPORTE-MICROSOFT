$ErrorActionPreference = "Stop"

Write-Host "Iniciando conexión a Microsoft Graph..." -ForegroundColor Cyan
Write-Host "IMPORTANTE: Asegúrate de usar la cuenta de soporte@utmatamoros.edu.mx" -ForegroundColor Yellow

Connect-MgGraph -Scopes "Group.ReadWrite.All", "Team.Create", "Directory.ReadWrite.All" -ContextScope Process

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
    # Eliminar posibles espacios extra
    $nombre = $nombre.Trim()
    Write-Host "`nBuscando grupo: $nombre" -ForegroundColor Yellow
    
    # Manejar comillas simples si las hay
    $filtro = "DisplayName eq '$($nombre.Replace("'", "''"))'"
    $existe = Get-MgGroup -Filter $filtro -ErrorAction SilentlyContinue
    
    if ($existe) {
        $groupId = $existe.Id
        Write-Host "  [OK] Grupo encontrado. ID: $groupId"
        Write-Host "  Activando como Clase en Teams..."
        try {
            $params = @{
                "template@odata.bind" = "https://graph.microsoft.com/v1.0/teamsTemplates('educationClass')"
                "group@odata.bind" = "https://graph.microsoft.com/v1.0/groups('$groupId')"
            }
            New-MgTeam -BodyParameter $params -ErrorAction Stop
            Write-Host "  [EXITO] Team de Clase activado correctamente." -ForegroundColor Green
        } catch {
            $err = $_.Exception.Message
            if ($err -match "Team already exists" -or $err -match "ya existe") {
                Write-Host "  [INFO] El grupo ya tiene un Team asociado." -ForegroundColor Cyan
            } else {
                Write-Warning "  [ERROR] $($err)"
            }
        }
    } else {
        Write-Host "  [ERROR] No se encontró el grupo M365 con ese nombre." -ForegroundColor Red
    }
}
Write-Host "`nProceso finalizado." -ForegroundColor Green
