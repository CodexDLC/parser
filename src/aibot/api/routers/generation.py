"""Endpoint ручной AI-генерации поста из произвольного текста."""

from fastapi import APIRouter, HTTPException, status

from aibot.api.deps import PostGenerationServiceDep
from aibot.api.schemas.generation import ManualGenerationRequest, ManualGenerationResponse
from aibot.integrations.ai_client import (
    AIClientAuthenticationError,
    AIClientInvalidResponseError,
    AIClientRateLimitError,
    AIClientTimeoutError,
)

router = APIRouter(prefix="/generate", tags=["generation"])


@router.post("/", response_model=ManualGenerationResponse, summary="Generate post manually")
async def generate_manually(
    payload: ManualGenerationRequest,
    service: PostGenerationServiceDep,
) -> ManualGenerationResponse:
    """Сгенерировать Telegram-пост из произвольного текста."""

    try:
        generated_text = await service.generate_manual_post(payload.text)
    except AIClientRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except AIClientTimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)) from exc
    except (AIClientAuthenticationError, AIClientInvalidResponseError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return ManualGenerationResponse(
        generated_text=generated_text,
        fake_mode=service.settings.ai_fake_mode or not service.settings.openai_api_key,
    )
