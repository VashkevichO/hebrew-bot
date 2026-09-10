"""Генерация озвучки инфинитивов глаголов (голос Hila, кэш по md5)."""
import asyncio
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")
from utils.tts import generate_audio
from utils.verbs import load_verbs


async def main():
    ok = 0
    errors = []
    for v in load_verbs():
        try:
            path = await generate_audio(v["infinitive"])
            print(f"OK {v['infinitive']} -> {path.name}")
            ok += 1
        except Exception as e:
            errors.append((v["infinitive"], str(e)))
            print(f"ERR {v['infinitive']}: {e}")
        await asyncio.sleep(0.4)
    print(f"\nГотово: {ok}, ошибок: {len(errors)}")
    for w, e in errors:
        print("  ", w, e)


if __name__ == "__main__":
    asyncio.run(main())
