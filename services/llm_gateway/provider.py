import json
import logging
import random
import re
import time as _time
from collections.abc import AsyncGenerator
from typing import Any

import requests
from prometheus_client import Counter, Histogram

from services.llm_gateway.config import settings
from services.llm_gateway.prompt_loader import get_prompt_parts
from services.llm_gateway.token_budget import fit_llm_input, trim_preserve_edges, count_tokens

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Marker prefix on invoke_llm()'s synthesized message when every Groq
# candidate failed (rate limit, outage, etc.) and no real completion came
# back. Callers that treat invoke_llm's return value as real model output
# (e.g. a vision description fed into a downstream classifier) must check
# for this prefix first -- otherwise an infra failure gets silently
# laundered through as if the model had actually analyzed the input.
LLM_CALL_FAILED_PREFIX = "I couldn't generate a response"

# Domain metrics: how many LLM calls, of what outcome, and how long they
# take, broken down by provider/model/pipeline-step ("role", e.g.
# "drafter", "judge", "rewriter"). Scraped via the futbot_common
# setup_metrics() /metrics endpoint already registered on this service's
# FastAPI app -- these share the same default Prometheus registry.
LLM_CALLS_TOTAL = Counter(
    "futbot_llm_calls_total",
    "Total LLM calls made, by provider/model/step/outcome.",
    ["provider", "model", "step", "status"],
)
LLM_CALL_DURATION_SECONDS = Histogram(
    "futbot_llm_call_duration_seconds",
    "LLM call latency in seconds, by provider/model/step.",
    ["provider", "model", "step"],
    buckets=(0.25, 0.5, 1, 2, 5, 10, 20, 40, 80),
)

GROQ_MODEL_MAP: dict[str, str] = {
    "orchestrator": settings.groq_model_orchestrator,
    "classifier": settings.groq_model_orchestrator,
    "compressor": settings.groq_model_120b,
    "rewriter": settings.groq_model_32b,
    "tool_planner": settings.groq_model_main,
    "vision": settings.groq_model_main,
    "drafter": settings.groq_model_120b,
    "simple_responder": settings.groq_model_32b,
    "judge": settings.groq_model_main,
}

GROQ_THINKING_ROLES = {"judge"}

# Every model in play across all roles, plus whatever extra models config
# adds -- this is the full pool a role can hop to when its own primary
# model's rate-limit bucket is exhausted. Order is deduped but otherwise
# arbitrary; _groq_model_candidates() rotates the starting point per role so
# concurrent roles don't all pile onto the same fallback first.
GROQ_ALL_MODELS: list[str] = list(
    dict.fromkeys(
        [
            *GROQ_MODEL_MAP.values(),
            *settings.groq_model_extra_pool,
            settings.groq_model_vision_fallback,
        ]
    )
)

# Models on this account that actually accept image content. Verified live on
# 2026-09-13: every non-qwen model here (gpt-oss family, allam-2-7b,
# groq/compound*) hard-rejects multimodal input with 400 "content must be a
# string" regardless of rate-limit state, so they can never stand in for a
# vision call no matter what the generic 429-fallback pool contains.
GROQ_VISION_MODELS: set[str] = {
    settings.groq_model_main,
    settings.groq_model_vision_fallback,
}


def _groq_model_candidates(role: str) -> list[str]:
    """Primary model for `role` first, then every other known model as a
    429 fallback -- ordered by a role-dependent rotation so different roles
    don't all reach for the same fallback model at once and just shift the
    bottleneck rather than spreading it."""
    primary = GROQ_MODEL_MAP.get(role, settings.groq_model_main)
    others = [m for m in GROQ_ALL_MODELS if m != primary]
    if others:
        offset = hash(role) % len(others)
        others = others[offset:] + others[:offset]
    return [primary, *others]

MODEL_ORCHESTRATOR = settings.model_orchestrator
MODEL_GENERATOR = settings.model_generator
MODEL_DECISION = settings.model_decision


def _parse_groq_duration(value: str | None) -> float | None:
    """Parse Groq's rate-limit reset headers, e.g. '4.372s' or '1m26.4s'."""
    if not value:
        return None
    match = re.match(r"^(?:(\d+)m)?(\d+(?:\.\d+)?)s$", value.strip())
    if not match:
        return None
    minutes = float(match.group(1)) if match.group(1) else 0.0
    seconds = float(match.group(2))
    return minutes * 60 + seconds


def _groq_retry_wait(resp: requests.Response, attempt: int, backoff_base: float) -> float:
    """
    Figure out how long to actually wait after a Groq 429.

    Groq's 429s are usually a per-minute token-bucket limit, not a short
    burst limit -- `Retry-After` is often absent, but `x-ratelimit-reset-tokens`
    / `x-ratelimit-reset-requests` tell you precisely when the bucket clears
    (e.g. "4.372s", "1m26.4s"). Prefer those over a blind exponential guess,
    which is far too short to clear a minute-long token bucket.
    """
    retry_after = resp.headers.get("retry-after")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass

    reset_candidates = [
        _parse_groq_duration(resp.headers.get("x-ratelimit-reset-tokens")),
        _parse_groq_duration(resp.headers.get("x-ratelimit-reset-requests")),
    ]
    reset_candidates = [c for c in reset_candidates if c is not None]
    if reset_candidates:
        # Whichever bucket (tokens or requests) is exhausted is the one
        # gating us; its reset governs how long we must wait.
        return max(reset_candidates)

    return backoff_base**attempt


def _strip_think_tags(text: str) -> str:
    stripped = re.sub(
        r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE
    )
    return stripped.strip()


def _shrink_groq_user_content(content: str | list[dict[str, Any]], target_tokens: int) -> str | list[dict[str, Any]]:
    if isinstance(content, list):
        text_part = next(
            (
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ),
            "",
        )
        shrunk = trim_preserve_edges(text_part, target_tokens)
        return [
            {**part, "text": shrunk}
            if isinstance(part, dict) and part.get("type") == "text"
            else part
            for part in content
        ]
    return trim_preserve_edges(str(content), target_tokens)


def _call_groq(
    role: str,
    system_prompt: str,
    user_content: str,
    image: bytes | None = None,
) -> tuple[str, str, int | None, int]:
    if not settings.groq_api_key:
        raise ValueError(
            "GROQ_API_KEY is not set. "
            "Add it to your .env file or environment when using LLM_PROVIDER=groq."
        )

    candidates = _groq_model_candidates(role)
    if image is not None:
        # Most of the fallback pool hard-rejects image content outright
        # (verified live -- see GROQ_VISION_MODELS), so hopping to an
        # arbitrary text-only model would just trade a 429 for a guaranteed
        # 400. Restrict to the known vision-capable models instead of
        # collapsing to a single one, so a rate-limited primary still has a
        # real (separately-quota'd) fallback to hop to.
        candidates = [c for c in candidates if c in GROQ_VISION_MODELS] or [candidates[0]]
    model = candidates[0]
    thinking = role in GROQ_THINKING_ROLES

    fitted_user = fit_llm_input(
        system_prompt=system_prompt,
        user_prompt=user_content,
        max_input_tokens=settings.llm_max_input_tokens,
    )

    if image is not None:
        import base64

        img_b64 = base64.b64encode(image).decode("utf-8")
        user_msg_content = [
            {"type": "text", "text": fitted_user},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
        ]
    else:
        user_msg_content = fitted_user

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg_content},
    ]

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if not thinking:
        model_lower = model.lower()
        if "gpt-oss" in model_lower or "gpt_oss" in model_lower:
            payload["reasoning_effort"] = "low"
        elif "qwen" in model_lower:
            payload["reasoning_effort"] = "none"

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    raw = ""
    clean = ""
    status_code: int | None = None
    t0 = _time.monotonic()
    shrink_attempts = 0
    user_token_budget = max(
        512,
        settings.llm_max_input_tokens - count_tokens(system_prompt) - 128,
    )

    for cycle in range(settings.groq_max_retries):
        cycle_wait: float | None = None

        for candidate_model in candidates:
            payload["model"] = candidate_model
            try:
                resp = requests.post(
                    GROQ_API_URL, json=payload, headers=headers, timeout=120
                )
                status_code = resp.status_code

                if resp.status_code == 413:
                    shrink_attempts += 1
                    current_user = payload["messages"][1]["content"]
                    target = max(256, user_token_budget // (2**shrink_attempts))
                    payload["messages"][1]["content"] = _shrink_groq_user_content(
                        current_user,
                        target,
                    )
                    logger.warning(
                        "Groq 413 on %s (%s); shrinking user prompt to ~%s tokens (attempt %s).",
                        role,
                        candidate_model,
                        target,
                        shrink_attempts,
                    )
                    if shrink_attempts >= 8:
                        latency_ms = int((_time.monotonic() - t0) * 1000)
                        return (
                            "",
                            (
                                "The model request was too large even after shrinking. "
                                "Try a shorter question or reduce retrieved context."
                            ),
                            status_code,
                            latency_ms,
                        )
                    continue

                if resp.status_code == 429:
                    # Each Groq model has its own independent rate-limit
                    # bucket, so a 429 on this one says nothing about the
                    # next candidate -- hop immediately instead of sleeping.
                    cycle_wait = _groq_retry_wait(resp, cycle, settings.groq_backoff_base)
                    logger.warning(
                        "Groq 429 on %s (%s), cycle %s/%s (reset-tokens=%s, "
                        "reset-requests=%s, retry-after=%s). Trying next model.",
                        role,
                        candidate_model,
                        cycle + 1,
                        settings.groq_max_retries,
                        resp.headers.get("x-ratelimit-reset-tokens"),
                        resp.headers.get("x-ratelimit-reset-requests"),
                        resp.headers.get("retry-after"),
                    )
                    continue

                if resp.status_code in {502, 503, 504}:
                    logger.warning(
                        "Groq %s on %s (%s), cycle %s/%s. Trying next model.",
                        resp.status_code,
                        role,
                        candidate_model,
                        cycle + 1,
                        settings.groq_max_retries,
                    )
                    continue

                if resp.status_code >= 400:
                    # raise_for_status()'s exception text is just "400 Client
                    # Error: Bad Request for url: ..." -- it drops Groq's JSON
                    # error body, which is the only place that says *why*
                    # (decommissioned model, unsupported param, real quota
                    # exhaustion, etc.). Log it before raising so failures are
                    # diagnosable without re-running the request by hand.
                    logger.error(
                        "Groq %s on %s (%s): %s",
                        resp.status_code,
                        role,
                        candidate_model,
                        resp.text[:500],
                    )

                resp.raise_for_status()
                raw = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                clean = _strip_think_tags(raw)
                latency_ms = int((_time.monotonic() - t0) * 1000)
                return raw, clean, status_code, latency_ms

            except requests.RequestException as e:
                logger.error(
                    "Groq API request error on %s (%s): %s", role, candidate_model, e
                )
                continue

        # Every candidate model failed (rate-limited, transient error, or
        # network error) in this cycle -- no fresh bucket left to hop to, so
        # back off for real before the next cycle.
        if cycle == settings.groq_max_retries - 1:
            break
        wait = min(
            (cycle_wait if cycle_wait is not None else settings.groq_backoff_base**cycle)
            + random.uniform(0, 0.5),
            settings.groq_backoff_max_sec,
        )
        logger.warning(
            "All %s Groq candidate models failed for %s; waiting %.2fs before retrying.",
            len(candidates),
            role,
            wait,
        )
        _time.sleep(wait)

    latency_ms = int((_time.monotonic() - t0) * 1000)
    return raw, clean, status_code, latency_ms


def _local_endpoint(model_name: str) -> str:
    model_name_lower = model_name.lower()
    if "0.8b" in model_name_lower:
        return settings.url_08b
    if "2b" in model_name_lower:
        return settings.url_2b
    if "4b" in model_name_lower:
        return settings.url_4b
    return settings.url_2b


def _local_unconfigured_message(model_name: str) -> str:
    return (
        "The local LLM endpoint is not configured for this model. "
        f"Set URL_2B/URL_4B in Settings (or .env) for `{model_name}`, "
        "or switch LLM_PROVIDER to groq with a valid GROQ_API_KEY."
    )


def _call_local(model_name: str, prompt: str) -> tuple[str, str, str, int | None, int]:
    api_url = _local_endpoint(model_name)
    if not api_url:
        message = _local_unconfigured_message(model_name)
        return "", message, message, None, 0

    if "/chat/completions" in api_url or "/v1/chat/completions" in api_url:
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
    else:
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"think": False},
        }

    raw = ""
    clean = ""
    status_code: int | None = None
    t0 = _time.monotonic()

    try:
        resp = requests.post(api_url, json=payload, timeout=120)
        status_code = resp.status_code
        resp.raise_for_status()
        if "/chat/completions" in api_url or "/v1/chat/completions" in api_url:
            raw = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        else:
            raw = resp.json().get("response", "").strip()
        clean = _strip_think_tags(raw)
        latency_ms = int((_time.monotonic() - t0) * 1000)
        return api_url, raw, clean, status_code, latency_ms
    except requests.RequestException as e:
        latency_ms = int((_time.monotonic() - t0) * 1000)
        logger.error("Error calling local LLM API (%s) at %s: %s", model_name, api_url, e)
        message = (
            f"I couldn't reach the local LLM at `{api_url}` "
            f"(HTTP {status_code or 'unknown'}). Check URL_2B/URL_4B and that the model server is running."
        )
        return api_url, message, message, status_code, latency_ms


def invoke_llm(
    prompt: str,
    model_name: str,
    step: str = "unknown",
    run_logger=None,
    iteration: int = 0,
    image: bytes | None = None,
    system_prompt: str | None = None,
) -> str:
    raw = ""
    clean = ""
    api_url = ""
    status_code: int | None = None
    latency_ms = 0

    if settings.llm_provider == "groq":
        api_url = GROQ_API_URL
        groq_model = GROQ_MODEL_MAP.get(step, settings.groq_model_main)
        sys_msg = system_prompt if system_prompt is not None else ""
        try:
            raw, clean, status_code, latency_ms = _call_groq(step, sys_msg, prompt, image=image)
        except ValueError as exc:
            clean = str(exc)
            raw = clean
            status_code = None
            latency_ms = 0
        log_model_name = groq_model
        if not clean.strip():
            clean = (
                f"{LLM_CALL_FAILED_PREFIX} — the Groq API returned an error "
                f"(HTTP {status_code or 'unknown'}). Verify GROQ_API_KEY and that "
                f"model `{groq_model}` is available on your Groq account."
            )
    else:
        local_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        api_url, raw, clean, status_code, latency_ms = _call_local(model_name, local_prompt)
        log_model_name = model_name

    call_status = "ok" if status_code is not None and 200 <= status_code < 300 else "error"
    LLM_CALLS_TOTAL.labels(
        provider=settings.llm_provider, model=log_model_name, step=step, status=call_status
    ).inc()
    LLM_CALL_DURATION_SECONDS.labels(
        provider=settings.llm_provider, model=log_model_name, step=step
    ).observe(latency_ms / 1000)

    if run_logger is not None:
        try:
            run_logger.log_llm_call(
                step=step,
                model_name=log_model_name,
                prompt=prompt,
                raw_response=raw,
                response=clean,
                api_url=api_url,
                status_code=status_code,
                latency_ms=latency_ms,
                iteration=iteration,
            )
        except Exception as log_err:
            logger.warning("Failed to log LLM call: %s", log_err)

    return clean


def invoke_llm_stream(
    prompt: str,
    model_name: str,
    step: str = "drafter",
    system_prompt: str | None = None,
) -> list[str]:
    """Non-streaming fallback tokens for local provider; Groq stream deferred to Phase 6 wiring."""
    text = invoke_llm(
        prompt,
        model_name=model_name,
        step=step,
        system_prompt=system_prompt,
    )
    return [text] if text else []


def parse_snapshot_json(raw: str, existing_snapshot: str) -> str:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.MULTILINE)
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, separators=(",", ":"))
    except json.JSONDecodeError:
        logger.warning("Snapshot compressor returned invalid JSON; keeping existing snapshot.")
        return existing_snapshot or "{}"
