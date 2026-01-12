#!/bin/bash
# Convenience script to run Claude-Terminal-Ex

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Set API key
export XAI_API_KEY="${XAI_API_KEY:-your-api-key-here}"

# Run the agent
claude-term-ex run "$@"
