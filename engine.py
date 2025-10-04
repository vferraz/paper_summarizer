from __future__ import annotations
import os, re, json, time
from typing import Dict, Any, List, Tuple


from dotenv import load_dotenv  # type: ignore
load_dotenv(override=False)

from openai import OpenAI

# Initialize client from environment variables (OPENAI_API_KEY, etc.).
# Do NOT pass api_key explicitly: we honor your existing environment/.env setup.
client = OpenAI()

PAGE_BREAK = "\n\n----- PAGE BREAK -----\n\n"

# ---------------- logging / safety helpers ----------------
_SUMMARIZER_DEBUG = os.getenv("SUMMARIZER_DEBUG", "1") != "0"
_warned_temp_once = False

def log_info(msg: str) -> None:
    if _SUMMARIZER_DEBUG:
        print(f"[ENGINE] {msg}")

def log_error(context: str, e: Exception) -> None:
    # Always show API errors; they’re vital for diagnosis.
    print(f"[ENGINE ERROR] {context}: {type(e).__name__}: {e}")

def _normalize_temperature(model: str, temperature: float | None) -> float:
    """
    Some models (e.g., gpt-5 family) reject temperature=0.
    We bump zero to a tiny positive value and warn once.
    """
    global _warned_temp_once
    t = 0.0 if temperature is None else float(temperature)
    if "gpt-5" in (model or "").lower() and t == 0.0:
        if not _warned_temp_once:
            print("[ENGINE WARN] temperature=0 is not allowed for gpt-5 models; using 0.1 instead.")
            _warned_temp_once = True
        return 0.1
    return t

# ---------------- helpers ----------------
_REF_HEAD_RE = re.compile(r'^\s*(references|bibliography|literature)\b', re.I | re.M)

def _truncate_by_reference_heading(text: str) -> str:
    pages = text.split(PAGE_BREAK)
    for i, p in enumerate(pages):
        if _REF_HEAD_RE.search(p):
            return PAGE_BREAK.join(pages[:i]).rstrip()
    return text

def clean_text(text: str, drop_refs_after_page:int|None=None, cut_at_references:bool=True) -> str:
    s = re.sub(r"\n{3,}", "\n\n", text).strip()
    if cut_at_references:
        s = _truncate_by_reference_heading(s)
    if drop_refs_after_page is not None:
        pages = s.split(PAGE_BREAK)
        if len(pages) > drop_refs_after_page:
            s = PAGE_BREAK.join(pages[:drop_refs_after_page]).rstrip()
    return s

def ensure_schema(d: Dict[str, Any], keys: List[str]) -> Dict[str, str]:
    out = {}
    for k in keys:
        v = d.get(k, "Not reported")
        if not isinstance(v, str):
            v = str(v)
        out[k] = (v.strip() or "Not reported")
    return out

def is_size_signal_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(t in msg for t in ["context length", "maximum context", "too many tokens", "input is too long"])

def _usage_dict(resp) -> Dict[str,int]:
    u = getattr(resp, "usage", None) or {}
    return {
        "prompt_tokens": int(getattr(u, "prompt_tokens", 0) or u.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(u, "completion_tokens", 0) or u.get("completion_tokens", 0) or 0),
        "total_tokens": int(getattr(u, "total_tokens", 0) or u.get("total_tokens", 0) or 0),
    }

def add_usage(a: Dict[str,int], b: Dict[str,int]) -> Dict[str,int]:
    return {
        "prompt_tokens": a.get("prompt_tokens",0) + b.get("prompt_tokens",0),
        "completion_tokens": a.get("completion_tokens",0) + b.get("completion_tokens",0),
        "total_tokens": a.get("total_tokens",0) + b.get("total_tokens",0),
    }

# Keep cfg param for compatibility, but we ignore it for client creation (env-only).
def call_chat_json(model:str, system_prompt:str, user_prompt:str, temperature:float, cfg:Dict[str,Any]) -> Tuple[Dict[str,Any], str, Dict[str,int]]:
    # Normalize temperature for models that reject 0
    temperature = _normalize_temperature(model, temperature)
    try:
        resp = client.chat.completions.create(
            model=model,
            response_format={"type":"json_object"},
            temperature=temperature,
            messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],
        )
    except Exception as e:
        # Surface the real API error and re-raise for upstream handling.
        log_error("call_chat_json", e)
        raise

    content = resp.choices[0].message.content or "{}"
    finish = resp.choices[0].finish_reason or ""
    usage = _usage_dict(resp)
    return json.loads(content), finish, usage

def split_in_two(text:str, overlap:int) -> Tuple[str,str]:
    n = len(text); mid = n//2
    return text[:max(0, mid + overlap//2)].strip(), text[max(0, mid - overlap//2):].strip()

# --------------- core ops (prompts come from cfg["prompts"]) ---------------
def try_single_pass(text:str, context:str, cfg:Dict[str,Any]) -> Tuple[Dict[str,str]|None, str, Dict[str,int]]:
    sys = cfg["prompts"]["system"]
    usr = cfg["prompts"]["single"].format(context=context, text=text)
    try:
        j, finish, u = call_chat_json(cfg["model"], sys, usr, cfg["temperature"], cfg)
        if finish == "length":
            return None, "finish_length", u
        return ensure_schema(j, cfg["schema_keys"]), "ok", u
    except Exception as e:
        # Log the actual exception
        log_error("try_single_pass", e)
        if is_size_signal_error(e):
            return None, "too_big", {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
        # Keep previous behavior but include type in status
        return None, f"error:{e.__class__.__name__}", {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}

def summarize_chunk(chunk:str, context:str, cfg:Dict[str,Any]) -> Tuple[Dict[str,str], Dict[str,int]]:
    sys = cfg["prompts"]["system"]
    usr = cfg["prompts"]["map"].format(context=context, chunk=chunk)
    tries, usage = 0, {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
    while True:
        tries += 1
        try:
            j, _, u = call_chat_json(cfg["model"], sys, usr, cfg["temperature"], cfg)
            usage = add_usage(usage, u)
            return ensure_schema(j, cfg["schema_keys"]), usage
        except Exception as e:
            log_error("summarize_chunk", e)
            if is_size_signal_error(e): raise
            if tries >= 2: raise
            time.sleep(0.6)

def reduce_partials(parts:List[Dict[str,str]], context:str, cfg:Dict[str,Any]) -> Tuple[Dict[str,str], Dict[str,int]]:
    sys = cfg["prompts"]["system"]
    usr = cfg["prompts"]["reduce"].format(context=context, partials=json.dumps(parts, ensure_ascii=False))
    tries, usage = 0, {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
    while True:
        tries += 1
        try:
            j, _, u = call_chat_json(cfg["model"], sys, usr, cfg["temperature"], cfg)
            usage = add_usage(usage, u)
            return ensure_schema(j, cfg["schema_keys"]), usage
        except Exception as e:
            log_error("reduce_partials", e)
            if tries >= 2:
                # Fall back to simple merge
                merged = {}
                for k in cfg["schema_keys"]:
                    val = "Not reported"
                    for p in parts:
                        v = (p.get(k) or "").strip()
                        if v and v.lower() != "not reported":
                            val = v; break
                    merged[k] = val
                return merged, usage
            time.sleep(0.8)

def recursive_binary_map(text:str, context:str, cfg:Dict[str,Any]) -> Tuple[Dict[str,str], Dict[str,int]]:
    try:
        part, u = summarize_chunk(text, context, cfg)
        return part, u
    except Exception as e:
        if is_size_signal_error(e):
            L, R = split_in_two(text, cfg["binary_overlap"])
            left, uL = recursive_binary_map(L, context, cfg)
            right, uR = recursive_binary_map(R, context, cfg)
            merged, uM = reduce_partials([left, right], context, cfg)
            return merged, add_usage(add_usage(uL, uR), uM)
        # Non-size errors bubble up to caller after being logged upstream
        raise

def chunked_map_reduce(text:str, context:str, cfg:Dict[str,Any]) -> Tuple[Dict[str,str], Dict[str,int]]:
    return recursive_binary_map(text, context, cfg)

def summarize_text(text:str, context:str, mode:str, cfg:Dict[str,Any]) -> Tuple[str, Dict[str,str]|None, Dict[str,int]]:
    cleaned = clean_text(
        text,
        cfg.get("drop_refs_after_page"),
        cfg.get("cut_at_references", True),
    )
    if mode == "never":
        s, _, u = try_single_pass(cleaned, context, cfg)
        return ("single", s, u) if s else ("single", None, u)
    if mode == "always":
        try:
            s, u = chunked_map_reduce(cleaned, context, cfg)
            return "chunked", s, u
        except Exception as e:
            log_error("summarize_text(always)", e)
            return "chunked", None, {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
    s, _, u1 = try_single_pass(cleaned, context, cfg)
    if s: return "single", s, u1
    try:
        s2, u2 = chunked_map_reduce(cleaned, context, cfg)
        return "chunked", s2, add_usage(u1, u2)
    except Exception as e:
        log_error("summarize_text(auto->chunked)", e)
        return "chunked", None, u1
