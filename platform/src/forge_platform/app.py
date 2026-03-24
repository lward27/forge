from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import SQLModel

from forge_platform.database import get_engine
from forge_platform.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(get_engine())
    yield


app = FastAPI(title="Forge Platform", lifespan=lifespan)
app.include_router(health.router)
