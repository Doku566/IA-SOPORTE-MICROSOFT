# Sistema de Soporte Técnico - UT Matamoros

Este proyecto implementa un sistema de soporte técnico automatizado diseñado para la Universidad Tecnológica de Matamoros. Su función principal es la gestión y automatización del restablecimiento de contraseñas institucionales mediante la integración con Microsoft Graph API y modelos de procesamiento de lenguaje (LLM).

## Arquitectura y Componentes

El sistema se basa en una arquitectura de servicios desacoplados que interactúan con el ecosistema de Microsoft 365:

1.  **Motor de Extracción (LLM):** Utiliza Llama 3.1 para la clasificación de intenciones y la extracción de entidades (matrícula, nombre, carrera) a partir de correos electrónicos no estructurados.
2.  **Módulo de Validación (Iron Gate):** Realiza una validación cruzada entre la solicitud del usuario y la base de datos institucional (+7,400 registros). Implementa lógica de normalización de texto para manejar variaciones en nombres y acentos.
3.  **Servicio de Correo (Microsoft Graph):** Gestiona el monitoreo del buzón de soporte, el envío de códigos OTP y la entrega de credenciales temporales.
4.  **Flujo de Aprobación Externa:** Implementa un mecanismo de seguridad donde las solicitudes provenientes de dominios externos (Gmail, Outlook personal, etc.) son bloqueadas y enviadas a una cola de aprobación manual por parte del administrador.

## Configuración del Sistema

### Requisitos Previos

*   Python 3.10 o superior.
*   Registro de aplicación en Azure Portal con permisos `Mail.ReadWrite`, `Mail.Send`, e `User.ReadWrite.All`.
*   Asignación del rol "Administrador de Usuarios" a la aplicación en Entra ID para ejecutar el reseteo de contraseñas.

### Instalación

1.  Instalación de dependencias:
    ```bash
    pip install -r requirements.txt
    ```
2.  Configuración de entorno:
    Copie el archivo `.env.example` a `.env` y complete las credenciales de Azure y la API Key de Groq.
3.  Preparación de la base de datos:
    ```bash
    python tools/create_db.py
    python tools/sync_students_ad.py
    ```

## Ejecución

Para iniciar el servicio de monitoreo y procesamiento:
```bash
python -m app.main
```

## Estructura de Directorios

*   `app/`: Contiene la lógica de negocio, modelos de datos y servicios de integración.
*   `data/`: Almacén de datos local (SQLite) para la persistencia de tickets y caché de estudiantes.
*   `tools/`: Scripts de administración para mantenimiento de base de datos y sincronización con Azure AD.
*   `docs/`: Documentación técnica detallada sobre la configuración de servicios externos.

---
Soporte Técnico - UT Matamoros | 2026
