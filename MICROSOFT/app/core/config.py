from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Sistema de Soporte Tecnico - UT Matamoros"
    API_V1_STR: str = "/api/v1"
    
    DATABASE_URL: str = "sqlite:///./data/students.db"
    
    GROQ_API_KEY: str = ""
    SECRET_KEY: str = "super_secret_key_change_me"
    
    SMTP_SERVER: str = "smtp.office365.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    IMAP_SERVER: str = "outlook.office365.com"

    AZURE_CLIENT_ID: str = ""
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_SECRET: str = ""
    GRAPH_USER_EMAIL: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
