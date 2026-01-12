"""Web search using DuckDuckGo."""

import logging
from typing import Dict, Any
from duckduckgo_search import DDGS

from claude_term_ex.tools.errors import (
    ToolResult,
    ErrorCode,
)

logger = logging.getLogger(__name__)


async def search_web(query: str, max_results: int = 10) -> ToolResult:
    """
    Perform a web search using DuckDuckGo.
    
    Args:
        query: Search query
        max_results: Maximum number of results to return
    
    Returns:
        ToolResult with search results
    """
    try:
        if not query or not query.strip():
            return ToolResult.error_result(
                code=ErrorCode.INVALID_PARAMS,
                message="Empty search query",
                recoverable=True,
                suggestion="Provide a non-empty search query.",
            )
        
        # Perform search
        ddgs = DDGS()
        results = []
        
        for result in ddgs.text(query, max_results=max_results):
            results.append({
                "title": result.get("title", ""),
                "url": result.get("href", ""),
                "snippet": result.get("body", ""),
            })
        
        search_result = {
            "query": query,
            "results": results,
            "count": len(results),
        }
        
        return ToolResult.success_result(
            result=search_result,
            metadata={
                "results_count": len(results),
            }
        )
    
    except Exception as e:
        logger.exception(f"Error performing web search: {query}")
        return ToolResult.error_result(
            code=ErrorCode.NETWORK_ERROR,
            message=f"Search failed: {str(e)}",
            recoverable=True,
            suggestion="Check network connection and try again.",
        )
