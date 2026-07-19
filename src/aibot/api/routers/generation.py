"""Endpoint постановки ручной AI-генерации в Celery."""

from fastapi import APIRouter, status

from aibot.api.deps import TaskQueueDep
from aibot.api.schemas.generation import ManualGenerationRequest
from aibot.api.schemas.task import TaskQueuedResponse

router = APIRouter(prefix="/generate", tags=["generation"])


@router.post(
    "/",
    response_model=TaskQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue manual post generation",
)
async def generate_manually(
    payload: ManualGenerationRequest,
    task_queue: TaskQueueDep,
) -> TaskQueuedResponse:
    """Поставить AI-генерацию произвольного текста в Celery."""

    task_id = task_queue.enqueue_manual_generation(payload.text)
    return TaskQueuedResponse(task_id=task_id)
