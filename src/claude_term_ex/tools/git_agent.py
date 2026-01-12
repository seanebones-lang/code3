"""Autonomous Git operations with full system access."""

import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
import git
from git import Repo, GitCommandError

from claude_term_ex.config import GIT_TIMEOUT_SECONDS
from claude_term_ex.tools.errors import (
    ToolResult,
    ErrorCode,
)

logger = logging.getLogger(__name__)


def resolve_path(path: str) -> Path:
    """Resolve a path, expanding ~ and making absolute."""
    return Path(path).expanduser().resolve()


async def git_operation(
    operation: str,
    repository_path: Optional[str] = None,
    repository_url: Optional[str] = None,
    branch: Optional[str] = None,
    message: Optional[str] = None,
    files: Optional[list] = None,
    remote_name: str = "origin",
) -> ToolResult:
    """
    Perform Git operations autonomously on any repository.
    
    Args:
        operation: Git operation (clone, commit, push, pull, status, etc.)
        repository_path: Local repository path (any path on system)
        repository_url: Remote repository URL (for clone)
        branch: Branch name (for checkout, push, pull)
        message: Commit message (for commit)
        files: List of files to add/commit (for commit)
        remote_name: Remote name (default: origin)
    
    Returns:
        ToolResult with operation results
    """
    try:
        if operation == "clone":
            if not repository_url:
                return ToolResult.error_result(
                    code=ErrorCode.MISSING_REQUIRED_PARAM,
                    message="repository_url required for clone operation",
                    recoverable=True,
                    suggestion="Provide a repository URL to clone.",
                )
            
            # Clone to specified path or current directory
            repo_name = Path(repository_url).stem
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]
            
            if repository_path:
                target_path = resolve_path(repository_path)
            else:
                target_path = Path.cwd() / repo_name
            
            if target_path.exists():
                return ToolResult.error_result(
                    code=ErrorCode.INVALID_PARAMS,
                    message=f"Directory already exists: {target_path}",
                    recoverable=True,
                    suggestion="Remove existing directory or use a different path.",
                )
            
            # Clone repository
            try:
                repo = Repo.clone_from(
                    repository_url,
                    str(target_path),
                    timeout=GIT_TIMEOUT_SECONDS
                )
                
                result = {
                    "operation": "clone",
                    "repository_url": repository_url,
                    "local_path": str(target_path),
                    "current_branch": repo.active_branch.name,
                }
                
                return ToolResult.success_result(
                    result=result,
                    metadata={"repository_url": repository_url}
                )
            except GitCommandError as e:
                return ToolResult.error_result(
                    code=ErrorCode.EXECUTION_FAILED,
                    message=f"Git clone failed: {str(e)}",
                    recoverable=True,
                    suggestion="Check repository URL and network connection.",
                )
        
        elif operation in ["commit", "push", "pull", "status", "add"]:
            if not repository_path:
                return ToolResult.error_result(
                    code=ErrorCode.MISSING_REQUIRED_PARAM,
                    message="repository_path required for this operation",
                    recoverable=True,
                    suggestion="Provide a repository path.",
                )
            
            # Resolve path
            repo_path = resolve_path(repository_path)
            
            if not repo_path.exists():
                return ToolResult.error_result(
                    code=ErrorCode.FILE_NOT_FOUND,
                    message=f"Repository not found: {repository_path}",
                    recoverable=True,
                    suggestion="Check repository path.",
                )
            
            try:
                repo = Repo(str(repo_path))
            except git.InvalidGitRepositoryError:
                return ToolResult.error_result(
                    code=ErrorCode.INVALID_PARAMS,
                    message=f"Not a valid Git repository: {repository_path}",
                    recoverable=True,
                    suggestion="Ensure the path points to a Git repository.",
                )
            
            if operation == "status":
                status = repo.git.status()
                is_dirty = repo.is_dirty()
                untracked = repo.untracked_files
                
                result = {
                    "operation": "status",
                    "repository_path": str(repo_path),
                    "current_branch": repo.active_branch.name if repo.head.is_valid() else None,
                    "is_dirty": is_dirty,
                    "untracked_files": untracked,
                    "status_output": status,
                }
                
                return ToolResult.success_result(result=result)
            
            elif operation == "add":
                if not files:
                    # Add all files
                    repo.git.add(A=True)
                    added_files = repo.untracked_files + [item.a_path for item in repo.index.diff(None)]
                else:
                    # Add specific files
                    added_files = []
                    for file_path in files:
                        file_full_path = repo_path / file_path
                        if file_full_path.exists():
                            repo.git.add(str(file_path))
                            added_files.append(file_path)
                
                result = {
                    "operation": "add",
                    "repository_path": str(repo_path),
                    "added_files": added_files,
                }
                
                return ToolResult.success_result(result=result)
            
            elif operation == "commit":
                if not message:
                    return ToolResult.error_result(
                        code=ErrorCode.MISSING_REQUIRED_PARAM,
                        message="commit message required",
                        recoverable=True,
                        suggestion="Provide a commit message.",
                    )
                
                # Add files if specified
                if files:
                    for file_path in files:
                        file_full_path = repo_path / file_path
                        if file_full_path.exists():
                            repo.git.add(str(file_path))
                
                # Commit
                try:
                    commit = repo.index.commit(message)
                    result = {
                        "operation": "commit",
                        "repository_path": str(repo_path),
                        "commit_hash": commit.hexsha,
                        "message": message,
                        "author": f"{commit.author.name} <{commit.author.email}>",
                    }
                    
                    return ToolResult.success_result(result=result)
                except GitCommandError as e:
                    return ToolResult.error_result(
                        code=ErrorCode.EXECUTION_FAILED,
                        message=f"Commit failed: {str(e)}",
                        recoverable=True,
                        suggestion="Ensure there are changes to commit.",
                    )
            
            elif operation == "push":
                branch_name = branch or repo.active_branch.name
                
                try:
                    remote = repo.remote(remote_name)
                    push_info = remote.push(branch_name)
                    
                    result = {
                        "operation": "push",
                        "repository_path": str(repo_path),
                        "branch": branch_name,
                        "remote": remote_name,
                        "pushed": len([info for info in push_info if info.flags & push_info[0].UP_TO_DATE == 0]) > 0,
                    }
                    
                    return ToolResult.success_result(result=result)
                except GitCommandError as e:
                    return ToolResult.error_result(
                        code=ErrorCode.EXECUTION_FAILED,
                        message=f"Push failed: {str(e)}",
                        recoverable=True,
                        suggestion="Check authentication and remote configuration.",
                    )
            
            elif operation == "pull":
                branch_name = branch or repo.active_branch.name
                
                try:
                    remote = repo.remote(remote_name)
                    pull_info = remote.pull(branch_name)
                    
                    result = {
                        "operation": "pull",
                        "repository_path": str(repo_path),
                        "branch": branch_name,
                        "remote": remote_name,
                        "updated": len(pull_info) > 0,
                    }
                    
                    return ToolResult.success_result(result=result)
                except GitCommandError as e:
                    return ToolResult.error_result(
                        code=ErrorCode.EXECUTION_FAILED,
                        message=f"Pull failed: {str(e)}",
                        recoverable=True,
                        suggestion="Check network connection and remote configuration.",
                    )
        
        else:
            return ToolResult.error_result(
                code=ErrorCode.INVALID_PARAMS,
                message=f"Unknown Git operation: {operation}",
                recoverable=True,
                suggestion="Supported operations: clone, status, add, commit, push, pull",
            )
    
    except Exception as e:
        logger.exception(f"Error in Git operation: {operation}")
        return ToolResult.error_result(
            code=ErrorCode.UNKNOWN,
            message=f"Unexpected error: {str(e)}",
            recoverable=True,
            suggestion="Check logs for details.",
        )
