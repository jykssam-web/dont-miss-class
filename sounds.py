# -*- coding: utf-8 -*-
"""알림 소리. 윈도우에 기본으로 있는 소리 중에서 고르거나 내 wav 파일을 쓴다."""
import os

try:
    import winsound
except ImportError:          # 윈도우가 아니면 소리 없음
    winsound = None

MEDIA = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Media")
_CANDIDATES = (("차임", "chimes.wav"), ("딩", "ding.wav"), ("알림", "notify.wav"),
               ("화음", "chord.wav"), ("알람", "Alarm01.wav"), ("벨", "Ring01.wav"),
               ("팡파르", "tada.wav"))


def builtin():
    """[(이름, 전체 경로)] — 이 PC에 실제로 있는 것만."""
    out = []
    for label, fn in _CANDIDATES:
        p = os.path.join(MEDIA, fn)
        if os.path.isfile(p):
            out.append((label, p))
    return out


def label_for(path):
    if not path:
        return "소리 없음"
    for label, p in builtin():
        if os.path.normcase(p) == os.path.normcase(path):
            return label
    return "내 파일: " + os.path.basename(path)


def play(path):
    """path 가 비면 아무것도 안 한다. 파일이 없어도 죽지 않는다."""
    if not path or winsound is None or not os.path.isfile(path):
        return
    try:
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except RuntimeError:
        pass


def stop():
    if winsound is not None:
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except RuntimeError:
            pass
