# Sistema de Soporte Tecnico - UT Matamoros

Este proyecto implementa un sistema de soporte tecnico automatizado diseñado para la Universidad Tecnologica de Matamoros. Su función principal es la gestión y automatización del restablecimiento de contraseñas institucionales mediante la integración con Microsoft Graph API y modelos de procesamiento de lenguaje (LLM).

## Arquitectura y Componentes

El sistema se basa en una arquitectura de servicios desacoplados que interactúan con el ecosistema de Microsoft 365:

1.  **Motor de Extraccion (LLM):** Utiliza Llama 3 para la clasificacion de intenciones y la extraccion de entidades a partir de correos electronicos.
2.  **Modulo de Validacion:** Realiza una validacion cruzada entre la solicitud del usuario y la base de datos institucional.
3.  **Servicio de Correo (Microsoft Graph):** Gestiona el monitoreo del buzón de soporte, el envio de codigos OTP y la entrega de credenciales.
4.  **Flujo de Aprobacion Externa:** Mecanismo de seguridad para solicitudes provenientes de dominios externos.

## Configuracion del Sistema

### Requisitos Previos

*   Python 3.10 o superior.
*   Registro de aplicacion en Azure Portal con permisos Mail.ReadWrite, Mail.Send, e User.ReadWrite.All.

### Instalacion

1.  Instalacion de dependencias:
    ```bash
    pip install -r requirements.txt
    ```
2.  Configuracion de entorno:
    Copie el archivo .env.example a .env y complete las credenciales.

## Ejecucion

Para iniciar el servicio:
```bash
python -m app.main
```

---
Soporte Tecnico - UT Matamoros | 2026
