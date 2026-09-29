"""MediStock 360 — FastAPI application entry point."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.background import run_forever
from app.config import settings
from app.seed.seed_db import seed_database
from app.services.memory_service import sync_incident_memory_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed_database()
    sync_incident_memory_status()
    task = asyncio.create_task(run_forever())
    yield
    task.cancel()


app = FastAPI(title="MediStock 360 API", version="1.0.0", lifespan=lifespan,
              description="Pharmacy inventory operations agent with persistent operational memory (Hindsight).")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # Never leak stack traces to the UI; the full traceback goes to the server log.
    logging.getLogger("medistock").exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Unexpected server error. The details were written to the backend log."})
