"""
fetch_data.py
Scopo: Recupera i dati delle partite del giorno dei Mondiali FIFA 2026
       da football-data.org API. In caso di errore usa RSS feed di fallback.
Dipendenze: requests, feedparser
Variabile d'ambiente richiesta: FOOTBALL_DATA_API_KEY
"""

import os
import sys
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

try:
    import requests
except ImportError:
    print("[ERRORE] requests non installato. Esegui: pip install requests")
    sys.exit(1)

try:
    import feedparser
except ImportError:
    print("[ERRORE] feedparser non installato. Esegui: pip install feedparser")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"
WC_COMPETITION_CODE = "WC"

RSS_FALLBACK_URL = "https://feeds.bbci.co.uk/sport/football/rss.xml"

STAGE_PRIORITY = {
    "FINAL": 6, "THIRD_PLACE": 5, "SEMI_FINALS": 4,
    "QUARTER_FINALS": 3, "ROUND_OF_16": 2, "GROUP_STAGE": 1,
}

EMERGENCY_FALLBACK_DATA = {
    "homeTeam": "Brazil",
    "awayTeam": "Argentina",
    "utcDate": datetime.now(timezone.utc).isoformat(),
    "score": {"fullTime": {"home": None, "away": None}},
    "status": "SCHEDULED",
    "stage": "GROUP_STAGE",
    "source": "emergency_fallback"
}


def get_api_key() -> Optional[str]:
    key = os.environ.get("FOOTBALL_DATA_API_KEY", "").strip()
    if not key:
        logger.warning("FOOTBALL_DATA_API_KEY non impostata o vuota.")
        return None
    return key


def fetch_today_matches() -> list:
    """
    Chiama football-data.org per le partite odierne della WC.
    Endpoint: GET /v4/competitions/WC/matches?dateFrom=YYYY-MM-DD&dateTo=YYYY-MM-DD
    Nota: verifica che il piano gratuito includa FIFA World Cup 2026 su football-data.org/person/login.
    """
    api_key = get_api_key()
    if not api_key:
        return []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = f"{FOOTBALL_DATA_BASE_URL}/competitions/{WC_COMPETITION_CODE}/matches"
    headers = {"X-Auth-Token": api_key}
    params = {"dateFrom": today, "dateTo": today}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        matches = data.get("matches", [])
        if not matches:
            logger.info("Nessuna partita oggi da football-data.org.")
            return []
        logger.info(f"Trovate {len(matches)} partite oggi da football-data.org.")
        return matches

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else "N/A"
        logger.error(f"HTTP {status_code} da football-data.org: {e}")
        if status_code == 403:
            logger.error("403 Forbidden: verifica che il piano includa il WC 2026.")
        return []
    except requests.exceptions.ConnectionError:
        logger.error("Impossibile connettersi a football-data.org.")
        return []
    except requests.exceptions.Timeout:
        logger.error("Timeout football-data.org (15s).")
        return []
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Parsing risposta football-data.org fallito: {e}")
        return []


def parse_match(raw_match: dict) -> dict:
    score_data = raw_match.get("score", {})
    full_time = score_data.get("fullTime", {}) or {}
    home_score = full_time.get("home")
    away_score = full_time.get("away")
    home_team_data = raw_match.get("homeTeam", {})
    away_team_data = raw_match.get("awayTeam", {})

    return {
        "homeTeam": home_team_data.get("name", "TBD"),
        "homeTeamTLA": home_team_data.get("tla", "???"),
        "awayTeam": away_team_data.get("name", "TBD"),
        "awayTeamTLA": away_team_data.get("tla", "???"),
        "utcDate": raw_match.get("utcDate", ""),
        "status": raw_match.get("status", "SCHEDULED"),
        "stage": raw_match.get("stage", ""),
        "scoreHome": home_score,
        "scoreAway": away_score,
        "hasScore": home_score is not None and away_score is not None,
        "source": "football-data.org"
    }


def fetch_from_rss_fallback() -> dict:
    """Legge BBC Sport Football RSS come fallback. Restituisce dati del primo articolo utile."""
    logger.info(f"Fallback RSS: {RSS_FALLBACK_URL}")
    try:
        feed = feedparser.parse(RSS_FALLBACK_URL)
        if not feed.entries:
            logger.warning("RSS feed vuoto o non raggiungibile.")
            return {}

        first_entry = feed.entries[0]
        title = first_entry.get("title", "FIFA World Cup 2026 Update")
        summary = first_entry.get("summary", "")
        link = first_entry.get("link", "")
        clean_summary = re.sub(r"<[^>]+>", "", summary).strip()
        logger.info(f"RSS: trovato articolo — '{title}'")

        return {
            "homeTeam": "World Cup 2026",
            "homeTeamTLA": "WC",
            "awayTeam": "FIFA Update",
            "awayTeamTLA": "FIFA",
            "utcDate": datetime.now(timezone.utc).isoformat(),
            "status": "NEWS",
            "stage": "World Cup 2026",
            "scoreHome": None,
            "scoreAway": None,
            "hasScore": False,
            "rssTitle": title,
            "rssSummary": clean_summary[:200] if clean_summary else "",
            "rssLink": link,
            "source": "rss_fallback_bbc"
        }

    except Exception as e:
        logger.error(f"RSS fallback fallito: {e}")
        return {}


def select_best_match(parsed_matches: list) -> dict:
    """
    Sceglie il match più rilevante tra quelli disponibili.
    Priorità: 1) match con risultato, 2) fase più avanzata del torneo.
    """
    finished = [m for m in parsed_matches if m.get("hasScore")]
    pool = finished if finished else parsed_matches
    return max(pool, key=lambda m: STAGE_PRIORITY.get(m.get("stage", ""), 0))


def get_match_data() -> dict:
    """
    Funzione principale. Orchestrazione:
    1. football-data.org API
    2. RSS BBC Sport fallback
    3. Dati hardcoded di emergenza
    """
    matches = fetch_today_matches()
    if matches:
        parsed = [parse_match(m) for m in matches]
        best = select_best_match(parsed)
        logger.info(
            f"Dato finale: {best['homeTeam']} vs {best['awayTeam']} "
            f"(stage={best.get('stage','?')}, hasScore={best.get('hasScore')}) — fonte: API"
        )
        return best

    logger.warning("API non disponibile — provo RSS fallback.")
    rss_data = fetch_from_rss_fallback()
    if rss_data:
        logger.info(f"Dato finale: RSS — '{rss_data.get('rssTitle', '')}' — fonte: RSS")
        return rss_data

    logger.error("Tutti i fallback falliti — uso dati di emergenza hardcoded.")
    EMERGENCY_FALLBACK_DATA["utcDate"] = datetime.now(timezone.utc).isoformat()
    return EMERGENCY_FALLBACK_DATA


if __name__ == "__main__":
    data = get_match_data()
    print("\n--- Dati partita del giorno ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))
