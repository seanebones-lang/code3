"""CLI entry point for Claude-Terminal-Ex."""

import asyncio
import click
import logging
import sys
import subprocess
from pathlib import Path

from claude_term_ex.agent import Agent
from claude_term_ex.tui.app import ClaudeTerminalApp
from claude_term_ex.config import setup_sandbox

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Claude-Terminal-Ex: Production-ready terminal AI agent."""
    pass


@cli.command()
def setup():
    """Set up the sandbox environment."""
    click.echo("Setting up sandbox environment...")
    try:
        # Run sandbox setup script
        script_path = Path(__file__).parent.parent.parent / "setup_sandbox.sh"
        if script_path.exists():
            subprocess.run(["bash", str(script_path)], check=True)
            click.echo(click.style("✓ Sandbox setup complete!", fg="green"))
        else:
            click.echo(click.style("✗ Setup script not found", fg="red"), err=True)
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"✗ Setup failed: {e}", fg="red"), err=True)
        sys.exit(1)


@cli.command()
@click.option("--session-id", help="Load an existing session")
@click.option("--no-tui", is_flag=True, help="Run in non-interactive mode")
def run(session_id: str, no_tui: bool):
    """Run the Claude-Terminal-Ex agent."""
    # Check for API key
    import os
    if not os.environ.get("XAI_API_KEY"):
        click.echo(
            click.style(
                "✗ XAI_API_KEY environment variable not set.\n"
                "Get your API key from https://x.ai/api/",
                fg="red"
            ),
            err=True
        )
        sys.exit(1)
    
    if no_tui:
        # Non-interactive mode
        click.echo("Running in non-interactive mode...")
        agent = Agent()
        
        async def interactive_loop():
            await agent.initialize()
            click.echo("Agent ready. Type 'exit' to quit.\n")
            
            while True:
                try:
                    user_input = input("grok> ").strip()
                    if not user_input or user_input.lower() == "exit":
                        break
                    
                    async for chunk in agent.process_message(user_input, stream=True):
                        click.echo(chunk, nl=False)
                    click.echo()  # Newline
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    click.echo(click.style(f"Error: {e}", fg="red"), err=True)
            
            await agent.close()
        
        asyncio.run(interactive_loop())
    else:
        # TUI mode
        agent = Agent()
        if session_id:
            # Load session (would need to implement)
            pass
        
        app = ClaudeTerminalApp(agent=agent)
        app.run()


@cli.command()
def tmux():
    """Create a new tmux session for Claude-Terminal-Ex."""
    session_name = "claude-term"
    
    click.echo(f"Creating tmux session '{session_name}'...")
    
    try:
        # Check if session exists
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True
        )
        
        if result.returncode == 0:
            click.echo(click.style(f"Session '{session_name}' already exists.", fg="yellow"))
            attach = click.confirm("Attach to existing session?", default=True)
            if attach:
                subprocess.run(["tmux", "attach", "-t", session_name])
        else:
            # Create new session
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", session_name, "claude-term-ex", "run"],
                check=True
            )
            click.echo(click.style(f"✓ Created session '{session_name}'", fg="green"))
            click.echo(f"Attach with: tmux attach -t {session_name}")
            click.echo(f"Or run: claude-term-ex tmux-attach")
    
    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"✗ Failed to create tmux session: {e}", fg="red"), err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.echo(
            click.style("✗ tmux not found. Install with: brew install tmux", fg="red"),
            err=True
        )
        sys.exit(1)


@cli.command()
@click.argument("session_name", default="claude-term")
def tmux_attach(session_name: str):
    """Attach to a tmux session."""
    try:
        subprocess.run(["tmux", "attach", "-t", session_name], check=True)
    except subprocess.CalledProcessError:
        click.echo(
            click.style(f"✗ Session '{session_name}' not found", fg="red"),
            err=True
        )
        sys.exit(1)
    except FileNotFoundError:
        click.echo(
            click.style("✗ tmux not found. Install with: brew install tmux", fg="red"),
            err=True
        )
        sys.exit(1)


@cli.command()
def list_sessions():
    """List all chat sessions."""
    import asyncio
    from claude_term_ex.persistence import SessionManager
    
    async def _list():
        sm = SessionManager()
        await sm.initialize()
        sessions = await sm.list_sessions(limit=20)
        await sm.close()
        
        if not sessions:
            click.echo("No sessions found.")
            return
        
        click.echo(f"\nFound {len(sessions)} session(s):\n")
        for session in sessions:
            click.echo(f"  {session['id']}")
            click.echo(f"    Created: {session['created_at']}")
            click.echo(f"    Messages: {session['message_count']}")
            click.echo()
    
    asyncio.run(_list())


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
