"""Generates audio files for all alphabet letters via TTS."""
import sys
import asyncio
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = Path(__file__).parent / "data"
AUDIO_DIR = Path(__file__).parent / "assets" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

with open(DATA_DIR / "alphabet.json", encoding="utf-8") as f:
    letters = json.load(f)["letters"]


async def generate():
    try:
        import edge_tts
    except ImportError:
        print("Install edge-tts: pip install edge-tts")
        return

    # Russian voice for letter names, Hebrew voice for letter sounds
    ru_voice = "ru-RU-SvetlanaNeural"
    he_voice = "he-IL-HilaNeural"

    for letter in letters:
        name = letter["name_ru"]
        en_name = letter["name_en"]
        sound = letter["sound"]
        audio_name = f"{en_name.lower().replace(' ', '_')}.mp3"
        audio_path = AUDIO_DIR / audio_name

        if audio_path.exists():
            print(f"[OK] {name} — already exists")
            continue

        try:
            text = f"Буква {name}. Звук {sound}" if sound and sound != chr(8212) else f"Буква {name}"
            communicate = edge_tts.Communicate(text, ru_voice)
            await communicate.save(str(audio_path))
            print(f"[OK] {name} — created ({audio_name})")
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"[ERR] {name} — error: {e}")


if __name__ == "__main__":
    asyncio.run(generate())
    print("\nDone!")
