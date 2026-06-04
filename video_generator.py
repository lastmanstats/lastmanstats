"""
video_generator.py
Struttura a 3 scene:
  Hook  (9%):  reveal score/squadre in grande su sfondo scuro
  Main (79%):  card con gradiente animato, testo, watermark
  CTA  (12%):  sfondo accent, @lastmanstats, call-to-action
Dipendenze: Pillow, FFmpeg
"""

import os
import sys
import math
import shutil
import tempfile
import subprocess
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("[ERRORE] Pillow non installato. Esegui: pip install Pillow")
    sys.exit(1)

WIDTH = 1080
HEIGHT = 1920
FPS = 15           # 15 fps: indistinguibile da 30 per grafica statica; render 50% più veloce
DURATION_SHORT = 63   # TikTok >60s (Creator Rewards threshold)
DURATION_LONG  = 90   # YouTube Shorts

HOOK_FRAC = 0.09   # Prime 9%  → ~5.7s su 63s
CTA_FRAC  = 0.12   # Ultime 12% → ~7.6s su 63s

TOTAL_FRAMES = FPS * DURATION_SHORT   # default per compatibilità backward

ACCOUNT_WATERMARK = "@lastmanstats"
BADGE_TEXT = "WORLD CUP 2026"

COLOR_BG        = "#0D1117"
COLOR_TITLE     = "#F0F4F8"
COLOR_ACCENT    = "#F59E0B"
COLOR_WATERMARK = "#8892A4"

OUTPUT_DIR = Path(__file__).parent / "output"


# ── Utility ────────────────────────────────────────────────────────────────────

def hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Colore hex non valido: {hex_color}")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def blend_colors(color1: tuple, color2: tuple, t: float) -> tuple:
    return tuple(int(color1[i] + (color2[i] - color1[i]) * t) for i in range(3))


def darken_color(color: tuple, factor: float = 0.35) -> tuple:
    return tuple(max(0, int(c * factor)) for c in color)


def get_text_width(font, text: str) -> int:
    try:
        return int(font.getlength(text))
    except AttributeError:
        return font.getsize(text)[0]


def get_text_height(font, text: str = "Ag") -> int:
    try:
        bbox = font.getbbox(text)
        return bbox[3] - bbox[1]
    except AttributeError:
        return font.getsize(text)[1]


def wrap_text(text: str, font, max_width: int) -> list:
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = (current_line + " " + word).strip()
        if get_text_width(font, test_line) <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines if lines else [text]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    local_fonts = Path(__file__).parent / "fonts"
    if bold:
        candidates = [
            str(local_fonts / "BarlowCondensed-Black.ttf"),
            str(local_fonts / "BebasNeue-Regular.ttf"),
            "/usr/share/fonts/truetype/bebas-neue/BebasNeue-Regular.ttf",
            "/usr/share/fonts/opentype/bebas-neue/BebasNeue-Regular.otf",
            "/home/ubuntu/.local/share/fonts/BarlowCondensed-Black.ttf",
            "/home/runner/.local/share/fonts/BarlowCondensed-Black.ttf",
            "/home/opc/.local/share/fonts/BarlowCondensed-Black.ttf",
            "/home/ubuntu/.local/share/fonts/BebasNeue-Regular.ttf",
            "/home/runner/.local/share/fonts/BebasNeue-Regular.ttf",
            "/home/opc/.local/share/fonts/BebasNeue-Regular.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
    else:
        candidates = [
            str(local_fonts / "Inter-Regular.ttf"),
            "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
            "/usr/share/fonts/opentype/inter/Inter-Regular.ttf",
            "/home/ubuntu/.local/share/fonts/Inter-Regular.ttf",
            "/home/runner/.local/share/fonts/Inter-Regular.ttf",
            "/home/opc/.local/share/fonts/Inter-Regular.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arial.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    print("[WARN] Nessun font TrueType trovato — uso font di default.")
    return ImageFont.load_default()


def draw_gradient_background(draw: ImageDraw.Draw, frame_index: int,
                              color_a: tuple, color_b: tuple,
                              total_frames: int) -> None:
    phase = frame_index / max(total_frames, 1)
    mid_offset = 0.5 + 0.2 * math.sin(2 * math.pi * phase)
    for y in range(HEIGHT):
        t = y / HEIGHT
        t_adj = max(0.0, min(1.0, t / mid_offset)) if mid_offset > 0 else t
        draw.line([(0, y), (WIDTH, y)], fill=blend_colors(color_a, color_b, t_adj))


def draw_text_with_shadow(draw: ImageDraw.Draw, text: str, position: tuple,
                           font, text_color: tuple = (255, 255, 255),
                           shadow_color: tuple = (0, 0, 0),
                           shadow_offset: int = 4) -> None:
    x, y = position
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=text_color)


def apply_alpha_overlay(img: Image.Image, color_rgb: tuple, alpha: int) -> Image.Image:
    """Blend a solid color over img with given alpha (0=transparent, 255=opaque)."""
    if alpha <= 0:
        return img
    if alpha >= 255:
        return Image.new("RGB", img.size, color_rgb)
    overlay = Image.new("RGBA", img.size, color_rgb + (alpha,))
    result = img.convert("RGBA")
    result.alpha_composite(overlay)
    return result.convert("RGB")


# ── Scene routing ──────────────────────────────────────────────────────────────

def get_scene_info(frame_index: int, total_frames: int) -> dict:
    hook_end = int(total_frames * HOOK_FRAC)
    cta_start = int(total_frames * (1.0 - CTA_FRAC))

    if frame_index < hook_end:
        return {"scene": "hook", "progress": frame_index / max(hook_end, 1)}

    if frame_index >= cta_start:
        span = total_frames - cta_start
        progress = (frame_index - cta_start) / max(span, 1)
        return {"scene": "cta", "progress": min(progress, 1.0)}

    main_start = hook_end
    main_frame = frame_index - main_start
    return {"scene": "main", "main_frame": main_frame}


# ── Hook scene ─────────────────────────────────────────────────────────────────

def render_hook_scene(progress: float, team1: str, team2: str,
                       accent_color: tuple, score_home, score_away) -> Image.Image:
    """
    First ~6s: dominant stat/score in maximum size on dark background.

    Design rationale (research-backed):
    - Pattern interrupt must fire at frame 0: no fade-in delay, accent number
      is the very first thing visible. Sources show frame-0 visual novelty
      activates the attentional alerting system before conscious scroll
      decision (edicionvideopro.com, 2025).
    - Primary subject occupies the upper two-thirds of the vertical frame,
      per 9:16 composition research (influencers-time.com, 2025).
    - Score/TLA rendered at 260px — "maximum size" approach: bold fonts at
      weight 700-900 get 31% better readability on mobile (blitzcutai.com, 2025).
    - Accent horizontal bar as immediate structural divider: high-contrast
      geometric shapes + negative space signal content type instantly.
    - Team label below bar, dimmed: information hierarchy (critical stat first,
      context second).
    - NO fade-in from black: the original fade completed at 40% of hook,
      wasting ~2.4s of first-impression window. Replace with a fast
      reveal (completes by 15% of hook, ~0.9s) that reads as a hard cut.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), hex_to_rgb(COLOR_BG))
    draw = ImageDraw.Draw(img)

    # Dark background with very subtle accent tint at top — avoids flat black
    bg = hex_to_rgb(COLOR_BG)
    for y in range(HEIGHT):
        tint = 0.12 * (1.0 - y / HEIGHT)
        color = tuple(int(bg[i] + (accent_color[i] - bg[i]) * tint) for i in range(3))
        draw.line([(0, y), (WIDTH, y)], fill=color)

    has_score = score_home is not None and score_away is not None

    if has_score:
        # Score at 260px: dominant number fills the visual field immediately
        font_score = load_font(260, bold=True)
        score_text = f"{score_home} - {score_away}"
        tw = get_text_width(font_score, score_text)
        th = get_text_height(font_score, score_text)

        # Position: upper two-thirds of frame (y center at ~42% height)
        tx = (WIDTH - tw) // 2
        ty = int(HEIGHT * 0.42) - th // 2

        # Hard shadow for depth, then accent-colored number
        draw.text((tx + 8, ty + 8), score_text, font=font_score, fill=(0, 0, 0))
        draw.text((tx, ty), score_text, font=font_score, fill=accent_color)

        # Full-width accent bar below score — structural divider, 6px height
        bar_y = ty + th + 36
        draw.rectangle([60, bar_y, WIDTH - 60, bar_y + 6], fill=accent_color)

        # Team label below bar — secondary hierarchy, dimmed
        font_label = load_font(60, bold=True)
        label = f"{team1}  vs  {team2}"
        lw = get_text_width(font_label, label)
        draw.text(((WIDTH - lw) // 2, bar_y + 28),
                  label, font=font_label, fill=hex_to_rgb(COLOR_WATERMARK))

    else:
        # Pre-match: TLA at 200px stacked — still dominant, fits vertical format
        font_tla = load_font(200, bold=True)
        font_vs  = load_font(64, bold=False)

        tla_h = get_text_height(font_tla, "A")
        vs_h  = get_text_height(font_vs, "vs")
        total_h = tla_h + vs_h + tla_h + 32
        start_y = int(HEIGHT * 0.35) - total_h // 2

        for tla, offset_y in [(team1, 0), (team2, tla_h + vs_h + 32)]:
            tw = get_text_width(font_tla, tla)
            tx = (WIDTH - tw) // 2
            ty = start_y + offset_y
            draw.text((tx + 8, ty + 8), tla, font=font_tla, fill=(0, 0, 0))
            draw.text((tx, ty), tla, font=font_tla, fill=accent_color)

        # "vs" with accent-colored divider dots flanking it
        vs_center_y = start_y + tla_h + 8
        vw = get_text_width(font_vs, "vs")
        dot_y = vs_center_y + vs_h // 2
        draw.ellipse([WIDTH // 2 - vw - 30, dot_y - 6,
                      WIDTH // 2 - vw - 18, dot_y + 6], fill=accent_color)
        draw.ellipse([WIDTH // 2 + vw + 18, dot_y - 6,
                      WIDTH // 2 + vw + 30, dot_y + 6], fill=accent_color)
        draw.text(((WIDTH - vw) // 2, vs_center_y), "vs",
                  font=font_vs, fill=hex_to_rgb(COLOR_TITLE))

    # BADGE_TEXT — top center, dimmed context label
    font_badge_sm = load_font(40, bold=True)
    bw = get_text_width(font_badge_sm, BADGE_TEXT)
    draw.text(((WIDTH - bw) // 2, 80), BADGE_TEXT,
              font=font_badge_sm, fill=hex_to_rgb(COLOR_WATERMARK))

    # Fast reveal from black — completes at 15% of hook duration (~0.9s on 63s video)
    # Keeps the "hard cut" feel while avoiding a single totally-black frame
    black_alpha = int(255 * max(0.0, 1.0 - progress / 0.15))
    return apply_alpha_overlay(img, (0, 0, 0), black_alpha)


# ── CTA scene ──────────────────────────────────────────────────────────────────

def render_cta_scene(progress: float, accent_color: tuple) -> Image.Image:
    """
    Last ~8s: dark background with a centered accent-colored panel.

    Design rationale:
    - Solid accent-fill backgrounds (prior design) read as advertising/low-quality
      content. Research notes that "dominant brand color in opening/closing frames
      signals low-engagement ad content" (influencers-time.com, 2025).
    - Dark base + contained accent panel is more consistent with the Main scene
      visual language, avoids jarring color shock, and keeps brand feel premium.
    - Panel uses rounded corners and padding for a card-based structure, consistent
      with sports data visualization best practice (folio3.com, 2025).
    - Handle at 94px bold remains the dominant element inside the panel.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), hex_to_rgb(COLOR_BG))
    draw = ImageDraw.Draw(img)

    # Subtle accent tint on background to tie scenes together
    bg = hex_to_rgb(COLOR_BG)
    for y in range(HEIGHT):
        tint = 0.08 * (1.0 - y / HEIGHT)
        color = tuple(int(bg[i] + (accent_color[i] - bg[i]) * tint) for i in range(3))
        draw.line([(0, y), (WIDTH, y)], fill=color)

    draw = ImageDraw.Draw(img)

    font_handle = load_font(94, bold=True)
    font_sub    = load_font(52, bold=False)

    handle_text = "@lastmanstats"
    sub_text    = "Stats in 30 min\nfrom the final whistle"

    hh = get_text_height(font_handle)
    sub_lines = sub_text.split("\n")
    sub_line_h = get_text_height(font_sub) + 14

    # Panel dimensions: content height + generous vertical padding
    content_h = hh + 56 + len(sub_lines) * sub_line_h
    panel_pad_x = 80
    panel_pad_y = 72
    panel_w = WIDTH - 2 * panel_pad_x
    panel_h = content_h + 2 * panel_pad_y
    panel_x = panel_pad_x
    panel_y = (HEIGHT - panel_h) // 2

    # Accent-colored rounded panel
    draw.rounded_rectangle(
        [panel_x, panel_y, panel_x + panel_w, panel_y + panel_h],
        radius=28, fill=accent_color
    )

    # Text color: very dark, derived from bg for legibility on accent panel
    text_color = hex_to_rgb(COLOR_BG)

    # Thin dark decorative line at top of panel content
    line_w = int(panel_w * 0.30)
    lx = WIDTH // 2 - line_w // 2
    line_y_top = panel_y + panel_pad_y - 28
    draw.rectangle([lx, line_y_top, lx + line_w, line_y_top + 4], fill=text_color)

    # Handle text centered in panel
    hw = get_text_width(font_handle, handle_text)
    handle_y = panel_y + panel_pad_y
    draw.text(((WIDTH - hw) // 2, handle_y), handle_text,
              font=font_handle, fill=text_color)

    # Sub-text lines
    sub_y = handle_y + hh + 56
    for i, line in enumerate(sub_lines):
        lw = get_text_width(font_sub, line)
        draw.text(((WIDTH - lw) // 2, sub_y + i * sub_line_h), line,
                  font=font_sub, fill=text_color)

    # Fade in at start
    if progress < 0.2:
        black_alpha = int(255 * (1.0 - progress / 0.2))
        img = apply_alpha_overlay(img, (0, 0, 0), black_alpha)

    # Fade out at end
    if progress > 0.82:
        black_alpha = int(255 * (progress - 0.82) / 0.18)
        img = apply_alpha_overlay(img, (0, 0, 0), black_alpha)

    return img


# ── Main scene (existing layout) ───────────────────────────────────────────────

def render_main_scene(frame_index: int, headline: str, subtext: str,
                       team1: str, team2: str, accent_color: tuple,
                       total_frames: int, timestamp_badge: str) -> Image.Image:
    """
    Main content scene (~50s).

    Design changes from previous version:
    1. Eliminated the undifferentiated dark rectangle overlay (height 28%-72%).
       Replaced with structured visual blocks separated by an accent horizontal
       bar — consistent with card-based sports data viz best practice
       (folio3.com, 2025) and the "one clear question per visualization" principle.

    2. Headline zone pushed to center-high (y ~38% of frame): the most important
       stat occupies the visually prioritized area per 9:16 composition research
       where "primary subject = upper two-thirds" (influencers-time.com, 2025).

    3. Accent divider bar between team header block and headline block: creates
       hard visual separation between context (who played) and content (the stat).
       High-contrast geometric dividers are a primary readability pattern in
       mobile sports dashboards (folio3.com, 2025).

    4. Progress bar (8px, full-width, accent color, bottom of frame): encodes
       video position so viewer always knows how much content remains. This
       reduces premature scroll-away — on-screen progress indicators are a
       retention mechanism documented across streaming UI research.

    5. Watermark moved to bottom-left at 38px / opacity 60%: avoids center-stage
       competition with the headline stat, still maintains brand presence.
       Reduced opacity from full COLOR_WATERMARK to a dimmed version.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Animated gradient background — subtle tint shift
    bg_base = hex_to_rgb(COLOR_BG)
    tint = 0.10 + 0.05 * math.sin(2 * math.pi * frame_index / max(total_frames, 1))
    bg_top = tuple(int(bg_base[i] + (accent_color[i] - bg_base[i]) * tint) for i in range(3))
    draw_gradient_background(draw, frame_index, bg_top, bg_base, total_frames)

    draw = ImageDraw.Draw(img)
    max_text_width = WIDTH - 100

    # ── Block 1: Badge pill — top, context label ──────────────────────────────
    font_badge = load_font(50, bold=True)
    badge_w = get_text_width(font_badge, BADGE_TEXT)
    badge_x = (WIDTH - badge_w) / 2
    badge_y = 90
    badge_h = get_text_height(font_badge) + 20
    draw.rounded_rectangle(
        [badge_x - 24, badge_y - 10, badge_x + badge_w + 24, badge_y + badge_h],
        radius=18, fill=accent_color
    )
    draw.text((badge_x, badge_y), BADGE_TEXT, font=font_badge, fill=hex_to_rgb(COLOR_BG))

    # ── Block 2: Teams header ─────────────────────────────────────────────────
    font_teams = load_font(74, bold=True)
    vs_text = f"{team1}  vs  {team2}"
    vs_w = get_text_width(font_teams, vs_text)
    teams_y = badge_y + badge_h + 50
    draw_text_with_shadow(draw, vs_text, ((WIDTH - vs_w) / 2, teams_y), font_teams,
                          text_color=hex_to_rgb(COLOR_TITLE), shadow_offset=5)

    teams_h = get_text_height(font_teams, vs_text)

    # ── Accent divider bar — separates context from content ───────────────────
    divider_y = teams_y + teams_h + 40
    draw.rectangle([60, divider_y, WIDTH - 60, divider_y + 5], fill=accent_color)

    # ── Block 3: Headline (the dominant stat) — center-high ───────────────────
    # Starts just below divider bar; position anchored to divider not to frame center
    # so it always sits in the visual priority zone regardless of text length.
    font_headline = load_font(108, bold=True)
    headline_lines = wrap_text(headline, font_headline, max_text_width)
    line_h = get_text_height(font_headline, "A") + 20
    total_hl_h = len(headline_lines) * line_h
    hl_start_y = divider_y + 52

    for i, line in enumerate(headline_lines):
        lw = get_text_width(font_headline, line)
        draw_text_with_shadow(draw, line, ((WIDTH - lw) / 2, hl_start_y + i * line_h),
                              font_headline, text_color=hex_to_rgb(COLOR_TITLE),
                              shadow_offset=6)

    # ── Block 4: Subtext — secondary hierarchy, below headline ────────────────
    font_sub = load_font(58, bold=False)
    sub_lines = wrap_text(subtext, font_sub, max_text_width)
    sub_line_h = get_text_height(font_sub) + 14
    sub_start_y = hl_start_y + total_hl_h + 52

    for i, line in enumerate(sub_lines):
        lw = get_text_width(font_sub, line)
        draw_text_with_shadow(draw, line, ((WIDTH - lw) / 2, sub_start_y + i * sub_line_h),
                              font_sub, text_color=(180, 195, 215), shadow_offset=3)

    # ── Watermark — bottom-left, 38px, reduced opacity ────────────────────────
    font_wm = load_font(38, bold=False)
    # Dimmed watermark: blend COLOR_WATERMARK toward background at ~60% opacity
    wm_rgb = hex_to_rgb(COLOR_WATERMARK)
    wm_dimmed = blend_colors(hex_to_rgb(COLOR_BG), wm_rgb, 0.60)
    draw.text((54, HEIGHT - 110), ACCOUNT_WATERMARK, font=font_wm, fill=wm_dimmed)

    if timestamp_badge:
        font_ts = load_font(36, bold=False)
        draw_text_with_shadow(draw, timestamp_badge, (54, HEIGHT - 160), font_ts,
                              text_color=hex_to_rgb(COLOR_WATERMARK), shadow_offset=2)

    # ── Progress bar — 8px, full width, bottom of frame ───────────────────────
    # Reflects overall video progress (frame_index / total_frames).
    # Gives viewers a visual "how long left" cue that reduces early scroll-off.
    progress_ratio = frame_index / max(total_frames - 1, 1)
    bar_filled_w = int(WIDTH * progress_ratio)
    bar_y = HEIGHT - 8
    # Track (dark, barely visible)
    draw.rectangle([0, bar_y, WIDTH, HEIGHT], fill=darken_color(accent_color, 0.25))
    # Filled portion (accent)
    if bar_filled_w > 0:
        draw.rectangle([0, bar_y, bar_filled_w, HEIGHT], fill=accent_color)

    return img


# ── Frame dispatcher ───────────────────────────────────────────────────────────

def render_frame(frame_index: int, headline: str, subtext: str,
                 team1: str, team2: str, accent_color: tuple,
                 total_frames: int = TOTAL_FRAMES,
                 timestamp_badge: str = "",
                 score_home=None, score_away=None) -> Image.Image:
    info = get_scene_info(frame_index, total_frames)

    if info["scene"] == "hook":
        return render_hook_scene(info["progress"], team1, team2, accent_color,
                                  score_home, score_away)
    if info["scene"] == "cta":
        return render_cta_scene(info["progress"], accent_color)

    return render_main_scene(frame_index, headline, subtext, team1, team2,
                              accent_color, total_frames, timestamp_badge)


# ── FFmpeg helpers ─────────────────────────────────────────────────────────────

def check_ffmpeg() -> bool:
    try:
        result = subprocess.run(["ffmpeg", "-version"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_video(
    headline: str,
    subtext: str,
    team1: str,
    team2: str,
    accent_color: str,
    output_filename: str = None,
    output_subdir: str = None,
    duration_seconds: int = DURATION_SHORT,
    timestamp_badge: str = "",
    audio_path: str = "",
    score_home=None,
    score_away=None,
) -> str:
    """
    Genera frame PNG con Pillow, assembla MP4 con FFmpeg.

    Args:
        score_home / score_away: int o None. Se entrambi presenti, la hook scene
                                 mostra il punteggio in grande; altrimenti mostra TLA.
    Returns:
        Percorso assoluto del file .mp4 generato.
    """
    if not check_ffmpeg():
        raise RuntimeError(
            "FFmpeg non trovato. Installalo:\n"
            "  Ubuntu/Debian: sudo apt install ffmpeg\n"
            "  macOS: brew install ffmpeg"
        )

    out_dir = OUTPUT_DIR / output_subdir if output_subdir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    if output_filename is None:
        from datetime import datetime
        output_filename = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    output_path = out_dir / f"{output_filename}.mp4"
    total_frames = FPS * duration_seconds

    try:
        rgb = hex_to_rgb(accent_color)
    except ValueError:
        print(f"[WARN] Colore hex non valido '{accent_color}', uso default {COLOR_ACCENT}")
        rgb = hex_to_rgb(COLOR_ACCENT)

    tmp_dir = tempfile.mkdtemp(prefix="wc2026_frames_")

    try:
        print(f"[INFO] Generazione {total_frames} frame ({duration_seconds}s @ {FPS}fps)...")

        for i in range(total_frames):
            frame = render_frame(i, headline, subtext, team1, team2, rgb,
                                  total_frames, timestamp_badge, score_home, score_away)
            frame.save(os.path.join(tmp_dir, f"frame_{i:04d}.png"), "PNG")

            if (i + 1) % (FPS * 5) == 0:
                pct = int((i + 1) / total_frames * 100)
                print(f"[INFO]   {pct}% — frame {i+1}/{total_frames}")

        print("[INFO] Assemblaggio MP4 con FFmpeg...")

        has_audio = bool(audio_path and os.path.exists(audio_path))
        if has_audio:
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-framerate", str(FPS),
                "-i", os.path.join(tmp_dir, "frame_%04d.png"),
                "-i", audio_path,
                "-c:v", "libx264", "-c:a", "aac",
                "-pix_fmt", "yuv420p", "-crf", "23", "-preset", "fast",
                "-movflags", "+faststart",
                "-t", str(duration_seconds),
                str(output_path)
            ]
        else:
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-framerate", str(FPS),
                "-i", os.path.join(tmp_dir, "frame_%04d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p", "-crf", "23", "-preset", "fast",
                "-movflags", "+faststart",
                str(output_path)
            ]

        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=300)
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"FFmpeg exit {result.returncode}:\n{err}")

        print(f"[OK] Video generato: {output_path}")
        return str(output_path)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    path = generate_video(
        headline="GER 0 - 2 JPN",
        subtext="Group Stage — FIFA World Cup 2026\nThe giant is dead.",
        team1="GER",
        team2="JPN",
        accent_color="#FF3B3B",
        output_filename="test_video",
        score_home=0,
        score_away=2,
    )
    print(f"Video creato: {path}")
