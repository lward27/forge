import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from forge_platform.database import get_session
from forge_platform.models.llm_provider import LLMProvider
from forge_platform.models.tenant_llm_config import TenantLLMConfig
from forge_platform.models.ai_usage import AIUsage

router = APIRouter(prefix="/admin", tags=["admin-llm"])


# ── LLM Providers ─────────────────────────────────────────

@router.post("/llm-providers", status_code=201)
def create_provider(body: dict, session: Session = Depends(get_session)):
    provider = LLMProvider(
        name=body["name"],
        api_url=body["api_url"],
        api_key_encrypted=body.get("api_key", ""),
        model=body["model"],
        pricing_input=body.get("pricing_input", 0),
        pricing_output=body.get("pricing_output", 0),
    )
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return _provider_response(provider)


@router.get("/llm-providers")
def list_providers(session: Session = Depends(get_session)):
    providers = list(session.exec(select(LLMProvider)).all())
    return {"providers": [_provider_response(p) for p in providers]}


@router.put("/llm-providers/{provider_id}")
def update_provider(provider_id: uuid.UUID, body: dict, session: Session = Depends(get_session)):
    p = session.get(LLMProvider, provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    for field in ["name", "api_url", "model", "pricing_input", "pricing_output", "is_active"]:
        if field in body:
            setattr(p, field, body[field])
    if "api_key" in body:
        p.api_key_encrypted = body["api_key"]
    session.add(p)
    session.commit()
    session.refresh(p)
    return _provider_response(p)


@router.delete("/llm-providers/{provider_id}")
def delete_provider(provider_id: uuid.UUID, session: Session = Depends(get_session)):
    p = session.get(LLMProvider, provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    session.delete(p)
    session.commit()
    return {"deleted": True}


# ── Tenant LLM Assignment ─────────────────────────────────

@router.post("/tenants/{tenant_id}/llm")
def assign_provider(tenant_id: uuid.UUID, body: dict, session: Session = Depends(get_session)):
    config = TenantLLMConfig(
        tenant_id=tenant_id,
        provider_id=body["provider_id"],
    )
    session.add(config)
    session.commit()
    session.refresh(config)
    return {"id": str(config.id), "tenant_id": str(tenant_id), "provider_id": str(config.provider_id)}


@router.get("/tenants/{tenant_id}/llm")
def get_tenant_llm(tenant_id: uuid.UUID, session: Session = Depends(get_session)):
    configs = list(session.exec(
        select(TenantLLMConfig).where(
            TenantLLMConfig.tenant_id == tenant_id,
            TenantLLMConfig.is_active == True,  # noqa: E712
        )
    ).all())
    result = []
    for c in configs:
        p = session.get(LLMProvider, c.provider_id)
        if p:
            result.append({
                "config_id": str(c.id),
                "provider": _provider_response(p),
            })
    return {"llm_configs": result}


@router.delete("/tenants/{tenant_id}/llm/{config_id}")
def remove_provider(tenant_id: uuid.UUID, config_id: uuid.UUID, session: Session = Depends(get_session)):
    config = session.get(TenantLLMConfig, config_id)
    if config is None or config.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Config not found")
    config.is_active = False
    session.add(config)
    session.commit()
    return {"deleted": True}


# ── Usage ─────────────────────────────────────────────────

@router.get("/ai-usage")
def get_usage(
    tenant_id: uuid.UUID | None = None,
    session: Session = Depends(get_session),
):
    stmt = select(AIUsage)
    if tenant_id:
        stmt = stmt.where(AIUsage.tenant_id == tenant_id)
    records = list(session.exec(stmt.order_by(AIUsage.created_at.desc()).limit(100)).all())  # type: ignore
    total_cost = sum(r.cost_input + r.cost_output for r in records)
    total_input = sum(r.input_tokens for r in records)
    total_output = sum(r.output_tokens for r in records)
    return {
        "total_cost": round(total_cost, 4),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "records": [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost": round(r.cost_input + r.cost_output, 6),
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ],
    }


def _provider_response(p):
    return {
        "id": str(p.id),
        "name": p.name,
        "api_url": p.api_url,
        "model": p.model,
        "pricing_input": p.pricing_input,
        "pricing_output": p.pricing_output,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
