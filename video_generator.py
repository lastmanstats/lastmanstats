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
COLOR_ACCENT    = "#00FF87"
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
            str(local_fonts / "BebasNeue-Regular.ttf"),
            "/usr/share/fonts/truetype/bebas-neue/BebasNeue-Regular.ttf",
            "/usr/share/fonts/opentype/bebas-neue/BebasNeue-Regular.otf",
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
    First ~6s: large score (or TLA vs TLA) on dark background.
    Fades in from black — acts as a pattern-interrupt before the main card.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), hex_to_rgb(COLOR_BG))
    draw = ImageDraw.Draw(img)

    # Accent-tinted gradient — stronger at top
    bg = hex_to_rgb(COLOR_BG)
    for y in range(HEIGHT):
        tint = 0.18 * (1.0 - y / HEIGHT)
        color = tuple(int(bg[i] + (accent_color[i] - bg[i]) * tint) for i in range(3))
        draw.line([(0, y), (WIDTH, y)], fill=color)

    has_score = score_home is not None and score_away is not None

    if has_score:
        font_score = load_font(210, bold=True)
        score_text = f"{score_home} - {score_away}"
        tw = get_text_width(font_score, score_text)
        th = get_text_height(font_score, score_text)
        tx = (WIDTH - tw) // 2
        ty = HEIGHT // 2 - th // 2 - 50

        # Shadow + text
        draw.text((tx + 7, ty + 7), score_text, font=font_score, fill=(0, 0, 0))
        draw.text((tx, ty), score_text, font=font_score, fill=accent_color)

        # Thin accent line under score
        line_y = ty + th + 30
        line_w = int(WIDTH * 0.45)
        lx = (WIDTH - line_w) // 2
        draw.rectangle([lx, line_y, lx + line_w, line_y + 4], fill=accent_color)

        # Team label below line
        font_label = load_font(56, bold=True)
        label = f"{team1}  vs  {team2}"
        lw = get_text_width(font_label, label)
        draw.text(((WIDTH - lw) // 2, line_y + 22), label,
                  font=font_label, fill=hex_to_rgb(COLOR_WATERMARK))
    else:
        # Pre-match: TLA1 / vs / TLA2 stacked
        font_tla = load_font(170, bold=True)
        font_vs  = load_font(60, bold=False)

        tla_h = get_text_height(font_tla, "A")
        vs_h  = get_text_height(font_vs, "vs")
        total_h = tla_h + vs_h + tla_h + 24
        start_y = (HEIGHT - total_h) // 2

        for tla, offset_y in [(team1, 0), (team2, tla_h + vs_h + 24)]:
            tw = get_text_width(font_tla, tla)
            tx = (WIDTH - tw) // 2
            ty = start_y + offset_y
            draw.text((tx + 6, ty + 6), tla, font=font_tla, fill=(0, 0, 0))
            draw.text((tx, ty), tla, font=font_tla, fill=accent_color)

        vw = get_text_width(font_vs, "vs")
        draw.text(((WIDTH - vw) // 2, start_y + tla_h + 8), "vs",
                  font=font_vs, fill=hex_to_rgb(COLOR_TITLE))

    # BADGE_TEXT — small, dimmed, top center
    font_badge_sm = load_font(40, bold=True)
    bw = get_text_width(font_badge_sm, BADGE_TEXT)
    draw.text(((WIDTH - bw) // 2, 80), BADGE_TEXT,
              font=font_badge_sm, fill=hex_to_rgb(COLOR_WATERMARK))

    # Fade in from black — completes at 40% of hook duration
    black_alpha = int(255 * max(0.0, 1.0 - progress * 2.5))
    return apply_alpha_overlay(img, (0, 0, 0), black_alpha)


# ── CTA scene ──────────────────────────────────────────────────────────────────

def render_cta_scene(progress: float, accent_color: tuple) -> Image.Image:
    """Last ~8s: solid accent-color background with handle and CTA text."""
    img = Image.new("RGB", (WIDTH, HEIGHT), accent_color)
    draw = ImageDraw.Draw(img)

    text_color = darken_color(accent_color, 0.10)

    font_handle = load_font(94, bold=True)
    font_sub    = load_font(52, bold=False)

    handle_text = "@lastmanstats"
    sub_text    = "Stats in 30 min\nfrom the final whistle"

    hw = get_text_width(font_handle, handle_text)
    hh = get_text_height(font_handle)
    sub_lines = sub_text.split("\n")
    sub_line_h = get_text_height(font_sub) + 14
    total_h = hh + 44 + len(sub_lines) * sub_line_h

    handle_y = (HEIGHT - total_h) // 2

    # Thin decorative line above handle
    line_w = int(WIDTH * 0.28)
    lx = (WIDTH - line_w) // 2
    draw.rectangle([lx, handle_y - 24, lx + line_w, handle_y - 21], fill=text_color)

    draw.text(((WIDTH - hw) // 2, handle_y), handle_text,
              font=font_handle, fill=text_color)

    sub_y = handle_y + hh + 44
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
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    bg_base = hex_to_rgb(COLOR_BG)
    tint = 0.10 + 0.05 * math.sin(2 * math.pi * frame_index / max(total_frames, 1))
    bg_top = tuple(int(bg_base[i] + (accent_color[i] - bg_base[i]) * tint) for i in range(3))
    draw_gradient_background(draw, frame_index, bg_top, bg_base, total_frames)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rectangle(
        [(0, int(HEIGHT * 0.28)), (WIDTH, int(HEIGHT * 0.72))],
        fill=(0, 0, 0, 130)
    )
    img = img.convert("RGBA")
    img.alpha_composite(overlay)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)

    max_text_width = WIDTH - 100

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

    font_teams = load_font(74, bold=True)
    vs_text = f"{team1}  vs  {team2}"
    vs_w = get_text_width(font_teams, vs_text)
    draw_text_with_shadow(draw, vs_text, ((WIDTH - vs_w) / 2, 270), font_teams,
                          text_color=hex_to_rgb(COLOR_TITLE), shadow_offset=5)

    font_headline = load_font(108, bold=True)
    headline_lines = wrap_text(headline, font_headline, max_text_width)
    line_h = get_text_height(font_headline, "A") + 20
    total_hl_h = len(headline_lines) * line_h
    hl_start_y = (HEIGHT - total_hl_h) // 2 - 60

    for i, line in enumerate(headline_lines):
        lw = get_text_width(font_headline, line)
        draw_text_with_shadow(draw, line, ((WIDTH - lw) / 2, hl_start_y + i * line_h),
                              font_headline, text_color=hex_to_rgb(COLOR_TITLE), shadow_offset=6)

    font_sub = load_font(58, bold=False)
    sub_lines = wrap_text(subtext, font_sub, max_text_width)
    sub_line_h = get_text_height(font_sub) + 14
    sub_start_y = hl_start_y + total_hl_h + 44

    for i, line in enumerate(sub_lines):
        lw = get_text_width(font_sub, line)
        draw_text_with_shadow(draw, line, ((WIDTH - lw) / 2, sub_start_y + i * sub_line_h),
                              font_sub, text_color=(180, 195, 215), shadow_offset=3)

    font_wm = load_font(46, bold=False)
    wm_w = get_text_width(font_wm, ACCOUNT_WATERMARK)
    draw_text_with_shadow(draw, ACCOUNT_WATERMARK, ((WIDTH - wm_w) / 2, HEIGHT - 130),
                          font_wm, text_color=hex_to_rgb(COLOR_WATERMARK), shadow_offset=2)

    if timestamp_badge:
        font_ts = load_font(36, bold=False)
        draw_text_with_shadow(draw, timestamp_badge, (40, HEIGHT - 195), font_ts,
                              text_color=hex_to_rgb(COLOR_WATERMARK), shadow_offset=2)

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
