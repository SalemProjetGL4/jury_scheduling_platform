from __future__ import annotations

from fastapi import FastAPI

from api.routes import router


app = FastAPI(title="Juriq Translator Service", version="0.1.0")


@app.get("/health", tags=["health"])
def healthcheck():
    return {"status": "ok"}


app.include_router(router)
