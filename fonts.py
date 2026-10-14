# -*- coding: utf-8 -*-
"""알림 창 글씨체. fonts 폴더의 .ttf/.otf 를 설치 없이 이 프로그램 안에서만 불러 쓴다.
없거나 못 불러오면 윈도우 기본 「맑은 고딕」으로 물러선다."""
import ctypes
import glob
import os

import store

FALLBACK = "맑은 고딕"
# 학교안심 서체: 파일 이름에 key 가 있으면 보여 줄 이름과, 윈도우에 등록되는 글씨체 이름.
# 윈도우는 이 서체를 영문이 아니라 한글 이름(「학교안심 우주 R」)으로 등록한다.
_KNOWN = (("Eunhasu", "학교안심 은하수", "학교안심 은하수 R"),
          ("Wooju", "학교안심 우주", "학교안심 우주 R"),
          ("Jiugae", "학교안심 지우개", "학교안심 지우개 R"))
_loaded = None        # [(보이는 이름, 윈도우에 등록된 글씨체 이름)]


def _load():
    global _loaded
    if _loaded is not None:
        return _loaded
    _loaded = []
    try:
        from PIL import ImageFont
        files = sorted(glob.glob(os.path.join(store.resource("fonts"), "*.[tToO][tT][fF]")))
        seen = set()
        for f in files:
            fam = ImageFont.truetype(f, 20).getname()[0]
            if fam in seen:            # ttf 와 otf 가 같이 있으면 한 번만
                continue
            # FR_PRIVATE(0x10): 이 프로그램에서만 보이고, 윈도우에 설치되지 않는다.
            if ctypes.windll.gdi32.AddFontResourceExW(f, 0x10, 0):
                seen.add(fam)
                name = os.path.basename(f)
                label, gdi = next(((l, g) for key, l, g in _KNOWN if key in name), (fam, fam))
                _loaded.append((label, gdi))
    except Exception as e:
        store.log("글씨체 불러오기 실패: %r" % e)
    return _loaded


def choices():
    """고를 수 있는 글씨체 [(보이는 이름, 글씨체)]. 맨 앞은 기본 글씨체."""
    return [("기본(맑은 고딕)", FALLBACK)] + _load()


def family(choice=""):
    """choice(저장된 글씨체)가 쓸 수 있으면 그것, 아니면 기본. 비어 있으면 첫 번째 학교안심 서체."""
    avail = _load()
    if choice == FALLBACK:
        return FALLBACK
    for _label, fam in avail:
        if fam == choice:
            return fam
    return avail[0][1] if avail and not choice else FALLBACK
