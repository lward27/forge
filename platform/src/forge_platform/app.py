import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlmodel import SQLModel, Session

from forge_platform.database import get_engine, get_session
from forge_platform.middleware.auth import get_api_key
from forge_platform.models import (  # noqa: F401
    ApiKey, ColumnDefinition, TableDefinition, Tenant, TenantDatabase,
)
from forge_platform.routers import auth, databases, health, rows, tables, tenants
from forge_platform.services import auth_service, kubernetes_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    SQLModel.metadata.create_all(engine)

    # Bootstrap admin key on first startup
    with Session(engine) as session:
        plaintext = auth_service.bootstrap_admin_key(session)
        if plaintext:
            try:
                kubernetes_service.create_secret(
                    namespace="forge-platform",
                    name="forge-admin-key",
                    data={"api-key": plaintext},
                    labels={"forge.lucas.engineering/managed-by": "forge-platform"},
                )
                logger.info("Admin key stored in K8s Secret forge-admin-key")
            except Exception:
                logger.warning(
                    "Could not store admin key in K8s Secret (may already exist)"
                )

    yield


app = FastAPI(title="Forge Platform", lifespan=lifespan)

# CORS — allow admin panel and tenant portal origins
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://admin.forge.lucas.engineering",
        "https://app.forge.lucas.engineering",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routes (no auth)
app.include_router(health.router)

# Protected routes (auth required via dependency)
app.include_router(auth.router, dependencies=[Depends(get_api_key)])
app.include_router(tenants.router, dependencies=[Depends(get_api_key)])
app.include_router(databases.router, dependencies=[Depends(get_api_key)])
app.include_router(tables.router, dependencies=[Depends(get_api_key)])
app.include_router(rows.router, dependencies=[Depends(get_api_key)])
