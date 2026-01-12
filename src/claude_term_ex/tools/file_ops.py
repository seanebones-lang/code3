"""File read and write operations with full system access."""

import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from claude_term_ex.config import MAX_FILE_SIZE_BYTES
from claude_term_ex.tools.errors import (
    ToolResult,
    ErrorCode,
)

logger = logging.getLogger(__name__)


def resolve_path(path: str) -> Path:
    """Resolve a path, expanding ~ and making absolute."""
    return Path(path).expanduser().resolve()


async def read_file(path: str, max_bytes: Optional[int] = None) -> ToolResult:
    """
    Read a file from anywhere on the system.
    
    Args:
        path: Path to file (can be absolute or relative, supports ~)
        max_bytes: Maximum bytes to read (defaults to config limit)
    
    Returns:
        ToolResult with file contents
    """
    try:
        # Resolve path
        file_path = resolve_path(path)
        
        # Check if file exists
        if not file_path.exists():
            return ToolResult.error_result(
                code=ErrorCode.FILE_NOT_FOUND,
                message=f"File not found: {path}",
                recoverable=True,
                suggestion="Check the file path and try again.",
            )
        
        if not file_path.is_file():
            return ToolResult.error_result(
                code=ErrorCode.INVALID_PARAMS,
                message=f"Path is not a file: {path}",
                recoverable=True,
                suggestion="Provide a path to a file, not a directory.",
            )
        
        # Check file size
        file_size = file_path.stat().st_size
        max_read = max_bytes or MAX_FILE_SIZE_BYTES
        
        if file_size > max_read:
            return ToolResult.error_result(
                code=ErrorCode.FILE_TOO_LARGE,
                message=f"File too large: {file_size} bytes (max: {max_read})",
                recoverable=True,
                suggestion=f"File exceeds size limit. Use max_bytes parameter to read partial content.",
                details={"file_size": file_size, "max_bytes": max_read}
            )
        
        # Read file
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read(max_read)
        except UnicodeDecodeError:
            # Try binary mode for non-text files
            with open(file_path, "rb") as f:
                content_bytes = f.read(max_read)
                content = content_bytes.decode("utf-8", errors="replace")
        
        result = {
            "content": content,
            "path": str(file_path),
            "size_bytes": file_size,
            "truncated": file_size > len(content.encode("utf-8")),
        }
        
        return ToolResult.success_result(
            result=result,
            metadata={
                "file_size": file_size,
                "bytes_read": len(content.encode("utf-8")),
            }
        )
    
    except PermissionError as e:
        return ToolResult.error_result(
            code=ErrorCode.PERMISSION_DENIED,
            message=f"Permission denied: {str(e)}",
            recoverable=True,
            suggestion="Check file permissions.",
        )
    
    except Exception as e:
        logger.exception(f"Error reading file: {path}")
        return ToolResult.error_result(
            code=ErrorCode.UNKNOWN,
            message=f"Unexpected error: {str(e)}",
            recoverable=True,
            suggestion="Check logs for details.",
        )


async def write_file(path: str, content: str, backup: bool = True) -> ToolResult:
    """
    Write content to a file anywhere on the system, optionally backing up existing file.
    
    Args:
        path: Path to file (can be absolute or relative, supports ~)
        content: Content to write
        backup: Whether to backup existing file
    
    Returns:
        ToolResult with write status
    """
    try:
        # Resolve path
        file_path = resolve_path(path)
        
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Backup existing file if requested
        backup_path = None
        if backup and file_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = file_path.with_suffix(f".{timestamp}.bak")
            shutil.copy2(file_path, backup_path)
        
        # Write file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            # Check for disk space issues
            if "No space left" in str(e):
                return ToolResult.error_result(
                    code=ErrorCode.DISK_FULL,
                    message="Disk full",
                    recoverable=False,
                    suggestion="Free up disk space and try again.",
                )
            raise
        
        result = {
            "path": str(file_path),
            "bytes_written": len(content.encode("utf-8")),
            "backup_created": backup_path is not None,
            "backup_path": str(backup_path) if backup_path else None,
        }
        
        return ToolResult.success_result(
            result=result,
            metadata={
                "bytes_written": len(content.encode("utf-8")),
            }
        )
    
    except PermissionError as e:
        return ToolResult.error_result(
            code=ErrorCode.PERMISSION_DENIED,
            message=f"Permission denied: {str(e)}",
            recoverable=True,
            suggestion="Check directory permissions.",
        )
    
    except Exception as e:
        logger.exception(f"Error writing file: {path}")
        return ToolResult.error_result(
            code=ErrorCode.UNKNOWN,
            message=f"Unexpected error: {str(e)}",
            recoverable=True,
            suggestion="Check logs for details.",
        )
