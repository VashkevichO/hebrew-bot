"""Generate Hebrew letter audio: just letter name + sound, Hebrew voice only."""
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

# Hebrew names for TTS - proper pronunciation
HEBREW_NAMES = {
    "Alef": "אָלֶף",
    "Bet": "בֵּית",
    "Vet": "בֵית",
    "Gimel": "גִּימֶל",
    "Dalet": "דָּלֶת",
    "He": "הֵא",
    "Vav": "וָו",
    "Zayin": "זַיִן",
    "Het": "חֵית",
    "Tet": "טֵית",
    "Yod": "יוֹד",
    "Kaf": "כַּף",
    "Khaf": "כַף",
    "Khaf Sofit": "כַּף סוֹפִית",
    "Lamed": "לָמֶד",
    "Mem": "מֵם",
    "Mem Sofit": "מֵם סוֹפִית",
    "Nun": "נוּן",
    "Nun Sofit": "נוּן סוֹפִית",
    "Samekh": "סָמֶךְ",
    "Ayin": "עַיִן",
    "Pe": "פֵּא",
    "Fe": "פֵא",
    "Fe Sofit": "פֵא סוֹפִית",
    "Tsadi": "צָדִי",
    "Tsadi Sofit": "צָדִי סוֹפִית",
    "Qof": "קוֹף",
    "Resh": "רֵישׁ",
    "Shin": "שִׁין",
    "Sin": "שִׂין",
    "Tav": "תָּו",
}


async def generate_one(letter, voice="he-IL-HilaNeural"):
    """Generate one letter audio. Returns path or None."""
    en_name = letter["name_en"]
    he_name = HEBREW_NAMES.get(en_name, "")
    sound = letter["sound"]
    audio_name = f"{en_name.lower().replace(' ', '_')}.mp3"
    audio_path = AUDIO_DIR / audio_name

    # Text: letter name + sound example
    if sound and sound != chr(8212):
        # Say letter name, then the letter with a sample vowel sound
        text = f"{he_name}"
    else:
        text = f"{he_name}"

    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(audio_path))
        return audio_path, audio_name
    except Exception as e:
        return None, str(e)


async def generate_all():
    try:
        import edge_tts
    except ImportError:
        print("Install edge-tts: pip install edge-tts")
        return

    voice = "he-IL-HilaNeural"

    for letter in letters:
        en_name = letter["name_en"]
        audio_name = f"{en_name.lower().replace(' ', '_')}.mp3"
        audio_path = AUDIO_DIR / audio_name

        if audio_path.exists():
            audio_path.unlink()

        result, info = await generate_one(letter, voice)
        if result:
            print(f"[OK] {letter['name_ru']} -> {info}")
        else:
            print(f"[ERR] {letter['name_ru']}: {info}")
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(generate_all())
    print("\nDone!")
