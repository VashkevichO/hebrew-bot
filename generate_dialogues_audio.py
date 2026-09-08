"""Generate audio for dialogue lines (партия 1: диалоги 1-6).

Читает data/dialogues.json, для каждой реплики берёт variant["tts"] (если есть)
или variant["he"], генерирует mp3 через edge-tts (Hila) с кэшем по md5 в assets/sounds/.
"""
import sys
import asyncio
import hashlib
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SOUNDS_DIR = BASE_DIR / "assets" / "sounds"
SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

VOICE = "he-IL-HilaNeural"

with open(DATA_DIR / "dialogues.json", encoding="utf-8") as f:
    data = json.load(f)


def filename_for(text):
    h = hashlib.md5(text.encode()).hexdigest()
    return SOUNDS_DIR / f"{h}.mp3"


async def generate_one(text):
    """Генерирует файл, если его нет в кеше. Возвращает (путь, сгенерировано_или_кэш)."""
    path = filename_for(text)
    if path.exists():
        return path, "cache"
    import edge_tts
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(path))
    return path, "new"


async def generate_all():
    try:
        import edge_tts
    except ImportError:
        print("Install edge-tts: pip install edge-tts")
        return

    total = 0
    new = 0
    cached = 0
    errors = []

    for dlg in data["dialogues"]:
        dlg_id = dlg["id"]
        title = dlg["title_ru"]
        print(f"\n== {dlg_id} · {title} ==")
        for line in dlg["lines"]:
            for vi, variant in enumerate(line["variants"]):
                text = variant.get("tts") or variant["he"]
                try:
                    path, status = await generate_one(text)
                    total += 1
                    if status == "new":
                        new += 1
                    else:
                        cached += 1
                    note = variant.get("note", "")
                    print(f"  [{status:>5}] {text}  ({note})")
                except Exception as e:
                    errors.append((text, str(e)))
                    print(f"  [ ERR] {text}: {e}")
                await asyncio.sleep(0.3)

    print(f"\n=== ИТОГО: {total} реплик, новых: {new}, из кеша: {cached}, ошибок: {len(errors)} ===")
    if errors:
        for text, err in errors:
            print(f"  ERR {text}: {err}")


if __name__ == "__main__":
    asyncio.run(generate_all())