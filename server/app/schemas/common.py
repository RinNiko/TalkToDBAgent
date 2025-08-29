"""
Common Pydantic schemas used across the application.
"""
from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    """Base response model."""
    success: bool = True
    message: str = "Operation completed successfully"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseResponse):
    """Error response model."""
    success: bool = False
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1, description="Page number")
    size: int = Field(default=20, ge=1, le=100, description="Page size")
    sort_by: Optional[str] = Field(default="created_at", description="Sort field")
    sort_order: str = Field(default="desc", pattern=r"^(asc|desc)$", description="Sort order")


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""
    items: list[Any]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


class DatabaseConnectionInfo(BaseModel):
    """Database connection information."""
    id: Optional[int] = None
    name: str = Field(..., description="Connection name")
    database_type: str = Field(..., description="Database type (postgresql, mysql, sqlserver, sqlite)")
    host: Optional[str] = Field(None, description="Database host")
    port: Optional[int] = Field(None, description="Database port")
    database: str = Field(..., description="Database name")
    username: Optional[str] = Field(None, description="Database username")
    password: Optional[str] = Field(None, description="Database password (encrypted)")
    connection_string: Optional[str] = Field(None, description="Full connection string (encrypted)")
    is_active: bool = Field(default=True, description="Whether connection is active")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LLMProviderInfo(BaseModel):
    """LLM provider information."""
    id: Optional[int] = None
    provider: str = Field(..., description="Provider name (openai, azure_openai, anthropic, gemini, groq)")
    api_key: Optional[str] = Field(None, description="API key (encrypted)")
    endpoint: Optional[str] = Field(None, description="Custom endpoint URL")
    api_version: Optional[str] = Field(None, description="API version")
    is_default: bool = Field(default=False, description="Whether this is the default provider")
    is_active: bool = Field(default=True, description="Whether provider is active")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class QueryRequest(BaseModel):
    """Natural language query request."""
    prompt: str = Field(..., description="Natural language query")
    connection_id: int = Field(..., description="Database connection ID")
    provider: Optional[str] = Field(None, description="LLM provider to use")
    model: Optional[str] = Field(None, description="Specific model to use")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="LLM temperature")
    max_tokens: Optional[int] = Field(None, ge=1, le=4000, description="Maximum tokens")
    include_schema: bool = Field(default=True, description="Whether to include schema context")


class QueryResponse(BaseModel):
    """Query generation response."""
    sql: str = Field(..., description="Generated SQL query")
    explanation: Optional[str] = Field(None, description="Explanation of the query")
    warnings: list[str] = Field(default_factory=list, description="Any warnings about the query")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    execution_time_ms: Optional[int] = Field(None, description="SQL generation time in milliseconds")


class QueryExecutionRequest(BaseModel):
    """SQL execution request."""
    sql: str = Field(..., description="SQL query to execute")
    connection_id: int = Field(..., description="Database connection ID")
    require_approval: bool = Field(default=False, description="Whether to require user approval")
    timeout_seconds: Optional[int] = Field(None, ge=1, le=300, description="Execution timeout")


class QueryExecutionResponse(BaseModel):
    """Query execution response."""
    success: bool = Field(..., description="Whether execution was successful")
    rows: list[Dict[str, Any]] = Field(default_factory=list, description="Query results")
    columns: list[str] = Field(default_factory=list, description="Column names")
    row_count: int = Field(..., description="Number of rows returned")
    execution_time_ms: int = Field(..., description="Execution time in milliseconds")
    sql_executed: str = Field(..., description="Actual SQL that was executed")
    warnings: list[str] = Field(default_factory=list, description="Execution warnings")
    error: Optional[str] = Field(None, description="Error message if execution failed")
