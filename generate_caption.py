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

MODEL_NAME = "gemini-2.0-flash"
MODEL_FALLBACK = "gemini-1.5-flash"

GENERATION_CONFIG = {
    "temperature": 0.85,
    "top_p": 0.95,
    "max_output_tokens": 512,
}

# Five hook categories — one is selected per match context and injected into the prompt.
# Forcing a single category prevents Gemini from averaging across all five (= generic output).
HOOK_CATEGORIES = {
    "surprise": (
        "SORPRESA — Il risultato ha sfidato ogni previsione. Hook ad alto impatto, "
        "usa il risultato reale. Esempio: 'GERMANY ELIMINATED BY MOROCCO 2-0!'"
    ),
    "exclusivity": (
        "ESCLUSIVITÀ — Momento storico, non si ripeterà per anni. Enfatizza unicità e rarità. "
        "Esempio: 'HISTORY MADE: FIRST-EVER WC SEMI BETWEEN THESE TWO!'"
    ),
    "challenge": (
        "SFIDA ALLA CONOSCENZA — Testa il fan con una statistica inattesa, usa un numero o record concreto. "
        "Esempio: 'SPAIN HAVEN\\'T LOST IN 22 WC GROUP GAMES. UNTIL NOW?'"
    ),
    "urgency": (
        "URGENZA — Eliminazione o gloria stanotte, non ci sono seconde chance. Crea pressione emotiva. "
        "Esempio: 'ONE TEAM GOES HOME TONIGHT. FOREVER.'"
    ),
    "confirmation": (
        "CONFERMA DI SOSPETTI — Il favorito ha vinto come previsto, ma i numeri lo rendono più impressionante. "
        "Esempio: 'BRAZIL WIN AGAIN. 5TH WORLD CUP NOW IN THEIR SIGHTS.'"
    ),
}


def select_hook_category(match_data: dict) -> str:
    has_score = match_data.get("hasScore", False)
    stage = match_data.get("stage", "").upper()
    home_score = match_data.get("scoreHome") or 0
    away_score = match_data.get("scoreAway") or 0

    knockout_stages = {"QUARTER_FINALS", "SEMI_FINALS", "FINAL", "THIRD_PLACE"}
    is_knockout = any(k in stage for k in knockout_stages)

    if not has_score:
        return "urgency" if is_knockout else "challenge"

    goal_diff = abs(home_score - away_score)
    if goal_diff >= 3:
        return "surprise"
    if is_knockout:
        return "exclusivity"
    if goal_diff == 0:
        return "challenge"
    return "confirmation"


def build_prompt(match_data: dict) -> str:
    source = match_data.get("source", "")
    has_score = match_data.get("hasScore", False)
    category = select_hook_category(match_data)
    category_instruction = HOOK_CATEGORIES[category]

    # CTA is truthful: timing claim only when content is post-match
    cta = (
        "Follow for WC stats in 30 min from final whistle"
        if has_score
        else "Follow @lastmanstats for daily World Cup stats"
    )

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

    return f"""Sei un social media manager esperto di calcio internazionale con 10 anni di esperienza su TikTok e YouTube Shorts.
Genera contenuto virale per i Mondiali FIFA 2026. Il tuo account (@lastmanstats) pubblica stats entro 30 minuti dal fischio finale.

{context_block}
CATEGORIA HOOK: {category_instruction}

CTA obbligatoria da includere nella caption: "{cta}"

Genera ESATTAMENTE questo JSON (nessun testo fuori dal JSON):
{{
  "hook": "<frase d'impatto max 10 parole, in inglese, segui RIGOROSAMENTE la categoria indicata>",
  "caption": "<caption TikTok/YouTube max 150 caratteri, 2-3 emoji, termina con la CTA>",
  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5"]
}}

Regole:
- hook: segui RIGOROSAMENTE la categoria indicata, usa numeri reali dalla partita se disponibili
- caption: informativa e coinvolgente, deve terminare con la CTA esatta fornita
- hashtags: 5 hashtag, mix generici (WorldCup2026, FIFA2026) e specifici (squadre, nazione)
- Rispondi SOLO con il JSON, nessun markdown, nessuna spiegazione."""


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
