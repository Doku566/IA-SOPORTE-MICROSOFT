# Motor de Soporte IA UTM - Documentación Técnica y Arquitectura

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Microsoft Graph API](https://img.shields.io/badge/Microsoft-Graph%20API-0078D4.svg)
![Ollama](https://img.shields.io/badge/LLM-Ollama%20(Phi3)-black.svg)
![Status](https://img.shields.io/badge/Status-Production-success.svg)

## Resumen Ejecutivo

Sistema orquestador automatizado, desarrollado en lenguaje Python, diseñado para la gestión y resolución autónoma de incidentes de soporte técnico de nivel 1 en la **Universidad Tecnológica de Matamoros (UTM)**. 

Este sistema reemplaza la intervención manual en flujos de trabajo críticos, optimizando los tiempos de respuesta para la comunidad estudiantil.

**Autor y Desarrollador Principal:** Domingo González Hernández (Departamento de Sistemas).

---

## 1. Características Funcionales

*   **Clasificación Cognitiva (Zero-Shot):** Implementación de un Modelo de Lenguaje Grande (LLM) local vía Ollama (modelo Phi-3) encargado de procesar el Procesamiento de Lenguaje Natural (NLP) de los correos entrantes, logrando una clasificación de alta precisión en categorías predefinidas (`PASSWORD_RESET`, `INFORMACION`, `ANOMALIA`, `IGNORAR`).
*   **Restablecimiento Automatizado de Credenciales:** Integración bidireccional con **Microsoft Graph API**. El sistema detecta solicitudes legítimas, genera secuencias criptográficas temporales, aplica el método `PATCH` directo en el Directorio Activo (Microsoft Entra ID) forzando el cambio de credenciales y notifica al usuario mediante un canal seguro.
*   **Protocolo de Seguridad y Control de Acceso:** 
    *   Validación estricta de dominios institucionales y análisis de expresiones regulares para distinguir entre estudiantes (matrículas numéricas) y personal administrativo.
    *   Filtro de aislamiento para correos externos (servicios de terceros como Gmail o Outlook): el motor interrumpe el flujo automatizado y exige verificación documental (identificación oficial), escalando la solicitud al panel del Administrador para su dictamen (Aprobación/Rechazo manual).
*   **Generación Dinámica de Respuestas (RAG):** Módulo de consulta estructurada a una Base de Conocimientos interna (`kb_utm.txt`) para resolver consultas institucionales con plantillas HTML corporativas.

---

## 2. Arquitectura del Sistema

1.  **Módulo de Interfaz (Poller):** Ciclo de consulta asíncrona hacia el buzón oficial `Soporte-IA@utmatamoros.edu.mx` a través de Microsoft Graph API.
2.  **Motor de Inferencia LLM:** Evaluación heurística del contenido de los mensajes, mitigando vulnerabilidades como el uso de "Magic Links" obsoletos.
3.  **Capa de Autenticación (Azure AD):** El sistema opera bajo un *App Registration* validado en Entra ID, contando con los privilegios granulares `User Administrator` y `Mail.ReadWrite` mediante el flujo de credenciales de cliente (OAuth 2.0).
4.  **Persistencia de Datos:** Base de datos relacional local (`soporte.db` - SQLite) que actúa como bitácora de auditoría para el seguimiento de tickets, correos de origen y estados de resolución.

---

## 3. Guía de Despliegue y Configuración

### 3.1. Requisitos del Entorno
*   Intérprete de Python versión 3.9 o superior.
*   [Ollama](https://ollama.com/) configurado en el servidor local con el modelo base `phi3` inicializado.
*   Registro de Aplicación aprovisionado en Microsoft Entra ID con permisos tipo *Application* para Microsoft Graph.

### 3.2. Instalación de Dependencias
```bash
git clone https://github.com/tu-usuario/UTM-Soporte-IA.git
cd UTM-Soporte-IA
python -m venv venv
source venv/bin/activate  # Entornos Windows: venv\Scripts\activate
pip install requests msal python-dotenv
```

### 3.3. Configuración de Variables de Entorno (`.env`)
Es imperativo configurar el archivo `.env` en la raíz del directorio con los parámetros criptográficos del tenant:
```env
TENANT_ID=identificador_del_tenant
CLIENT_ID=identificador_de_la_aplicacion
CLIENT_SECRET=secreto_de_la_aplicacion
OLLAMA_URL=http://localhost:11434/api/generate
SUPPORT_EMAIL=Soporte-IA@utmatamoros.edu.mx
ADMIN_EMAIL=correo_administrador_autorizado@utmatamoros.edu.mx
```

---

## 4. Ejecución del Servicio

Para inicializar el daemon del orquestador en el servidor de producción:

```bash
python -u orchestrator.py
```

El log del sistema registrará la latencia de las peticiones HTTP y el resultado del análisis cognitivo en intervalos de 30 segundos.

---

**© 2026 Domingo González Hernández.**  
Desarrollo de Software e Infraestructura - Universidad Tecnológica de Matamoros.  
*Este sistema representa propiedad intelectual orientada a la eficiencia operativa institucional.*
