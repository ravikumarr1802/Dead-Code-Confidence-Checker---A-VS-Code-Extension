"""
Explainable AI helpers for the Dead Code Confidence Checker.

- Loads API keys from .env or config.json
- Calls DeepSeek for code reasoning
- Calls OpenAI for structured XAI output
- Falls back cleanly when keys or network access are unavailable
"""
import hashlib
import json
import os
import time
from typing import Any, Dict

import requests

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass


def load_api_settings() -> Dict[str, str]:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    config: Dict[str, Any] = {}

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                config = json.load(handle)
        except Exception:
            config = {}

    return {
        "openai_provider": (config.get("OPENAI_PROVIDER") or os.getenv("OPENAI_PROVIDER", "openai")).lower(),
        "enable_deepseek": (config.get("ENABLE_DEEPSEEK") or os.getenv("ENABLE_DEEPSEEK", "")).lower(),
        "openai_key": config.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", ""),
        "groq_key": config.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY", ""),
        "deepseek_key": config.get("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY", ""),
        "openai_model": config.get("OPENAI_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "openai_base_url": config.get("OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "deepseek_model": config.get("DEEPSEEK_MODEL") or os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    }


SETTINGS = load_api_settings()
CACHE: Dict[str, Any] = {}
LAST_OPENAI_CALL_AT = 0.0


def _read_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _read_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def hash_input(*args: object) -> str:
    hasher = hashlib.sha256()
    for arg in args:
        hasher.update(str(arg).encode("utf-8"))
    return hasher.hexdigest()


def _wait_for_openai_slot() -> None:
    global LAST_OPENAI_CALL_AT

    min_interval = max(0.0, _read_float_env("OPENAI_MIN_INTERVAL_SECONDS", 1.0))
    now = time.time()
    elapsed = now - LAST_OPENAI_CALL_AT
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    LAST_OPENAI_CALL_AT = time.time()


def _post_with_retries(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int) -> requests.Response:
    max_retries = max(0, _read_int_env("OPENAI_MAX_RETRIES", 3))
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            _wait_for_openai_slot()
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            if response.status_code == 429 and attempt < max_retries:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = max(float(retry_after), 1.0) if retry_after else float(2 ** attempt)
                except ValueError:
                    delay = float(2 ** attempt)
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response
        except requests.HTTPError as exc:
            last_error = exc
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 429 and attempt < max_retries:
                retry_after = exc.response.headers.get("Retry-After") if exc.response is not None else None
                try:
                    delay = max(float(retry_after), 1.0) if retry_after else float(2 ** attempt)
                except ValueError:
                    delay = float(2 ** attempt)
                time.sleep(delay)
                continue
            raise
        except requests.RequestException as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(float(2 ** attempt))
                continue
            raise

    if last_error is not None:
        raise last_error
    raise RuntimeError("OpenAI request failed without a captured exception.")


def _format_openai_error(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status_code = exc.response.status_code
        try:
            payload = exc.response.json()
        except ValueError:
            payload = {}
        message = payload.get("error", {}).get("message") or str(exc)
        failed_generation = payload.get("error", {}).get("failed_generation")
        if failed_generation:
            message = f"{message} Failed generation: {failed_generation}"
        if status_code == 429:
            return f"Rate limited or quota exceeded (HTTP 429): {message}"
        return f"HTTP {status_code}: {message}"
    return str(exc)


def _is_groq_json_validation_error(exc: Exception) -> bool:
    if not isinstance(exc, requests.HTTPError) or exc.response is None:
        return False
    try:
        payload = exc.response.json()
    except ValueError:
        return False
    if exc.response.status_code != 400:
        return False
    message = (payload.get("error", {}).get("message") or "").lower()
    return "failed to validate json" in message or "generated json" in message


def _get_openai_compatible_provider() -> Dict[str, str]:
    provider = SETTINGS.get("openai_provider", "openai").lower()
    base_url = (SETTINGS.get("openai_base_url") or "https://api.openai.com/v1").rstrip("/")
    model = SETTINGS.get("openai_model", "gpt-4o-mini")

    if provider == "groq":
        return {
            "provider": "Groq",
            "api_key": SETTINGS.get("groq_key", ""),
            "base_url": base_url if base_url != "https://api.openai.com/v1" else "https://api.groq.com/openai/v1",
            "model": model if model != "gpt-4o-mini" else "openai/gpt-oss-20b",
        }

    return {
        "provider": "OpenAI",
        "api_key": SETTINGS.get("openai_key", ""),
        "base_url": base_url,
        "model": model,
    }


def should_use_deepseek() -> bool:
    setting = SETTINGS.get("enable_deepseek", "")
    if setting:
        return setting in {"1", "true", "yes", "on"}
    return SETTINGS.get("openai_provider", "openai").lower() != "groq"


def _format_deepseek_error(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status_code = exc.response.status_code
        try:
            payload = exc.response.json()
        except ValueError:
            payload = {}
        message = (
            payload.get("error", {}).get("message")
            or payload.get("message")
            or str(exc)
        )
        if status_code == 402:
            return f"Billing required or credits exhausted (HTTP 402): {message}"
        if status_code == 429:
            return f"Rate limited (HTTP 429): {message}"
        return f"HTTP {status_code}: {message}"
    return str(exc)


def deepseek_analysis(code: str, features: Dict[str, Any], timeout: int = 20) -> Dict[str, Any]:
    """
    Ask DeepSeek for a code-usage assessment.
    Returns: {is_unused, reasoning, key_observations}
    """
    if not SETTINGS["deepseek_key"]:
        return {
            "is_unused": None,
            "reasoning": "DeepSeek API key not configured.",
            "key_observations": [],
        }

    cache_key = hash_input("deepseek", code, json.dumps(features, sort_keys=True))
    if cache_key in CACHE:
        return CACHE[cache_key]

    prompt = (
        "You are reviewing a possibly unused Python code entity.\n"
        "Use the code snippet and static features below.\n"
        "Return strict JSON with keys: is_unused, reasoning, key_observations.\n\n"
        f"Code:\n{code}\n\n"
        f"Features:\n{json.dumps(features, ensure_ascii=False)}"
    )

    payload = {
        "model": SETTINGS["deepseek_model"],
        "messages": [
            {"role": "system", "content": "You are a precise code-analysis assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 500,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {SETTINGS['deepseek_key']}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        result = {
            "is_unused": parsed.get("is_unused"),
            "reasoning": parsed.get("reasoning", ""),
            "key_observations": parsed.get("key_observations", []),
        }
        CACHE[cache_key] = result
        return result
    except Exception as exc:
        return {
            "is_unused": None,
            "reasoning": f"DeepSeek unavailable: {_format_deepseek_error(exc)}",
            "key_observations": [],
        }


def generate_xai_explanation(
    entity: Dict[str, Any],
    features: Dict[str, Any],
    lr_output: Dict[str, Any],
    deepseek_output: Dict[str, Any],
    timeout: int = 25,
) -> Dict[str, Any]:
    """
    Ask OpenAI for a structured explanation.
    Returns a strict JSON-compatible dict.
    """
    provider_settings = _get_openai_compatible_provider()
    provider_name = provider_settings["provider"]

    if not provider_settings["api_key"]:
        return {
            "summary": f"{provider_name} API key not configured.",
            "risk_level": "Medium",
            "confidence": lr_output.get("confidence", 0.5),
            "confidence_explanation": "ML-only confidence.",
            "factors": [],
            "llm_reasoning": "",
            "recommendation": "Review manually.",
            "action": "review",
        }

    cache_key = hash_input(
        "openai",
        entity.get("name"),
        json.dumps(features, sort_keys=True),
        json.dumps(lr_output, sort_keys=True),
        json.dumps(deepseek_output, sort_keys=True),
    )
    if cache_key in CACHE:
        return CACHE[cache_key]

    prompt = f"""
You are an expert code explainer.

Entity:
{json.dumps(entity, ensure_ascii=False)}

Static features:
{json.dumps(features, ensure_ascii=False)}

ML output:
{json.dumps(lr_output, ensure_ascii=False)}

DeepSeek reasoning:
{json.dumps(deepseek_output, ensure_ascii=False)}

Return only valid JSON with this exact shape:
{{
  "summary": "string",
  "risk_level": "Low | Medium | High",
  "confidence": 0.0,
  "confidence_explanation": "string",
  "factors": [{{"feature": "string", "impact": "high|medium|low", "description": "string"}}],
  "llm_reasoning": "string",
  "recommendation": "string",
  "action": "keep | review | remove"
}}
"""

    def build_payload(use_json_mode: bool) -> Dict[str, Any]:
        system_content = "You are a code analysis XAI assistant. Reply with JSON only."
        user_prompt = prompt
        if provider_name == "Groq" and not use_json_mode:
            system_content = (
                "You are a code analysis XAI assistant. "
                "Return exactly one valid JSON object and no markdown, no backticks, and no extra text."
            )
            user_prompt = prompt + "\nReturn a single compact valid JSON object only."

        payload: Dict[str, Any] = {
            "model": provider_settings["model"],
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 700,
            "temperature": 0.2,
        }
        if use_json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    headers = {
        "Authorization": f"Bearer {provider_settings['api_key']}",
        "Content-Type": "application/json",
    }

    try:
        response = _post_with_retries(
            f"{provider_settings['base_url']}/chat/completions",
            headers=headers,
            payload=build_payload(use_json_mode=True),
            timeout=timeout,
        )
        content = response.json()["choices"][0]["message"]["content"]
        result = json.loads(content)
        CACHE[cache_key] = result
        return result
    except Exception as exc:
        if provider_name == "Groq" and _is_groq_json_validation_error(exc):
            try:
                response = _post_with_retries(
                    f"{provider_settings['base_url']}/chat/completions",
                    headers=headers,
                    payload=build_payload(use_json_mode=False),
                    timeout=timeout,
                )
                content = response.json()["choices"][0]["message"]["content"]
                result = json.loads(content)
                CACHE[cache_key] = result
                return result
            except Exception as retry_exc:
                exc = retry_exc
        fallback_reason = (
            deepseek_output.get("reasoning")
            if isinstance(deepseek_output, dict) and deepseek_output.get("reasoning")
            else f"{provider_name} unavailable: {_format_openai_error(exc)}"
        )
        return {
            "summary": f"{provider_name} unavailable: {_format_openai_error(exc)}",
            "risk_level": "Medium",
            "confidence": lr_output.get("confidence", 0.5),
            "confidence_explanation": "ML-only confidence because LLM providers were unavailable.",
            "factors": [],
            "llm_reasoning": fallback_reason,
            "recommendation": "Review manually using the ML signals, or restore provider billing/quota.",
            "action": "review",
        }
