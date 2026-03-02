"""LLM integration via LiteLLM for BYOK CLI operations."""

import json
import logging
import os

import litellm

from mcptube.config import settings

logger = logging.getLogger(__name__)

# Suppress LiteLLM's verbose logging
litellm.suppress_debug_info = True


class LLMError(Exception):
    """Raised when an LLM operation fails."""


class LLMClient:
    """Thin wrapper over LiteLLM for CLI-mode LLM operations.

    Auto-detects available API keys and uses the configured
    default model. Falls back gracefully if no key is available.
    """

    _KEY_TO_MODEL = {
        "ANTHROPIC_API_KEY": "anthropic/claude-sonnet-4-20250514",
        "OPENAI_API_KEY": "gpt-4o",
        "GOOGLE_API_KEY": "gemini/gemini-2.0-flash",
    }

    def __init__(self, model: str | None = None) -> None:
        """Initialize LLM client.

        Args:
            model: LiteLLM model string. If None, auto-detects from
                   available API keys or falls back to settings.default_model.
        """
        self._model = model or self._detect_model()

    @property
    def model(self) -> str:
        return self._model

    @property
    def available(self) -> bool:
        """Check if any LLM provider is configured."""
        return any(os.environ.get(key) for key in self._KEY_TO_MODEL)

    def classify(self, title: str, description: str, channel: str) -> list[str]:
        """Classify a video into tags based on metadata.

        Args:
            title: Video title.
            description: Video description.
            channel: Channel name.

        Returns:
            List of classification tags.

        Raises:
            LLMError: If classification fails.
        """
        prompt = (
            "You are a video classification system. Given the following YouTube video metadata, "
            "return a JSON array of relevant topic tags (3-8 tags). Tags should be concise, "
            "specific, and useful for filtering a video library.\n\n"
            f"Title: {title}\n"
            f"Channel: {channel}\n"
            f"Description: {description[:500]}\n\n"
            "Return ONLY a JSON array of strings, e.g. [\"AI\", \"LLM\", \"Tutorial\"]. "
            "No explanation, no markdown."
        )
        response = self._complete(prompt)
        return self._parse_tags(response)
    
    def answer_question(self, question: str, transcripts: list[dict]) -> str:
        """Answer a question based on video transcript(s).

        Args:
            question: User's question.
            transcripts: List of dicts with keys: video_id, title, channel, transcript_text.

        Returns:
            Answer string.

        Raises:
            LLMError: If answering fails.
        """
        video_blocks = "\n\n".join(
            f"=== VIDEO: {t['title']} ({t['video_id']}) by {t['channel']} ===\n{t['transcript_text']}"
            for t in transcripts
        )

        prompt = (
            "You are a video analyst. Answer the following question based ONLY on "
            "the provided video transcript(s). Cite timestamps [MM:SS] when referencing "
            "specific moments. If the answer cannot be found in the transcripts, say so.\n\n"
            f"TRANSCRIPTS:\n{video_blocks}\n\n"
            f"QUESTION: {question}\n\n"
            "Provide a clear, well-structured answer."
        )
        return self._complete(prompt)


    def _complete(self, prompt: str, max_tokens: int = 4096) -> str:
        """Send a completion request to the configured LLM."""
        if not self.available:
            raise LLMError(
                "No LLM API key found. Set one of: "
                + ", ".join(self._KEY_TO_MODEL.keys())
            )
        try:
            response = litellm.completion(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise LLMError(f"LLM request failed ({self._model}): {e}") from e

    def _detect_model(self) -> str:
        """Auto-detect the best available model from environment keys.
        
        Priority order:
        1. Model passed to constructor
        2. MCPTUBE_DEFAULT_MODEL environment variable
        3. API key detection (ANTHROPIC, OPENAI, GOOGLE)
        4. Default fallback to gpt-4o
        
        If OPENAI_BASE_URL is set, prepends 'openai/' prefix to model names
        to route through the OpenAI-compatible endpoint.
        """
        # Check if using OpenAI-compatible endpoint
        openai_base_url = os.environ.get("OPENAI_BASE_URL")
        
        # Check for explicit MCPTUBE_DEFAULT_MODEL env var first
        default_model_env = os.environ.get("MCPTUBE_DEFAULT_MODEL")
        if default_model_env:
            # Prepend 'openai/' prefix if using OpenAI-compatible endpoint
            if openai_base_url and not default_model_env.startswith("openai/"):
                model = f"openai/{default_model_env}"
            else:
                model = default_model_env
            logger.info("Using model from MCPTUBE_DEFAULT_MODEL: %s", model)
            return model
        
        # Then check for API keys
        for key, model in self._KEY_TO_MODEL.items():
            if os.environ.get(key):
                # Prepend 'openai/' prefix if using OpenAI-compatible endpoint
                if openai_base_url and not model.startswith("openai/"):
                    model = f"openai/{model}"
                logger.info("Auto-detected LLM provider: %s → %s", key, model)
                return model
        
        # Finally fallback to settings.default_model
        fallback = settings.default_model
        if openai_base_url and not fallback.startswith("openai/"):
            fallback = f"openai/{fallback}"
        return fallback

    @staticmethod
    def _parse_tags(response: str) -> list[str]:
        """Parse a JSON array of tags from LLM response."""
        # Strip markdown fences if present
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            tags = json.loads(text)
            if isinstance(tags, list) and all(isinstance(t, str) for t in tags):
                return tags
        except json.JSONDecodeError:
            pass
        raise LLMError(f"Failed to parse tags from LLM response: {response[:100]}")
