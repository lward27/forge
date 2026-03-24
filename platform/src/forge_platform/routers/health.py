from fastapi import APIRouter, Depends
from sqlmodel import Session, text

from forge_platform.database import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready(session: Session = Depends(get_session)):
    session.exec(text("SELECT 1"))
    return {"status": "ready", "database": "connected"}
