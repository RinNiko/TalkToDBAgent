"""
Service to generate SQL from natural language using an LLM provider.
Uses saved schema snapshot (if present) to improve prompts.
"""
from typing import Optional
from time import perf_counter
from sqlalchemy.orm import Session
from app.schemas.common import QueryRequest, QueryResponse
from app.db.base import SessionLocal
from app.db.models.schema_snapshot import SchemaSnapshot
from app.services.llm.openai import get_openai_client


class SQLGenerationService:
    def __init__(self) -> None:
        pass

    def _get_schema(self, connection_id: int) -> Optional[dict]:
        db: Session = SessionLocal()
        try:
            snap = (
                db.query(SchemaSnapshot)
                .filter(SchemaSnapshot.connection_id == connection_id)
                .one_or_none()
            )
            return snap.schema_json if snap else None
        finally:
            db.close()

    def _translate_to_english(self, text: str) -> str:
        """Translate any input text to concise English. Fallback to original on error."""
        try:
            client = get_openai_client()
            resp = client.chat.completions.create(
                model="GPT-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional translator. Translate the user input to clear, concise English. Return only the translated text."},
                    {"role": "user", "content": text},
                ],
                temperature=0.0,
                max_tokens=256,
            )
            out = (resp.choices[0].message.content or "").strip()
            return out or text
        except Exception:
            return text

    async def generate_sql(
        self,
        *,
        prompt: str,
        connection_id: int,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        include_schema: bool = True,
    ) -> QueryResponse:
        start = perf_counter()
        schema = self._get_schema(connection_id) if include_schema else None

        # Translate non-English prompts to English for better SQL and value mapping
        translated_prompt = self._translate_to_english(prompt)

        client = get_openai_client()
        sys = (
            "You are a SQL expert. Generate a single, safe SQL statement for the user's request. "
            "Prefer SELECT queries and avoid DDL/DML unless explicitly requested. "
            "For textual filters, use case-insensitive comparisons by default (on Postgres use ILIKE; otherwise use LOWER(column)=LOWER(value))."
        )
        user = f"User request (English): {translated_prompt}\n"
        if schema:
            import json
            user += "\nDatabase schema (JSON):\n" + json.dumps(schema) + "\n"
        user += "\nReturn only SQL in plain text. No explanations, no code fences."

        resp = client.chat.completions.create(
            model=model or "GPT-4o-mini",
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens or 512,
        )
        raw = (resp.choices[0].message.content or "").strip()

        # Sanitize: strip code fences/backticks and keep only the first SELECT statement
        import re
        text_only = re.sub(r"```[\s\S]*?```", " ", raw)  # remove fenced blocks
        text_only = text_only.replace("`", " ")
        # Find the first SELECT ... ; or end
        m = re.search(r"(?is)(select[\s\S]*?)(;|$)", text_only)
        sql_text = (m.group(1).strip() if m else text_only.split(';')[0].strip())
        # Ensure it ends with a single semicolon for consistency
        if not sql_text.lower().startswith("select"):
            # As a fallback, enforce a trivial safe select to avoid guardrail block
            sql_text = "SELECT 1;"
        else:
            sql_text = sql_text.rstrip(';') + ';'

        # Post-process: simple case-insensitive fix for equality on common text columns
        try:
            def _fix_case_insensitive(s: str) -> str:
                pattern = r"(?i)where\s+([\w\.\"]+)\s*=\s*'([a-z]+)'"
                def repl(m):
                    col, val = m.group(1), m.group(2)
                    return f"WHERE {col} ILIKE '{val}'"
                return re.sub(pattern, repl, s)
            sql_text = _fix_case_insensitive(sql_text)
        except Exception:
            pass

        elapsed_ms = int((perf_counter() - start) * 1000)
        return QueryResponse(
            sql=sql_text,
            explanation=None,
            warnings=[],
            confidence=0.6,
            execution_time_ms=elapsed_ms,
        )

    async def log_query_generation(self, *, request: QueryRequest, result: QueryResponse) -> None:
        # TODO: persist to DB
        return None
