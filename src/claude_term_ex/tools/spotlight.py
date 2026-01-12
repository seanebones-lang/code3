"""macOS Spotlight search integration."""

import logging
import subprocess
import asyncio
from typing import Dict, Any, List
from pathlib import Path

from claude_term_ex.config import (
    SPOTLIGHT_MAX_RESULTS,
    SPOTLIGHT_TIMEOUT_SECONDS,
    IS_MACOS,
)
from claude_term_ex.tools.errors import (
    ToolResult,
    ErrorCode,
)

logger = logging.getLogger(__name__)


async def spotlight_search(
    query: str,
    max_results: Optional[int] = None,
    file_types: Optional[List[str]] = None
) -> ToolResult:
    """
    Search files using macOS Spotlight (mdfind).
    
    Args:
        query: Search query (Spotlight syntax)
        max_results: Maximum number of results
        file_types: Optional list of file extensions to filter (e.g., ['pdf', 'txt'])
    
    Returns:
        ToolResult with search results
    """
    if not IS_MACOS:
        return ToolResult.error_result(
            code=ErrorCode.INVALID_PARAMS,
            message="Spotlight search requires macOS",
            recoverable=False,
            suggestion="Spotlight is only available on macOS.",
        )
    
    try:
        if not query or not query.strip():
            return ToolResult.error_result(
                code=ErrorCode.INVALID_PARAMS,
                message="Empty search query",
                recoverable=True,
                suggestion="Provide a non-empty search query.",
            )
        
        max_results = max_results or SPOTLIGHT_MAX_RESULTS
        
        # Build mdfind command
        cmd = ["mdfind", query]
        
        # Add file type filter if specified
        if file_types:
            type_query = " OR ".join([f"kMDItemFSName == '*.{ext}'" for ext in file_types])
            cmd.extend(["-onlyin", str(Path.home()), type_query])
        
        # Execute mdfind
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024,  # 1MB limit
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=SPOTLIGHT_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            return ToolResult.error_result(
                code=ErrorCode.TIMEOUT,
                message=f"Spotlight search timed out after {SPOTLIGHT_TIMEOUT_SECONDS}s",
                recoverable=True,
                suggestion="Try a more specific query or increase timeout.",
            )
        
        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")
            return ToolResult.error_result(
                code=ErrorCode.EXECUTION_FAILED,
                message=f"mdfind failed: {error_msg}",
                recoverable=True,
                suggestion="Check Spotlight query syntax.",
            )
        
        # Parse results
        output = stdout.decode("utf-8", errors="replace")
        paths = [line.strip() for line in output.split("\n") if line.strip()]
        
        # Limit results
        paths = paths[:max_results]
        
        # Get metadata for each file
        results = []
        for path_str in paths:
            try:
                path = Path(path_str)
                if not path.exists():
                    continue
                
                # Get basic file info
                stat = path.stat()
                
                # Try to get Spotlight metadata
                try:
                    mdls_process = await asyncio.create_subprocess_exec(
                        "mdls",
                        str(path),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    mdls_stdout, _ = await asyncio.wait_for(
                        mdls_process.communicate(),
                        timeout=1.0
                    )
                    metadata_text = mdls_stdout.decode("utf-8", errors="replace")
                except Exception:
                    metadata_text = ""
                
                results.append({
                    "path": str(path),
                    "name": path.name,
                    "size_bytes": stat.st_size,
                    "modified": stat.st_mtime,
                    "metadata": metadata_text[:500] if metadata_text else None,  # Limit metadata size
                })
            except Exception as e:
                logger.debug(f"Error processing result {path_str}: {e}")
                continue
        
        search_result = {
            "query": query,
            "results": results,
            "count": len(results),
            "file_types": file_types,
        }
        
        return ToolResult.success_result(
            result=search_result,
            metadata={
                "results_count": len(results),
                "total_found": len(paths),
            }
        )
    
    except Exception as e:
        logger.exception(f"Error in Spotlight search: {query}")
        return ToolResult.error_result(
            code=ErrorCode.UNKNOWN,
            message=f"Unexpected error: {str(e)}",
            recoverable=True,
            suggestion="Check logs for details.",
        )
