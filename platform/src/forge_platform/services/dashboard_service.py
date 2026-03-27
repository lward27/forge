import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from forge_platform.models.dashboard import Dashboard


def create_dashboard(
    session: Session,
    database_id: uuid.UUID,
    name: str,
    is_default: bool = False,
    config: dict | None = None,
) -> Dashboard:
    # If setting as default, unset any existing default
    if is_default:
        _unset_defaults(session, database_id)

    dashboard = Dashboard(
        database_id=database_id,
        name=name,
        is_default=is_default,
        config=config or {"widgets": [], "grid_cols": 12},
    )
    session.add(dashboard)
    session.commit()
    session.refresh(dashboard)
    return dashboard


def list_dashboards(session: Session, database_id: uuid.UUID) -> list[Dashboard]:
    return list(session.exec(
        select(Dashboard).where(Dashboard.database_id == database_id)
    ).all())


def get_dashboard(session: Session, dashboard_id: uuid.UUID) -> Dashboard | None:
    return session.get(Dashboard, dashboard_id)


def get_default_dashboard(session: Session, database_id: uuid.UUID) -> Dashboard | None:
    return session.exec(
        select(Dashboard).where(
            Dashboard.database_id == database_id,
            Dashboard.is_default == True,  # noqa: E712
        )
    ).first()


def update_dashboard(
    session: Session,
    dashboard_id: uuid.UUID,
    name: str | None = None,
    is_default: bool | None = None,
    config: dict | None = None,
) -> Dashboard | None:
    dashboard = session.get(Dashboard, dashboard_id)
    if dashboard is None:
        return None

    if name is not None:
        dashboard.name = name
    if is_default is not None and is_default:
        _unset_defaults(session, dashboard.database_id)
        dashboard.is_default = True
    if config is not None:
        dashboard.config = config

    dashboard.updated_at = datetime.now(timezone.utc)
    session.add(dashboard)
    session.commit()
    session.refresh(dashboard)
    return dashboard


def delete_dashboard(session: Session, dashboard_id: uuid.UUID) -> bool:
    dashboard = session.get(Dashboard, dashboard_id)
    if dashboard is None:
        return False
    session.delete(dashboard)
    session.commit()
    return True


def _unset_defaults(session: Session, database_id: uuid.UUID) -> None:
    existing = session.exec(
        select(Dashboard).where(
            Dashboard.database_id == database_id,
            Dashboard.is_default == True,  # noqa: E712
        )
    ).all()
    for d in existing:
        d.is_default = False
        session.add(d)
    session.flush()
