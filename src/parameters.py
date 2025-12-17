"""
Centralized configuration for all tunable parameters.

Optimized for fast CPU inference with minimal memory usage.
Supports hybrid LLM modes: local Ollama and cloud (Groq).
"""

import os
from pathlib import Path

from dotenv import load_dotenv


def _clean_env_value(value: str) -> str:
	value = (value or "").strip()
	if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
		value = value[1:-1].strip()
	return value


# Load environment variables from the repo-root .env file.
# Use override=True so a previously-set shell variable doesn't silently win.
_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=_REPO_ROOT / ".env", override=True)

# ============================================================================
# LLM Mode Configuration
# ============================================================================
LLM_MODE = os.getenv("LLM_MODE", "cloud")  # "local" or "cloud"
# local: Uses Ollama with qwen2.5:3b-instruct-q4_K_M (fast, private, requires local Ollama)
# cloud: Uses Groq API (fast, high-quality, requires GROQ_API_KEY)

GROQ_API_KEY = _clean_env_value(os.getenv("GROQ_API_KEY", ""))
# Groq API key for cloud mode

# ============================================================================
# Ingestion Parameters
# ============================================================================
CHUNK_SIZE = 200              # Words per chunk (reduced from 250 to 200 for memory efficiency)
CHUNK_OVERLAP = 20            # Word overlap between chunks (reduced from 25 to minimize redundancy)

# ============================================================================
# Retrieval Parameters
# ============================================================================
TOP_K_RETRIEVAL = 1           # Documents to retrieve for context (reduced from 2 to 1 for memory)
TOP_K_LLM = 10                # LLM diversity parameter (reduced from 15 to 10 for stability)

# ============================================================================
# LLM Generation Parameters
# ============================================================================
TEMPERATURE = 0.3             # 0 = deterministic, 1 = creative (0.3 allows detail without chaos)
MAX_TOKENS = 300              # Max response length for local (Ollama). Cloud will use a higher limit
REPEAT_PENALTY = 1.0          # Avoid repetition (lower = less computation)
REQUEST_TIMEOUT = 60          # Request timeout in seconds (reduced from 300 to 60 for stability)

# ============================================================================
# Performance Notes for CPU
# ============================================================================
# These settings are heavily optimized for CPU inference with limited memory:
# - Very small chunks (250 words) = minimal processing
# - Minimal overlap = no redundant data
# - Very few retrieved documents (2) = minimal vectors to process
# - Lower temperature = deterministic, faster generation
# - Very short responses (150 tokens) = quick completion
# - Lower top_k = focused, efficient generation
# - Lower repeat_penalty = less computation overhead
#
# Expected performance on Ryzen 7 3700X / i7-11th gen:
# - Full pipeline: 3-5 seconds per query
# - Just LLM inference: 1.5-2.5 seconds
# - Vector search: 10-30ms
#
# Memory usage: ~500MB-1GB (very lean on CPU)
