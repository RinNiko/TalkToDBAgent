from typing import Dict, Any, List
from sqlalchemy.engine import create_engine
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.services.llm.openai import get_openai_client
from app.db.models.schema_snapshot import SchemaSnapshot


class SchemaDiscoveryService:
    def __init__(self) -> None:
        pass

    async def discover_and_save(self, *, connection_id: int, connection_string: str, session: Session) -> Dict[str, Any]:
        raw = self._introspect_schema(connection_string)
        normalized = await self._normalize_with_ai(raw)

        snapshot = (
            session.query(SchemaSnapshot)
            .filter(SchemaSnapshot.connection_id == connection_id)
            .one_or_none()
        )
        if snapshot is None:
            snapshot = SchemaSnapshot(connection_id=connection_id, name=normalized.get("database") or "")
            session.add(snapshot)
        snapshot.schema_json = normalized
        session.commit()
        session.refresh(snapshot)
        return normalized

    def _introspect_schema(self, connection_string: str) -> Dict[str, Any]:
        engine = create_engine(connection_string, pool_pre_ping=True)
        tables: List[Dict[str, Any]] = []
        database_name = "unknown"
        with engine.connect() as conn:
            dialect = conn.dialect.name
            if dialect in ("postgresql", "postgres"):
                # Database name
                try:
                    database_name = conn.execute(text("SELECT current_database()")) .scalar() or database_name
                except Exception:
                    pass
                sql = text(
                    """
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_type='BASE TABLE' AND table_schema NOT IN ('pg_catalog','information_schema')
                    ORDER BY table_schema, table_name;
                    """
                )
                rows = conn.execute(sql).fetchall()
                for schema, table in rows:
                    col_sql = text(
                        """
                        SELECT column_name,
                               data_type,
                               udt_name,
                               character_maximum_length,
                               numeric_precision,
                               numeric_scale,
                               is_nullable
                        FROM information_schema.columns
                        WHERE table_schema=:schema AND table_name=:table
                        ORDER BY ordinal_position;
                        """
                    )
                    cols = conn.execute(col_sql, {"schema": schema, "table": table}).fetchall()

                    # Primary key columns
                    pk_sql = text(
                        """
                        SELECT kcu.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                          ON tc.constraint_name = kcu.constraint_name
                         AND tc.table_schema = kcu.table_schema
                         AND tc.table_name = kcu.table_name
                        WHERE tc.table_schema=:schema AND tc.table_name=:table AND tc.constraint_type='PRIMARY KEY';
                        """
                    )
                    pk_cols = {r[0] for r in conn.execute(pk_sql, {"schema": schema, "table": table}).fetchall()}

                    # Unique columns (include any column participating in a UNIQUE constraint)
                    uq_sql = text(
                        """
                        SELECT kcu.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                          ON tc.constraint_name = kcu.constraint_name
                         AND tc.table_schema = kcu.table_schema
                         AND tc.table_name = kcu.table_name
                        WHERE tc.table_schema=:schema AND tc.table_name=:table AND tc.constraint_type='UNIQUE';
                        """
                    )
                    uq_cols = {r[0] for r in conn.execute(uq_sql, {"schema": schema, "table": table}).fetchall()}

                    def _compose_type(row) -> str:
                        # row indices based on the SELECT above
                        _, data_type, udt_name, char_len, num_prec, num_scale, _ = row
                        try:
                            if udt_name in ("varchar", "bpchar"):
                                if char_len:
                                    return f"varchar({int(char_len)})"
                                return "varchar"
                            if udt_name in ("int4", "int2", "int8"):
                                return {"int2": "smallint", "int4": "integer", "int8": "bigint"}[udt_name]
                            if udt_name in ("numeric",):
                                if num_prec and num_scale is not None:
                                    return f"numeric({int(num_prec)},{int(num_scale)})"
                                if num_prec:
                                    return f"numeric({int(num_prec)})"
                                return "numeric"
                            if udt_name in ("timestamp", "timestamptz"):
                                return "timestamp" if udt_name == "timestamp" else "timestamptz"
                            if udt_name in ("json", "jsonb"):
                                return udt_name
                            if udt_name == "bool":
                                return "boolean"
                            if udt_name == "text":
                                return "text"
                            # fallback to data_type
                            return str(data_type)
                        except Exception:
                            return str(data_type)

                    columns = [
                        {
                            "name": r[0],
                            "type": _compose_type(r),
                            "nullable": True if str(r[6]).lower() == "yes" else False,
                            "primary_key": r[0] in pk_cols,
                            "unique": r[0] in uq_cols,
                        }
                        for r in cols
                    ]
                    tables.append({"schema": schema, "name": table, "columns": columns})
            else:
                # Basic fallback: SQLAlchemy inspector could be used; skipping for brevity
                pass
        return {"database": database_name, "tables": tables}

    async def _normalize_with_ai(self, raw_schema: Dict[str, Any]) -> Dict[str, Any]:
        client = get_openai_client()
        prompt = (
            "You are a database architect. Normalize and annotate the following database schema into a concise JSON with keys: "
            "database, tables:[{schema,name,columns:[{name,type,nullable,pk?,unique?}], sample_query?}]. "
            "CRITICAL: Do not invent or remove tables or columns. Keep exactly the same tables and columns as provided in Raw schema. "
            "Only return JSON, no extra text.\n\nRaw schema:\n" + str(raw_schema)
        )
        resp = client.chat.completions.create(
            model="GPT-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        content = resp.choices[0].message.content or "{}"
        import json

        normalized: Dict[str, Any]
        try:
            normalized = json.loads(content)
        except Exception:
            normalized = {"database": raw_schema.get("database", "unknown"), "tables": raw_schema.get("tables", [])}

        # Validate against raw to prevent hallucinations
        raw_tables = [t.get("name") for t in raw_schema.get("tables", []) if isinstance(t, dict)]
        norm_tables = [t.get("name") for t in normalized.get("tables", []) if isinstance(t, dict)]
        if not norm_tables or set(norm_tables) != set(raw_tables):
            normalized = {
                "database": raw_schema.get("database", "unknown"),
                "tables": [
                    {
                        "schema": t.get("schema"),
                        "name": t.get("name"),
                        "columns": [
                            {
                                "name": c.get("name"),
                                "type": c.get("type"),
                                "nullable": c.get("nullable", True),
                                "primary_key": c.get("primary_key", False),
                                "unique": c.get("unique", False),
                            }
                            for c in t.get("columns", [])
                        ],
                    }
                    for t in raw_schema.get("tables", [])
                    if isinstance(t, dict)
                ],
            }
        return normalized
