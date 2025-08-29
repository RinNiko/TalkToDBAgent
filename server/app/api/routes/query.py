"""
Query generation and execution endpoints.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.schemas.common import (
    QueryRequest, 
    QueryResponse, 
    QueryExecutionRequest, 
    QueryExecutionResponse,
    BaseResponse
)
from app.services.sql.sql_chain import SQLGenerationService
from app.services.sql.executor import SQLExecutorService
from app.services.sql.guardrails import SQLGuardrailsService
from app.core.config import get_settings
from app.services.llm.openai import get_openai_client

router = APIRouter()
settings = get_settings()


class ChartSuggestRequest(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    max_rows: int = Field(default=200, ge=1, le=1000)
    prompt: Optional[str] = None


class ChartSuggestResponse(BaseModel):
    type: str
    xKey: Optional[str] = None
    yKey: Optional[str] = None
    yKeys: Optional[List[str]] = None
    title: Optional[str] = None
    groupBy: Optional[str] = None
    agg: Optional[str] = Field(default=None, description="One of: count, sum, avg")
    valueKey: Optional[str] = None


class GenerateExecuteSuggestResponse(BaseModel):
    sql: str
    execution: QueryExecutionResponse
    chart: Dict[str, Any]


_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@router.post("/suggest-chart", response_model=ChartSuggestResponse)
async def suggest_chart(payload: ChartSuggestRequest, debug: bool = False):
    """Ask the LLM to choose a chart and mapping. If it fails, return a tiny heuristic.
    When debug=true, include raw LLM output in the JSON (debug_content) and add X-Chart-Source headers.
    """
    if not payload.columns:
        raise HTTPException(status_code=400, detail="No columns provided")

    cols = payload.columns
    sample_rows = payload.rows[: payload.max_rows]
    allowed_types = ["pie", "doughnut", "bar", "line", "radar", "polarArea", "scatter"]
    allowed_aggs = ["count", "sum", "avg"]

    def is_numeric(col: str) -> bool:
        for r in sample_rows[:20]:
            try:
                float(r.get(col))
            except Exception:
                return False
        return bool(sample_rows)

    numeric_cols = [c for c in cols if is_numeric(c)]
    categorical_cols = [c for c in cols if c not in numeric_cols]

    raw_content: Optional[str] = None
    try:
        client = get_openai_client()
        system_msg = (
            "You are a data visualization assistant. "
            "Choose a chart type from this list: " + ", ".join(allowed_types) + ". "
            "Return STRICT JSON with keys: type, xKey, yKey or yKeys, title, and optionally groupBy, agg (count|sum|avg), valueKey. "
            "Rules: If you do not return groupBy+agg, you MUST return both xKey (categorical) and yKey (numeric). Do not invent columns."
        )
        user_msg = (
            f"Question: {payload.prompt or ''}\n"
            f"Columns: {cols}\n"
            f"Sample rows (JSON): {sample_rows}"
        )
        resp = client.chat.completions.create(
            model="GPT-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
        )
        import json, re
        raw_content = resp.choices[0].message.content or "{}"
        cleaned = raw_content.strip()
        cleaned = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", cleaned)
        json_text = re.search(r"\{[\s\S]*\}$", cleaned)
        data = json.loads(json_text.group(0) if json_text else cleaned)

        # Validate / clamp
        ctype = str(data.get("type", "")).strip()
        if ctype not in allowed_types:
            ctype = "bar"
        def ok(name: Optional[str]) -> Optional[str]:
            return name if (name in cols) else None
        xKey = ok(data.get("xKey"))
        yKey = ok(data.get("yKey"))
        yKeys = [k for k in (data.get("yKeys") or []) if k in cols] or None
        groupBy = ok(data.get("groupBy"))
        agg = data.get("agg") if data.get("agg") in allowed_aggs else None
        valueKey = ok(data.get("valueKey"))

        # Guardrail: If no aggregation, ensure yKey numeric and xKey categorical
        if groupBy is None and agg is None:
            if not yKey:
                # prefer numeric named like average/price/mileage
                ranked = sorted(
                    [c for c in numeric_cols if c != xKey],
                    key=lambda n: (
                        any(k in n.lower() for k in ("avg","average","mean")),
                        any(k in n.lower() for k in ("price","amount","total","mileage")),
                    ),
                    reverse=True,
                )
                yKey = ranked[0] if ranked else (numeric_cols[0] if numeric_cols else None)
            if not xKey or (yKey and xKey == yKey):
                x_candidates = [c for c in categorical_cols if c.lower() not in ("id","vin")]
                xKey = x_candidates[0] if x_candidates else (cols[0] if cols else None)
        else:
            # Aggregation path: ensure groupBy exists; if yKey missing, set via valueKey
            if not groupBy:
                groupBy = xKey or (categorical_cols[0] if categorical_cols else cols[0])
            if not yKey and valueKey:
                yKey = valueKey

        payload_out = ChartSuggestResponse(
            type=ctype,
            xKey=xKey,
            yKey=yKey,
            yKeys=yKeys,
            title=data.get("title"),
            groupBy=groupBy,
            agg=agg,
            valueKey=valueKey,
        )
        h = dict(_NO_CACHE_HEADERS)
        h["X-Chart-Source"] = "llm"
        return JSONResponse(content={**payload_out.dict(), "debug_content": raw_content}, headers=h)
    except Exception:
        # Minimal readable fallback
        group_by = next((c for c in categorical_cols if c.lower() not in ("id","vin")), (categorical_cols[0] if categorical_cols else cols[0]))
        prefer_val = next((c for c in ("price","mileage","amount","total") if c in [x.lower() for x in cols]), None)
        value_key = next((c for c in cols if c.lower()==prefer_val), None) if prefer_val else None
        agg = "avg" if value_key and value_key in numeric_cols else "count"
        if agg != "avg":
            value_key = None
        payload_out = ChartSuggestResponse(
            type="bar",
            xKey=group_by,
            yKey=None,
            yKeys=None,
            title=None,
            groupBy=group_by,
            agg=agg,
            valueKey=value_key,
        )
        if debug:
            h = dict(_NO_CACHE_HEADERS)
            h["X-Chart-Source"] = "fallback"
            return JSONResponse(content={**payload_out.dict(), "debug_content": raw_content or ""}, headers=h)
        return payload_out


@router.post("/generate", response_model=QueryResponse)
async def generate_sql(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    sql_service: SQLGenerationService = Depends(),
    guardrails: SQLGuardrailsService = Depends()
):
    """
    Generate SQL from natural language query.
    """
    try:
        # Generate SQL using LLM
        result = await sql_service.generate_sql(
            prompt=request.prompt,
            connection_id=request.connection_id,
            provider=request.provider,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            include_schema=request.include_schema
        )
        
        # Apply guardrails
        validation_result = await guardrails.validate_sql(
            sql=result.sql,
            connection_id=request.connection_id
        )
        
        if not validation_result.is_safe:
            result.warnings.extend(validation_result.warnings)
            if validation_result.block_execution:
                raise HTTPException(
                    status_code=400,
                    detail=f"SQL blocked by guardrails: {'; '.join(validation_result.warnings)}"
                )
        
        # Log query generation in background
        background_tasks.add_task(
            sql_service.log_query_generation,
            request=request,
            result=result
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate SQL: {str(e)}"
        )


@router.post("/execute", response_model=QueryExecutionResponse)
async def execute_sql(
    request: QueryExecutionRequest,
    background_tasks: BackgroundTasks,
    executor: SQLExecutorService = Depends(),
    guardrails: SQLGuardrailsService = Depends()
):
    """
    Execute SQL query with optional approval requirement.
    """
    try:
        # Validate SQL if approval is required
        if request.require_approval or settings.require_sql_approval:
            validation_result = await guardrails.validate_sql(
                sql=request.sql,
                connection_id=request.connection_id
            )
            
            if not validation_result.is_safe:
                raise HTTPException(
                    status_code=400,
                    detail=f"SQL execution blocked: {'; '.join(validation_result.warnings)}"
                )
        
        # Execute SQL
        result = await executor.execute_sql(
            sql=request.sql,
            connection_id=request.connection_id,
            timeout_seconds=request.timeout_seconds or settings.max_execution_time_seconds,
            max_rows=settings.max_rows_returned
        )
        
        # Log execution in background
        background_tasks.add_task(
            executor.log_query_execution,
            request=request,
            result=result
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute SQL: {str(e)}"
        )


@router.post("/generate-and-execute", response_model=QueryExecutionResponse)
async def generate_and_execute(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    sql_service: SQLGenerationService = Depends(),
    executor: SQLExecutorService = Depends(),
    guardrails: SQLGuardrailsService = Depends()
):
    """
    Generate SQL and execute it in one request.
    """
    try:
        # Generate SQL first
        sql_result = await sql_service.generate_sql(
            prompt=request.prompt,
            connection_id=request.connection_id,
            provider=request.provider,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            include_schema=request.include_schema
        )
        
        # Validate generated SQL
        validation_result = await guardrails.validate_sql(
            sql=sql_result.sql,
            connection_id=request.connection_id
        )
        
        if not validation_result.is_safe:
            sql_result.warnings.extend(validation_result.warnings)
            if validation_result.block_execution:
                raise HTTPException(
                    status_code=400,
                    detail=f"Generated SQL blocked by guardrails: {'; '.join(validation_result.warnings)}"
                )
        
        # Execute the generated SQL
        execution_result = await executor.execute_sql(
            sql=sql_result.sql,
            connection_id=request.connection_id,
            timeout_seconds=settings.max_execution_time_seconds,
            max_rows=settings.max_rows_returned
        )
        
        # Add generation info to execution result
        execution_result.sql_executed = sql_result.sql
        execution_result.warnings.extend(sql_result.warnings)
        
        # Log both operations in background
        background_tasks.add_task(
            sql_service.log_query_generation,
            request=request,
            result=sql_result
        )
        
        background_tasks.add_task(
            executor.log_query_execution,
            request=QueryExecutionRequest(
                sql=sql_result.sql,
                connection_id=request.connection_id,
                require_approval=False
            ),
            result=execution_result
        )
        
        return execution_result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate and execute SQL: {str(e)}"
        )


@router.post("/generate-execute-suggest", response_model=GenerateExecuteSuggestResponse)
async def generate_execute_suggest(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    sql_service: SQLGenerationService = Depends(),
    executor: SQLExecutorService = Depends(),
    guardrails: SQLGuardrailsService = Depends(),
):
    """Generate SQL, execute it, and suggest a chart in a single call."""
    # 1) Generate SQL
    gen = await sql_service.generate_sql(
        prompt=request.prompt,
        connection_id=request.connection_id,
        provider=request.provider,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        include_schema=request.include_schema,
    )
    # 2) Guardrails on generated SQL
    validation = await guardrails.validate_sql(sql=gen.sql, connection_id=request.connection_id)
    if not validation.is_safe and validation.block_execution:
        raise HTTPException(status_code=400, detail=f"Generated SQL blocked by guardrails: {'; '.join(validation.warnings)}")

    # 3) Execute
    exec_res = await executor.execute_sql(
        sql=gen.sql,
        connection_id=request.connection_id,
        timeout_seconds=request.temperature or settings.max_execution_time_seconds,
        max_rows=settings.max_rows_returned,
    )

    # 4) Suggest chart
    chart_payload = {
        "columns": exec_res.columns,
        "rows": exec_res.rows,
        "prompt": request.prompt,
        "max_rows": min(len(exec_res.rows), settings.max_rows_returned),
    }
    # Reuse the existing endpoint function to avoid duplicating logic
    try:
        import json as _json
        resp = await suggest_chart(ChartSuggestRequest(**chart_payload), debug=True)  # type: ignore
        if isinstance(resp, JSONResponse):
            chart_dict = _json.loads(resp.body.decode("utf-8"))
        else:
            # Fallback if the implementation changes
            chart_dict = resp  # type: ignore
    except Exception:
        chart_dict = {"type": "bar", "xKey": None, "yKey": None}

    return GenerateExecuteSuggestResponse(sql=gen.sql, execution=exec_res, chart=chart_dict)


@router.get("/models", response_model=List[str])
async def get_available_models():
    """
    Get list of available LLM models.
    """
    return [
        "gpt-4o",
        "gpt-4o-mini", 
        "gpt-4-turbo",
        "gpt-3.5-turbo",
        "claude-3-5-sonnet",
        "claude-3-haiku",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "llama-3.1-8b",
        "llama-3.1-70b",
        "mixtral-8x7b",
        "qwen2.5-7b"
    ]
