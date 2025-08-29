"""
Database schema endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from typing import Optional, List
import random
import uuid
from sqlalchemy.orm import Session

from app.db.base import get_db_session
from app.db.models.schema_snapshot import SchemaSnapshot
from app.db.models.connection import DbConnection
from app.services.sql.schema_discovery import SchemaDiscoveryService
from app.services.llm.openai import get_openai_client

router = APIRouter()


class DiscoverRequest(BaseModel):
    connection_string: Optional[str] = Field(None, description="SQLAlchemy connection string for the target DB (optional if stored)")


class QuickExamplesResponse(BaseModel):
    examples: List[str]


def _resolve_connection_string(connection_id: int, payload: DiscoverRequest, db: Session) -> str:
    if payload.connection_string:
        return payload.connection_string
    rec = db.query(DbConnection).filter(DbConnection.id == connection_id).one_or_none()
    if not rec or not rec.connection_string:
        raise HTTPException(status_code=400, detail="Connection string not provided and not found for this connection id")
    return rec.connection_string


def _build_dynamic_examples(schema: dict) -> List[str]:
    examples: List[str] = []
    tables = [t for t in (schema or {}).get("tables", []) if isinstance(t, dict)]

    def is_numeric(tp: str) -> bool:
        tp = (tp or "").lower()
        return tp.startswith(("int", "bigint", "smallint", "numeric", "decimal", "double", "real"))

    def is_text(tp: str) -> bool:
        tp = (tp or "").lower()
        return tp.startswith(("varchar", "text", "char")) or tp in ("json", "jsonb")

    def is_date(tp: str) -> bool:
        tp = (tp or "").lower()
        return ("timestamp" in tp) or tp in ("date", "time", "timestamptz")

    for t in tables[:3]:
        tname = t.get("name") or "table"
        cols = t.get("columns", [])
        num_cols = [c.get("name") for c in cols if is_numeric(str(c.get("type")))]
        cat_cols = [c.get("name") for c in cols if is_text(str(c.get("type")))]
        date_cols = [c.get("name") for c in cols if is_date(str(c.get("type")))]

        examples.append(f"How many rows are in {tname}?")
        if num_cols and cat_cols:
            examples.append(f"Show average {num_cols[0]} by {cat_cols[0]}")
        if cat_cols:
            examples.append(f"Count how many {tname} per {cat_cols[0]}")
        if num_cols:
            examples.append(f"List top 10 {tname} by {num_cols[0]}")
        if date_cols:
            examples.append(f"Show monthly counts for {tname} over the last 12 months")

    # De-duplicate and cap
    seen = set()
    deduped: List[str] = []
    for q in examples:
        if q not in seen:
            deduped.append(q)
            seen.add(q)
        if len(deduped) >= 6:
            break

    if not deduped:
        deduped = ["Show row counts per table", "List distinct values by category"]
    return deduped


@router.get("/{connection_id}")
async def get_schema(connection_id: int, db: Session = Depends(get_db_session)):
    snapshot = (
        db.query(SchemaSnapshot)
        .filter(SchemaSnapshot.connection_id == connection_id)
        .one_or_none()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="No schema snapshot. Please run discovery.")
    return snapshot.schema_json


@router.post("/{connection_id}/discover")
async def discover_schema(connection_id: int, payload: DiscoverRequest, db: Session = Depends(get_db_session)):
    service = SchemaDiscoveryService()
    conn_str = _resolve_connection_string(connection_id, payload, db)
    result = await service.discover_and_save(connection_id=connection_id, connection_string=conn_str, session=db)
    return {"message": "Schema discovered and saved", "schema": result}


@router.post("/{connection_id}/refresh")
async def refresh_schema(connection_id: int, payload: DiscoverRequest, db: Session = Depends(get_db_session)):
    service = SchemaDiscoveryService()
    conn_str = _resolve_connection_string(connection_id, payload, db)
    result = await service.discover_and_save(connection_id=connection_id, connection_string=conn_str, session=db)
    return {"message": "Schema refreshed", "schema": result}


@router.get("/{connection_id}/tables")
async def get_tables(connection_id: int, db: Session = Depends(get_db_session)):
    snapshot = (
        db.query(SchemaSnapshot)
        .filter(SchemaSnapshot.connection_id == connection_id)
        .one_or_none()
    )
    if not snapshot:
        return {"tables": []}
    schema = snapshot.schema_json or {}
    tables = [t.get("name") for t in schema.get("tables", []) if isinstance(t, dict)]
    return {"tables": tables}


@router.get("/{connection_id}/tables/{table_name}")
async def get_table_schema(connection_id: int, table_name: str, db: Session = Depends(get_db_session)):
    snapshot = (
        db.query(SchemaSnapshot)
        .filter(SchemaSnapshot.connection_id == connection_id)
        .one_or_none()
    )
    if not snapshot:
        return {"name": table_name, "columns": []}
    schema = snapshot.schema_json or {}
    for t in schema.get("tables", []):
        if isinstance(t, dict) and t.get("name") == table_name:
            return t
    return {"name": table_name, "columns": []}


_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@router.get("/{connection_id}/quick-examples", response_model=QuickExamplesResponse)
async def get_quick_examples(connection_id: int, db: Session = Depends(get_db_session), debug: bool = False, raw: bool = False):
    """Return 4-6 natural language example questions tailored to the saved schema. More varied on each call."""
    snapshot = (
        db.query(SchemaSnapshot)
        .filter(SchemaSnapshot.connection_id == connection_id)
        .one_or_none()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="No schema snapshot. Please run discovery.")

    schema = snapshot.schema_json or {}

    raw_content = None
    try:
        client = get_openai_client()
        token = uuid.uuid4().hex
        system_msg = (
            "You are a QA/Data Analyst crafting decision-focused questions for a manager. "
            "Only propose data analytics questions (KPIs, trends, comparisons, segmentation). "
            "Never ask about columns, data types, schema, or table structure. "
            "Keep each question concise (<= 15 words). Respond ONLY with a JSON array of strings."
        )
        user_msg = (
            "Generate 4 to 6 short, varied questions about the data using these patterns: "
            "'Top 10 by <numeric>', 'Average <numeric> by <category>', 'Count per <category>', "
            "'Monthly counts last 12 months', 'Filter where <category>=<value> and <numeric> > <threshold>', "
            "'Trend of <numeric> by month', 'Share of <category> by count'.\n\n"
            f"Randomization token: {token}\n"
            f"Schema context (JSON-like): {str(schema)}"
        )
        resp = client.chat.completions.create(
            model="GPT-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
        )
        import json, re
        raw_content = resp.choices[0].message.content or "[]"
        if raw:
            # Return the model's raw response as-is (plain text)
            return Response(content=raw_content, media_type="text/plain")
        cleaned = raw_content.strip()
        cleaned = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", cleaned)
        m = re.search(r"\[[\s\S]*\]", cleaned)
        json_text = m.group(0) if m else cleaned
        items = json.loads(json_text)
        if isinstance(items, list) and all(isinstance(x, str) for x in items):
            items = [s.strip() for s in items if isinstance(s, str) and s.strip()]
            # Filter out schema-related questions
            banned = [
                " column ", " columns", "data type", "datatype", "schema", "table structure", "structured in this schema",
                "what columns", "which columns", "which column", "explain the", "show the schema", "describe the table",
                "primary key", "foreign key", "unique column", "is the ", "nullable", "mandatory"
            ]
            def is_banned(s: str) -> bool:
                low = s.lower()
                return any(b in low for b in banned)
            allowed_keywords = [
                "top ", "highest", "lowest",
                "average", "avg", "mean", "median", "percentile", "distribution",
                "count", "sum", "min", "max", "ratio", "share",
                " per ", " by ", "group",
                "monthly", "weekly", "daily", "trend", "growth", "over last", "last ", "year", "quarter",
                "filter", "where", "between", "greater than", "less than", "before", "after", "compare"
            ]
            def is_allowed(s: str) -> bool:
                low = s.lower()
                return any(k in low for k in allowed_keywords) or any(ch.isdigit() for ch in low)
            filtered_out = [s for s in items if is_banned(s) or not is_allowed(s)]
            filtered = [s for s in items if (not is_banned(s)) and is_allowed(s)]
            # Dedup and cap
            dedup = list(dict.fromkeys(filtered))
            random.shuffle(dedup)
            examples = dedup[:6]
            # If too few remain, mix in dynamic data-centric examples
            if len(examples) < 4:
                extras = _build_dynamic_examples(schema)
                for e in extras:
                    if e not in examples:
                        examples.append(e)
                        if len(examples) >= 6:
                            break
            h = dict(_NO_CACHE_HEADERS)
            h["X-Examples-Source"] = "llm"
            payload = {"examples": examples}
            if debug:
                payload["debug_content"] = (raw_content[:1000] + "…") if len(raw_content) > 1000 else raw_content
                payload["filtered_out"] = filtered_out[:6]
            return JSONResponse(content=payload, headers=h)
    except Exception as e:
        err = str(e)
        if raw:
            # When raw is requested but LLM failed, return the captured raw content or error
            return Response(content=(raw_content or err), media_type="text/plain")

    # Dynamic, schema-driven fallback (no hard-coded domain strings)
    examples = _build_dynamic_examples(schema)
    h = dict(_NO_CACHE_HEADERS)
    h["X-Examples-Source"] = "fallback"
    if 'err' in locals():
        h["X-Examples-Error"] = err.split(':')[0][:32]
    payload = {"examples": examples}
    if debug and raw_content is not None:
        payload["debug_content"] = (raw_content[:500] + "…") if len(raw_content) > 500 else raw_content
    return JSONResponse(content=payload, headers=h)
