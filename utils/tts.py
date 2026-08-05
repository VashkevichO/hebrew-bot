import hashlib
from pathlib import Path

SOUNDS_DIR = Path(__file__).parent.parent / "assets" / "sounds"
SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

# Основной голос — Hila (женский, иврит)
VOICE = "he-IL-HilaNeural"
# Запасной — Avri (мужской)
VOICE_ALT = "he-IL-AvriNeural"


def _filename(text):
    h = hashlib.md5(text.encode()).hexdigest()
    return SOUNDS_DIR / f"{h}.mp3"


async def generate_audio(text, voice=VOICE):
    """Генерирует аудиофайл, если его нет в кеше. Возвращает путь к файлу."""
    path = _filename(text)
    if path.exists():
        return path

    try:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(path))
        return path
    except ImportError:
        raise ImportError(
            "edge-tts не установлен. Выполни: pip install edge-tts"
        )
    except Exception as e:
        raise RuntimeError(f"Ошибка TTS: {e}")


async def generate_letter_audio(letter_name, letter_char, voice=VOICE):
    """Буква: называем её имя и произносим звук."""
    text = f"{letter_char}. {letter_name}"
    return await generate_audio(text, voice)


async def generate_word_audio(word_he, voice=VOICE):
    """Произносим слово."""
    return await generate_audio(word_he, voice)
