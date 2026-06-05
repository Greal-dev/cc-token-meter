#!/usr/bin/env python
"""StatusLine Claude Code — bandeau conso tokens / coût (base prix API).

Lit le JSON de statusline sur stdin, parse la fin du transcript .jsonl pour
extraire les tokens du dernier message (contexte) et du dernier tour, calcule
le coût tour + session sur base des prix API publics Anthropic.

Affiche : Modèle | contexte utilisé | Token In | Token Out | $ tour | $ session
"""
import json
import os
import sys

# Python embed écrit en cp1252 sur Windows ; forcer UTF-8 pour les séparateurs.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# Prix API par million de tokens (USD). Match par sous-chaîne sur model.id.
# in = input frais, out = output, cw = cache write 5min, cr = cache read.
PRICING = {
    "opus":   {"in": 15.0, "out": 75.0, "cw": 18.75, "cr": 1.50},
    "sonnet": {"in": 3.0,  "out": 15.0, "cw": 3.75,  "cr": 0.30},
    "haiku":  {"in": 1.0,  "out": 5.0,  "cw": 1.25,  "cr": 0.10},
}
DEFAULT_PRICE = PRICING["opus"]

# Codes ANSI
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"
SEP = f"{DIM} │ {RESET}"


def price_for(model_id: str) -> dict:
    mid = (model_id or "").lower()
    for key, val in PRICING.items():
        if key in mid:
            return val
    return DEFAULT_PRICE


def context_window(model_id: str) -> int:
    mid = (model_id or "").lower()
    if "1m" in mid:
        return 1_000_000
    return 200_000


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(int(n))


def cost(u: dict, p: dict) -> float:
    return (
        u.get("input_tokens", 0) * p["in"]
        + u.get("cache_creation_input_tokens", 0) * p["cw"]
        + u.get("cache_read_input_tokens", 0) * p["cr"]
        + u.get("output_tokens", 0) * p["out"]
    ) / 1_000_000


def tail_lines(path: str, max_bytes: int = 2_000_000) -> list:
    """Lit les dernières lignes du fichier sans tout charger."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
                f.readline()  # jette la 1re ligne potentiellement coupée
            data = f.read()
    except OSError:
        return []
    out = []
    for raw in data.decode("utf-8", "replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except ValueError:
            continue
    return out


def entry_usage(e: dict):
    """Renvoie le dict usage d'un message assistant, sinon None."""
    if e.get("type") != "assistant":
        return None
    msg = e.get("message") or {}
    u = msg.get("usage")
    return u if isinstance(u, dict) else None


def is_real_user_turn(e: dict) -> bool:
    """True si l'entrée est une vraie saisie utilisateur (pas un tool_result)."""
    if e.get("type") != "user":
        return False
    content = (e.get("message") or {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        return any(
            isinstance(b, dict) and b.get("type") == "text" for b in content
        )
    return False


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        data = {}

    model = data.get("model") or {}
    model_id = model.get("id") or ""
    model_name = model.get("display_name") or model_id or "?"
    transcript = data.get("transcript_path") or ""

    price = price_for(model_id)
    win = context_window(model_id)

    entries = tail_lines(transcript) if transcript else []

    # Contexte = usage du dernier message assistant
    ctx_tokens = 0
    last_usage = None
    for e in reversed(entries):
        u = entry_usage(e)
        if u is not None:
            last_usage = u
            break
    if last_usage:
        ctx_tokens = (
            last_usage.get("input_tokens", 0)
            + last_usage.get("cache_creation_input_tokens", 0)
            + last_usage.get("cache_read_input_tokens", 0)
        )

    # Tour = somme des usages assistant depuis la dernière vraie saisie user
    turn_in = turn_out = 0
    turn_cost = 0.0
    for e in reversed(entries):
        if is_real_user_turn(e):
            break
        u = entry_usage(e)
        if u is None:
            continue
        turn_in += (
            u.get("input_tokens", 0)
            + u.get("cache_creation_input_tokens", 0)
            + u.get("cache_read_input_tokens", 0)
        )
        turn_out += u.get("output_tokens", 0)
        turn_cost += cost(u, price)

    # Session = somme sur tout le transcript chargé (tail). Pour les très gros
    # transcripts tronqués, on complète avec le coût Claude Code si dispo.
    sess_cost = sum(
        cost(u, price) for u in (entry_usage(e) for e in entries) if u
    )
    cc_cost = (data.get("cost") or {}).get("total_cost_usd")
    if isinstance(cc_cost, (int, float)) and cc_cost > sess_cost:
        sess_cost = cc_cost  # transcript tronqué : fallback sur total fourni

    pct = (ctx_tokens / win * 100) if win else 0
    pct_color = GREEN if pct < 50 else (YELLOW if pct < 80 else "\033[31m")

    parts = [
        f"{CYAN}{model_name}{RESET}",
        f"ctx {fmt_tokens(ctx_tokens)}/{fmt_tokens(win)} {pct_color}{pct:.0f}%{RESET}",
        f"In {fmt_tokens(turn_in)}",
        f"Out {fmt_tokens(turn_out)}",
        f"tour {GREEN}${turn_cost:.3f}{RESET}",
        f"sess {GREEN}${sess_cost:.2f}{RESET}",
    ]
    sys.stdout.write(SEP.join(parts))


if __name__ == "__main__":
    main()
