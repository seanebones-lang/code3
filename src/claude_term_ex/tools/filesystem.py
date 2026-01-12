"""Filesystem tools: list_dir, grep, glob search, and smart editing."""

import asyncio
import fnmatch
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from claude_term_ex.tools.errors import ToolResult, ErrorCode

logger = logging.getLogger(__name__)


def resolve_path(path: str) -> Path:
    """Resolve a path, expanding ~ and making absolute."""
    return Path(path).expanduser().resolve()


async def list_dir(
    target_directory: str,
    ignore_globs: Optional[List[str]] = None,
    show_hidden: bool = False
) -> ToolResult:
    """
    List files and directories in a given path.
    
    Args:
        target_directory: Directory path to list
        ignore_globs: Optional list of glob patterns to ignore
        show_hidden: Whether to show hidden files (starting with .)
    
    Returns:
        ToolResult with directory listing
    """
    try:
        dir_path = resolve_path(target_directory)
        
        if not dir_path.exists():
            return ToolResult.error_result(
                code=ErrorCode.FILE_NOT_FOUND,
                message=f"Directory not found: {target_directory}",
                recoverable=True,
                suggestion="Check the directory path and try again.",
            )
        
        if not dir_path.is_dir():
            return ToolResult.error_result(
                code=ErrorCode.INVALID_PARAMS,
                message=f"Path is not a directory: {target_directory}",
                recoverable=True,
                suggestion="Provide a path to a directory, not a file.",
            )
        
        ignore_globs = ignore_globs or []
        entries = []
        
        for entry in sorted(dir_path.iterdir()):
            name = entry.name
            
            # Skip hidden files unless requested
            if not show_hidden and name.startswith('.'):
                continue
            
            # Check ignore patterns
            should_ignore = False
            for pattern in ignore_globs:
                # Add **/ prefix if not present
                if not pattern.startswith('**/'):
                    pattern = f'**/{pattern}'
                if fnmatch.fnmatch(name, pattern.replace('**/', '')):
                    should_ignore = True
                    break
            
            if should_ignore:
                continue
            
            entry_info = {
                "name": name,
                "type": "directory" if entry.is_dir() else "file",
                "path": str(entry),
            }
            
            # Add file size for files
            if entry.is_file():
                try:
                    entry_info["size_bytes"] = entry.stat().st_size
                except:
                    pass
            
            entries.append(entry_info)
        
        result = {
            "directory": str(dir_path),
            "entries": entries,
            "count": len(entries),
        }
        
        return ToolResult.success_result(result=result)
    
    except PermissionError as e:
        return ToolResult.error_result(
            code=ErrorCode.PERMISSION_DENIED,
            message=f"Permission denied: {str(e)}",
            recoverable=True,
            suggestion="Check directory permissions.",
        )
    
    except Exception as e:
        logger.exception(f"Error listing directory: {target_directory}")
        return ToolResult.error_result(
            code=ErrorCode.UNKNOWN,
            message=f"Unexpected error: {str(e)}",
            recoverable=True,
            suggestion="Check logs for details.",
        )


async def grep_search(
    pattern: str,
    path: Optional[str] = None,
    file_type: Optional[str] = None,
    glob_pattern: Optional[str] = None,
    case_insensitive: bool = False,
    context_lines: int = 0,
    max_results: int = 100
) -> ToolResult:
    """
    Search for a regex pattern in files using ripgrep or grep.
    
    Args:
        pattern: Regex pattern to search for
        path: File or directory to search in (defaults to current directory)
        file_type: File type filter (e.g., 'py', 'js', 'ts')
        glob_pattern: Glob pattern to filter files (e.g., '*.py')
        case_insensitive: Whether to ignore case
        context_lines: Number of context lines before/after match
        max_results: Maximum number of results to return
    
    Returns:
        ToolResult with search results
    """
    try:
        search_path = resolve_path(path) if path else Path.cwd()
        
        if not search_path.exists():
            return ToolResult.error_result(
                code=ErrorCode.FILE_NOT_FOUND,
                message=f"Path not found: {path}",
                recoverable=True,
                suggestion="Check the path and try again.",
            )
        
        # Try ripgrep first, fall back to grep
        use_ripgrep = True
        try:
            subprocess.run(["rg", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            use_ripgrep = False
        
        if use_ripgrep:
            cmd = ["rg", "--json", "-m", str(max_results)]
            
            if case_insensitive:
                cmd.append("-i")
            
            if context_lines > 0:
                cmd.extend(["-C", str(context_lines)])
            
            if file_type:
                cmd.extend(["-t", file_type])
            
            if glob_pattern:
                cmd.extend(["--glob", glob_pattern])
            
            cmd.append(pattern)
            cmd.append(str(search_path))
        else:
            # Fallback to grep
            cmd = ["grep", "-r", "-n"]
            
            if case_insensitive:
                cmd.append("-i")
            
            if context_lines > 0:
                cmd.extend(["-C", str(context_lines)])
            
            if glob_pattern:
                cmd.extend(["--include", glob_pattern])
            
            cmd.append(pattern)
            cmd.append(str(search_path))
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30
        )
        
        output = stdout.decode("utf-8", errors="replace")
        
        # Parse results
        matches = []
        if use_ripgrep:
            import json
            for line in output.strip().split('\n'):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get('type') == 'match':
                        match_data = data.get('data', {})
                        matches.append({
                            "file": match_data.get('path', {}).get('text', ''),
                            "line_number": match_data.get('line_number', 0),
                            "content": match_data.get('lines', {}).get('text', '').strip(),
                        })
                except json.JSONDecodeError:
                    continue
        else:
            # Parse grep output
            for line in output.strip().split('\n'):
                if not line:
                    continue
                # Format: file:line:content
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    matches.append({
                        "file": parts[0],
                        "line_number": int(parts[1]) if parts[1].isdigit() else 0,
                        "content": parts[2].strip(),
                    })
        
        result = {
            "pattern": pattern,
            "path": str(search_path),
            "matches": matches[:max_results],
            "total_matches": len(matches),
            "truncated": len(matches) > max_results,
        }
        
        return ToolResult.success_result(result=result)
    
    except asyncio.TimeoutError:
        return ToolResult.error_result(
            code=ErrorCode.TIMEOUT,
            message="Search timed out",
            recoverable=True,
            suggestion="Try a more specific pattern or smaller search scope.",
        )
    
    except Exception as e:
        logger.exception(f"Error in grep search: {pattern}")
        return ToolResult.error_result(
            code=ErrorCode.UNKNOWN,
            message=f"Unexpected error: {str(e)}",
            recoverable=True,
            suggestion="Check logs for details.",
        )


async def glob_file_search(
    glob_pattern: str,
    target_directory: Optional[str] = None,
    max_results: int = 100
) -> ToolResult:
    """
    Search for files matching a glob pattern.
    
    Args:
        glob_pattern: Glob pattern to match (e.g., '*.py', '**/*.js')
        target_directory: Directory to search in (defaults to current directory)
        max_results: Maximum number of results
    
    Returns:
        ToolResult with matching file paths
    """
    try:
        search_dir = resolve_path(target_directory) if target_directory else Path.cwd()
        
        if not search_dir.exists():
            return ToolResult.error_result(
                code=ErrorCode.FILE_NOT_FOUND,
                message=f"Directory not found: {target_directory}",
                recoverable=True,
                suggestion="Check the directory path.",
            )
        
        # Add **/ prefix if not present for recursive search
        if not glob_pattern.startswith('**/'):
            glob_pattern = f'**/{glob_pattern}'
        
        matches = []
        for match in search_dir.glob(glob_pattern):
            if match.is_file():
                matches.append({
                    "path": str(match),
                    "name": match.name,
                    "size_bytes": match.stat().st_size,
                    "modified": datetime.fromtimestamp(match.stat().st_mtime).isoformat(),
                })
                
                if len(matches) >= max_results:
                    break
        
        # Sort by modification time (most recent first)
        matches.sort(key=lambda x: x["modified"], reverse=True)
        
        result = {
            "pattern": glob_pattern,
            "directory": str(search_dir),
            "matches": matches,
            "total_matches": len(matches),
        }
        
        return ToolResult.success_result(result=result)
    
    except Exception as e:
        logger.exception(f"Error in glob search: {glob_pattern}")
        return ToolResult.error_result(
            code=ErrorCode.UNKNOWN,
            message=f"Unexpected error: {str(e)}",
            recoverable=True,
            suggestion="Check logs for details.",
        )


async def search_replace(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False
) -> ToolResult:
    """
    Perform exact string replacement in a file.
    
    Args:
        file_path: Path to the file to modify
        old_string: The exact text to replace (must be unique unless replace_all=True)
        new_string: The replacement text
        replace_all: If True, replace all occurrences; if False, old_string must be unique
    
    Returns:
        ToolResult with replacement status
    """
    try:
        path = resolve_path(file_path)
        
        if not path.exists():
            return ToolResult.error_result(
                code=ErrorCode.FILE_NOT_FOUND,
                message=f"File not found: {file_path}",
                recoverable=True,
                suggestion="Check the file path.",
            )
        
        if not path.is_file():
            return ToolResult.error_result(
                code=ErrorCode.INVALID_PARAMS,
                message=f"Path is not a file: {file_path}",
                recoverable=True,
                suggestion="Provide a path to a file.",
            )
        
        # Read file
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for old_string
        occurrences = content.count(old_string)
        
        if occurrences == 0:
            return ToolResult.error_result(
                code=ErrorCode.INVALID_PARAMS,
                message=f"String not found in file: {old_string[:50]}...",
                recoverable=True,
                suggestion="Check that the old_string exactly matches content in the file.",
            )
        
        if not replace_all and occurrences > 1:
            return ToolResult.error_result(
                code=ErrorCode.INVALID_PARAMS,
                message=f"String found {occurrences} times. Must be unique or use replace_all=True",
                recoverable=True,
                suggestion="Provide more context to make old_string unique, or set replace_all=True.",
            )
        
        # Create backup
        backup_path = path.with_suffix(f'.{datetime.now().strftime("%Y%m%d_%H%M%S")}.bak')
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
            replacements_made = occurrences
        else:
            new_content = content.replace(old_string, new_string, 1)
            replacements_made = 1
        
        # Write file
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        result = {
            "file_path": str(path),
            "replacements_made": replacements_made,
            "backup_path": str(backup_path),
            "old_string_preview": old_string[:100] + "..." if len(old_string) > 100 else old_string,
            "new_string_preview": new_string[:100] + "..." if len(new_string) > 100 else new_string,
        }
        
        return ToolResult.success_result(result=result)
    
    except PermissionError as e:
        return ToolResult.error_result(
            code=ErrorCode.PERMISSION_DENIED,
            message=f"Permission denied: {str(e)}",
            recoverable=True,
            suggestion="Check file permissions.",
        )
    
    except Exception as e:
        logger.exception(f"Error in search_replace: {file_path}")
        return ToolResult.error_result(
            code=ErrorCode.UNKNOWN,
            message=f"Unexpected error: {str(e)}",
            recoverable=True,
            suggestion="Check logs for details.",
        )


async def read_lints(
    paths: Optional[List[str]] = None,
    linter: str = "auto"
) -> ToolResult:
    """
    Read linter/compiler errors from files.
    
    Args:
        paths: List of file or directory paths to check
        linter: Linter to use ('auto', 'pylint', 'flake8', 'mypy', 'eslint', 'tsc')
    
    Returns:
        ToolResult with linter errors
    """
    try:
        if not paths:
            paths = [str(Path.cwd())]
        
        resolved_paths = [str(resolve_path(p)) for p in paths]
        
        # Detect linter based on file types
        all_files = []
        for p in resolved_paths:
            path = Path(p)
            if path.is_file():
                all_files.append(path)
            elif path.is_dir():
                all_files.extend(path.rglob('*'))
        
        extensions = set(f.suffix.lower() for f in all_files if f.is_file())
        
        diagnostics = []
        
        # Python linting
        if '.py' in extensions:
            try:
                # Try ruff first (fast)
                cmd = ["ruff", "check", "--output-format=json"] + resolved_paths
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await process.communicate()
                
                if stdout:
                    import json
                    try:
                        errors = json.loads(stdout.decode())
                        for err in errors:
                            diagnostics.append({
                                "file": err.get("filename", ""),
                                "line": err.get("location", {}).get("row", 0),
                                "column": err.get("location", {}).get("column", 0),
                                "severity": "error" if err.get("code", "").startswith("E") else "warning",
                                "message": err.get("message", ""),
                                "code": err.get("code", ""),
                                "linter": "ruff",
                            })
                    except json.JSONDecodeError:
                        pass
            except FileNotFoundError:
                # Fall back to flake8
                try:
                    cmd = ["flake8", "--format=%(path)s:%(row)d:%(col)d: %(code)s %(text)s"] + resolved_paths
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, _ = await process.communicate()
                    
                    for line in stdout.decode().strip().split('\n'):
                        if not line:
                            continue
                        parts = line.split(':', 3)
                        if len(parts) >= 4:
                            diagnostics.append({
                                "file": parts[0],
                                "line": int(parts[1]) if parts[1].isdigit() else 0,
                                "column": int(parts[2]) if parts[2].isdigit() else 0,
                                "severity": "error",
                                "message": parts[3].strip(),
                                "linter": "flake8",
                            })
                except FileNotFoundError:
                    pass
        
        # JavaScript/TypeScript linting
        if '.js' in extensions or '.ts' in extensions or '.tsx' in extensions or '.jsx' in extensions:
            try:
                cmd = ["eslint", "--format=json"] + resolved_paths
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await process.communicate()
                
                if stdout:
                    import json
                    try:
                        results = json.loads(stdout.decode())
                        for file_result in results:
                            for msg in file_result.get("messages", []):
                                diagnostics.append({
                                    "file": file_result.get("filePath", ""),
                                    "line": msg.get("line", 0),
                                    "column": msg.get("column", 0),
                                    "severity": "error" if msg.get("severity") == 2 else "warning",
                                    "message": msg.get("message", ""),
                                    "code": msg.get("ruleId", ""),
                                    "linter": "eslint",
                                })
                    except json.JSONDecodeError:
                        pass
            except FileNotFoundError:
                pass
        
        result = {
            "paths": resolved_paths,
            "diagnostics": diagnostics,
            "total_errors": len([d for d in diagnostics if d.get("severity") == "error"]),
            "total_warnings": len([d for d in diagnostics if d.get("severity") == "warning"]),
        }
        
        return ToolResult.success_result(result=result)
    
    except Exception as e:
        logger.exception(f"Error reading lints")
        return ToolResult.error_result(
            code=ErrorCode.UNKNOWN,
            message=f"Unexpected error: {str(e)}",
            recoverable=True,
            suggestion="Check logs for details.",
        )
