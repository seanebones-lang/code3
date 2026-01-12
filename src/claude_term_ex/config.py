"""Configuration and settings for Claude-Terminal-Ex."""

import os
import platform
from pathlib import Path
from typing import Optional

# Detect ARM64 architecture
IS_ARM64 = platform.machine() == "arm64"
IS_MACOS = platform.system() == "Darwin"

# Base directories
HOME = Path.home()
SANDBOX_DIR = HOME / ".claude-term-sandbox"
LOGS_DIR = HOME / ".claude-term" / "logs"
DB_DIR = HOME / ".claude-term"
DB_PATH = DB_DIR / "claude_term_ex.db"

# API Configuration
# Don't raise error at import time - let Agent class handle it
XAI_API_KEY = os.environ.get("XAI_API_KEY")

GROK_MODEL = "grok-4-1-fast-reasoning"
GROK_BASE_URL = "https://api.x.ai/v1"
GROK_STREAMING = True

# Context window management
MAX_CONTEXT_TOKENS = 128_000
MAX_MESSAGE_TOKENS = 100_000  # Reserve space for responses
TOKEN_ESTIMATE_CHARS = 4  # Rough estimate: 1 token ≈ 4 chars

# Tool execution limits
TOOL_TIMEOUT_SECONDS = 30
TOOL_RATE_LIMIT_PER_MINUTE = 60  # Increased for more tool-heavy workflows
MAX_FILE_SIZE_BYTES = 1_048_576  # 1MB default
MAX_BASH_OUTPUT_BYTES = 10_485_760  # 10MB max output

# Security settings
HIGH_RISK_COMMANDS = [
    "rm -rf",
    "sudo",
    "chmod 777",
    "dd if=",
    "mkfs",
    "fdisk",
    "format",
    "> /dev/",
]

# Sandbox validation
def ensure_sandbox_path(path: str) -> Path:
    """Ensure a path is within the sandbox directory."""
    resolved = Path(path).resolve()
    sandbox_resolved = SANDBOX_DIR.resolve()
    
    try:
        resolved.relative_to(sandbox_resolved)
    except ValueError:
        raise ValueError(
            f"Path {path} is outside sandbox directory {SANDBOX_DIR}. "
            "All file operations must be within the sandbox."
        )
    
    return resolved

def is_high_risk_command(command: str) -> bool:
    """Check if a command is considered high-risk."""
    command_lower = command.lower().strip()
    return any(risk in command_lower for risk in HIGH_RISK_COMMANDS)

# Logging configuration
def get_log_file() -> Path:
    """Get today's log file path."""
    from datetime import date
    log_file = LOGS_DIR / f"{date.today().isoformat()}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    return log_file

# Jupyter kernel configuration
JUPYTER_KERNEL_NAME = "python3"
JUPYTER_PRELOAD_MODULES = ["numpy", "pandas", "sympy"]
if IS_ARM64:
    JUPYTER_PRELOAD_MODULES.append("mlx")

# MLX configuration (M1 only)
MLX_ENABLED = IS_ARM64 and IS_MACOS
MLX_FALLBACK_ENABLED = True  # Use MLX when API unavailable

# Spotlight search configuration
SPOTLIGHT_MAX_RESULTS = 50
SPOTLIGHT_TIMEOUT_SECONDS = 5

# Git agent configuration
GIT_CREDENTIAL_HELPER = "osxkeychain" if IS_MACOS else "cache"
GIT_TIMEOUT_SECONDS = 60

# TUI configuration
TUI_PROMPT = "grok> "
TUI_STREAMING_DELAY_MS = 10  # Delay between character renders for streaming effect
TUI_STATUS_REFRESH_MS = 100  # Status bar refresh rate

# Sandbox setup (placeholder - actual setup done by script)
def setup_sandbox():
    """Placeholder for sandbox setup."""
    pass

# Performance targets
TARGET_LATENCY_MS = 250  # Target end-to-end latency
STREAMING_CHUNK_SIZE = 16  # Characters per streaming chunk
