import asyncio
import json
from functools import wraps
from ollama import chat
import logging
logger = logging.getLogger(__name__)


def parse_json_content(content: str) -> dict:
    """Accept strict JSON plus fenced JSON occasionally returned by Gemma."""
    cleaned = content.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned[3:-3].strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
    return json.loads(cleaned)

def retry_json(attempts=3):
    def decorator(function):
        @wraps(function)
        async def wrapped(*args, **kwargs):
            error = None
            for attempt in range(attempts):
                try: return await function(*args, **kwargs)
                except (json.JSONDecodeError, ValueError) as exc:
                    error = exc
                    if attempt + 1 < attempts: await asyncio.sleep(0.1 * 2 ** attempt)
            raise error
        return wrapped
    return decorator

async def complete_json(client, system: str, user: str, output_model=None):
    if client is None:
        logger.warning("complete_json: client/model is None, skipping LLM call")
        return None

    response_format = output_model.model_json_schema() if output_model is not None else "json"

    last_exc = None
    for attempt in range(3):
        try:
            response = await asyncio.to_thread(
                chat,
                model=client,
                messages=[
                    {"role": "system", "content": f"{system}\nReturn valid JSON only."},
                    {"role": "user", "content": user},
                ],
                format=response_format,
            )
            # defensively handle both dict-style and attribute-style responses
            content = (
                response["message"]["content"]
                if isinstance(response, dict)
                else response.message.content
            )
            logger.debug("complete_json raw content (attempt %d): %r", attempt, content)
            return parse_json_content(content)

        except Exception as e:
            last_exc = e
            logger.warning(
                "complete_json attempt %d failed: %s: %s",
                attempt, type(e).__name__, e
            )
            if attempt == 2:
                raise
            await asyncio.sleep(0.2 * 2 ** attempt)

    raise last_exc