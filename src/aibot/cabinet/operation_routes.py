"""Authenticated polling routes operational состояния."""

import uuid

from fastapi import APIRouter, HTTPException, Request

from aibot.config import Settings


def build_cabinet_operation_router(settings: Settings) -> APIRouter:
    """Собрать read-only JSON polling endpoint внутри защищённого mount."""

    router = APIRouter()
    mount = settings.cabinet_mount_path.rstrip("/")

    @router.get(f"{mount}/pipeline/{{run_id}}/status")
    async def pipeline_status(run_id: uuid.UUID, request: Request) -> dict[str, object]:
        item = await request.app.state.cabinet_operational_reader.get_pipeline_run(run_id)
        if item is None:
            raise HTTPException(status_code=404, detail="PipelineRun not found")
        return {
            "id": str(item.id),
            "operation": item.operation,
            "status": item.status,
            "task_id": item.task_id,
            "result_counts": item.result_counts,
            "error_category": item.error_category,
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
            "finished_at": item.finished_at.isoformat() if item.finished_at else None,
        }

    return router
