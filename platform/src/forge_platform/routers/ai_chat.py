"""AI Chat endpoint — orchestrates LLM + tool execution."""
import json
import logging
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal


class SafeEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal, datetime, date, UUID, etc."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from forge_platform.database import get_session
from forge_platform.models.ai_conversation import AIConversation
from forge_platform.models.ai_usage import AIUsage
from forge_platform.models.llm_provider import LLMProvider
from forge_platform.models.tenant_llm_config import TenantLLMConfig
from forge_platform.services import ai_context, ai_tools, database_service, llm_service, tenant_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

MAX_TOOL_ROUNDS = 5  # allow enough rounds for template deploy + populate


@router.post("/chat")
def chat(
    body: dict,
    session: Session = Depends(get_session),
):
    tenant_id = uuid.UUID(body["tenant_id"])
    database_id = uuid.UUID(body["database_id"])
    message = body["message"]
    conversation_id = body.get("conversation_id")

    # Get tenant and database
    tenant = tenant_service.get_tenant(session, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant_db = database_service.get_database(session, tenant_id, database_id)
    if tenant_db is None:
        raise HTTPException(status_code=404, detail="Database not found")

    # Get LLM provider for this tenant
    provider = _get_provider(session, tenant_id)
    if provider is None:
        raise HTTPException(status_code=400, detail="No LLM provider configured for this tenant")

    # Load or create conversation
    conversation = None
    if conversation_id:
        conversation = session.get(AIConversation, uuid.UUID(conversation_id))

    if conversation is None:
        conversation = AIConversation(
            tenant_id=tenant_id,
            database_id=database_id,
            messages=[],
        )
        session.add(conversation)
        session.flush()

    # Build system context
    context = ai_context.build_context(
        session, tenant.name, tenant_db.name, tenant_db.id
    )

    # Build messages for LLM
    llm_messages = [{"role": "system", "content": context}]

    # Add conversation history
    for m in conversation.messages:
        llm_messages.append(m)

    # Add new user message
    llm_messages.append({"role": "user", "content": message})

    # Track actions taken
    actions_taken = []
    total_input = 0
    total_output = 0
    final_content = None

    # Tool execution loop
    for _round in range(MAX_TOOL_ROUNDS):
        result = llm_service.chat_completion(provider, llm_messages, ai_tools.TOOLS)
        total_input += result.get("input_tokens", 0)
        total_output += result.get("output_tokens", 0)

        tool_calls = result.get("tool_calls")
        content = result.get("content")

        if content:
            final_content = content

        if not tool_calls:
            # No more tool calls — done
            break

        # Add assistant message with tool calls
        assistant_msg = {"role": "assistant", "content": content}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        llm_messages.append(assistant_msg)

        # Execute each tool call
        for tc in tool_calls:
            func = tc["function"]
            tool_name = func["name"]
            try:
                tool_args = json.loads(func["arguments"]) if isinstance(func["arguments"], str) else func["arguments"]
            except json.JSONDecodeError:
                tool_args = {}

            logger.info("Executing tool: %s args=%s", tool_name, tool_args)
            tool_result = ai_tools.execute_tool(session, tenant_db, tool_name, tool_args)
            actions_taken.append({
                "tool": tool_name,
                "args": tool_args,
                "result": "success" if "error" not in tool_result else tool_result["error"],
            })

            # Add tool result to messages
            llm_messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": json.dumps(tool_result, cls=SafeEncoder),
            })

    # Save conversation with actions metadata
    conversation.messages = conversation.messages + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": final_content or "", "actions": actions_taken},
    ]
    conversation.updated_at = datetime.now(timezone.utc)
    session.add(conversation)

    # Track usage
    usage = AIUsage(
        tenant_id=tenant_id,
        provider_id=provider.id,
        input_tokens=total_input,
        output_tokens=total_output,
        cost_input=total_input * provider.pricing_input / 1_000_000,
        cost_output=total_output * provider.pricing_output / 1_000_000,
    )
    session.add(usage)
    session.commit()

    return {
        "conversation_id": str(conversation.id),
        "response": final_content or "",
        "actions_taken": actions_taken,
        "usage": {
            "input_tokens": total_input,
            "output_tokens": total_output,
        },
    }


@router.get("/conversations")
def list_conversations(
    tenant_id: str,
    database_id: str,
    session: Session = Depends(get_session),
):
    convos = list(session.exec(
        select(AIConversation).where(
            AIConversation.tenant_id == uuid.UUID(tenant_id),
            AIConversation.database_id == uuid.UUID(database_id),
        ).order_by(AIConversation.updated_at.desc())  # type: ignore
    ).all())
    return {
        "conversations": [
            {
                "id": str(c.id),
                "message_count": len(c.messages),
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in convos
        ]
    }


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: uuid.UUID, session: Session = Depends(get_session)):
    c = session.get(AIConversation, conversation_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "id": str(c.id),
        "messages": c.messages,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: uuid.UUID, session: Session = Depends(get_session)):
    c = session.get(AIConversation, conversation_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    session.delete(c)
    session.commit()
    return {"deleted": True}


def _get_provider(session: Session, tenant_id: uuid.UUID) -> LLMProvider | None:
    """Get the active LLM provider for a tenant."""
    config = session.exec(
        select(TenantLLMConfig).where(
            TenantLLMConfig.tenant_id == tenant_id,
            TenantLLMConfig.is_active == True,  # noqa: E712
        )
    ).first()
    if config is None:
        return None
    return session.get(LLMProvider, config.provider_id)
