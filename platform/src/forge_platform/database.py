from functools import lru_cache

from sqlmodel import Session, create_engine

from forge_platform.config import settings


@lru_cache
def get_engine():
    return create_engine(settings.database_url)


def get_session():
    with Session(get_engine()) as session:
        yield session
