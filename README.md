# Motor de Soporte IA e Infraestructura Automatizada para Microsoft 365 y Graph API



El presente documento describe las especificaciones técnicas, arquitectura e instrucciones de despliegue del **Motor de Soporte IA e Infraestructura Automatizada**, una solución de asistencia técnica de Nivel 1 (Tier-1 IT Service Desk) desarrollada en lenguaje Python para entornos corporativos y universitarios basados en Microsoft 365 y Microsoft Entra ID (anteriormente Azure Active Directory).

A diferencia de los modelos de orquestación en la nube basados en API públicas, este sistema implementa un modelo de seguridad de **Cero Fugas de Información (Zero Data Leakage)** y **Confianza Cero (Zero Trust)** mediante la integración de tres componentes críticos:

1. **Inferencia Cognitiva Local (Ollama - Modelos Phi-3 / Llama 3 / Qwen):** El procesamiento de lenguaje natural (NLP) para la clasificación de incidencias y análisis semántico de correos electrónicos entrantes se ejecuta de manera cien por ciento local dentro del servidor, evitando la transmisión de datos sensibles o identidades de estudiantes hacia infraestructuras de terceros.
2. **Motor Heurístico Determinista de Alta Velocidad (Latencia < 2 ms):** De forma paralela a la inferencia del modelo, el sistema ejecuta reglas de negocio locales para la validación de matrículas institucionales, comprobación de formatos y consulta en texto plano del reglamento y directorio institucional (`kb_utm.txt`), erradicando el riesgo de alucinaciones asociadas a los modelos de lenguaje.
3. **Integración Nativa vía Microsoft Graph API (OAuth 2.0):** El motor interactúa de manera programática con el ecosistema de Microsoft 365 para la lectura y envío de mensajería oficial, restablecimiento automatizado y seguro de credenciales en Microsoft Entra ID, liberación de correos retenidos en cuarentena y canalización automática de solicitudes interdepartamentales.

**Desarrollo y Arquitectura Principal:** Departamento de Sistemas e Infraestructura TI (UTM).

---

## 1. Características Principales y Especificaciones de Funcionamiento

* **Consulta Determinista de Normativas (`kb_utm.txt`):** Toda la información corporativa, reglamentos de titulación, aranceles bancarios de trámites, horarios de laboratorios y directorios académicos y administrativos se almacena en un archivo de texto plano estructurado. El sistema extrae en microsegundos la sección temática exacta solicitada por el usuario, formateando la respuesta en plantillas HTML corporativas.
* **Gestión Automatizada de Identidades y Credenciales (Microsoft Entra ID):**
  * *Alumnos y Usuarios Institucionales:* Al detectar una solicitud legítima proveniente de una cuenta `@utmatamoros.edu.mx` o una matrícula válida, el sistema autentica la solicitud, genera una contraseña temporal criptográficamente robusta (`hashlib` + `string`), ejecuta la mutación `PATCH` directamente en Graph API y envía las credenciales de acceso de forma segura.
  * *Solicitudes desde Correos Externos (Gmail, Outlook.com, Yahoo):* Por directivas de seguridad corporativa, cualquier solicitud de reseteo de contraseña proveniente de un dominio externo es interceptada y suspendida. El orquestador requiere la adjunción de una identificación oficial del alumno y transfiere el ticket al panel de administración para dictamen manual.
  * *Cuentas de Personal Docente y Administrativo:* El sistema discrimina automáticamente las cuentas del personal docente y administrativo, evitando modificaciones automatizadas y derivando el caso a la mesa de soporte técnico especializada.
* **Enrutamiento Interdepartamental Inteligente (`Forward` Graph API):** Cuando el análisis semántico identifica consultas o envíos de documentación dirigidos a áreas específicas (como la Coordinación de Estadías y Prácticas Profesionales o Servicios Escolares), el sistema reenvía el correo original y sus archivos adjuntos de manera íntegra al departamento correspondiente, notificando simultáneamente al remitente sobre la canalización de su trámite.
* **Defensa Proactiva y Mitigación de Phishing:** El núcleo incorpora rutinas de monitoreo e invocación de scripts PowerShell (`.ps1`) y métodos Python para identificar campañas masivas de suplantación de identidad, incautar correos maliciosos en buzones corporativos y emitir alertas de ciberseguridad a los usuarios afectados.
* **Auditoría y Trazabilidad Local (`soporte_utm.db`):** El sistema mantiene una base de datos relacional local en formato SQLite donde se registra el historial de tickets, resúmenes de conversación, intenciones detectadas y análisis estadístico para la optimización continua de preguntas frecuentes.

---

## 2. Requisitos Previos y Configuración del Entorno de Despliegue

### 2.1 Requisitos del Servidor
* **Sistema Operativo:** Windows Server, Windows 10/11 o distribución Linux (Ubuntu/Debian/RHEL).
* **Intérprete de Python:** Versión 3.9 o superior configurada en las variables de entorno (`PATH`).
* **Motor de Inferencia Ollama:** Instalado en el servidor con el modelo base descargado (`phi3` o superior).
* **Privilegios de Administración:** Acceso como Administrador de Aplicaciones o Administrador Global en Microsoft Entra ID (Azure Portal).

### 2.2 Instalación de Dependencias del Proyecto
Abra una sesión de terminal en el directorio principal del proyecto y ejecute los siguientes comandos para crear un entorno virtual aislado e instalar las bibliotecas oficiales:

```bash
# 1. Clonar el repositorio
git clone https://github.com/Doku566/IA-SOPORTE-MICROSOFT.git
cd IA-SOPORTE-MICROSOFT

# 2. Crear y activar el entorno virtual
python -m venv venv

# En sistemas Windows (Command Prompt):
venv\Scripts\activate
# En sistemas Windows (PowerShell):
venv\Scripts\Activate.ps1
# En sistemas Linux / macOS:
source venv/bin/activate

# 3. Instalar dependencias de la aplicación
pip install requests msal python-dotenv fastapi reportlab PyQt5 pywin32 Pillow
```

---

## 3. Registro de la Aplicación en Microsoft Entra ID (Azure)

Para que el orquestador posea autorización para interactuar de forma delegada o como servicio con Microsoft Graph API, es obligatorio registrar la aplicación:

1. Acceda al portal de administración en [https://portal.azure.com/](https://portal.azure.com/) y seleccione **Microsoft Entra ID**.
2. Diríjase a la sección **Registros de aplicaciones (App registrations)** y haga clic en **Nuevo registro (New registration)**.
3. Asigne un nombre descriptivo a la aplicación (por ejemplo, `Soporte-IA-Orquestador-UTM`).
4. En el panel de navegación izquierdo, seleccione **Certificados y secretos (Certificates & secrets)**, genere un nuevo **Secreto de cliente (Client secret)** y conserve una copia segura de su valor.
5. Diríjase a **Permisos de API (API permissions)**, seleccione **Agregar un permiso -> Microsoft Graph -> Permisos de aplicación (Application permissions)** y agregue los siguientes alcances:
   * `Mail.ReadWrite`: Permite leer, mover, categorizar y marcar correos en el buzón de soporte técnico.
   * `Mail.Send`: Permite al servicio enviar correos electrónicos oficiales de respuesta y canalización.
   * `User.ReadWrite.All`: Permite leer atributos de identidad y actualizar la contraseña de las cuentas de estudiantes en Microsoft Entra ID.
6. Haga clic en el botón **Conceder consentimiento de administrador para [Nombre del Tenant]** para autorizar el uso de estas interfaces en toda la organización.

---

## 4. Configuración de Archivos Críticos del Sistema (`.env` y `kb_utm.txt`)

### 4.1 Archivo de Variables de Entorno (`.env`)
El repositorio incluye el archivo de plantilla `.env.template`. Cree una copia o renómbrelo exactamente como `.env` en el directorio raíz. Introduzca los identificadores criptográficos y de red de su infraestructura corporativa:

```env
# ==============================================================================
# CONFIGURACIÓN DE MICROSOFT ENTRA ID (GRAPH API OAUTH 2.0)
# ==============================================================================
# ID de directorio (inquilino/Tenant ID) de su organización en Azure Entra ID
TENANT_ID=xxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# ID de aplicación (cliente/Client ID) generado al registrar la aplicación
CLIENT_ID=yyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy

# Valor del secreto de cliente creado en la sección Certificados y secretos
CLIENT_SECRET=zzzzzzzz~zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz

# ==============================================================================
# IDENTIDADES Y BUZONES DE ATENCIÓN OFICIAL
# ==============================================================================
# Dirección de correo electrónico del buzón automatizado que procesará incidencias
SUPPORT_EMAIL=soporte-ia@tu-organizacion.edu.mx

# Dirección de correo electrónico del administrador o responsable del servicio TI
ADMIN_EMAIL=admin.ti@tu-organizacion.edu.mx

# ==============================================================================
# ENDPOINTS LOCALES Y PUERTOS DE OPERACIÓN
# ==============================================================================
# URL del servicio REST local de Ollama (por defecto opera en el puerto 11434)
OLLAMA_URL=http://localhost:11434/api/generate

# Puerto de escucha para el servidor web administrativo y API REST FastAPI
FASTAPI_PORT=8000

# URL de acceso local o de red para los enlaces de verificación y gestión
BASE_URL=http://localhost:8000
```

> **NOTA DE SEGURIDAD:** El archivo `.env` se encuentra explícitamente excluido del seguimiento de control de versiones mediante el archivo `.gitignore`. Es responsabilidad del administrador garantizar que las credenciales reales de producción jamás sean publicadas en repositorios públicos.

### 4.2 Archivo de Base de Conocimientos Institucional (`kb_utm.txt`)
El archivo `kb_utm.txt` es la fuente de verdad estática de la organización. Para adaptar el motor a otra institución o actualizar normativas vigentes, edite las secciones respetando la estructura por encabezados numerados (por ejemplo, `## 1. Misión`, `## 9. Titulación y Estadías`, `## 12. Directorio`). Cuando el módulo de clasificación detecte consultas informativas, la búsqueda se dirigirá y delimitará exclusivamente a este archivo.

---

## 5. Puesta en Marcha del Orquestador

### 5.1 Preparación y Verificación del Modelo de IA Local
Asegúrese de que el servicio base de Ollama se encuentre activo y de haber descargado previamente el modelo lingüístico en el servidor:

```bash
# Descarga e inicialización del modelo base Phi-3 (recomendado para alta velocidad en CPU)
ollama pull phi3
```

### 5.2 Ejecución del Servicio en Entornos Windows
El repositorio incluye un script por lotes optimizado (`start_soporte_ia.bat`) para su ejecución continua en servidores de infraestructura Windows:

```cmd
start_soporte_ia.bat
```

Este procedimiento ejecuta de forma secuencial:
1. La limpieza y finalización de procesos duplicados del orquestador.
2. La inicialización del servicio de inferencia Ollama en segundo plano (aplicando directivas para evitar sobrecarga del búfer de memoria en procesadores genéricos).
3. La activación del entorno virtual de Python.
4. El inicio del ciclo de monitoreo continuo de Graph API (`orchestrator.py`).

### 5.3 Ejecución Estándar desde Consola / Linux
Para iniciar el servicio en servidores Linux o en modo manual:

```bash
python -u orchestrator.py
```

El sistema iniciará el ciclo de sondeo del buzón institucional en intervalos periódicos de 30 segundos, emitiendo en la salida estándar un informe estructurado con el identificador de cada mensaje procesado, su clasificación de intención, el tiempo de respuesta del modelo y el folio del ticket generado.

---

## 6. Estructura de Archivos del Núcleo del Proyecto

* **`orchestrator.py`:** Motor principal del sistema. Administra la conexión con Microsoft Graph API, el bucle de procesamiento de buzón, el análisis semántico y determinista, el enrutamiento interdepartamental y la generación de maquetación HTML.
* **`database.py`:** Módulo relacional y de persistencia. Configura las tablas locales SQLite (`soporte_utm.db`), controla la concurrencia en el registro de tickets y almacena estadísticas para auditoría corporativa.
* **`admin_dashboard.py`:** Módulo web FastAPI para la visualización y gestión administrativa de los tickets de soporte.
* **`kb_utm.txt`:** Base de conocimientos institucional estructurada en texto plano.
* **`.env.template`:** Plantilla estandarizada de variables de configuración para nuevos despliegues.
* **`Guia_Arquitectura_e_Ingenieria_Soporte_IA_UTM.md`:** Documento de especificación arquitectónica detallada, análisis de rendimiento y esquemas de ciberseguridad corporativa.
* **`start_soporte_ia.bat`:** Script de automatización y despliegue para servidores Windows.
* **`generar_manual_pdf.py`:** Herramienta de generación automática de documentación ejecutiva en formato PDF (normativa APA) utilizando ReportLab.

---

## 7. Licencia y Derechos de Propiedad Corporativa

Este desarrollo forma parte de la infraestructura de automatización y ciberseguridad corporativa de la institución.
* **Desarrollo e Ingeniería:** Departamento de Sistemas - Universidad Tecnológica de Matamoros (UTM).
* **Autoría y Mantenimiento:** Departamento de Sistemas e Infraestructura TI (`Sistemas TI`).
