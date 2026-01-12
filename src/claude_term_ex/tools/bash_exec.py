"""Bash command execution with full system access."""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional

from claude_term_ex.config import (
    TOOL_TIMEOUT_SECONDS,
    MAX_BASH_OUTPUT_BYTES,
)
from claude_term_ex.tools.errors import (
    ToolResult,
    ErrorCode,
    ToolTimeout,
)

logger = logging.getLogger(__name__)


async def execute_bash(
    command: str, 
    confirm_high_risk: bool = False,
    working_directory: Optional[str] = None
) -> ToolResult:
    """
    Execute a bash command with full system access.
    
    Args:
        command: The shell command to execute
        confirm_high_risk: Whether high-risk commands are pre-confirmed
        working_directory: Optional directory to run command in (defaults to user's home)
    
    Returns:
        ToolResult with stdout, stderr, and exit code
    """
    start_time = time.time()
    
    try:
        # Determine working directory
        if working_directory:
            cwd = Path(working_directory).expanduser().resolve()
        else:
            cwd = Path.home()
        
        # Ensure directory exists
        if not cwd.exists():
            return ToolResult.error_result(
                code=ErrorCode.FILE_NOT_FOUND,
                message=f"Working directory not found: {cwd}",
                recoverable=True,
                suggestion="Provide a valid working directory path."
            )
        
        # Execute using shell for full bash capability
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
            limit=MAX_BASH_OUTPUT_BYTES,
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=TOOL_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise ToolTimeout(f"Command timed out after {TOOL_TIMEOUT_SECONDS}s")
        
        exit_code = process.returncode
        
        # Decode output
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        result = {
            "stdout": stdout_text,
            "stderr": stderr_text,
            "exit_code": exit_code,
            "command": command,
            "cwd": str(cwd),
        }
        
        return ToolResult.success_result(
            result=result,
            metadata={
                "duration_ms": duration_ms,
                "working_directory": str(cwd),
            }
        )
    
    except ToolTimeout as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return ToolResult.error_result(
            code=ErrorCode.TIMEOUT,
            message=str(e),
            recoverable=True,
            suggestion="Try a simpler command or increase timeout.",
            metadata={"duration_ms": duration_ms}
        )
    
    except Exception as e:
        logger.exception(f"Unexpected error executing bash command: {command[:50]}")
        duration_ms = int((time.time() - start_time) * 1000)
        return ToolResult.error_result(
            code=ErrorCode.UNKNOWN,
            message=f"Unexpected error: {str(e)}",
            recoverable=True,
            suggestion="Check logs for details.",
            metadata={"duration_ms": duration_ms}
        )
