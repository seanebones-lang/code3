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
