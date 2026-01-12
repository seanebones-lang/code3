"""Main Textual TUI application."""

import asyncio
import logging
from typing import Optional
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, TextArea, Static
from textual.containers import Vertical, Horizontal
from textual.binding import Binding
from textual.message import Message

from claude_term_ex.agent import Agent
from claude_term_ex.config import TUI_PROMPT, TUI_STREAMING_DELAY_MS
from claude_term_ex.tui.widgets import StreamingTextArea, ToolVisualizer, StatusBar

logger = logging.getLogger(__name__)


class ClaudeTerminalApp(App):
    """Main terminal application for Claude-Terminal-Ex."""
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #prompt-input {
        height: 3;
        border: solid $primary;
    }
    
    #response-area {
        border: solid $secondary;
    }
    
    #tool-visualizer {
        height: 20;
        border: solid $accent;
    }
    
    #status-bar {
        height: 1;
        background: $panel;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear", "Clear", priority=True),
    ]
    
    def __init__(self, agent: Optional[Agent] = None):
        """Initialize the app."""
        super().__init__()
        self.agent = agent or Agent()
        self.response_area: Optional[StreamingTextArea] = None
        self.tool_visualizer: Optional[ToolVisualizer] = None
        self.status_bar: Optional[StatusBar] = None
        self.prompt_input: Optional[Input] = None
        self._processing = False
    
    async def on_mount(self) -> None:
        """Called when app is mounted."""
        await self.agent.initialize()
        self.prompt_input = self.query_one("#prompt-input", Input)
        self.prompt_input.focus()
    
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header(show_clock=True)
        
        with Vertical():
            yield Static("[bold cyan]Claude-Terminal-Ex[/bold cyan] - Terminal AI Agent", id="title")
            
            yield Input(
                placeholder=TUI_PROMPT,
                id="prompt-input"
            )
            
            yield StreamingTextArea(
                id="response-area",
                read_only=True,
                language="markdown"
            )
            
            yield ToolVisualizer(id="tool-visualizer")
            
            yield StatusBar(id="status-bar")
        
        yield Footer()
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle prompt input submission."""
        if self._processing:
            return
        
        user_input = event.value.strip()
        if not user_input:
            return
        
        # Clear input
        self.prompt_input.value = ""
        
        # Show user message in response area
        self.response_area = self.query_one("#response-area", StreamingTextArea)
        self.response_area.append_stream(f"\n[bold green]{TUI_PROMPT}[/bold green] {user_input}\n\n")
        
        # Process message
        self._processing = True
        await self._process_message(user_input)
        self._processing = False
    
    async def _process_message(self, user_message: str):
        """Process a user message."""
        try:
            self.status_bar = self.query_one("#status-bar", StatusBar)
            self.tool_visualizer = self.query_one("#tool-visualizer", ToolVisualizer)
            
            # Update status
            self.status_bar.update_status(
                tokens=0,
                latency_ms=0,
                tool_queue=0
            )
            
            # Stream response
            import time
            full_response = ""
            start_time = time.time()
            
            async for chunk in self.agent.process_message(user_message, stream=True):
                full_response += chunk
                
                # Update response area with streaming effect
                self.response_area.append_stream(chunk)
                
                # Update latency
                elapsed_ms = int((time.time() - start_time) * 1000)
                self.status_bar.update_status(
                    tokens=len(full_response) // 4,  # Rough estimate
                    latency_ms=elapsed_ms,
                    tool_queue=0
                )
                
                # Small delay for streaming effect
                await asyncio.sleep(TUI_STREAMING_DELAY_MS / 1000.0)
            
            # Final status update
            elapsed_ms = int((time.time() - start_time) * 1000)
            tokens = await self.agent.session_manager.get_session_token_count()
            
            self.status_bar.update_status(
                tokens=tokens,
                latency_ms=elapsed_ms,
                tool_queue=0
            )
            
            # Add newline
            self.response_area.append_stream("\n\n")
        
        except Exception as e:
            logger.exception("Error processing message")
            error_msg = f"[bold red]Error:[/bold red] {str(e)}\n"
            self.response_area.append_stream(error_msg)
    
    def action_clear(self) -> None:
        """Clear the response area."""
        self.response_area = self.query_one("#response-area", StreamingTextArea)
        self.response_area.text = ""
    
    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()
    
    async def on_unmount(self) -> None:
        """Cleanup on unmount."""
        await self.agent.close()
