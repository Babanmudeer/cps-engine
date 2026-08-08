import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.config import GeminiConfig
from ..core.few_shot_prompts import FewShotPrompts


logger = logging.getLogger(__name__)


class GeminiAgent:
    """Gemini AI Agent with Digital Mallam Persona."""

    def __init__(self, config: GeminiConfig):
        self.config = config

        if not config.api_key:
            raise ValueError("GEMINI_API_KEY is not configured")

        genai.configure(api_key=config.api_key)

        system_instruction = """
You are Digital Mallam, a wise, respectful and knowledgeable
Hausa historian and teacher.

Your responsibilities:
- Answer questions accurately.
- Respect Hausa culture and traditions.
- Explain historical topics clearly.
- Do not invent facts.
- If information is uncertain, say so.
- Use respectful language.
- Respond in the user's language when possible.

For Hausa responses:
- Use natural Hausa.
- Use greetings such as "Sannu" or "Barka da zuwa"
  when appropriate.
- Keep answers clear and educational.
"""

        self.model = genai.GenerativeModel(
            config.model,
            generation_config={
                "temperature": config.temperature,
                "max_output_tokens": config.max_tokens,
            },
            system_instruction=system_instruction,
        )

        self.metrics = {
            "generations": 0,
            "avg_tokens": 0,
            "errors": 0,
        }

        logger.info(
            "Gemini Agent initialized with model: %s",
            config.model,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=2,
            max=10,
        ),
    )
    async def generate_cypher(
        self,
        question: str,
        intent: Optional[str] = None,
    ) -> str:
        try:
            prompt = (
                FewShotPrompts.CYPHER_GENERATION_PROMPT.format(
                    question=question,
                    intent=intent or "HISTORICAL_FACT",
                )
            )

            loop = asyncio.get_running_loop()

            response = await loop.run_in_executor(
                None,
                self.model.generate_content,
                prompt,
            )

            text = getattr(response, "text", "")
            cypher = self._clean_cypher(text)

            self._update_metrics(len(cypher))

            return cypher

        except Exception as exc:
            self.metrics["errors"] += 1
            logger.error(
                "Gemini Cypher generation failed: %s",
                exc,
            )
            raise

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=5,
        ),
    )
    async def generate_answer(
        self,
        question: str,
        results: List[Dict[str, Any]],
        cypher: str,
        intent: Optional[str] = None,
    ) -> str:
        try:
            if intent in ["CULTURAL", "RELATIONSHIP"]:
                prompt = (
                    FewShotPrompts.CULTURAL_CONTEXT_PROMPT.format(
                        question=question,
                        data=json.dumps(
                            results[:10],
                            indent=2,
                            ensure_ascii=False,
                        ),
                    )
                )
            else:
                prompt = FewShotPrompts.get_answer_prompt(
                    question,
                    results,
                    cypher,
                    True,
                )

            loop = asyncio.get_running_loop()

            response = await loop.run_in_executor(
                None,
                self.model.generate_content,
                prompt,
            )

            text = getattr(response, "text", "")

            self.metrics["generations"] += 1

            return self._clean_answer(text)

        except Exception as exc:
            self.metrics["errors"] += 1
            logger.error(
                "Gemini answer generation failed: %s",
                exc,
            )
            raise

    async def generate_direct_answer(
        self,
        question: str,
    ) -> str:
        try:
            prompt = f"""
You are Digital Mallam, a respectful Hausa historian.

Question:
{question}

Instructions:
- Answer directly.
- Be accurate.
- Do not invent information.
- If you are uncertain, say so.
- Use Hausa when the user asks in Hausa.
- Use English when the user asks in English.

Response:
"""

            loop = asyncio.get_running_loop()

            response = await loop.run_in_executor(
                None,
                self.model.generate_content,
                prompt,
            )

            text = getattr(response, "text", "")

            self.metrics["generations"] += 1

            return self._clean_answer(text)

        except Exception as exc:
            self.metrics["errors"] += 1
            logger.error(
                "Gemini direct answer failed: %s",
                exc,
            )

            return (
                "Na yi hakuri. A halin yanzu ban samu "
                "amsar tambayar ba."
            )

    async def generate_answer_from_vector(
        self,
        question: str,
        vector_results: List[Dict[str, Any]],
        intent: Optional[str] = None,
    ) -> str:
        try:
            context_parts = []

            for result in vector_results[:5]:
                text = result.get("text", "")
                if text:
                    context_parts.append(text)

            context = "\n".join(context_parts)

            prompt = f"""
You are Digital Mallam, a knowledgeable Hausa historian.

Question:
{question}

Historical Context:
{context}

Instructions:
- Answer using the supplied context.
- Do not invent facts.
- Explain clearly.
- Add cultural context when relevant.
- Use Hausa when appropriate.

Response:
"""

            loop = asyncio.get_running_loop()

            response = await loop.run_in_executor(
                None,
                self.model.generate_content,
                prompt,
            )

            text = getattr(response, "text", "")

            self.metrics["generations"] += 1

            return self._clean_answer(text)

        except Exception:
            return await self.generate_direct_answer(question)

    def _clean_cypher(self, text: str) -> str:
        text = re.sub(
            r"```(?:cypher|sql)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = text.replace("```", "")

        lines = text.strip().splitlines()

        cleaned = [
            line
            for line in lines
            if not line.strip().startswith(
                ("//", "--", "/*")
            )
        ]

        return "\n".join(cleaned).strip()

    def _clean_answer(self, text: str) -> str:
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _update_metrics(self, token_count: int):
        generations = self.metrics["generations"]

        self.metrics["generations"] = generations + 1

        self.metrics["avg_tokens"] = (
            (
                self.metrics["avg_tokens"] * generations
                + token_count
            )
            / self.metrics["generations"]
        )

    async def health_check(self) -> bool:
        try:
            loop = asyncio.get_running_loop()

            response = await loop.run_in_executor(
                None,
                self.model.generate_content,
                "Respond with exactly: Sannu",
            )

            text = getattr(response, "text", "")

            return (
                "Sannu" in text
                or "sannu" in text
            )

        except Exception as exc:
            logger.error(
                "Gemini health check failed: %s",
                exc,
            )
            return False

    def get_metrics(self) -> Dict[str, Any]:
        return {
            **self.metrics,
            "model": self.config.model,
            "persona": "Digital Mallam",
      }
