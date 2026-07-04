from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "core" / "static" / "core" / "images" / "icons"
THEME_COLOR = "#18324a"
TEXT_COLOR = "#ffffff"


def load_font(size):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def rounded_icon(size, filename, maskable=False):
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    padding = int(size * (0.18 if maskable else 0.08))
    radius = int(size * 0.18)
    draw.rounded_rectangle(
        (padding, padding, size - padding, size - padding),
        radius=radius,
        fill=THEME_COLOR,
    )

    font = load_font(int(size * (0.32 if maskable else 0.38)))
    text = "SP"
    box = draw.textbbox((0, 0), text, font=font)
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    draw.text(
        ((size - text_width) / 2, (size - text_height) / 2 - box[1]),
        text,
        fill=TEXT_COLOR,
        font=font,
    )

    image.save(OUTPUT_DIR / filename)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rounded_icon(192, "social-pressure-icon-192.png")
    rounded_icon(512, "social-pressure-icon-512.png")
    rounded_icon(512, "social-pressure-maskable-512.png", maskable=True)


if __name__ == "__main__":
    main()
