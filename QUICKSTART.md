# Quick Start Guide

## 1. Set Your API Key

```bash
export XAI_API_KEY="your-xai-api-key-here"
```

To make it permanent, add to your `~/.zshrc` or `~/.bash_profile`:
```bash
echo 'export XAI_API_KEY="your-xai-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

## 2. Install Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install the package and dependencies
pip install --upgrade pip setuptools wheel
pip install -e .
```

## 3. Setup Sandbox

```bash
./setup_sandbox.sh
# OR
claude-term-ex setup
```

## 4. Run the Agent

```bash
# TUI mode (default)
claude-term-ex run

# Non-interactive mode
claude-term-ex run --no-tui

# With tmux
claude-term-ex tmux
```

## Troubleshooting

If you get import errors, make sure all dependencies are installed:
```bash
pip install xai-sdk textual click jupyter_client ipykernel mlx gitpython duckduckgo-search aiosqlite rich pydantic
```
