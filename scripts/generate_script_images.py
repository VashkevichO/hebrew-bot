import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent.parent
FONT_PATH = BASE / "assets" / "fonts" / "GveretLevin-Regular.ttf"
OUT_DIR = BASE / "assets" / "script"
ALPHABET_JSON = BASE / "data" / "alphabet.json"

OUT_DIR.mkdir(parents=True, exist_ok=True)

font = ImageFont.truetype(str(FONT_PATH), 200)

with open(ALPHABET_JSON, encoding="utf-8") as f:
    data = json.load(f)

for letter in data["letters"]:
    lid = letter["id"]
    name_en = letter["name_en"]
    ch = letter["letter"]

    img = Image.new("RGBA", (300, 300), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    bbox = draw.textbbox((0, 0), ch, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (300 - w) / 2 - bbox[0]
    y = (300 - h) / 2 - bbox[1]
    draw.text((x, y), ch, font=font, fill=(0, 0, 0, 255))

    filename = f"{name_en.replace(' ', '_')}.png"
    out_path = OUT_DIR / filename
    img.save(out_path)

    letter["script_image"] = f"script/{filename}"
    print(f"[{lid:2d}] {name_en:12s} -> {filename} ({out_path.stat().st_size} bytes)")

with open(ALPHABET_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("\nDone. alphabet.json updated with script_image fields.")
