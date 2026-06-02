"""
video_generator.py
Scopo: Genera un video MP4 9:16 (1080x1920, 15 secondi) con grafica testo
       e sfondo a gradiente animato. Non utilizza clip video di partite reali.
Dipendenze: Pillow, FFmpeg installato nel sistema (chiamato via subprocess)
Uso: python video_generator.py  oppure  from video_generator import generate_video
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
FPS = 30
DURATION_SECONDS = 15
TOTAL_FRAMES = FPS * DURATION_SECONDS

ACCOUNT_WATERMARK = "@lastmanstats"
BADGE_TEXT = "WORLD CUP 2026"

# Palette A — Neo Stadio
COLOR_BG        = "#0D1117"   # Abisso notturno (sfondo)
COLOR_TITLE     = "#F0F4F8"   # Bianco ghiaccio (titoli)
COLOR_ACCENT    = "#00FF87"   # Verde plasma (badge / accento brand)
COLOR_WATERMARK = "#8892A4"   # Grigio sidereo (watermark)

DURATION_SHORT = 63   # TikTok (>60s richiesti per Creator Rewards monetization)
DURATION_LONG  = 90   # YouTube Shorts

OUTPUT_DIR = Path(__file__).parent / "output"


def hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Colore hex non valido: {hex_color}")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def blend_colors(color1: tuple, color2: tuple, t: float) -> tuple:
    return tuple(int(color1[i] + (color2[i] - color1[i]) * t) for i in range(3))


def darken_color(color: tuple, factor: float = 0.35) -> tuple:
    return tuple(max(0, int(c * factor)) for c in color)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    local_fonts = Path(__file__).parent / "fonts"
    if bold:
        candidates = [
            # Cartella locale fonts/ (GitHub Actions la popola nel workflow)
            str(local_fonts / "BebasNeue-Regular.ttf"),
            # Percorsi sistema Linux
            "/usr/share/fonts/truetype/bebas-neue/BebasNeue-Regular.ttf",
            "/usr/share/fonts/opentype/bebas-neue/BebasNeue-Regular.otf",
            "/home/ubuntu/.local/share/fonts/BebasNeue-Regular.ttf",
            "/home/runner/.local/share/fonts/BebasNeue-Regular.ttf",
            "/home/opc/.local/share/fonts/BebasNeue-Regular.ttf",
            # fallback
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
    else:
        candidates = [
            # Cartella locale fonts/ (GitHub Actions la popola nel workflow)
            str(local_fonts / "Inter-Regular.ttf"),
            # Percorsi sistema Linux
            "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
            "/usr/share/fonts/opentype/inter/Inter-Regular.ttf",
            "/home/ubuntu/.local/share/fonts/Inter-Regular.ttf",
            "/home/runner/.local/share/fonts/Inter-Regular.ttf",
            "/home/opc/.local/share/fonts/Inter-Regular.ttf",
            # fallback
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

    print(f"[WARN] Nessun font TrueType trovato — uso font di default (qualita' ridotta).")
    return ImageFont.load_default()


def draw_gradient_background(draw: ImageDraw.Draw, frame_index: int,
                              color_a: tuple, color_b: tuple,
                              total_frames: int = TOTAL_FRAMES) -> None:
    phase = frame_index / total_frames
    mid_offset = 0.5 + 0.2 * math.sin(2 * math.pi * phase)

    for y in range(HEIGHT):
        t = y / HEIGHT
        t_adj = max(0.0, min(1.0, t / mid_offset)) if mid_offset > 0 else t
        color = blend_colors(color_a, color_b, t_adj)
        draw.line([(0, y), (WIDTH, y)], fill=color)


def draw_text_with_shadow(draw: ImageDraw.Draw, text: str, position: tuple,
                           font, text_color: tuple = (255, 255, 255),
                           shadow_color: tuple = (0, 0, 0),
                           shadow_offset: int = 4) -> None:
    x, y = position
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=text_color)


def wrap_text(text: str, font, max_width: int) -> list:
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = (current_line + " " + word).strip()
        try:
            line_width = font.getlength(test_line)
        except AttributeError:
            line_width = font.getsize(test_line)[0]

        if line_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines if lines else [text]


def get_text_height(font, text: str = "Ag") -> int:
    try:
        bbox = font.getbbox(text)
        return bbox[3] - bbox[1]
    except AttributeError:
        return font.getsize(text)[1]


def render_frame(frame_index: int, headline: str, subtext: str,
                 team1: str, team2: str, accent_color: tuple,
                 total_frames: int = TOTAL_FRAMES,
                 timestamp_badge: str = "") -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    bg_base = hex_to_rgb(COLOR_BG)
    phase_bg = frame_index / total_frames
    tint = 0.10 + 0.05 * math.sin(2 * math.pi * phase_bg)
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
    try:
        badge_w = font_badge.getlength(BADGE_TEXT)
    except AttributeError:
        badge_w = font_badge.getsize(BADGE_TEXT)[0]

    badge_x = (WIDTH - badge_w) / 2
    badge_y = 90
    badge_h = get_text_height(font_badge) + 20

    draw.rounded_rectangle(
        [badge_x - 24, badge_y - 10, badge_x + badge_w + 24, badge_y + badge_h],
        radius=18,
        fill=accent_color
    )
    draw.text((badge_x, badge_y), BADGE_TEXT, font=font_badge, fill=hex_to_rgb(COLOR_BG))

    font_teams = load_font(74, bold=True)
    vs_text = f"{team1}  vs  {team2}"
    try:
        vs_w = font_teams.getlength(vs_text)
    except AttributeError:
        vs_w = font_teams.getsize(vs_text)[0]

    vs_x = (WIDTH - vs_w) / 2
    draw_text_with_shadow(draw, vs_text, (vs_x, 270), font_teams,
                          text_color=hex_to_rgb(COLOR_TITLE), shadow_offset=5)

    font_headline = load_font(108, bold=True)
    headline_lines = wrap_text(headline, font_headline, max_text_width)
    line_h = get_text_height(font_headline, "A") + 20
    total_hl_h = len(headline_lines) * line_h
    hl_start_y = (HEIGHT - total_hl_h) // 2 - 60

    for i, line in enumerate(headline_lines):
        try:
            lw = font_headline.getlength(line)
        except AttributeError:
            lw = font_headline.getsize(line)[0]
        lx = (WIDTH - lw) / 2
        ly = hl_start_y + i * line_h
        draw_text_with_shadow(draw, line, (lx, ly), font_headline,
                              text_color=hex_to_rgb(COLOR_TITLE), shadow_offset=6)

    font_sub = load_font(58, bold=False)
    sub_lines = wrap_text(subtext, font_sub, max_text_width)
    sub_line_h = get_text_height(font_sub) + 14
    sub_start_y = hl_start_y + total_hl_h + 44

    for i, line in enumerate(sub_lines):
        try:
            lw = font_sub.getlength(line)
        except AttributeError:
            lw = font_sub.getsize(line)[0]
        lx = (WIDTH - lw) / 2
        ly = sub_start_y + i * sub_line_h
        draw_text_with_shadow(draw, line, (lx, ly), font_sub,
                              text_color=(180, 195, 215), shadow_offset=3)

    font_wm = load_font(46, bold=False)
    try:
        wm_w = font_wm.getlength(ACCOUNT_WATERMARK)
    except AttributeError:
        wm_w = font_wm.getsize(ACCOUNT_WATERMARK)[0]

    wm_x = (WIDTH - wm_w) / 2
    draw_text_with_shadow(draw, ACCOUNT_WATERMARK, (wm_x, HEIGHT - 130), font_wm,
                          text_color=hex_to_rgb(COLOR_WATERMARK), shadow_offset=2)

    # Timestamp badge: bottom-left, 36px Inter (spec: 24px — scaled up for legibility at ~390px phone width)
    if timestamp_badge:
        font_ts = load_font(36, bold=False)
        draw_text_with_shadow(draw, timestamp_badge, (40, HEIGHT - 195), font_ts,
                              text_color=hex_to_rgb(COLOR_WATERMARK), shadow_offset=2)

    return img


def check_ffmpeg() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


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
) -> str:
    """
    Genera frame PNG con Pillow, assembla MP4 con FFmpeg.

    Args:
        headline         : Testo principale (es. "BRA 2 - 1 ARG")
        subtext          : Testo secondario (es. "Quarti di Finale — FIFA World Cup 2026")
        team1            : Codice squadra 1 (es. "BRA")
        team2            : Codice squadra 2 (es. "ARG")
        accent_color     : Colore hex accento (es. "#009C3B")
        output_filename  : Nome file senza estensione. Default: timestamp.
        output_subdir    : Sottocartella dentro output/ (es. "2026-06-11").
        duration_seconds : Durata video in secondi (DURATION_SHORT=15 TikTok,
                           DURATION_LONG=62 YouTube Shorts).

    Returns:
        Percorso assoluto del file .mp4 generato.
    """
    if not check_ffmpeg():
        raise RuntimeError(
            "FFmpeg non trovato. Installalo:\n"
            "  Oracle Linux 8: sudo dnf install ffmpeg\n"
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
            frame = render_frame(i, headline, subtext, team1, team2, rgb, total_frames, timestamp_badge)
            frame_path = os.path.join(tmp_dir, f"frame_{i:04d}.png")
            frame.save(frame_path, "PNG")

            if (i + 1) % (FPS * 5) == 0:
                pct = int((i + 1) / total_frames * 100)
                print(f"[INFO]   {pct}% — frame {i+1}/{total_frames}")

        print("[INFO] Assemblaggio MP4 con FFmpeg...")

        has_audio = bool(audio_path and os.path.exists(audio_path))
        if has_audio:
            # Audio plays for its duration; video continues silently until duration_seconds.
            # -t clips output to exact target length regardless of audio length.
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-framerate", str(FPS),
                "-i", os.path.join(tmp_dir, "frame_%04d.png"),
                "-i", audio_path,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-pix_fmt", "yuv420p",
                "-crf", "23",
                "-preset", "fast",
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
                "-pix_fmt", "yuv420p",
                "-crf", "23",
                "-preset", "fast",
                "-movflags", "+faststart",
                str(output_path)
            ]

        result = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300
        )

        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"FFmpeg exit {result.returncode}:\n{err}")

        print(f"[OK] Video generato: {output_path}")
        return str(output_path)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    path = generate_video(
        headline="BRASILE VS ARGENTINA",
        subtext="Quarti di Finale — FIFA World Cup 2026\nMetLife Stadium, New Jersey",
        team1="BRA",
        team2="ARG",
        accent_color="#1565C0",
        output_filename="test_video"
    )
    print(f"Video creato: {path}")
