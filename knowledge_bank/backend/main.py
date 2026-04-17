from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api import approvals, knowledge, signals, sources, summary
from backend.db.init_db import init_db

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Knowledge Bank MVP",
    description="Hackathon MVP backend for the Durham AI Education System Upgrade Knowledge Bank module.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(sources.router)
app.include_router(summary.router)
app.include_router(knowledge.router)
app.include_router(approvals.router)
app.include_router(signals.router)
