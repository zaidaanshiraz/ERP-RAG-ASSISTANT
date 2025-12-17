"""
Configuration management for device selection (CPU/GPU).

Supports environment variable configuration with automatic GPU detection fallback.
"""

import os
import torch


class Config:
    """Global configuration for device and model settings."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # Device configuration
        self.use_gpu = self._get_device_config()
        self.device = self._detect_device()
        
        # Model configuration (keep existing defaults)
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        # qwen2.5:3b-instruct-q4_K_M - Quantized for optimized speed and quality
        # GPU (GTX 1660): 1-3 seconds
        # CPU (8+ cores): 4-6 seconds
        # Iris Xe: 5-10 seconds
        # Quantized size (2.0GB) with excellent quality and faster inference
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct-q4_K_M")
        
    def _get_device_config(self) -> bool:
        """
        Get device preference from environment variable.
        
        Returns:
            True if GPU should be used, False for CPU-only
        """
        use_gpu = os.getenv("USE_GPU", "false").lower()
        
        if use_gpu == "true":
            return True
        elif use_gpu == "false":
            return False
        else:  # "auto" or any other value
            return torch.cuda.is_available()
    
    def _detect_device(self) -> str:
        """
        Detect and return the device string for model loading.
        
        Returns:
            'cuda' if GPU is available and enabled, otherwise 'cpu'
        """
        if self.use_gpu and torch.cuda.is_available():
            device = "cuda"
            gpu_name = torch.cuda.get_device_name(0)
            print(f"[Config] Using GPU: {gpu_name}")
        else:
            device = "cpu"
            if self.use_gpu and not torch.cuda.is_available():
                print("[Config] GPU requested but not available, falling back to CPU")
            else:
                print("[Config] Using CPU")
        
        return device
    
    def get_device_info(self) -> dict:
        """
        Get detailed device information.
        
        Returns:
            Dictionary with device configuration details
        """
        info = {
            "device": self.device,
            "use_gpu": self.use_gpu,
            "cuda_available": torch.cuda.is_available(),
        }
        
        if torch.cuda.is_available():
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_memory_gb"] = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        
        return info


# Global configuration instance
config = Config()
