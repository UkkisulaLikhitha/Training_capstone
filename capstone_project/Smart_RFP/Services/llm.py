"""
llm.py
------
Thin wrapper around the Groq chat API.

Key design choice: if no GROQ_API_KEY is set (or a call fails), we fall back to
a deterministic "demo mode" so the WHOLE app still runs and produces sensible
output without any key. Add your key in .env to get real LLM-written drafts.

Unlike a silent fallback, this version remembers the last Groq error and exposes
ping()/groq_status() so the Settings page can tell you *exactly* why a key is
not working (invalid key, decommissioned model, network, quota, etc.).
"""

import config

import time

from langsmith import traceable

from metrics import (
    LLM_REQUESTS,
    LLM_ERRORS,
    LLM_LATENCY,
    LLM_DEMO_MODE,
)

_client = None
_last_error = ""          # human-readable reason the last Groq call failed
_used_demo = False        # True if the most recent chat() used the demo fallback


def _get_client():
    """Construct (once) and return a Groq client, or None if no key/SDK."""
    global _client, _last_error
    if _client is not None:
        return _client
    if not config.GROQ_API_KEY:
        _last_error = "No GROQ_API_KEY found (check your .env file)."
        return None
    try:
        from groq import Groq
        _client = Groq(api_key=config.GROQ_API_KEY)
        return _client
    except Exception as e:
        _last_error = f"Could not initialise Groq client: {e}"
        print(f"[llm] {_last_error}")
        return None


def llm_available() -> bool:
    """True if a key is present and the client object constructs.
    NOTE: this does not guarantee the key/model actually work — use ping()."""
    return _get_client() is not None


def last_error() -> str:
    return _last_error


def used_demo() -> bool:
    return _used_demo


def ping() -> dict:
    """
    Make a tiny real API call to verify the key AND model actually work.
    Returns: {ok: bool, model: str, message: str}
    The message carries the real Groq error text when ok is False — this is what
    tells you whether the problem is the key, the model name, quota, or network.
    """
    global _last_error
    if not config.GROQ_API_KEY:
        return {"ok": False, "model": config.GROQ_MODEL,
                "message": "No GROQ_API_KEY found. Add it to your .env file."}
        LLM_DEMO_MODE.inc()
    client = _get_client()
    if client is None:
        return {"ok": False, "model": config.GROQ_MODEL, "message": _last_error}
    try:
        resp = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        reply = resp.choices[0].message.content.strip()
        _last_error = ""
        return {"ok": True, "model": config.GROQ_MODEL,
                "message": f"Connected. Model replied: {reply!r}"}
    except Exception as e:
        _last_error = str(e)
        return {"ok": False, "model": config.GROQ_MODEL, "message": str(e)}

@traceable(
    name="Groq Chat",
    run_type="llm",
)
def chat(system_prompt: str, user_prompt: str, temperature: float = 0.3,
         max_tokens: int = 900) -> str:
    """
    Send a single-turn chat to Groq and return the text.
    Falls back to _demo_response() if Groq is unavailable or errors.
    """
    global _last_error, _used_demo
    client = _get_client()
    LLM_REQUESTS.inc()
    start_time = time.perf_counter()
    if client is None:
        _used_demo = True
        return _demo_response(user_prompt)
    try:
        resp = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        print(resp.usage)
        _last_error = ""
        _used_demo = False
        elapsed = time.perf_counter() - start_time
        LLM_LATENCY.observe(
            time.perf_counter() - start_time
        )
        print(
            f"[LLM] Model={config.GROQ_MODEL} "
            f"Latency={elapsed:.2f}s"
        )

        return resp.choices[0].message.content.strip()
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        print(
            f"[LLM] Failed after {elapsed:.2f}s : {e}"
        )
        # Network / model / quota error -> don't crash the pipeline
        _last_error = str(e)
        _used_demo = True
        print(f"[llm] Groq call failed, using demo fallback: {e}")
        LLM_ERRORS.inc()
        LLM_DEMO_MODE.inc()
        return _demo_response(user_prompt, error=str(e))


def _demo_response(user_prompt: str, error: str = "") -> str:
    """
    Deterministic, source-grounded draft used when Groq is unavailable.
    It echoes back the retrieved context so the pipeline output is meaningful.
    """
    context = ""
    if "CONTEXT:" in user_prompt:
        context = user_prompt.split("CONTEXT:", 1)[1].strip()
        context = context.split("REQUIREMENT:")[0].strip()
    snippet = context[:400] if context else "relevant internal material"

    note = ""
    if error:
        note = ("\n\n(Note: demo mode — the Groq call failed. Open Settings → "
                "Test Groq connection to see the exact reason.)")
    elif not config.GROQ_API_KEY:
        note = ("\n\n(Note: demo mode — no GROQ_API_KEY set. Add one in .env for "
                "full LLM drafting.)")

    return (
        "In response to this requirement, we propose the following approach. "
        "Drawing on our prior experience and internal references, we will deliver "
        "a solution that directly addresses the stated need. Specifically: "
        f"{snippet}{note}"
    )
