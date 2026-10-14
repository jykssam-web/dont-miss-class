# -*- coding: utf-8 -*-
"""알림 창 글씨체. fonts 폴더에 .ttf/.otf 파일이 있으면 설치 없이 이 프로그램 안에서만 불러 쓴다.
없거나 못 불러오면 윈도우 기본 「맑은 고딕」으로 물러선다."""
import ctypes
import glob
import os

import store

FALLBACK = "맑은 고딕"
_family = None


def family():
    """쓸 글씨체 이름. 처음 한 번만 불러온다."""
    global _family
    if _family is not None:
        return _family
    _family = FALLBACK
    try:
        files = sorted(glob.glob(os.path.join(store.resource("fonts"), "*.[tToO][tT][fF]")))
        if not files:
            return _family
        # 굵은 글씨를 따로 둔 파일이 여럿이면 첫 파일의 이름을 쓴다.
        from PIL import ImageFont
        name = ImageFont.truetype(files[0], 20).getname()[0]
        loaded = 0
        for f in files:
            # FR_PRIVATE(0x10): 이 프로그램에서만 보이고, 윈도우에 설치되지 않는다.
            loaded += ctypes.windll.gdi32.AddFontResourceExW(f, 0x10, 0)
        if loaded:
            _family = name
    except Exception as e:
        store.log("글씨체 불러오기 실패: %r" % e)
    return _family
