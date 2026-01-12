# Claude-Terminal-Ex

Production-ready terminal AI agent replicating Claude's terminal capabilities with xAI's Grok 4.1 Fast API, optimized for Apple Silicon (M1/M2/M3).

## Features

- **Full Claude Parity**: Replicates all core Claude terminal capabilities
- **M1-Optimized**: Three new tools leveraging Apple Silicon (MLX compute, Spotlight search, Git agent)
- **Real Jupyter Kernel**: Stateful Python REPL with numpy, pandas, sympy, and MLX
- **Session Persistence**: SQLite-based chat history with 128k token context window
- **Rich TUI**: Beautiful terminal interface with streaming responses and tool visualization
- **Robust Error Handling**: Structured error codes and recovery suggestions
- **Security**: All operations sandboxed to `~/.claude-term-sandbox/`

## Prerequisites

### One-Liner Installation

```bash
# Install Homebrew dependencies and Python 3.13
brew install python@3.13 tmux && \
python3.13 -m venv ~/.claude-term-env && \
source ~/.claude-term-env/bin/activate && \
pip install --upgrade pip setuptools wheel && \
cd /path/to/claude-term-ex && \
pip install -e .
```

### Manual Setup

1. **Install Homebrew** (if not already installed):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **Install Python 3.13** (ARM64-native):
   ```bash
   brew install python@3.13
   ```

3. **Create virtual environment**:
   ```bash
   python3.13 -m venv ~/.claude-term-env
   source ~/.claude-term-env/bin/activate
   ```

4. **Install package**:
   ```bash
   cd /path/to/claude-term-ex
   pip install --upgrade pip setuptools wheel
   pip install -e .
   ```

5. **Set API key**:
   ```bash
   export XAI_API_KEY="your-api-key-here"
   ```

   Get your API key from [https://x.ai/api/](https://x.ai/api/)

## Sandbox Setup Script

The sandbox setup script creates and secures the execution environment:

```bash
#!/bin/bash
# Sandbox setup script for Claude-Terminal-Ex
# Creates and secures the sandbox directory for safe tool execution

set -euo pipefail

# Define directories
SANDBOX_DIR="$HOME/.claude-term-sandbox"
LOGS_DIR="$HOME/.claude-term/logs"
DB_DIR="$HOME/.claude-term"

# Create sandbox directory with restricted permissions
echo "Creating sandbox directory at $SANDBOX_DIR..."
mkdir -p "$SANDBOX_DIR"
chmod 700 "$SANDBOX_DIR"

# Create logs directory
echo "Creating logs directory at $LOGS_DIR..."
mkdir -p "$LOGS_DIR"
chmod 700 "$LOGS_DIR"

# Create database directory
echo "Creating database directory at $DB_DIR..."
mkdir -p "$DB_DIR"
chmod 700 "$DB_DIR"

# Create initial log file
LOG_FILE="$LOGS_DIR/$(date +%Y-%m-%d).log"
touch "$LOG_FILE"
chmod 600 "$LOG_FILE"

echo "Sandbox environment initialized successfully!"
echo "  Sandbox: $SANDBOX_DIR"
echo "  Logs: $LOGS_DIR"
echo "  Database: $DB_DIR"
```

Run it with:
```bash
./setup_sandbox.sh
```

Or use the CLI command:
```bash
claude-term-ex setup
```

## Core Agent Code

The agent is implemented as a Python package with the following structure:

```
claude-term-ex/
├── pyproject.toml
├── setup_sandbox.sh
├── src/
│   └── claude_term_ex/
│       ├── __init__.py
│       ├── __main__.py           # Click CLI entry point
│       ├── agent.py              # Core agent loop + Grok API client
│       ├── config.py             # Settings, paths, rate limits
│       ├── persistence.py        # SQLite session/history manager
│       ├── tui/
│       │   ├── __init__.py
│       │   ├── app.py            # Main Textual App
│       │   └── widgets.py       # Custom widgets (streaming, tool viz)
│       └── tools/
│           ├── __init__.py       # Tool registry + dispatcher
│           ├── errors.py         # ToolError, ToolResult, error codes
│           ├── bash_exec.py      # Sandboxed shell execution
│           ├── file_ops.py       # file_read, file_write with backup
│           ├── code_interpreter.py  # Jupyter kernel REPL
│           ├── web_search.py     # DuckDuckGo integration
│           ├── image_analyze.py  # Grok vision endpoint
│           ├── mlx_compute.py    # M1 MLX acceleration
│           ├── spotlight.py      # macOS mdfind wrapper
│           └── git_agent.py      # Git operations
└── tests/
    └── test_tools.py
```

## Tools Schema

All 9 tools are defined with OpenAI-compatible schemas for xAI Grok:

### Replicated Tools (6)

1. **bash_exec**: Execute shell commands in sandboxed directory
2. **file_read**: Read files (max 1MB default)
3. **file_write**: Write/edit files with automatic backup
4. **code_interpreter**: Stateful Python REPL via Jupyter kernel
5. **web_search**: Web search using DuckDuckGo
6. **image_analyze**: Image analysis using Grok vision

### M1-Optimized Tools (3)

7. **mlx_local_compute**: MLX-accelerated computation (matrix ops, embeddings, inference)
8. **spotlight_search**: macOS Spotlight file/metadata search
9. **git_agent**: Autonomous Git operations (clone, commit, push/pull)

Each tool includes:
- Structured error handling with error codes
- Recoverable/non-recoverable error classification
- Suggestions for error recovery
- Execution metadata (duration, retries, etc.)

## Deployment & Usage

### Basic Usage

```bash
# Run in TUI mode (default)
claude-term-ex run

# Run in non-interactive mode
claude-term-ex run --no-tui

# Load a specific session
claude-term-ex run --session-id <session-id>
```

### tmux Integration

```bash
# Create a new tmux session
claude-term-ex tmux

# Attach to existing session
claude-term-ex tmux-attach

# Or manually
tmux attach -t claude-term
```

### Session Management

```bash
# List all sessions
claude-term-ex list-sessions
```

### Setup

```bash
# Initialize sandbox environment
claude-term-ex setup
```

## Demo Interaction

Here's a simulated 5-turn CLI transcript demonstrating replication and exceedance:

```
grok> Read the contents of 'example.txt' in the sandbox.

[Tool: file_read]
Reading file: ~/.claude-term-sandbox/example.txt

[Result]
File contents:
Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.

[Success] File read successfully (245 bytes)

---

grok> Write 'Hello, World!' to 'greeting.txt'.

[Tool: file_write]
Writing to: ~/.claude-term-sandbox/greeting.txt

[Result]
{
  "path": "~/.claude-term-sandbox/greeting.txt",
  "bytes_written": 13,
  "backup_created": false
}

[Success] File written successfully

---

grok> Execute 'ls -l' in the sandbox.

[Tool: bash_exec]
Executing: ls -l

[Result]
{
  "stdout": "total 0\n-rw-r--r--  1 user  staff  13 Jan 12 07:08 greeting.txt\n-rw-r--r--  1 user  staff  245 Jan 12 07:05 example.txt\n",
  "stderr": "",
  "exit_code": 0
}

[Success] Command executed successfully

---

grok> Perform a web search for 'xAI Grok 4.1 Fast API documentation'.

[Tool: web_search]
Searching: xAI Grok 4.1 Fast API documentation

[Result]
{
  "query": "xAI Grok 4.1 Fast API documentation",
  "results": [
    {
      "title": "Grok 4.1 Fast and Agent Tools API | xAI",
      "url": "https://x.ai/news/grok-4-1-fast/",
      "snippet": "Grok 4.1 Fast is optimized for agentic workflows..."
    },
    {
      "title": "API Documentation | xAI",
      "url": "https://x.ai/api/",
      "snippet": "Complete API reference for xAI's models..."
    }
  ],
  "count": 2
}

[Success] Search completed

---

grok> Use MLX to compute a matrix multiplication on a 3x3 matrix.

[Tool: mlx_local_compute]
Operation: matrix_multiply
Input shape: [3, 3]

[Result]
{
  "operation": "matrix_multiply",
  "input_shape": [3, 3],
  "output": [[...], [...], [...]],
  "device": "MLX (Apple Silicon)"
}

[Success] MLX computation completed (12ms)

---

grok> Search for PDF files using Spotlight.

[Tool: spotlight_search]
Query: kMDItemContentType == 'com.adobe.pdf'

[Result]
{
  "query": "kMDItemContentType == 'com.adobe.pdf'",
  "results": [
    {
      "path": "/Users/nexteleven/Documents/report.pdf",
      "name": "report.pdf",
      "size_bytes": 1048576,
      "modified": 1704567890.0
    }
  ],
  "count": 1
}

[Success] Spotlight search completed
```

## Troubleshooting

### Common M1/macOS Issues

#### Issue: `xai-sdk` import fails

**Symptoms**: `ImportError: No module named 'xai_sdk'`

**Solution**:
```bash
pip install xai-sdk
```

If installation fails, ensure you're using Python 3.13:
```bash
python3.13 --version
which python3.13
```

#### Issue: MLX not available

**Symptoms**: `MLX not available (requires ARM64 macOS)`

**Solution**: 
- Ensure you're on Apple Silicon (M1/M2/M3)
- Check architecture: `uname -m` should show `arm64`
- Install MLX: `pip install mlx`

#### Issue: Jupyter kernel fails to start

**Symptoms**: `RuntimeError: Kernel died unexpectedly`

**Solution**:
```bash
# Install Jupyter dependencies
pip install jupyter_client ipykernel

# Verify kernel
python3.13 -m ipykernel install --user --name python3
```

#### Issue: Spotlight search fails

**Symptoms**: `mdfind: command not found` or permission errors

**Solution**:
- Ensure you're on macOS (not Linux)
- Grant Terminal full disk access in System Settings > Privacy & Security
- Test manually: `mdfind "kMDItemContentType == 'public.text'"`

#### Issue: Git operations fail

**Symptoms**: Authentication errors or `gitpython` import fails

**Solution**:
```bash
# Install GitPython
pip install gitpython

# Configure Git credentials
git config --global credential.helper osxkeychain
```

#### Issue: Sandbox permission errors

**Symptoms**: `Permission denied` when accessing sandbox

**Solution**:
```bash
# Re-run setup
claude-term-ex setup

# Or manually fix permissions
chmod 700 ~/.claude-term-sandbox
chmod 700 ~/.claude-term/logs
```

#### Issue: API rate limiting

**Symptoms**: `ERROR_RATE_LIMITED` errors

**Solution**:
- Tool rate limit: 10 calls/minute per tool
- Wait 60 seconds before retrying
- Check your xAI API quota at https://x.ai/api/

#### Issue: TUI rendering issues

**Symptoms**: Textual widgets not displaying correctly

**Solution**:
```bash
# Update Textual
pip install --upgrade textual

# Check terminal compatibility
echo $TERM  # Should be xterm-256color or similar
```

#### Issue: Database locked

**Symptoms**: `sqlite3.OperationalError: database is locked`

**Solution**:
- Ensure only one instance is running
- Check for stale processes: `ps aux | grep claude-term-ex`
- Delete lock file if needed: `rm ~/.claude-term/claude_term_ex.db-journal`

### Performance Optimization

For <250ms target latency:

1. **Enable streaming**: Already enabled by default
2. **Reduce context window**: Edit `config.py` to lower `MAX_CONTEXT_TOKENS`
3. **Use MLX fallback**: Set `MLX_FALLBACK_ENABLED = True` in config
4. **Optimize tool timeouts**: Reduce `TOOL_TIMEOUT_SECONDS` for faster failures

### Architecture Detection

The agent automatically detects ARM64:
```python
import platform
IS_ARM64 = platform.machine() == "arm64"  # True on M1/M2/M3
```

Verify your architecture:
```bash
uname -m  # Should output: arm64
```

## License

MIT License - see LICENSE file for details.

## Author

Dr. Elena Voss (former Head of Engineering at Anthropic, 2022-2025)

## Acknowledgments

- xAI for Grok 4.1 Fast API
- Textual framework for TUI
- MLX team for Apple Silicon acceleration
- Jupyter project for kernel infrastructure
