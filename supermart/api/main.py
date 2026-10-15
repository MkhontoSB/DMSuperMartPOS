# supermart/api/main.py
from fastapi import FastAPI
from sqlalchemy import text
from supermart.database import SessionLocal
 
app = FastAPI(title="SuperMart POS API", version="1.0.0")
 
@app.get("/health/live", include_in_schema=False)
def liveness():
    return {"status": "alive"}
 
@app.get("/health/ready", include_in_schema=False)
def readiness():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ready"}
