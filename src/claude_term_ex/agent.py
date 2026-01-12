"""Core agent loop with xAI Grok integration using OpenAI-compatible API."""

import asyncio
import logging
import os
import json
from typing import AsyncIterator, Dict, Any, Optional, List
from datetime import datetime

from openai import AsyncOpenAI

from claude_term_ex.config import (
    XAI_API_KEY,
    GROK_MODEL,
    GROK_BASE_URL,
    GROK_STREAMING,
    TARGET_LATENCY_MS,
    STREAMING_CHUNK_SIZE,
    get_log_file,
)
from claude_term_ex.persistence import SessionManager
from claude_term_ex.tools.registry import dispatch_tool, TOOLS_SCHEMA

logger = logging.getLogger(__name__)


class Agent:
    """Core agent that manages conversation and tool calling with Grok."""
    
    def __init__(self, session_manager: Optional[SessionManager] = None):
        """Initialize the agent."""
        if not XAI_API_KEY:
            raise EnvironmentError(
                "XAI_API_KEY environment variable not set. "
                "Get your API key from https://x.ai/api/"
            )
        
        # Use OpenAI client with xAI's OpenAI-compatible API
        self.client = AsyncOpenAI(
            api_key=XAI_API_KEY,
            base_url=GROK_BASE_URL,
        )
        self.session_manager = session_manager or SessionManager()
        self.current_session_id: Optional[str] = None
    
    async def initialize(self):
        """Initialize the agent and session."""
        await self.session_manager.initialize()
        self.current_session_id = await self.session_manager.create_session()
        logger.info(f"Agent initialized with session: {self.current_session_id}")
    
    async def close(self):
        """Close agent and cleanup."""
        await self.session_manager.close()
    
    def _log_action(self, action: str, details: Dict[str, Any]):
        """Log an action to the log file."""
        try:
            log_file = get_log_file()
            timestamp = datetime.now().isoformat()
            log_entry = f"[{timestamp}] {action}: {details}\n"
            with open(log_file, "a") as f:
                f.write(log_entry)
        except Exception as e:
            logger.debug(f"Failed to write log: {e}")
    
    async def process_message(
        self,
        user_message: str,
        stream: bool = True
    ) -> AsyncIterator[str]:
        """
        Process a user message and yield streaming response.
        
        Args:
            user_message: User's message
            stream: Whether to stream the response
        
        Yields:
            Response chunks as strings
        """
        # Save user message
        await self.session_manager.add_message("user", user_message)
        
        # Get conversation history
        messages = await self.session_manager.get_messages()
        
        # Convert to OpenAI format
        openai_messages = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role in ["user", "assistant", "system"]:
                openai_messages.append({"role": role, "content": content})
            elif role == "tool":
                # Tool results are handled separately
                continue
        
        # Log action
        self._log_action("user_message", {"message": user_message[:100]})
        
        # Call Grok API with tool calling
        try:
            if stream:
                async for chunk in self._stream_with_tools(openai_messages):
                    yield chunk
            else:
                response = await self._call_with_tools(openai_messages)
                yield response
        except Exception as e:
            logger.exception("Error processing message")
            error_msg = f"Error: {str(e)}"
            yield error_msg
            await self.session_manager.add_message("assistant", error_msg)
    
    async def _call_with_tools(self, messages: List[Dict]) -> str:
        """Call Grok API with tools (non-streaming)."""
        # Call API
        response = await self.client.chat.completions.create(
            model=GROK_MODEL,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
        )
        
        message = response.choices[0].message
        content = message.content or ""
        
        # Handle tool calls
        if message.tool_calls:
            # Add assistant message with tool calls to history
            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in message.tool_calls
                ]
            })
            
            # Execute each tool
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_params = json.loads(tool_call.function.arguments)
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.error(f"Failed to parse tool arguments: {e}")
                    # Add error result
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": f"Error parsing arguments: {e}"
                    })
                    continue
                
                # Dispatch tool
                result = await dispatch_tool(
                    tool_name,
                    tool_params,
                    grok_client=self.client
                )
                
                # Add tool result to messages
                if result.success:
                    content = json.dumps(result.result) if isinstance(result.result, dict) else str(result.result)
                else:
                    content = f"Error: {result.error.message}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": content
                })
                
                # Log tool execution
                self._log_action("tool_execution", {
                    "tool": tool_name,
                    "success": result.success,
                })
            
            # Get final response after tool execution
            final_response = await self.client.chat.completions.create(
                model=GROK_MODEL,
                messages=messages,
            )
            content = final_response.choices[0].message.content or ""
        
        # Save assistant message
        await self.session_manager.add_message("assistant", content)
        
        return content
    
    async def _stream_with_tools(
        self,
        messages: List[Dict]
    ) -> AsyncIterator[str]:
        """Call Grok API with tools (streaming)."""
        # Call API with streaming
        stream = await self.client.chat.completions.create(
            model=GROK_MODEL,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
            stream=True,
        )
        
        full_content = ""
        tool_calls_data = {}  # id -> {name, arguments}
        current_tool_id = None
        
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue
            
            # Handle content
            if delta.content:
                full_content += delta.content
                yield delta.content
            
            # Handle tool calls (accumulated across chunks)
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    tc_id = tc_delta.id or current_tool_id
                    if tc_delta.id:
                        current_tool_id = tc_delta.id
                        tool_calls_data[tc_id] = {
                            "id": tc_id,
                            "name": tc_delta.function.name if tc_delta.function else "",
                            "arguments": ""
                        }
                    
                    if tc_id and tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_data[tc_id]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_data[tc_id]["arguments"] += tc_delta.function.arguments
        
        # If we have tool calls, execute them
        if tool_calls_data:
            # Add assistant message with tool calls to history
            messages.append({
                "role": "assistant",
                "content": full_content,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        }
                    }
                    for tc in tool_calls_data.values()
                ]
            })
            
            # Execute tools
            for tc_id, tc_data in tool_calls_data.items():
                tool_name = tc_data["name"]
                try:
                    tool_params = json.loads(tc_data["arguments"])
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.error(f"Failed to parse tool arguments for {tool_name}: {e}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": f"Error parsing arguments: {e}"
                    })
                    continue
                
                # Dispatch tool
                result = await dispatch_tool(
                    tool_name,
                    tool_params,
                    grok_client=self.client
                )
                
                # Add tool result
                if result.success:
                    content = json.dumps(result.result) if isinstance(result.result, dict) else str(result.result)
                else:
                    content = f"Error: {result.error.message}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": content
                })
                
                # Log tool execution
                self._log_action("tool_execution", {
                    "tool": tool_name,
                    "success": result.success,
                })
            
            # Get final response with tool results (streaming)
            final_stream = await self.client.chat.completions.create(
                model=GROK_MODEL,
                messages=messages,
                stream=True,
            )
            
            final_content = ""
            async for chunk in final_stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    final_content += delta.content
                    yield delta.content
            
            # Save final assistant message
            await self.session_manager.add_message("assistant", final_content)
        else:
            # No tool calls, just save the content
            await self.session_manager.add_message("assistant", full_content)
