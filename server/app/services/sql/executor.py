"""
Service to execute SQL queries safely.
This executes against a stored DbConnection by connection_id.
"""
from typing import Optional, Dict, Any, List
from time import perf_counter
from sqlalchemy import text
from sqlalchemy.engine import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import inspect

from app.schemas.common import QueryExecutionRequest, QueryExecutionResponse
from app.db.base import SessionLocal, Base
from app.db.models.connection import DbConnection
from app.db.models.query_history import QueryHistory


class SQLExecutorService:
    def __init__(self) -> None:
        pass

    def _get_connection_string(self, connection_id: int) -> str:
        # Use a short-lived session to fetch the connection string
        db: Session = SessionLocal()
        try:
            rec = db.query(DbConnection).filter(DbConnection.id == connection_id).one_or_none()
            if not rec:
                raise ValueError(f"Connection id {connection_id} not found")
            return rec.connection_string
        finally:
            db.close()

    async def execute_sql(
        self,
        *,
        sql: str,
        connection_id: int,
        timeout_seconds: int = 30,
        max_rows: int = 1000,
    ) -> QueryExecutionResponse:
        start = perf_counter()
        conn_str = self._get_connection_string(connection_id)
        rows: List[Dict[str, Any]] = []
        columns: List[str] = []

        try:
            engine = create_engine(conn_str, pool_pre_ping=True)
            with engine.connect() as conn:
                result = conn.execution_options(stream_results=True).execute(text(sql))
                columns = list(result.keys()) if result.returns_rows else []
                if result.returns_rows:
                    count = 0
                    for row in result:
                        rows.append({k: row[i] for i, k in enumerate(columns)})
                        count += 1
                        if count >= max_rows:
                            break
        except SQLAlchemyError as e:
            elapsed_ms = int((perf_counter() - start) * 1000)
            return QueryExecutionResponse(
                success=False,
                rows=[],
                columns=[],
                row_count=0,
                execution_time_ms=elapsed_ms,
                sql_executed=sql,
                warnings=[],
                error=str(e),
            )

        elapsed_ms = int((perf_counter() - start) * 1000)
        return QueryExecutionResponse(
            success=True,
            rows=rows,
            columns=columns,
            row_count=len(rows),
            execution_time_ms=elapsed_ms,
            sql_executed=sql,
            warnings=[],
            error=None,
        )

    async def log_query_execution(
        self, *, request: QueryExecutionRequest, result: QueryExecutionResponse
    ) -> None:
        db: Session = SessionLocal()
        try:
            # Ensure table exists in case app started before model import
            try:
                insp = inspect(db.bind)
                if not insp.has_table(QueryHistory.__tablename__):
                    Base.metadata.create_all(bind=db.bind)
            except Exception:
                pass
            rec = QueryHistory(
                connection_id=request.connection_id,
                prompt=None,
                sql=result.sql_executed or request.sql,
                row_count=result.row_count,
                execution_time_ms=result.execution_time_ms,
                success=result.success,
                error=result.error,
            )
            db.add(rec)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        return None
