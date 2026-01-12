"""Custom Textual widgets for the TUI."""

from textual.widgets import TextArea, Static, Collapsible
from textual.containers import Container, Vertical, Horizontal
from textual.reactive import reactive
from rich.console import RenderableType
from rich.text import Text
from rich.syntax import Syntax
from rich.panel import Panel
from typing import Optional
import json


class StreamingTextArea(TextArea):
    """Text area that supports streaming text updates."""
    
    def append_stream(self, text: str):
        """Append text to the text area."""
        current = self.text
        self.text = current + text
        self.scroll_end(animate=False)


class ToolVisualizer(Container):
    """Widget to visualize tool execution."""
    
    tool_name = reactive("")
    tool_status = reactive("")
    tool_result = reactive("")
    
    def compose(self):
        with Collapsible(title="Tool Execution", collapsed=True):
            yield Static("", id="tool-name")
            yield Static("", id="tool-status")
            yield Static("", id="tool-result")
    
    def watch_tool_name(self, tool_name: str):
        """Update tool name display."""
        name_widget = self.query_one("#tool-name")
        name_widget.update(f"[bold cyan]Tool:[/bold cyan] {tool_name}")
    
    def watch_tool_status(self, tool_status: str):
        """Update tool status display."""
        status_widget = self.query_one("#tool-status")
        status_widget.update(f"[bold yellow]Status:[/bold yellow] {tool_status}")
    
    def watch_tool_result(self, tool_result: str):
        """Update tool result display."""
        result_widget = self.query_one("#tool-result")
        
        # Try to format as JSON if possible
        try:
            result_data = json.loads(tool_result)
            formatted = json.dumps(result_data, indent=2)
            syntax = Syntax(formatted, "json", theme="monokai", line_numbers=True)
            result_widget.update(Panel(syntax, title="Result", border_style="green"))
        except:
            # Plain text
            result_widget.update(f"[dim]Result:[/dim]\n{tool_result}")
    
    def show_tool_execution(self, name: str, status: str, result: str):
        """Show a tool execution."""
        self.tool_name = name
        self.tool_status = status
        self.tool_result = result
        
        # Expand the collapsible
        collapsible = self.query_one(Collapsible)
        collapsible.collapsed = False


class StatusBar(Static):
    """Status bar showing session info."""
    
    tokens = reactive(0)
    latency_ms = reactive(0)
    tool_queue = reactive(0)
    
    def render(self) -> RenderableType:
        """Render the status bar."""
        parts = [
            f"[bold]Tokens:[/bold] {self.tokens:,}",
            f"[bold]Latency:[/bold] {self.latency_ms}ms",
            f"[bold]Tools:[/bold] {self.tool_queue}",
        ]
        return Text(" | ".join(parts), style="dim")
    
    def update_status(self, tokens: int, latency_ms: int, tool_queue: int):
        """Update status bar values."""
        self.tokens = tokens
        self.latency_ms = latency_ms
        self.tool_queue = tool_queue
