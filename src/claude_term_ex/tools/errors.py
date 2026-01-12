"""Error handling for tool execution."""

from dataclasses import dataclass, field
from typing import Any, Optional, Dict


# Error code constants
class ErrorCode:
    """Error codes for tool execution failures."""
    
    # Sandbox violations
    SANDBOX_VIOLATION = "ERROR_SANDBOX_VIOLATION"
    PATH_TRAVERSAL = "ERROR_PATH_TRAVERSAL"
    
    # Execution errors
    TIMEOUT = "ERROR_TIMEOUT"
    PROCESS_KILLED = "ERROR_PROCESS_KILLED"
    EXECUTION_FAILED = "ERROR_EXECUTION_FAILED"
    
    # Resource errors
    FILE_NOT_FOUND = "ERROR_FILE_NOT_FOUND"
    PERMISSION_DENIED = "ERROR_PERMISSION_DENIED"
    FILE_TOO_LARGE = "ERROR_FILE_TOO_LARGE"
    DISK_FULL = "ERROR_DISK_FULL"
    
    # Network errors
    API_TIMEOUT = "ERROR_API_TIMEOUT"
    RATE_LIMITED = "ERROR_RATE_LIMITED"
    NETWORK_ERROR = "ERROR_NETWORK_ERROR"
    
    # Validation errors
    INVALID_PARAMS = "ERROR_INVALID_PARAMS"
    SCHEMA_MISMATCH = "ERROR_SCHEMA_MISMATCH"
    MISSING_REQUIRED_PARAM = "ERROR_MISSING_REQUIRED_PARAM"
    
    # Unknown errors
    UNKNOWN = "ERROR_UNKNOWN"


@dataclass
class ToolError:
    """Structured error information for tool execution."""
    
    code: str
    message: str
    recoverable: bool = True
    suggestion: str = ""
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "code": self.code,
            "message": self.message,
            "recoverable": self.recoverable,
            "suggestion": self.suggestion,
        }
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class ToolResult:
    """Result of tool execution."""
    
    success: bool
    result: Any = None
    error: Optional[ToolError] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        output = {
            "success": self.success,
            "metadata": self.metadata,
        }
        
        if self.success:
            output["result"] = self.result
        else:
            output["error"] = self.error.to_dict() if self.error else None
        
        return output
    
    @classmethod
    def success_result(cls, result: Any, metadata: Optional[Dict[str, Any]] = None) -> "ToolResult":
        """Create a successful result."""
        return cls(
            success=True,
            result=result,
            metadata=metadata or {}
        )
    
    @classmethod
    def error_result(
        cls,
        code: str,
        message: str,
        recoverable: bool = True,
        suggestion: str = "",
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "ToolResult":
        """Create an error result."""
        return cls(
            success=False,
            error=ToolError(
                code=code,
                message=message,
                recoverable=recoverable,
                suggestion=suggestion,
                details=details
            ),
            metadata=metadata or {}
        )


# Custom exceptions
class SandboxViolation(Exception):
    """Raised when an operation violates sandbox constraints."""
    pass


class ToolTimeout(Exception):
    """Raised when a tool execution times out."""
    pass


class ToolValidationError(Exception):
    """Raised when tool parameters are invalid."""
    pass
