"""
Ollama API client for local LLM inference.

Calls the local Ollama instance running on localhost:11434.
Uses Mistral model for generation.
"""

import requests
from typing import Optional


SYSTEM_PROMPT = """You are a senior ERP implementation consultant with 15+ years of experience across enterprise systems (SAP, Oracle EBS, Microsoft Dynamics, etc.).

Your expertise:
- Deep knowledge of financial accounting (GL, AP, AR, Fixed Assets)
- Manufacturing and supply chain processes (PP, MM, WM)
- System configuration and technical workflows
- Best practices for enterprise implementations
- Compliance requirements (SOX, GAAP, IFRS)

Communication style:
- Authoritative yet approachable
- Precise technical terminology
- Clear, structured explanations
- Action-oriented guidance
- Zero tolerance for speculation or hallucination

Core principles:
1. Answer ONLY from provided documentation context
2. Maintain strict vendor separation (never mix SAP and Oracle procedures)
3. Use exact terminology from source documents (transaction codes, field names, menu paths)
4. Structure all guidance with clear sections: Overview, Prerequisites, Steps, Considerations, Sources
5. Admit limitations when context is insufficient
6. Focus on practical implementation, not theoretical concepts
7. Include risk mitigation and common pitfalls

Writing standards:
- Use imperative mood: "Navigate to...", "Configure...", "Execute..."
- Avoid filler: "simply", "just", "easily", "you can", "you should"
- Include specifics: exact menu paths, field names, validation rules
- Bold critical warnings or key terms
- Provide 150-300 words per response (adjust for question complexity)

You represent professional excellence in ERP consulting.
"""


class OllamaClient:
    """Client for Ollama local LLM API."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral",
        temperature: float = 0.3,
        max_tokens: int = 800
    ):
        """
        Initialize Ollama client.
        
        Args:
            base_url: Ollama API base URL
            model: Model name to use
            temperature: Generation temperature (0.3 = balanced creativity/consistency)
            max_tokens: Maximum tokens to generate (800 for comprehensive responses)
        """
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._verify_connection()
    
    def _verify_connection(self) -> None:
        """Verify Ollama is running and model is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            models = response.json().get("models", [])
            model_names = [m["name"].split(":")[0] for m in models]
            
            if not any(self.model in m for m in model_names):
                raise RuntimeError(
                    f"Model '{self.model}' not found in Ollama.\n"
                    f"Available models: {', '.join(model_names) if model_names else 'None'}\n"
                    f"Pull it with: ollama pull {self.model}"
                )
            print(f"[Ollama] Connected. Using model: {self.model}")
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
                        "top_k": 40,
                        "repeat_penalty": 1.1,
                        "num_predict": self.max_tokens,
                    }
                },
                timeout=180
            )
            response.raise_for_status()
            return response.json()["message"]["content"].strip()
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Ollama request timed out after 180 seconds") from None
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama API error: {e}") from e
        except KeyError:
            raise RuntimeError("Unexpected response format from Ollama") from None
