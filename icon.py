# -*- coding: utf-8 -*-
"""트레이·exe 아이콘을 그린다(종 모양). 그림 파일을 따로 들고 다니지 않는다."""
from PIL import Image, ImageDraw


def make_image(size=256):
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.22), fill=(31, 84, 168, 255))
    white = (255, 255, 255, 255)
    # 종: 둥근 머리 + 퍼지는 몸통 + 아랫단 + 추
    d.ellipse((s * 0.28, s * 0.20, s * 0.72, s * 0.62), fill=white)
    d.polygon([(s * 0.28, s * 0.42), (s * 0.72, s * 0.42), (s * 0.82, s * 0.70),
               (s * 0.18, s * 0.70)], fill=white)
    d.rounded_rectangle((s * 0.16, s * 0.66, s * 0.84, s * 0.73), radius=int(s * 0.03), fill=white)
    d.ellipse((s * 0.42, s * 0.74, s * 0.58, s * 0.88), fill=(255, 176, 32, 255))
    d.ellipse((s * 0.46, s * 0.12, s * 0.54, s * 0.22), fill=white)
    return img


def save_ico(path):
    make_image(256).save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    import sys
    save_ico(sys.argv[1] if len(sys.argv) > 1 else "app.ico")
