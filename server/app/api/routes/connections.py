"""
Database connections management endpoints.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.engine import create_engine
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import get_db_session
from app.db.models.connection import DbConnection

router = APIRouter()


class ConnectionCreate(BaseModel):
    name: str
    connection_string: str


class ConnectionTestRequest(BaseModel):
    connection_string: str = Field(..., description="SQLAlchemy connection string")
    timeout_seconds: int = Field(default=5, ge=1, le=60)


@router.post("/test")
async def test_connection(payload: ConnectionTestRequest):
    try:
        engine = create_engine(payload.connection_string, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return {"success": True, "message": "Connection successful"}
    except SQLAlchemyError as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")


@router.post("/")
async def create_connection(payload: ConnectionCreate, db: Session = Depends(get_db_session)):
    exists = db.query(DbConnection).filter(DbConnection.name == payload.name).one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Connection name already exists")
    rec = DbConnection(name=payload.name, connection_string=payload.connection_string)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "name": rec.name}


@router.get("/")
async def list_connections(db: Session = Depends(get_db_session)):
    items = db.query(DbConnection).order_by(DbConnection.created_at.desc()).all()
    return [{"id": c.id, "name": c.name} for c in items]


@router.put("/{connection_id}")
async def update_connection(connection_id: int):
    return {"message": f"Update connection {connection_id} endpoint - TODO: implement"}


@router.delete("/{connection_id}")
async def delete_connection(connection_id: int):
    return {"message": f"Delete connection {connection_id} endpoint - TODO: implement"}
