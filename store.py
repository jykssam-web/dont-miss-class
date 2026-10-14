# -*- coding: utf-8 -*-
"""설정·시간표 저장. %APPDATA%\\놓치지마수업\\settings.json 한 파일.
환경변수 DMC_HOME 이 있으면 그 폴더를 쓴다(검사용)."""
import json
import os
import sys
import threading

APP_NAME = "놓치지마수업"
_lock = threading.Lock()

DEFAULTS = {
    "configured": False,
    "enabled": True,
    "school_name": "",
    "school_code": "",
    "local_code": "",
    "teacher": "",            # 내 이름(전체). 컴시간은 두 글자로 줄여 준다
    "lesson_min": 45,
    "times": [],              # 교시별 시작 시각 ["08:50", …]
    "sound": "",              # 소리 파일 경로. 비면 소리 없음
    "font": "",               # 알림 글씨체. 비면 기본 서체(학교안심)
    "my_tid": None,           # 컴시간 교사 번호(같은 이름 속에서 나를 가른다)
    "my_sample": None,        # 내가 고른 대표 수업 {"subject","room"}. 번호가 바뀌어도 나를 다시 찾는 열쇠
    "my_subjects": [],        # 이름이 같은 선생님과 가를 내 과목. 비면 이름만으로
    "exclude_rooms": "",      # 이름이 겹쳐 섞인 남의 반 「2-3, 3-1」. 내 수업에서 뺀다
    "autostart": True,
    "cache": None,            # 마지막으로 받은 컴시간 시간표
    "fetched_at": "",
    "manual": {},             # 직접 입력 시간표 {"요일(0=월)-교시": "1-4 수학"}
}


def home():
    base = os.environ.get("DMC_HOME") or os.path.join(
        os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
    os.makedirs(base, exist_ok=True)
    return base


def _path():
    return os.path.join(home(), "settings.json")


def load():
    data = dict(DEFAULTS)
    try:
        with open(_path(), encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            data.update(raw)
        if data["sound"] == "none":          # 처음 만든 옛 값
            data["sound"] = ""
    except (OSError, ValueError):
        pass
    return data


def save(data):
    """통째로 쓴다. 쓰다 끊겨도 옛 파일이 남도록 임시 파일을 거친다."""
    with _lock:
        tmp = _path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, _path())


def update(**kw):
    data = load()
    data.update(kw)
    save(data)
    return data


def log(msg):
    """창이 없는 프로그램이라 문제를 파일에 남긴다."""
    try:
        from datetime import datetime
        with open(os.path.join(home(), "log.txt"), "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (datetime.now().strftime("%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def resource(name):
    """묶음(exe) 안이든 소스 폴더든 같은 이름으로 파일을 찾는다."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)
