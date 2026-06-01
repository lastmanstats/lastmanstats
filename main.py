"""
main.py
Scopo: Orchestratore principale della pipeline.
       Chiama in sequenza: fetch_data -> generate_caption -> video_generator
       Salva output in output/YYYY-MM-DD/ con log su console.
       Ogni step ha gestione errori indipendente con fallback hardcoded.
Uso: python main.py            (pipeline completa)
     python main.py --dry-run  (test senza generare il video)
"""

import sys
import os
import logging
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("wc2026_pipeline")

SCRIPT_DIR = Path(__file__).parent
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

FALLBACK_MATCH_DATA = {
    "homeTeam": "World Cup",
    "homeTeamTLA": "WC",
    "awayTeam": "2026",
    "awayTeamTLA": "USA",
    "utcDate": f"{TODAY}T18:00:00Z",
    "status": "SCHEDULED",
    "stage": "FIFA World Cup 2026",
    "scoreHome": None,
    "scoreAway": None,
    "hasScore": False,
    "source": "emergency_fallback"
}

FALLBACK_CAPTION_DATA = {
    "hook": "WORLD CUP 2026 — History in the Making!",
    "caption": "The biggest tournament on earth is HERE! Follow for daily World Cup 2026 updates! ⚽🏆",
    "hashtags": ["#WorldCup2026", "#FIFA2026", "#Football", "#Soccer", "#WC2026"]
}

TEAM_COLORS = {
    "BRA": "#009C3B", "ARG": "#43A8E0", "GER": "#000000", "FRA": "#003087",
    "ESP": "#AA151B", "POR": "#006600", "ENG": "#CF102D", "ITA": "#003DA5",
    "NED": "#FF6600", "USA": "#002868", "MEX": "#006847", "CAN": "#FF0000",
    "MAR": "#C1272D", "SEN": "#00853F", "JPN": "#BC002D", "KOR": "#003478",
}
DEFAULT_ACCENT_COLOR = "#00FF87"   # Palette A — verde plasma (fallback senza team color)


def import_module_safe(module_name: str):
    try:
        import importlib
        return importlib.import_module(module_name)
    except ImportError as e:
        logger.error(f"Impossibile importare {module_name}: {e}")
        return None


def get_accent_color(tla1: str, tla2: str) -> str:
    return TEAM_COLORS.get(tla1.upper(), TEAM_COLORS.get(tla2.upper(), DEFAULT_ACCENT_COLOR))


def step_fetch_data() -> dict:
    logger.info("=== STEP 1: Fetch dati partita ===")
    fetch_module = import_module_safe("fetch_data")
    if not fetch_module:
        logger.error("Modulo fetch_data non disponibile — uso fallback hardcoded.")
        return FALLBACK_MATCH_DATA
    try:
        match_data = fetch_module.get_match_data()
        if match_data:
            logger.info(f"Partita recuperata: {match_data.get('homeTeam')} vs {match_data.get('awayTeam')}")
            return match_data
        return FALLBACK_MATCH_DATA
    except Exception as e:
        logger.error(f"Errore in fetch_data: {e}")
        return FALLBACK_MATCH_DATA


def step_generate_caption(match_data: dict) -> dict:
    logger.info("=== STEP 2: Generazione caption con Gemini ===")
    caption_module = import_module_safe("generate_caption")
    if not caption_module:
        logger.error("Modulo generate_caption non disponibile — uso fallback.")
        return FALLBACK_CAPTION_DATA
    try:
        caption_data = caption_module.generate_caption(match_data)
        if caption_data:
            logger.info(f"Caption generata: hook='{caption_data.get('hook', '')[:50]}'")
            return caption_data
        return FALLBACK_CAPTION_DATA
    except Exception as e:
        logger.error(f"Errore in generate_caption: {e}")
        return FALLBACK_CAPTION_DATA


def build_video_params(match_data: dict, caption_data: dict) -> dict:
    home_tla = match_data.get("homeTeamTLA", "HOM")
    away_tla = match_data.get("awayTeamTLA", "AWY")
    has_score = match_data.get("hasScore", False)
    stage = match_data.get("stage", "FIFA World Cup 2026")

    if has_score:
        headline = f"{home_tla} {match_data.get('scoreHome', 0)} - {match_data.get('scoreAway', 0)} {away_tla}"
    elif match_data.get("source") == "rss_fallback_bbc":
        rss_title = match_data.get("rssTitle", "World Cup 2026 Update")
        headline = rss_title[:38].upper() if len(rss_title) > 38 else rss_title.upper()
    else:
        headline = f"{home_tla} vs {away_tla}"

    hook = caption_data.get("hook", "")
    subtext = f"{stage}\n{hook}" if hook else stage

    return {
        "headline": headline,
        "subtext": subtext,
        "team1": home_tla,
        "team2": away_tla,
        "accent_color": get_accent_color(home_tla, away_tla)
    }


def step_generate_video(match_data: dict, caption_data: dict, output_date_dir: str) -> dict:
    """Genera due video: 15s per TikTok e 62s per YouTube Shorts (Option C)."""
    logger.info("=== STEP 3: Generazione video (TikTok 15s + YouTube 62s) ===")
    video_module = import_module_safe("video_generator")
    if not video_module:
        logger.error("Modulo video_generator non disponibile.")
        return {"tiktok": "", "youtube": ""}
    try:
        params = build_video_params(match_data, caption_data)
        logger.info(f"Parametri video: headline='{params['headline']}' colore={params['accent_color']}")

        path_tiktok = video_module.generate_video(
            headline=params["headline"],
            subtext=params["subtext"],
            team1=params["team1"],
            team2=params["team2"],
            accent_color=params["accent_color"],
            output_filename=f"tiktok_{output_date_dir}",
            output_subdir=output_date_dir,
            duration_seconds=video_module.DURATION_SHORT
        )
        logger.info(f"[OK] TikTok: {path_tiktok}")

        path_youtube = video_module.generate_video(
            headline=params["headline"],
            subtext=params["subtext"],
            team1=params["team1"],
            team2=params["team2"],
            accent_color=params["accent_color"],
            output_filename=f"youtube_{output_date_dir}",
            output_subdir=output_date_dir,
            duration_seconds=video_module.DURATION_LONG
        )
        logger.info(f"[OK] YouTube: {path_youtube}")

        return {"tiktok": path_tiktok, "youtube": path_youtube}
    except Exception as e:
        logger.error(f"Errore in video_generator: {e}")
        return {"tiktok": "", "youtube": ""}


def save_metadata(output_dir: Path, match_data: dict, caption_data: dict, video_paths: dict):
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "video_tiktok": video_paths.get("tiktok", ""),
        "video_youtube": video_paths.get("youtube", ""),
        "match": match_data,
        "caption": caption_data,
    }
    meta_path = output_dir / "metadata.json"
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Metadata salvati: {meta_path}")
    except IOError as e:
        logger.error(f"Salvataggio metadata fallito: {e}")


def main(dry_run: bool = False):
    logger.info("=" * 60)
    logger.info("LAST MAN STATS — Content Pipeline avviata")
    logger.info(f"Data: {TODAY} | dry_run={dry_run}")
    logger.info("=" * 60)

    output_base = SCRIPT_DIR / "output" / TODAY
    output_base.mkdir(parents=True, exist_ok=True)

    match_data = step_fetch_data()
    caption_data = step_generate_caption(match_data)

    video_paths = {"tiktok": "", "youtube": ""}
    if not dry_run:
        video_paths = step_generate_video(match_data, caption_data, TODAY)
    else:
        logger.info("=== STEP 3: Generazione video SALTATA (dry-run) ===")

    save_metadata(output_base, match_data, caption_data, video_paths)

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETATA")
    if video_paths.get("tiktok"):
        logger.info(f"  TikTok:  {video_paths['tiktok']}")
    if video_paths.get("youtube"):
        logger.info(f"  YouTube: {video_paths['youtube']}")
    logger.info(f"  Hook:    {caption_data.get('hook', 'N/A')}")
    logger.info(f"  Caption: {caption_data.get('caption', 'N/A')[:80]}")
    logger.info(f"  Tags:    {' '.join(caption_data.get('hashtags', []))}")
    logger.info(f"  Output:  {output_base}/")
    logger.info("=" * 60)

    return {
        "success": True,
        "date": TODAY,
        "video_tiktok": video_paths.get("tiktok", ""),
        "video_youtube": video_paths.get("youtube", ""),
        "caption": caption_data,
        "match": {
            "home": match_data.get("homeTeam"),
            "away": match_data.get("awayTeam"),
            "score": f"{match_data.get('scoreHome', '-')} - {match_data.get('scoreAway', '-')}",
            "source": match_data.get("source")
        }
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="World Cup 2026 Content Pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Esegui fetch e caption senza generare il video")
    args = parser.parse_args()
    result = main(dry_run=args.dry_run)
    sys.exit(0 if result.get("success") else 1)
