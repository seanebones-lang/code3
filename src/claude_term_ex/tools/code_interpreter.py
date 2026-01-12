"""Stateful Python REPL using Jupyter kernel."""

import logging
import asyncio
from typing import Dict, Any, Optional
from jupyter_client import KernelManager
import json

from claude_term_ex.config import (
    JUPYTER_KERNEL_NAME,
    JUPYTER_PRELOAD_MODULES,
    TOOL_TIMEOUT_SECONDS,
)
from claude_term_ex.tools.errors import (
    ToolResult,
    ErrorCode,
    ToolTimeout,
)

logger = logging.getLogger(__name__)

# Global kernel manager (singleton)
_kernel_manager: Optional[KernelManager] = None
_kernel_client: Optional[Any] = None


async def get_kernel() -> tuple[KernelManager, Any]:
    """Get or create the Jupyter kernel."""
    global _kernel_manager, _kernel_client
    
    if _kernel_manager is None or (hasattr(_kernel_manager, 'is_alive') and not _kernel_manager.is_alive()):
        _kernel_manager = KernelManager(kernel_name=JUPYTER_KERNEL_NAME)
        _kernel_manager.start_kernel()
        _kernel_client = _kernel_manager.client()
        
        # Pre-load modules
        preload_code = "\n".join([f"import {mod}" for mod in JUPYTER_PRELOAD_MODULES])
        if preload_code:
            # Run in executor since execute is synchronous
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _kernel_client.execute, preload_code)
            # Wait for execution
            await asyncio.sleep(0.5)
        
        logger.info(f"Jupyter kernel started with preloaded modules: {JUPYTER_PRELOAD_MODULES}")
    
    return _kernel_manager, _kernel_client


async def execute_code(code: str, timeout: Optional[int] = None) -> ToolResult:
    """
    Execute Python code in a stateful Jupyter kernel.
    
    Args:
        code: Python code to execute
        timeout: Execution timeout in seconds
    
    Returns:
        ToolResult with stdout, stderr, and execution results
    """
    timeout = timeout or TOOL_TIMEOUT_SECONDS
    
    try:
        km, kc = await get_kernel()
        
        if not km.is_alive():
            raise RuntimeError("Kernel died unexpectedly")
        
        # Execute code (run in executor since it's synchronous)
        loop = asyncio.get_event_loop()
        msg_id = await loop.run_in_executor(None, kc.execute, code)
        
        # Collect outputs
        stdout_parts = []
        stderr_parts = []
        result_parts = []
        error_occurred = False
        
        # Wait for execution with timeout
        import time
        start_time = time.time()
        
        while True:
            try:
                # get_iopub_msg is synchronous, run in executor
                # Use functools.partial to avoid lambda closure issues
                from functools import partial
                msg = await asyncio.wait_for(
                    loop.run_in_executor(None, partial(kc.get_iopub_msg, timeout=1.0)),
                    timeout=max(1.0, timeout - (time.time() - start_time))
                )
            except asyncio.TimeoutError:
                raise ToolTimeout(f"Code execution timed out after {timeout}s")
            
            msg_type = msg.get("msg_type", "")
            content = msg.get("content", {})
            
            if msg_type == "stream":
                name = content.get("name", "")
                text = content.get("text", "")
                if name == "stdout":
                    stdout_parts.append(text)
                elif name == "stderr":
                    stderr_parts.append(text)
            
            elif msg_type == "execute_result":
                result_parts.append(content.get("data", {}).get("text/plain", ""))
            
            elif msg_type == "error":
                error_occurred = True
                error_name = content.get("ename", "Error")
                error_value = content.get("evalue", "")
                traceback = content.get("traceback", [])
                stderr_parts.append(f"{error_name}: {error_value}\n" + "\n".join(traceback))
            
            elif msg_type == "status" and content.get("execution_state") == "idle":
                # Check if this is our message
                parent_header = msg.get("parent_header", {})
                if isinstance(parent_header, dict) and parent_header.get("msg_id") == msg_id:
                    break
        
        stdout = "".join(stdout_parts)
        stderr = "".join(stderr_parts)
        result = "\n".join(result_parts) if result_parts else None
        
        execution_result = {
            "stdout": stdout,
            "stderr": stderr,
            "result": result,
            "error": error_occurred,
            "code": code,
        }
        
        return ToolResult.success_result(
            result=execution_result,
            metadata={
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }
        )
    
    except ToolTimeout as e:
        return ToolResult.error_result(
            code=ErrorCode.TIMEOUT,
            message=str(e),
            recoverable=True,
            suggestion="Try simpler code or increase timeout.",
        )
    
    except Exception as e:
        logger.exception(f"Error executing Python code")
        return ToolResult.error_result(
            code=ErrorCode.EXECUTION_FAILED,
            message=f"Execution failed: {str(e)}",
            recoverable=True,
            suggestion="Check code syntax and dependencies.",
        )


async def reset_kernel() -> ToolResult:
    """Reset the kernel state."""
    global _kernel_manager, _kernel_client
    
    try:
        if _kernel_manager:
            _kernel_manager.shutdown_kernel()
        _kernel_manager = None
        _kernel_client = None
        
        return ToolResult.success_result(
            result={"message": "Kernel reset successfully"},
            metadata={}
        )
    except Exception as e:
        logger.exception("Error resetting kernel")
        return ToolResult.error_result(
            code=ErrorCode.UNKNOWN,
            message=f"Failed to reset kernel: {str(e)}",
            recoverable=True,
            suggestion="Try restarting the agent.",
        )
