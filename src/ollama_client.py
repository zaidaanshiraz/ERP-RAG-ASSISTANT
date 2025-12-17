"""
Ollama API client for local LLM inference.

Calls the local Ollama instance running on localhost:11434.
Uses Qwen 2.5 3B model for fast, efficient generation.
"""

import requests
from typing import Optional
from . import parameters


SYSTEM_PROMPT = """You are a helpful and knowledgeable ERP consultant assistant. Your role is to provide clear, accurate, and comprehensive answers to questions about Enterprise Resource Planning systems, business processes, and implementation strategies.

Guidelines:
- Answer questions in a conversational, friendly tone
- Provide detailed explanations with practical examples
- Structure complex answers with clear sections and bullet points
- Always cite your sources when referencing specific information
- Include document names and relevance in your citations
- Be honest about limitations if information is incomplete
- Focus on practical, actionable guidance
- Use plain language while maintaining technical accuracy
- Keep responses concise but thorough

Citation format:
- End answers with "Sources:" followed by document names
- Include document names naturally in explanations: "According to [Document Name]..."
- Provide context about what information came from which source

Your goal is to be helpful, accurate, and transparent about where information comes from."""


class OllamaClient:
    """Client for Ollama local LLM API."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:3b-instruct-q4_K_M",
        temperature: float = None,
        max_tokens: int = None
    ):
        """
        Initialize Ollama client.
        
        Args:
            base_url: Ollama API base URL
            model: Model name to use
            temperature: Generation temperature (uses parameters.TEMPERATURE if not set)
            max_tokens: Maximum tokens to generate (uses parameters.MAX_TOKENS if not set)
        """
        self.base_url = base_url
        self.model = model
        self.temperature = temperature if temperature is not None else parameters.TEMPERATURE
        self.max_tokens = max_tokens if max_tokens is not None else parameters.MAX_TOKENS
        self._verify_connection()
    
    def _verify_connection(self) -> None:
        """Verify Ollama is running and model is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]
            
            # Check if model exists (handle both "mistral" and "mistral:latest")
            model_base = self.model.split(":")[0]  # Get base name (e.g., "mistral" from "mistral:latest")
            available_bases = [name.split(":")[0] for name in model_names]
            
            if self.model not in model_names and model_base not in available_bases:
                raise RuntimeError(
                    f"Model '{self.model}' not found in Ollama.\n"
                    f"Available models: {', '.join(model_names) if model_names else 'None'}\n"
                    f"Pull it with: ollama pull {self.model}"
                )
            
            # Use exact model name if available, otherwise use base name with :latest
            if self.model in model_names:
                model_to_use = self.model
            else:
                # Find the exact variant (e.g., mistral:latest)
                matching = [name for name in model_names if name.startswith(model_base)]
                model_to_use = matching[0] if matching else self.model
                self.model = model_to_use  # Update to use exact name
            
            print(f"[Ollama] Connected. Using model: {model_to_use}")
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.base_url}\n"
                f"Start it with: ollama serve"
            ) from e
    
    def generate_answer(self, prompt: str) -> str:
        """
        Generate answer using Ollama Chat API with system prompt.
        
        Args:
            prompt: Input prompt for generation (should include context and question)
        
        Returns:
            Generated text response
        
        Raises:
            RuntimeError: If API call fails
        """
        max_retries = 2
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = requests.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False,
                        "options": {
                            "temperature": self.temperature,
                            "top_p": 0.9,
                            "top_k": parameters.TOP_K_LLM,
                            "repeat_penalty": parameters.REPEAT_PENALTY,
                            "num_predict": self.max_tokens,
                        }
                    },
                    timeout=parameters.REQUEST_TIMEOUT
                )
                response.raise_for_status()
                return response.json()["message"]["content"].strip()
            
            except requests.exceptions.Timeout:
                raise RuntimeError(
                    f"Ollama request timed out after {parameters.REQUEST_TIMEOUT} seconds.\n"
                    f"Model '{self.model}' may be overloaded or running on slow hardware.\n"
                    f"Try: ollama pull {self.model}"
                ) from None
            
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 500:
                    retry_count += 1
                    if retry_count < max_retries:
                        import time
                        print(f"[Ollama] Server error (500), retrying... ({retry_count}/{max_retries})")
                        time.sleep(2)  # Wait 2 seconds before retry
                        continue
                    
                    raise RuntimeError(
                        f"Ollama server error (500) - Model crashed after retries.\n"
                        f"Solutions:\n"
                        f"1. The model ran out of memory. Try reducing MAX_TOKENS or TOP_K_RETRIEVAL in parameters.py\n"
                        f"2. Restart Ollama: ollama serve\n"
                        f"3. Ensure model is pulled: ollama pull {self.model}\n"
                        f"4. Check available system memory (need at least 4GB free)"
                    ) from e
                else:
                    raise RuntimeError(f"Ollama API error ({e.response.status_code}): {e}") from e
            
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"Ollama API connection error: {e}") from e
            
            except KeyError:
                raise RuntimeError("Unexpected response format from Ollama") from None
