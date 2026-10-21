# supermart/api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from supermart.api.routes.inventory import router as inventory_router
from supermart.config import settings
from supermart.database import SessionLocal

app = FastAPI(title="SuperMart POS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(inventory_router)


@app.get("/health/live", include_in_schema=False)
def liveness():
    return {"status": "alive"}


@app.get("/health/ready", include_in_schema=False)
def readiness():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ready"}
