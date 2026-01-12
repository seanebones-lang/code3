"""Image analysis using Grok vision capabilities."""

import logging
import base64
from pathlib import Path
from typing import Dict, Any, Optional

from claude_term_ex.config import MAX_FILE_SIZE_BYTES
from claude_term_ex.tools.errors import (
    ToolResult,
    ErrorCode,
)

logger = logging.getLogger(__name__)


async def analyze_image(
    image_path: str,
    prompt: Optional[str] = None,
    grok_client: Optional[Any] = None
) -> ToolResult:
    """
    Analyze an image using Grok's vision capabilities.
    
    Args:
        image_path: Path to image file (any path on local machine)
        prompt: Optional prompt/question about the image
        grok_client: xAI Grok client instance (will be injected by agent)
    
    Returns:
        ToolResult with image analysis
    """
    try:
        if grok_client is None:
            return ToolResult.error_result(
                code=ErrorCode.INVALID_PARAMS,
                message="Grok client not provided",
                recoverable=False,
                suggestion="Image analysis requires Grok API client.",
            )
        
        # Resolve path
        file_path = Path(image_path).expanduser().resolve()
        
        # Check if file exists
        if not file_path.exists():
            return ToolResult.error_result(
                code=ErrorCode.FILE_NOT_FOUND,
                message=f"Image not found: {image_path}",
                recoverable=True,
                suggestion="Check the image path and try again.",
            )
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            return ToolResult.error_result(
                code=ErrorCode.FILE_TOO_LARGE,
                message=f"Image too large: {file_size} bytes (max: {MAX_FILE_SIZE_BYTES})",
                recoverable=True,
                suggestion="Resize or compress the image.",
                details={"file_size": file_size, "max_bytes": MAX_FILE_SIZE_BYTES}
            )
        
        # Read and encode image
        with open(file_path, "rb") as f:
            image_data = f.read()
        
        image_base64 = base64.b64encode(image_data).decode("utf-8")
        
        # Determine MIME type from extension
        ext = file_path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(ext, "image/jpeg")
        
        # Prepare message for Grok
        analysis_prompt = prompt or "Describe this image in detail."
        
        # Call Grok API with image
        # Note: This is a simplified version - actual xAI SDK may have different API
        try:
            # Using OpenAI-compatible format for vision
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": analysis_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]
            
            # Call Grok API (OpenAI-compatible interface)
            response = await grok_client.chat.completions.create(
                model="grok-4-1-fast-reasoning",
                messages=messages,
                max_tokens=1000,
            )
            
            analysis_text = response.choices[0].message.content
            
            result = {
                "analysis": analysis_text,
                "image_path": str(file_path),
                "prompt": analysis_prompt,
                "image_size_bytes": file_size,
            }
            
            return ToolResult.success_result(
                result=result,
                metadata={
                    "image_size_bytes": file_size,
                    "mime_type": mime_type,
                }
            )
        
        except Exception as api_error:
            logger.exception("Error calling Grok API for image analysis")
            return ToolResult.error_result(
                code=ErrorCode.API_TIMEOUT,
                message=f"Grok API error: {str(api_error)}",
                recoverable=True,
                suggestion="Check API key and network connection.",
            )
    
    except Exception as e:
        logger.exception(f"Error analyzing image: {image_path}")
        return ToolResult.error_result(
            code=ErrorCode.UNKNOWN,
            message=f"Unexpected error: {str(e)}",
            recoverable=True,
            suggestion="Check logs for details.",
        )
