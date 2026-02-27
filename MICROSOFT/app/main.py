import asyncio
from fastapi import FastAPI, BackgroundTasks
from contextlib import asynccontextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.services.processor import ProcessorService
from app.models.student import Student

# Base de Datos
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

is_polling_active = True

async def email_polling_loop():
    print("Iniciando ciclo de revision de correos...")
    
    while is_polling_active:
        try:
            db = SessionLocal()
            processor = ProcessorService(db)
            await asyncio.to_thread(processor.process_inbox)
            db.close()
        except Exception as e:
            print(f"Error critico en servidor: {e}")
        
        await asyncio.sleep(30)

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    polling_task = loop.create_task(email_polling_loop())
    yield
    global is_polling_active
    is_polling_active = False
    polling_task.cancel()
    print("Deteniendo servicio...")

app = FastAPI(
    title="Sistema de Soporte Tecnico - UT Matamoros",
    description="Sistema de Soporte Automatizado (Validacion y OTP)",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
def read_root():
    return {"status": "active", "service": "Soporte Tecnico"}

@app.get("/health")
def health_check():
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        db_status = "ok"
    except:
        db_status = "error"
        
    return {
        "status": "ok", 
        "database": db_status, 
        "polling": "active" if is_polling_active else "inactive"
    }

if __name__ == "__main__":
    import uvicorn
    import sys
    import os
    sys.path.append(os.getcwd())
    print("Arrancando servidor de soporte...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
