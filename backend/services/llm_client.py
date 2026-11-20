import json
import logging
import re

from openai import OpenAI, OpenAIError

import config

logger = logging.getLogger(__name__)
client = OpenAI(
    api_key=config.OPENROUTER_API_KEY, base_url=config.OPENROUTER_BASE_URL,
    timeout=15, max_retries=0,
) if config.OPENROUTER_API_KEY else None


def parse_object(raw: str) -> dict:
    decoder = json.JSONDecoder()
    start = re.search(r"\{\s*(?:\"|\})", raw)
    if start is None:
        raise ValueError("No JSON object in the model response")
    data, _ = decoder.raw_decode(raw[start.start():])
    return data


def call_llm_json(system_prompt: str, user_prompt: str) -> dict:
    if client is None:
        return {}
    for model in config.LLM_MODELS:
        if not model or (not model.endswith(":free") and model != "openrouter/free"):
            continue
        try:
            options = {} if model == "openrouter/free" else {"response_format": {"type": "json_object"}}
            response = client.chat.completions.create(
                model=model, temperature=0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                **options,
            )
            return parse_object(response.choices[0].message.content or "")
        except (OpenAIError, ValueError, IndexError, AttributeError) as error:
            logger.info("OpenRouter model %s unavailable (%s)", model, type(error).__name__)
    return {}
