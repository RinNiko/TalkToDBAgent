"""
SQL guardrails to prevent dangerous queries.
"""
from typing import List
from pydantic import BaseModel


class SQLValidationResult(BaseModel):
    is_safe: bool
    warnings: List[str]
    block_execution: bool


class SQLGuardrailsService:
    def __init__(self) -> None:
        pass

    async def validate_sql(self, *, sql: str, connection_id: int) -> SQLValidationResult:
        sql_upper = sql.strip().upper()
        warnings: List[str] = []
        block = False

        dangerous_keywords = [
            "DROP ",
            "TRUNCATE ",
            "ALTER ",
            "DELETE ",
            "UPDATE ",
            "INSERT ",
            "MERGE ",
            "CREATE ",
            "REPLACE ",
            "GRANT ",
            "REVOKE ",
        ]

        if not sql_upper.startswith("SELECT"):
            for kw in dangerous_keywords:
                if kw in sql_upper:
                    warnings.append(f"Detected dangerous keyword: {kw.strip()}")
                    block = True
        
        # Basic multi-statement detection
        if ";" in sql_upper.strip().rstrip(";"):
            warnings.append("Multiple SQL statements detected; only single SELECT allowed")
            block = True

        is_safe = not block
        return SQLValidationResult(is_safe=is_safe, warnings=warnings, block_execution=block)
