"""
generate_audio.py
Genera un MP3 di voiceover dal testo narration via OpenAI TTS.
Voce: onyx (profonda, da commentatore sportivo — non robotica).
Modello: tts-1 (~€0.002 per clip a 50-60 parole).
Variabile d'ambiente richiesta: OPENAI_API_KEY
Se OPENAI_API_KEY assente, restituisce "" senza errori bloccanti.
"""

import os
import logging

logger = logging.getLogger(__name__)

VOICE = "onyx"
TTS_MODEL = "tts-1"

try:
    import openai as _openai_module
    _openai_available = True
except ImportError:
    _openai_module = None
    _openai_available = False
    logger.warning("openai non installato — audio disabilitato. Esegui: pip install openai")


def generate_audio(narration_text: str, output_path: str) -> str:
    """
    Converte narration_text in MP3 con OpenAI TTS.

    Args:
        narration_text : Testo da vocalizzare (idealmente 50-60 parole).
        output_path    : Percorso assoluto del file MP3 di output.

    Returns:
        output_path se il file è stato creato con successo, "" altrimenti.
    """
    if not _openai_available:
        return ""

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.info("OPENAI_API_KEY non impostata — video senza audio.")
        return ""

    narration_text = narration_text.strip()
    if not narration_text:
        logger.warning("Narration vuota — audio saltato.")
        return ""

    try:
        client = _openai_module.OpenAI(api_key=api_key)
        response = client.audio.speech.create(
            model=TTS_MODEL,
            voice=VOICE,
            input=narration_text,
            response_format="mp3",
        )
        response.stream_to_file(output_path)
        logger.info(f"Audio generato ({VOICE}): {output_path}")
        return output_path
    except Exception as e:
        logger.warning(f"TTS fallito: {e} — video procede senza audio.")
        return ""


if __name__ == "__main__":
    import sys
    test_text = (
        "Germany. Out. In the group stage. "
        "Zero-two. Japan with one of the biggest upsets in World Cup history. "
        "The giant is dead. The numbers don't lie. "
        "Follow Last Man Stats — stats within thirty minutes of the final whistle."
    )
    out = generate_audio(test_text, "/tmp/test_narration.mp3")
    if out:
        print(f"[OK] Audio salvato: {out}")
    else:
        print("[SKIP] OPENAI_API_KEY non impostata o TTS fallito.")
        sys.exit(0)
