"""Tool registry and dispatcher with robust error handling."""

import logging
import asyncio
import time
from typing import Dict, Any, Optional, Callable, List
from collections import defaultdict
from dataclasses import dataclass

from claude_term_ex.tools.errors import (
    ToolResult,
    ToolError,
    ErrorCode,
    ToolTimeout,
    ToolValidationError,
)
from claude_term_ex.tools import bash_exec
from claude_term_ex.tools import file_ops
from claude_term_ex.tools import code_interpreter
from claude_term_ex.tools import web_search
from claude_term_ex.tools import image_analyze
from claude_term_ex.tools import mlx_compute
from claude_term_ex.tools import spotlight
from claude_term_ex.tools import git_agent
from claude_term_ex.tools import filesystem
from claude_term_ex.config import TOOL_TIMEOUT_SECONDS, TOOL_RATE_LIMIT_PER_MINUTE

logger = logging.getLogger(__name__)


# Rate limiting
_rate_limit_counts: Dict[str, List[float]] = defaultdict(list)


def check_rate_limit(tool_name: str) -> bool:
    """Check if tool is within rate limit."""
    now = time.time()
    minute_ago = now - 60
    
    # Clean old entries
    _rate_limit_counts[tool_name] = [
        t for t in _rate_limit_counts[tool_name] if t > minute_ago
    ]
    
    # Check limit
    if len(_rate_limit_counts[tool_name]) >= TOOL_RATE_LIMIT_PER_MINUTE:
        return False
    
    # Add current call
    _rate_limit_counts[tool_name].append(now)
    return True


# Tool schemas (OpenAI-compatible format for xAI Grok)
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "bash_exec",
            "description": "Execute shell commands on the local machine with full system access. Can run any bash command. Returns stdout, stderr, and exit code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute"
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Directory to run the command in (supports ~, defaults to user's home directory)"
                    },
                    "confirm_high_risk": {
                        "type": "boolean",
                        "description": "Whether high-risk commands are pre-confirmed (default: false)",
                        "default": False
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Read the contents of any file on the local machine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file (absolute path or relative with ~ for home directory)"
                    },
                    "max_bytes": {
                        "type": "integer",
                        "description": "Maximum number of bytes to read (default: 1MB)",
                        "default": 1048576
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": "Write or create a file anywhere on the local machine. Creates backup of existing files by default.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file (absolute path or relative with ~ for home directory)"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    },
                    "backup": {
                        "type": "boolean",
                        "description": "Whether to backup existing file (default: true)",
                        "default": True
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and directories in a given path. Shows file names, types, and sizes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_directory": {
                        "type": "string",
                        "description": "Directory path to list (supports ~ for home directory)"
                    },
                    "ignore_globs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional glob patterns to ignore (e.g., ['*.pyc', 'node_modules'])"
                    },
                    "show_hidden": {
                        "type": "boolean",
                        "description": "Whether to show hidden files starting with . (default: false)",
                        "default": False
                    }
                },
                "required": ["target_directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search for a regex pattern in files using ripgrep or grep. Fast text search across files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for"
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory to search in (defaults to current directory)"
                    },
                    "file_type": {
                        "type": "string",
                        "description": "File type filter (e.g., 'py', 'js', 'ts')"
                    },
                    "glob_pattern": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g., '*.py')"
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "description": "Whether to ignore case (default: false)",
                        "default": False
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of context lines before/after match (default: 0)",
                        "default": 0
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 100)",
                        "default": 100
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "glob_file_search",
            "description": "Search for files matching a glob pattern. Returns matching file paths sorted by modification time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "glob_pattern": {
                        "type": "string",
                        "description": "Glob pattern to match (e.g., '*.py', '**/*.js')"
                    },
                    "target_directory": {
                        "type": "string",
                        "description": "Directory to search in (defaults to current directory)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 100)",
                        "default": 100
                    }
                },
                "required": ["glob_pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_replace",
            "description": "Perform exact string replacement in a file. The old_string must be unique unless replace_all is True. Creates backup automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to modify"
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact text to replace (must be unique in file unless replace_all=True)"
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The replacement text"
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace all occurrences (default: false - requires unique old_string)",
                        "default": False
                    }
                },
                "required": ["file_path", "old_string", "new_string"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_lints",
            "description": "Read linter/compiler errors from files. Supports Python (ruff/flake8) and JavaScript/TypeScript (eslint).",
            "parameters": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of file or directory paths to check"
                    },
                    "linter": {
                        "type": "string",
                        "description": "Linter to use (auto, pylint, flake8, mypy, eslint, tsc)",
                        "default": "auto"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "code_interpreter",
            "description": "Execute Python code in a stateful REPL using Jupyter kernel. Pre-loaded with numpy, pandas, sympy, and MLX (on M1). Maintains state across calls.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Execution timeout in seconds (default: 30)",
                        "default": 30
                    }
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Perform a web search using DuckDuckGo. Returns titles, URLs, and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "image_analyze",
            "description": "Analyze an image using Grok's vision capabilities. Can describe images, read text, identify objects.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to image file (absolute path or with ~ for home directory)"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Optional prompt/question about the image"
                    }
                },
                "required": ["image_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mlx_local_compute",
            "description": "Perform MLX-accelerated computation on M1/M2/M3 chips. Supports matrix operations, embeddings, and lightweight inference.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "Operation type: matrix_multiply, embedding, or inference",
                        "enum": ["matrix_multiply", "embedding", "inference"]
                    },
                    "input_data": {
                        "type": "array",
                        "description": "Input data as array/list"
                    },
                    "model_name": {
                        "type": "string",
                        "description": "Optional model name for inference operations"
                    }
                },
                "required": ["operation", "input_data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "spotlight_search",
            "description": "Search files using macOS Spotlight (mdfind). Returns file paths with metadata. Great for finding files by content or name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (Spotlight syntax)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 50)",
                        "default": 50
                    },
                    "file_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of file extensions to filter (e.g., ['pdf', 'txt'])"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_agent",
            "description": "Perform Git operations autonomously. Supports clone, status, add, commit, push, pull on any repository on the local machine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "Git operation: clone, status, add, commit, push, or pull",
                        "enum": ["clone", "status", "add", "commit", "push", "pull"]
                    },
                    "repository_path": {
                        "type": "string",
                        "description": "Local repository path (required for status, add, commit, push, pull)"
                    },
                    "repository_url": {
                        "type": "string",
                        "description": "Remote repository URL (required for clone)"
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch name (for checkout, push, pull)"
                    },
                    "message": {
                        "type": "string",
                        "description": "Commit message (required for commit)"
                    },
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of files to add/commit"
                    },
                    "remote_name": {
                        "type": "string",
                        "description": "Remote name (default: origin)",
                        "default": "origin"
                    }
                },
                "required": ["operation"]
            }
        }
    },
]


# Tool registry mapping names to functions
TOOL_REGISTRY: Dict[str, Callable] = {
    "bash_exec": bash_exec.execute_bash,
    "file_read": file_ops.read_file,
    "file_write": file_ops.write_file,
    "list_dir": filesystem.list_dir,
    "grep": filesystem.grep_search,
    "glob_file_search": filesystem.glob_file_search,
    "search_replace": filesystem.search_replace,
    "read_lints": filesystem.read_lints,
    "code_interpreter": code_interpreter.execute_code,
    "web_search": web_search.search_web,
    "image_analyze": image_analyze.analyze_image,
    "mlx_local_compute": mlx_compute.mlx_compute,
    "spotlight_search": spotlight.spotlight_search,
    "git_agent": git_agent.git_operation,
}


async def dispatch_tool(
    name: str,
    params: Dict[str, Any],
    grok_client: Optional[Any] = None
) -> ToolResult:
    """
    Dispatch a tool call with robust error handling.
    
    Args:
        name: Tool name
        params: Tool parameters
        grok_client: Optional Grok client (for tools that need it)
    
    Returns:
        ToolResult with execution result or error
    """
    start_time = time.time()
    
    # Check if tool exists
    if name not in TOOL_REGISTRY:
        return ToolResult.error_result(
            code=ErrorCode.INVALID_PARAMS,
            message=f"Unknown tool: {name}",
            recoverable=True,
            suggestion=f"Available tools: {', '.join(TOOL_REGISTRY.keys())}",
            metadata={"tool_name": name}
        )
    
    # Check rate limit
    if not check_rate_limit(name):
        return ToolResult.error_result(
            code=ErrorCode.RATE_LIMITED,
            message=f"Rate limit exceeded for tool: {name}",
            recoverable=True,
            suggestion=f"Wait before retrying. Limit: {TOOL_RATE_LIMIT_PER_MINUTE} calls/minute",
            metadata={"tool_name": name}
        )
    
    # Get tool function
    tool_func = TOOL_REGISTRY[name]
    
    # Inject grok_client for image_analyze if needed
    if name == "image_analyze" and grok_client:
        params["grok_client"] = grok_client
    
    try:
        # Execute tool with timeout
        if asyncio.iscoroutinefunction(tool_func):
            result = await asyncio.wait_for(
                tool_func(**params),
                timeout=TOOL_TIMEOUT_SECONDS
            )
        else:
            # Synchronous function - run in executor
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: tool_func(**params)),
                timeout=TOOL_TIMEOUT_SECONDS
            )
        
        # Add execution metadata
        duration_ms = int((time.time() - start_time) * 1000)
        if result.metadata:
            result.metadata["duration_ms"] = duration_ms
            result.metadata["tool_name"] = name
        else:
            result.metadata = {
                "duration_ms": duration_ms,
                "tool_name": name,
            }
        
        return result
    
    except asyncio.TimeoutError:
        duration_ms = int((time.time() - start_time) * 1000)
        return ToolResult.error_result(
            code=ErrorCode.TIMEOUT,
            message=f"Tool {name} timed out after {TOOL_TIMEOUT_SECONDS}s",
            recoverable=True,
            suggestion="Try simpler input or increase timeout.",
            metadata={"duration_ms": duration_ms, "tool_name": name}
        )
    
    except ToolValidationError as e:
        return ToolResult.error_result(
            code=ErrorCode.INVALID_PARAMS,
            message=f"Invalid parameters: {str(e)}",
            recoverable=True,
            suggestion="Check tool parameters and try again.",
            metadata={"tool_name": name}
        )
    
    except Exception as e:
        logger.exception(f"Unexpected error in tool {name}")
        duration_ms = int((time.time() - start_time) * 1000)
        return ToolResult.error_result(
            code=ErrorCode.UNKNOWN,
            message=f"Unexpected error: {str(e)}",
            recoverable=True,
            suggestion="Check logs at ~/.claude-term/logs/",
            metadata={"duration_ms": duration_ms, "tool_name": name}
        )


class ToolRegistry:
    """Tool registry manager."""
    
    @staticmethod
    def get_tool_schema(name: str) -> Optional[Dict[str, Any]]:
        """Get tool schema by name."""
        for tool in TOOLS_SCHEMA:
            if tool["function"]["name"] == name:
                return tool
        return None
    
    @staticmethod
    def list_tools() -> List[str]:
        """List all available tool names."""
        return list(TOOL_REGISTRY.keys())
    
    @staticmethod
    def get_all_schemas() -> List[Dict[str, Any]]:
        """Get all tool schemas."""
        return TOOLS_SCHEMA
