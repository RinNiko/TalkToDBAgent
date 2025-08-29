"""
Query history endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.base import get_db_session
from app.db.models.query_history import QueryHistory
from app.schemas.common import QueryExecutionRequest
from app.services.sql.executor import SQLExecutorService

router = APIRouter()


class HistoryItem(BaseModel):
    id: int
    connection_id: int
    prompt: Optional[str] = None
    sql: str
    row_count: int
    execution_time_ms: int
    success: bool
    error: Optional[str] = None
    pinned: bool
    created_at: str


class HistoryListResponse(BaseModel):
    items: list[HistoryItem]


@router.get("/")
async def list_history(limit: int = 50, db: Session = Depends(get_db_session)):
    """List recent query history (pinned first, then recent)."""
    q = db.query(QueryHistory).order_by(desc(QueryHistory.pinned), desc(QueryHistory.created_at)).limit(limit)
    items = [
        HistoryItem(
            id=r.id,
            connection_id=r.connection_id,
            prompt=r.prompt,
            sql=r.sql,
            row_count=r.row_count,
            execution_time_ms=r.execution_time_ms,
            success=r.success,
            error=r.error,
            pinned=r.pinned,
            created_at=r.created_at.isoformat()+"Z",
        ) for r in q.all()
    ]
    return {"items": items}


@router.post("/{history_id}/pin")
async def pin_history(history_id: int, pinned: bool = True, db: Session = Depends(get_db_session)):
    rec = db.query(QueryHistory).filter(QueryHistory.id == history_id).one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="History not found")
    rec.pinned = bool(pinned)
    db.commit()
    return {"success": True, "pinned": rec.pinned}


@router.post("/{history_id}/rerun")
async def rerun_query(history_id: int, db: Session = Depends(get_db_session)):
    rec = db.query(QueryHistory).filter(QueryHistory.id == history_id).one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="History not found")
    executor = SQLExecutorService()
    result = await executor.execute_sql(sql=rec.sql, connection_id=rec.connection_id)
    # Log new run
    await executor.log_query_execution(
        request=QueryExecutionRequest(sql=rec.sql, connection_id=rec.connection_id, require_approval=False),
        result=result,
    )
    return result


@router.delete("/{history_id}")
async def delete_history_item(history_id: int, db: Session = Depends(get_db_session)):
    rec = db.query(QueryHistory).filter(QueryHistory.id == history_id).one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="History not found")
    db.delete(rec)
    db.commit()
    return {"success": True}
