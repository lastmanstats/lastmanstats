"""
upset_templates.py
Pre-built video templates for the 5 most likely WC 2026 upsets.
Reduces time-to-publish from ~45 min to 15-20 min when an upset occurs.
No Gemini call — hooks are pre-written and dynamically filled with real scores.

Usage:
  python upset_templates.py <template> --team1 TLA --team2 TLA [options]

Templates:
  giant_killed   -- Top-5 nation eliminated in group stage
  record_goals   -- Historic high-scoring match (fill in actual scores)
  penalty_drama  -- Knockout round decided by penalties
  comeback       -- Team wins after being 2-0 down (fill in final score)
  dark_horse     -- Unfancied team reaches semi-finals

Examples:
  python upset_templates.py giant_killed --team1 GER --team2 JPN --score-home 0 --score-away 2
  python upset_templates.py penalty_drama --team1 BRA --team2 FRA --team1-full Brazil
  python upset_templates.py comeback --team1 MAR --team2 ESP --score-home 3 --score-away 2
  python upset_templates.py record_goals --team1 ARG --team2 KSA --score-home 7 --score-away 0
  python upset_templates.py dark_horse --team1 MAR --team1-full Morocco
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

TEAM_COLORS = {
    "BRA": "#009C3B", "ARG": "#43A8E0", "GER": "#000000", "FRA": "#003087",
    "ESP": "#AA151B", "POR": "#006600", "ENG": "#CF102D", "ITA": "#003DA5",
    "NED": "#FF6600", "USA": "#002868", "MEX": "#006847", "CAN": "#FF0000",
    "MAR": "#C1272D", "SEN": "#00853F", "JPN": "#BC002D", "KOR": "#003478",
}

# Template definitions — hooks are either static strings or callables that receive match args.
TEMPLATES = {
    "giant_killed": {
        "display_name": "Giant Killed",
        "accent_color": "#FF3B3B",
        "score_required": True,
    },
    "record_goals": {
        "display_name": "Record Goals",
        "accent_color": "#FFD700",
        "score_required": True,
    },
    "penalty_drama": {
        "display_name": "Penalty Drama",
        "accent_color": "#8B5CF6",
        "score_required": False,
    },
    "comeback": {
        "display_name": "Epic Comeback",
        "accent_color": "#00FF87",
        "score_required": True,
    },
    "dark_horse": {
        "display_name": "Dark Horse",
        "accent_color": "#F59E0B",
        "score_required": False,
    },
}


def build_hook(template_key: str, team1: str, team2: str,
               score_home: int, score_away: int) -> str:
    if template_key == "giant_killed":
        return f"{team2} JUST ELIMINATED {team1}. THE GIANT IS DEAD."
    if template_key == "record_goals":
        total = score_home + score_away
        return f"HISTORY: {total} GOALS IN ONE WORLD CUP GAME."
    if template_key == "penalty_drama":
        return f"{team1} WIN ON PENALTIES. THE CRUELEST WAY TO GO."
    if template_key == "comeback":
        return f"DOWN 2-0. WON {score_home}-{score_away}. UNBELIEVABLE."
    if template_key == "dark_horse":
        return f"{team1} IN THE SEMI-FINALS. NOBODY SAW THIS COMING."
    return "WORLD CUP 2026 — HISTORY IN THE MAKING."


def build_headline(template_key: str, team1: str, team2: str,
                   score_home: int, score_away: int) -> str:
    if template_key == "penalty_drama":
        return f"{team1} WIN ON PENS"
    if template_key == "dark_horse":
        return f"{team1} — SEMI-FINALS"
    return f"{team1} {score_home} - {score_away} {team2}"


def build_subtext(template_key: str) -> str:
    subtexts = {
        "giant_killed": "Group Stage Elimination\nFIFA World Cup 2026",
        "record_goals": "Historic Score\nFIFA World Cup 2026",
        "penalty_drama": "Knockout Round — Penalties\nFIFA World Cup 2026",
        "comeback": "The Greatest Comeback\nFIFA World Cup 2026",
        "dark_horse": "Semi-Final Qualification\nFIFA World Cup 2026",
    }
    return subtexts.get(template_key, "FIFA World Cup 2026")


def build_caption(template_key: str, team1_full: str, team2_full: str,
                  score_home: int, score_away: int) -> str:
    cta = "Follow for WC stats in 30 min from final whistle"
    if template_key == "giant_killed":
        raw = f"{team1_full} ELIMINATED from #WorldCup2026 \U0001f6a8 {cta}"
    elif template_key == "record_goals":
        total = score_home + score_away
        raw = f"{total} goals in ONE game at #WorldCup2026 \U0001f92f {cta}"
    elif template_key == "penalty_drama":
        raw = f"{team1_full} through on penalties at #WorldCup2026 \U0001f494 {cta}"
    elif template_key == "comeback":
        raw = f"2-0 down, won {score_home}-{score_away}. {team1_full} is UNREAL \U0001f631 {cta}"
    elif template_key == "dark_horse":
        raw = f"{team1_full} in the WC SEMI-FINALS \U0001f30d {cta}"
    else:
        raw = f"{team1_full} vs {team2_full} #WorldCup2026 ⚽ {cta}"
    return raw[:150]


def build_narration(template_key: str, team1_full: str, team2_full: str,
                    score_home: int, score_away: int) -> str:
    cta = "Follow Last Man Stats — stats within thirty minutes of the final whistle."
    if template_key == "giant_killed":
        return (
            f"{team1_full}. Out. In the group stage. "
            f"The final score: {team2_full} {score_away}, {team1_full} {score_home}. "
            f"One of the biggest shocks this World Cup has ever seen. "
            f"The numbers don't lie. {cta}"
        )
    if template_key == "record_goals":
        total = score_home + score_away
        return (
            f"{total} goals. In one World Cup game. "
            f"{team1_full} {score_home}, {team2_full} {score_away}. "
            f"History written tonight. This is why we watch football. {cta}"
        )
    if template_key == "penalty_drama":
        return (
            f"Penalties. The cruellest way to go out of a World Cup. "
            f"{team1_full} hold their nerve. {team2_full} are heading home. "
            f"Football is beautiful. Football is brutal. {cta}"
        )
    if template_key == "comeback":
        return (
            f"Two nil down. Most teams would have given up. "
            f"Not {team1_full}. Final score: {score_home}-{score_away}. "
            f"The greatest comeback story of this tournament. {cta}"
        )
    if template_key == "dark_horse":
        return (
            f"{team1_full} are in the semi-finals of the World Cup. "
            f"Say that again. The semi-finals. "
            f"Nobody predicted this. The numbers told a different story. Now we know. {cta}"
        )
    return f"World Cup 2026. Extraordinary scenes tonight. {cta}"


def build_hashtags(template_key: str, team1: str, team2: str) -> list:
    base = ["#WorldCup2026", "#FIFA2026", "#Football"]
    extras = {
        "giant_killed": [f"#{team2}Out", "#GiantKilling"],
        "record_goals": ["#HistoricGoals", "#WorldCupRecord"],
        "penalty_drama": ["#Penalties", "#WorldCupDrama"],
        "comeback": ["#Comeback", "#WorldCupDrama"],
        "dark_horse": [f"#{team1}", "#DarkHorse"],
    }
    return (base + extras.get(template_key, ["#WC2026", "#Soccer"]))[:5]


def get_accent(template_key: str, team1: str, override: str = "") -> str:
    if override:
        return override
    return TEMPLATES[template_key]["accent_color"]


def generate_upset_video(
    template_key: str,
    team1: str,
    team2: str,
    team1_full: str = "",
    team2_full: str = "",
    score_home: int = 0,
    score_away: int = 0,
    accent_override: str = "",
) -> dict:
    if template_key not in TEMPLATES:
        raise ValueError(
            f"Template '{template_key}' non trovato. Disponibili: {list(TEMPLATES.keys())}"
        )

    team1_full = team1_full or team1
    team2_full = team2_full or team2

    hook = build_hook(template_key, team1, team2, score_home, score_away)
    headline = build_headline(template_key, team1, team2, score_home, score_away)
    subtext = build_subtext(template_key)
    caption = build_caption(template_key, team1_full, team2_full, score_home, score_away)
    hashtags = build_hashtags(template_key, team1, team2)
    narration = build_narration(template_key, team1_full, team2_full, score_home, score_away)
    accent_color = get_accent(template_key, team1, accent_override)

    tpl = TEMPLATES[template_key]
    print(f"\n[UPSET] Template:  {tpl['display_name']}")
    print(f"[UPSET] Headline:  {headline}")
    print(f"[UPSET] Hook:      {hook}")
    print(f"[UPSET] Caption:   {caption}")
    print(f"[UPSET] Tags:      {' '.join(hashtags)}")
    print(f"[UPSET] Narration: {narration[:80]}...")
    print(f"[UPSET] Colore:    {accent_color}\n")

    sys.path.insert(0, str(Path(__file__).parent))
    try:
        import video_generator as vg
    except ImportError as e:
        print(f"[ERRORE] Impossibile importare video_generator: {e}")
        sys.exit(1)

    # Genera audio — gracefully degraded se OPENAI_API_KEY assente
    audio_path = ""
    try:
        import generate_audio as ga
        today_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        from pathlib import Path as _Path
        out_dir = _Path(__file__).parent / "output" / today_ts
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_path = ga.generate_audio(narration, str(out_dir / f"narration_upset_{template_key}.mp3"))
    except ImportError:
        pass

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = f"upset_{template_key}_{today}"

    # Templates without a meaningful score (penalties, dark horse) use None
    # so the hook scene shows the team TLA instead of "0 - 0".
    score_required = TEMPLATES[template_key].get("score_required", True)
    hook_home = score_home if score_required else None
    hook_away = score_away if score_required else None

    path_tiktok = vg.generate_video(
        headline=headline,
        subtext=subtext,
        team1=team1,
        team2=team2,
        accent_color=accent_color,
        timestamp_badge="LIVE STATS",
        audio_path=audio_path,
        output_filename=f"tiktok_{slug}",
        output_subdir=today,
        duration_seconds=vg.DURATION_SHORT,
        score_home=hook_home,
        score_away=hook_away,
    )
    print(f"[OK] TikTok:  {path_tiktok}")

    path_youtube = vg.generate_video(
        headline=headline,
        subtext=subtext,
        team1=team1,
        team2=team2,
        accent_color=accent_color,
        timestamp_badge="LIVE STATS",
        audio_path=audio_path,
        output_filename=f"youtube_{slug}",
        output_subdir=today,
        duration_seconds=vg.DURATION_LONG,
        score_home=hook_home,
        score_away=hook_away,
    )
    print(f"[OK] YouTube: {path_youtube}")

    return {
        "template": template_key,
        "headline": headline,
        "hook": hook,
        "caption": caption,
        "hashtags": hashtags,
        "tiktok": path_tiktok,
        "youtube": path_youtube,
        "accent_color": accent_color,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Genera video per i 5 upset più probabili del WC 2026",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "template", choices=list(TEMPLATES.keys()),
        help="Template da usare"
    )
    parser.add_argument("--team1", required=True, help="TLA squadra 1 (es. GER, BRA)")
    parser.add_argument("--team2", default="OPP", help="TLA squadra 2 (es. JPN, ARG)")
    parser.add_argument("--team1-full", default="", dest="team1_full",
                        help="Nome completo squadra 1 per caption (es. 'Germany')")
    parser.add_argument("--team2-full", default="", dest="team2_full",
                        help="Nome completo squadra 2 per caption")
    parser.add_argument("--score-home", type=int, default=0, dest="score_home",
                        help="Gol squadra 1 (default 0)")
    parser.add_argument("--score-away", type=int, default=0, dest="score_away",
                        help="Gol squadra 2 (default 0)")
    parser.add_argument("--color", default="",
                        help="Colore accento hex override (es. #FF3B3B)")

    args = parser.parse_args()

    result = generate_upset_video(
        template_key=args.template,
        team1=args.team1.upper(),
        team2=args.team2.upper(),
        team1_full=args.team1_full,
        team2_full=args.team2_full,
        score_home=args.score_home,
        score_away=args.score_away,
        accent_override=args.color,
    )

    print("\n=== OUTPUT FINALE ===")
    print(f"TikTok:  {result['tiktok']}")
    print(f"YouTube: {result['youtube']}")
    print(f"Hook:    {result['hook']}")
    print(f"Caption: {result['caption']}")
    print(f"Tags:    {' '.join(result['hashtags'])}")


if __name__ == "__main__":
    main()
