# -*- coding: utf-8 -*-
"""알림 창 그림. 모서리가 둥글고 그림자가 있는 카드를 그림 한 장으로 그린다.
화면 도구(Tk)는 반투명 모서리를 못 그려서, 윈도우에 그림을 그대로 얹는 방식(native_window.py)을 쓴다."""
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import fonts

TOP = (22, 58, 102)          # 카드 위쪽 색
BOTTOM = (11, 33, 66)        # 카드 아래쪽 색
FG = (255, 255, 255)
SUB = (185, 205, 234)
ACCENT = (255, 176, 32)
ACCENT_TEXT = (58, 37, 0)
SS = 2                       # 크게 그려서 줄이면 가장자리가 매끈해진다


def _font(path, px):
    return ImageFont.truetype(path, int(px))


def _text_size(draw, text, font, stroke=0):
    l, t, r, b = draw.textbbox((0, 0), text, font=font, anchor="ls", stroke_width=stroke)
    return r - l, font.getmetrics()[0] + font.getmetrics()[1]


def render(period, time_text, lesson, family, scale, screen_w):
    """알림 그림을 만든다. (RGBA 그림, 그림자 여백 px)

    scale: 화면 배율(1.0 = 96dpi). screen_w: 화면 가로 px.
    """
    s = scale * SS
    reg_path, bold_path = fonts.file_for(family)
    big_path = bold_path or reg_path
    fake_bold = bold_path is None            # 굵은 파일이 없으면 글자 둘레를 덧그려 굵게 한다

    room = (lesson.get("room") or "").strip()
    subject = (lesson.get("subject") or "").strip()
    big = ("%s 수업입니다" % room) if room else ("%s 수업입니다" % (subject or "수업"))

    margin = int(44 * s)
    card_w = int(min(1000 * scale, screen_w * 0.74) * SS)
    probe = ImageDraw.Draw(Image.new("L", (4, 4)))

    # 큰 글: 카드 안에 들어가는 가장 큰 크기
    size = 88 * s
    while size > 40 * s:
        f = _font(big_path, size)
        stroke = max(1, int(size * 0.018)) if fake_bold else 0
        if _text_size(probe, big, f, stroke)[0] <= card_w - 110 * s:
            break
        size -= 4 * s
    f_big = _font(big_path, size)
    big_stroke = max(1, int(size * 0.018)) if fake_bold else 0
    f_top = _font(reg_path, 32 * s)
    f_sub = _font(reg_path, 40 * s)
    f_pill = _font(big_path, 32 * s)
    f_hint = _font(reg_path, 21 * s)

    top_txt = "%d교시 · %s" % (period, time_text)
    hint = "화면 아무 곳이나 누르면 닫힙니다"
    h_top = _text_size(probe, top_txt, f_top)[1]
    h_big = _text_size(probe, big, f_big, big_stroke)[1]
    h_sub = _text_size(probe, subject, f_sub)[1] if (subject and room) else 0
    pill_w = pill_h = 0
    if lesson.get("replaced"):
        tw, th = _text_size(probe, "바뀐 수업", f_pill, 1 if fake_bold else 0)
        pill_w, pill_h = tw + int(60 * s), th + int(16 * s)
    h_hint = _text_size(probe, hint, f_hint)[1]

    gaps = [int(44 * s), int(14 * s), int(10 * s), int(22 * s), int(30 * s), int(36 * s)]
    card_h = (gaps[0] + h_top + gaps[1] + h_big
              + ((gaps[2] + h_sub) if h_sub else 0)
              + ((gaps[3] + pill_h) if pill_h else 0)
              + gaps[4] + h_hint + gaps[5])

    W, H = card_w + 2 * margin, card_h + 2 * margin
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    radius = int(40 * s)
    box = (margin, margin, margin + card_w - 1, margin + card_h - 1)

    # 그림자: 카드 모양을 번지게 해서 아래로 조금 내린다
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((box[0], box[1] + int(10 * s), box[2], box[3] + int(10 * s)),
                                         radius=radius, fill=(0, 0, 0, 120))
    sh = sh.filter(ImageFilter.GaussianBlur(int(18 * s)))
    img.alpha_composite(sh)

    # 카드: 위에서 아래로 색이 조금 짙어지게
    grad = Image.new("RGBA", (card_w, card_h))
    gd = ImageDraw.Draw(grad)
    for y in range(card_h):
        t = y / max(1, card_h - 1)
        gd.line((0, y, card_w, y), fill=tuple(int(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3)) + (255,))
    mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card_w - 1, card_h - 1), radius=radius, fill=255)
    img.paste(grad, (margin, margin), mask)
    # 가장자리에 아주 옅은 선(빛 받은 느낌)
    ImageDraw.Draw(img).rounded_rectangle(box, radius=radius, outline=(255, 255, 255, 38), width=max(1, int(2 * s / SS)))

    d = ImageDraw.Draw(img)
    cx = margin + card_w // 2
    y = margin + gaps[0]
    d.text((cx, y), top_txt, font=f_top, fill=SUB, anchor="mt")
    y += h_top + gaps[1]
    d.text((cx, y), big, font=f_big, fill=FG, anchor="mt", stroke_width=big_stroke, stroke_fill=FG)
    y += h_big
    if h_sub:
        y += gaps[2]
        d.text((cx, y), subject, font=f_sub, fill=SUB, anchor="mt")
        y += h_sub
    if pill_h:
        y += gaps[3]
        d.rounded_rectangle((cx - pill_w // 2, y, cx + pill_w // 2, y + pill_h), radius=pill_h // 2, fill=ACCENT)
        d.text((cx, y + pill_h // 2), "바뀐 수업", font=f_pill, fill=ACCENT_TEXT, anchor="mm",
               stroke_width=1 if fake_bold else 0, stroke_fill=ACCENT_TEXT)
        y += pill_h
    y += gaps[4]
    d.text((cx, y), hint, font=f_hint, fill=SUB, anchor="mt")

    out = img.resize((W // SS, H // SS), Image.LANCZOS)
    return out, margin // SS
