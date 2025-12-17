"""Groq API client for cloud-based LLM inference.

Keeps the same interface as other LLM clients:
- generate_answer(prompt: str) -> str
- format_with_sources(answer: str, sources: List[Dict]) -> str

Cloud model default: llama-3.1-8b-instant
Env var: GROQ_API_KEY
"""

import os
from typing import List, Dict

from . import parameters


SYSTEM_PROMPT = """You are a senior ERP implementation consultant.

PRIORITY: Provide HIGH-QUALITY answers grounded in the provided context.

What makes a good answer here:
- Specific: avoid generic filler. Prefer concrete ERP concepts (BOM, routing, work orders, MRP, capacity, QC, costing).
- Grounded: use the retrieved context as the source of truth; do not invent vendor-specific facts.
- Actionable: give clear steps/checklists and decision points.
- Cited: always include a final section titled "Sources:" listing the documents used.
- Complete: finish the thought; do not stop mid-sentence.

Style:
- Use short headings and bullet points.
- For "How do I implement…" questions: give an ordered implementation plan (phases) and key configuration/data prerequisites.

If the context is thin or only partially relevant:
- Say what is missing, ask up to 2 clarifying questions, and still provide the best general ERP guidance you can WITHOUT claiming it comes from the documents.
"""


class GroqClient:
    """Client for Groq Cloud LLM API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "llama-3.1-8b-instant",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        self.api_key = (api_key or parameters.GROQ_API_KEY or os.getenv("GROQ_API_KEY") or "").strip()
        if not self.api_key:
            raise RuntimeError(
                "Groq API key not found.\n"
                "Set it in .env as GROQ_API_KEY=..."
            )

        self.model = model
        self.temperature = temperature if temperature is not None else 0.2
        self.max_tokens = max_tokens if max_tokens is not None else parameters.MAX_TOKENS

        try:
            from groq import Groq  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "groq package not installed.\n"
                "Install it with: pip install groq"
            ) from e

        self._client = Groq(api_key=self.api_key)

    def generate_answer(self, prompt: str) -> str:
        def _looks_truncated(text: str) -> bool:
            if not text:
                return True
            if len(text) < 220:
                return True
            return text[-1] not in ".!?)]\"'”’"

        def _generate_once(p: str, max_out: int) -> tuple[str, str]:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": p},
                ],
                temperature=self.temperature,
                max_tokens=max_out,
            )
            choice = resp.choices[0]
            text = (choice.message.content or "").strip()
            finish = (choice.finish_reason or "").strip()
            return text, finish

        try:
            cloud_max_tokens = max(self.max_tokens * 4, 1200)
            answer, finish_reason = _generate_once(prompt, cloud_max_tokens)

            # If it looks cut off (or explicitly length-capped), do one continuation call.
            if finish_reason == "length" or _looks_truncated(answer):
                tail = (answer or "")[-800:]
                continue_prompt = (
                    prompt
                    + "\n\n---\n"
                    + "The assistant's draft answer (may be cut off):\n"
                    + tail
                    + "\n\n---\n"
                    + "Continue the answer from exactly where it stopped. "
                    + "Do NOT repeat earlier content. Finish all sentences. "
                    + "If you haven't yet included a final section titled 'Sources:', include it at the end. "
                    + "Return only the continuation text."
                )

                try:
                    cont, _ = _generate_once(continue_prompt, max(400, min(900, cloud_max_tokens // 2)))
                    if cont:
                        if tail and cont.startswith(tail):
                            cont = cont[len(tail):].lstrip()
                        answer = (answer.rstrip() + "\n" + cont.strip()).strip()
                except Exception:
                    pass

            return answer.strip()

        except Exception as e:
            message = str(e)
            lower = message.lower()

            if "invalid_api_key" in lower or "invalid api key" in lower or "unauthorized" in lower:
                raise RuntimeError(f"Invalid Groq API key. Error: {e}") from e

            if "rate" in lower or "limit" in lower or "quota" in lower:
                raise RuntimeError(f"Groq rate limit/quota exceeded. Error: {e}") from e

            raise RuntimeError(f"Groq API error: {e}") from e

    def format_with_sources(self, answer: str, sources: List[Dict]) -> str:
        if "Sources:" in answer or "sources:" in answer:
            return answer

        if sources:
            lines = ["\n\nSources:"]
            for source in sources:
                doc_name = source.get("document_name", "Unknown")
                lines.append(f"- {doc_name}")
            return (answer.rstrip() + "\n" + "\n".join(lines)).strip()

        return answer
