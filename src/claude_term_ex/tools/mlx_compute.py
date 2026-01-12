"""M1-native MLX acceleration for on-device computation."""

import logging
from typing import Dict, Any, Optional
import numpy as np

from claude_term_ex.config import MLX_ENABLED
from claude_term_ex.tools.errors import (
    ToolResult,
    ErrorCode,
)

logger = logging.getLogger(__name__)

# Try to import MLX
try:
    import mlx.core as mx
    import mlx.nn as nn
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False
    mx = None
    nn = None


async def mlx_compute(
    operation: str,
    input_data: Any,
    model_name: Optional[str] = None
) -> ToolResult:
    """
    Perform MLX-accelerated computation on M1/M2/M3 chips.
    
    Args:
        operation: Operation type (matrix_multiply, embedding, inference, etc.)
        input_data: Input data (list, dict, or numpy array)
        model_name: Optional model name for inference operations
    
    Returns:
        ToolResult with computation results
    """
    if not MLX_ENABLED or not MLX_AVAILABLE:
        return ToolResult.error_result(
            code=ErrorCode.INVALID_PARAMS,
            message="MLX not available (requires ARM64 macOS)",
            recoverable=False,
            suggestion="MLX acceleration requires Apple Silicon (M1/M2/M3) and macOS.",
        )
    
    try:
        # Convert input to MLX array
        if isinstance(input_data, list):
            mx_array = mx.array(input_data)
        elif isinstance(input_data, np.ndarray):
            mx_array = mx.array(input_data.tolist())
        else:
            return ToolResult.error_result(
                code=ErrorCode.INVALID_PARAMS,
                message=f"Unsupported input type: {type(input_data)}",
                recoverable=True,
                suggestion="Provide input as list or numpy array.",
            )
        
        result_data = None
        
        if operation == "matrix_multiply":
            # Simple matrix multiplication
            if mx_array.ndim != 2:
                return ToolResult.error_result(
                    code=ErrorCode.INVALID_PARAMS,
                    message="Matrix multiply requires 2D array",
                    recoverable=True,
                    suggestion="Provide a 2D matrix.",
                )
            # Multiply by transpose for demo
            result_data = mx.matmul(mx_array, mx_array.T)
            result_data = result_data.tolist()
        
        elif operation == "embedding":
            # Simple embedding computation (demo)
            # In production, this would load a real model
            embedding_dim = 128
            if mx_array.ndim == 1:
                mx_array = mx_array.reshape(1, -1)
            
            # Simple linear projection as demo
            weight = mx.random.normal((mx_array.shape[-1], embedding_dim))
            result_data = mx.matmul(mx_array, weight)
            result_data = result_data.tolist()
        
        elif operation == "inference":
            # Lightweight inference (demo)
            # In production, this would load a real MLX model
            if model_name:
                logger.info(f"Inference with model: {model_name}")
            
            # Simple forward pass demo
            if mx_array.ndim == 1:
                mx_array = mx_array.reshape(1, -1)
            
            # Demo: simple transformation
            hidden_dim = min(64, mx_array.shape[-1])
            weight1 = mx.random.normal((mx_array.shape[-1], hidden_dim))
            weight2 = mx.random.normal((hidden_dim, 1))
            
            hidden = mx.matmul(mx_array, weight1)
            hidden = mx.maximum(hidden, 0)  # ReLU
            output = mx.matmul(hidden, weight2)
            result_data = output.tolist()
        
        else:
            return ToolResult.error_result(
                code=ErrorCode.INVALID_PARAMS,
                message=f"Unknown operation: {operation}",
                recoverable=True,
                suggestion="Supported operations: matrix_multiply, embedding, inference",
            )
        
        result = {
            "operation": operation,
            "input_shape": list(mx_array.shape),
            "output": result_data,
            "model_name": model_name,
            "device": "MLX (Apple Silicon)",
        }
        
        return ToolResult.success_result(
            result=result,
            metadata={
                "operation": operation,
                "input_shape": list(mx_array.shape),
            }
        )
    
    except Exception as e:
        logger.exception(f"Error in MLX computation: {operation}")
        return ToolResult.error_result(
            code=ErrorCode.EXECUTION_FAILED,
            message=f"MLX computation failed: {str(e)}",
            recoverable=True,
            suggestion="Check input data format and try again.",
        )
