"""
generate_caption.py
Scopo: Genera hook, caption e hashtag per i video via OpenAI gpt-4o-mini.
Dipendenze: openai
Variabile d'ambiente richiesta: OPENAI_API_KEY
"""

import os
import sys
import json
import logging
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    print("[ERRORE] openai non installato. Esegui: pip install openai")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"

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

CTA obbligatoria da includere nella caption e nella narration: "{cta}"

Genera ESATTAMENTE questo JSON (nessun testo fuori dal JSON):
{{
  "hook": "<frase d'impatto max 10 parole, in inglese, segui RIGOROSAMENTE la categoria indicata>",
  "caption": "<caption TikTok/YouTube max 150 caratteri, 2-3 emoji, termina con la CTA>",
  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5"],
  "narration": "<voiceover 160-180 parole, inglese, tono commentatore sportivo (frasi corte e incalzanti, impatto immediato, niente emoji). Struttura: 1) Apri con il hook in forma di affermazione forte (2-3 frasi). 2) Sviluppa con 4-5 dati o fatti che costruiscono tensione narrativa progressiva, uno alla volta (7-8 frasi). 3) Inserisci un momento di pausa drammatica — una frase sola, corta, che lascia il dato nel silenzio. 4) Chiudi con: 'Follow Last Man Stats — stats within thirty minutes of the final whistle.' La narrazione deve riempire circa 55 secondi di parlato a ritmo normale.>"
}}

Regole:
- hook: segui RIGOROSAMENTE la categoria indicata, usa numeri reali dalla partita se disponibili
- caption: informativa e coinvolgente, deve terminare con la CTA esatta fornita
- hashtags: 5 hashtag, mix generici (WorldCup2026, FIFA2026) e specifici (squadre, nazione)
- narration: 160-180 parole, struttura in 4 blocchi (hook → dati → pausa drammatica → CTA finale), frasi corte e incalzanti, niente emoji, niente markdown, deve durare ~55 secondi a voce normale
- Rispondi SOLO con il JSON, nessun markdown, nessuna spiegazione."""


def call_openai(prompt: str) -> Optional[dict]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.error("OPENAI_API_KEY non impostata.")
        return None

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.85,
            max_tokens=800,
        )
        raw = response.choices[0].message.content
        logger.info(f"Caption generata con {MODEL}")
        return json.loads(raw)
    except Exception as e:
        logger.error(f"OpenAI caption fallita: {e}")
        return None


def validate_caption_output(data: dict) -> dict:
    hook = str(data.get("hook", "World Cup 2026 — Don't miss it!"))
    caption = str(data.get("caption", "Follow for World Cup 2026 daily updates! ⚽"))
    hashtags_raw = data.get("hashtags", [])
    narration = str(data.get("narration", ""))

    if len(hook) > 80:
        hook = hook[:77] + "..."
    if len(caption) > 150:
        caption = caption[:147] + "..."
    if len(narration) > 900:
        narration = narration[:900]

    if isinstance(hashtags_raw, list):
        hashtags = [str(h) if str(h).startswith("#") else f"#{h}"
                    for h in hashtags_raw[:5]]
    else:
        hashtags = ["#WorldCup2026", "#FIFA2026", "#Football", "#Soccer", "#WorldCup"]

    default_tags = ["#WorldCup2026", "#FIFA2026", "#Football", "#Soccer", "#WorldCup"]
    while len(hashtags) < 3:
        hashtags.append(default_tags[len(hashtags)])

    return {"hook": hook, "caption": caption, "hashtags": hashtags, "narration": narration}


FALLBACK_CAPTION = {
    "hook": "WORLD CUP 2026 — History in the Making!",
    "caption": "The biggest tournament on earth is HERE! Every goal, every drama — follow for daily World Cup 2026 updates! ⚽🏆",
    "hashtags": ["#WorldCup2026", "#FIFA2026", "#Football", "#Soccer", "#WC2026"],
    "narration": (
        "The FIFA World Cup 2026. The biggest stage in football. "
        "Thirty-two nations. One trophy. "
        "Every stat, every number — delivered within thirty minutes of the final whistle. "
        "Follow Last Man Stats for daily World Cup coverage."
    ),
}


def generate_caption(match_data: dict) -> dict:
    """
    Genera hook, caption e hashtags per la partita/notizia del giorno.
    Restituisce FALLBACK_CAPTION in caso di errore.
    """
    parsed = call_openai(build_prompt(match_data))

    if not parsed:
        logger.error("Nessuna risposta da OpenAI — uso fallback.")
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
