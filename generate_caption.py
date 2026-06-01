"""
generate_caption.py
Scopo: Genera hook, caption e hashtag per i video via Google Gemini Flash API.
Dipendenze: google-generativeai
Variabile d'ambiente richiesta: GEMINI_API_KEY

Nota modelli: usa gemini-2.0-flash-exp con fallback a gemini-1.5-flash.
Verifica modelli free tier aggiornati su: https://ai.google.dev/gemini-api/docs/models
"""

import os
import sys
import json
import logging
import re
from typing import Optional

try:
    import google.generativeai as genai
except ImportError:
    print("[ERRORE] google-generativeai non installato. Esegui: pip install google-generativeai")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.0-flash-exp"
MODEL_FALLBACK = "gemini-1.5-flash"

GENERATION_CONFIG = {
    "temperature": 0.85,
    "top_p": 0.95,
    "max_output_tokens": 512,
}


def build_prompt(match_data: dict) -> str:
    source = match_data.get("source", "")
    has_score = match_data.get("hasScore", False)

    if source == "rss_fallback_bbc":
        rss_title = match_data.get("rssTitle", "World Cup 2026 News")
        rss_summary = match_data.get("rssSummary", "")
        context_block = f"""
Notizia calcistica del giorno:
Titolo: {rss_title}
Sommario: {rss_summary}
Competizione: FIFA World Cup 2026
"""
    elif has_score:
        context_block = f"""
Partita terminata:
{match_data.get('homeTeam', 'Team A')} {match_data.get('scoreHome', 0)} - {match_data.get('scoreAway', 0)} {match_data.get('awayTeam', 'Team B')}
Fase: {match_data.get('stage', 'FIFA World Cup 2026')}
Competizione: FIFA World Cup 2026
"""
    else:
        context_block = f"""
Partita in programma:
{match_data.get('homeTeam', 'Team A')} vs {match_data.get('awayTeam', 'Team B')}
Data UTC: {match_data.get('utcDate', 'oggi')}
Fase: {match_data.get('stage', 'FIFA World Cup 2026')}
Competizione: FIFA World Cup 2026
"""

    return f"""Sei un social media manager esperto di calcio internazionale.
Genera contenuto virale per TikTok e YouTube Shorts sui Mondiali FIFA 2026.

{context_block}

Genera ESATTAMENTE questo JSON (nessun testo fuori dal JSON):
{{
  "hook": "<frase d'impatto max 10 parole, in inglese, per catturare l'attenzione nei primi 2 secondi>",
  "caption": "<caption per TikTok/YouTube max 150 caratteri, con 2-3 emoji, includi CTA (Follow for more!)>",
  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5"]
}}

Regole:
- hook: breve, drammatico, usa numeri o aggettivi forti (es. "BRAZIL DESTROYS ARGENTINA 3-0!")
- caption: informativa ma coinvolgente, include emoji calcistiche
- hashtags: 5 hashtag rilevanti, mix tra generici (WorldCup2026, FIFA) e specifici alla partita
- Rispondi SOLO con il JSON, nessun markdown, nessuna spiegazione.
"""


def configure_gemini() -> Optional[str]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.error("GEMINI_API_KEY non impostata come variabile d'ambiente.")
        return None
    genai.configure(api_key=api_key)
    return api_key


def call_gemini(prompt: str) -> Optional[str]:
    for model_name in [MODEL_NAME, MODEL_FALLBACK]:
        try:
            logger.info(f"Chiamata Gemini con modello: {model_name}")
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=GENERATION_CONFIG
            )
            response = model.generate_content(prompt)
            if response.text:
                return response.text.strip()
            else:
                logger.warning(f"Risposta vuota da {model_name}.")
        except Exception as e:
            logger.warning(f"Modello {model_name} fallito: {e}")
            continue
    return None


def parse_gemini_response(raw_text: str) -> Optional[dict]:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw_text)
    cleaned = re.sub(r"```\s*", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    logger.error(f"Impossibile parsare la risposta Gemini:\n{raw_text[:500]}")
    return None


def validate_caption_output(data: dict) -> dict:
    hook = str(data.get("hook", "World Cup 2026 — Don't miss it!"))
    caption = str(data.get("caption", "Follow for World Cup 2026 daily updates! ⚽"))
    hashtags_raw = data.get("hashtags", [])

    if len(hook) > 80:
        hook = hook[:77] + "..."
    if len(caption) > 150:
        caption = caption[:147] + "..."

    if isinstance(hashtags_raw, list):
        hashtags = [str(h) if str(h).startswith("#") else f"#{h}"
                    for h in hashtags_raw[:5]]
    else:
        hashtags = ["#WorldCup2026", "#FIFA2026", "#Football", "#Soccer", "#WorldCup"]

    default_tags = ["#WorldCup2026", "#FIFA2026", "#Football", "#Soccer", "#WorldCup"]
    while len(hashtags) < 3:
        hashtags.append(default_tags[len(hashtags)])

    return {"hook": hook, "caption": caption, "hashtags": hashtags}


FALLBACK_CAPTION = {
    "hook": "WORLD CUP 2026 — History in the Making!",
    "caption": "The biggest tournament on earth is HERE! Every goal, every drama — follow for daily World Cup 2026 updates! ⚽🏆",
    "hashtags": ["#WorldCup2026", "#FIFA2026", "#Football", "#Soccer", "#WC2026"]
}


def generate_caption(match_data: dict) -> dict:
    """
    Genera hook, caption e hashtags per la partita/notizia del giorno.
    Restituisce FALLBACK_CAPTION in caso di errore.
    """
    if not configure_gemini():
        logger.error("Gemini non configurato — uso fallback.")
        return FALLBACK_CAPTION

    prompt = build_prompt(match_data)
    raw_response = call_gemini(prompt)

    if not raw_response:
        logger.error("Nessuna risposta da Gemini — uso fallback.")
        return FALLBACK_CAPTION

    parsed = parse_gemini_response(raw_response)
    if not parsed:
        logger.error("Parsing fallito — uso fallback.")
        return FALLBACK_CAPTION

    result = validate_caption_output(parsed)
    logger.info(f"Caption generata: hook='{result['hook']}'")
    return result


if __name__ == "__main__":
    test_match = {
        "homeTeam": "Brazil",
        "homeTeamTLA": "BRA",
        "awayTeam": "Argentina",
        "awayTeamTLA": "ARG",
        "utcDate": "2026-06-25T19:00:00Z",
        "status": "SCHEDULED",
        "stage": "QUARTER_FINALS",
        "scoreHome": None,
        "scoreAway": None,
        "hasScore": False,
        "source": "football-data.org"
    }

    result = generate_caption(test_match)
    print("\n--- Caption generata ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))
