from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import SQLModel

from forge_platform.database import get_engine
from forge_platform.models import Tenant  # noqa: F401 — ensure models registered
from forge_platform.routers import health, tenants


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(get_engine())
    yield


app = FastAPI(title="Forge Platform", lifespan=lifespan)
app.include_router(health.router)
app.include_router(tenants.router)
