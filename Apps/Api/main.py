from fastapi import FastAPI
from Apps.Api.schemas.models import Recipe
app = FastAPI(title="Recipeer API", version="0.0.1")

@app.get("/health")
def health(): 
    return {"ok": True}

