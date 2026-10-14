# -*- coding: utf-8 -*-
"""컴시간알리미에서 **내 수업**을 가져온다.

컴시간이 주는 것은 반별 시간표다. 그래서 전 학년 전 반을 훑어 담당 교사가 나인
칸만 골라 모은다. 컴시간은 이름을 두 글자로 잘라 주므로(정유경 → 정유) 앞글자로
견준다. 같은 성에 같은 앞 두 글자 선생님이 있으면 남의 수업이 섞일 수 있어서,
처음 설정할 때 골라 낸 수업을 화면에 보여 확인받는다.

비공식 파서(pycomcigan, MIT)다. 컴시간이 구조를 바꾸면 멈춘다. 그래서 못 받아도
프로그램이 죽지 않고, 마지막에 받아 둔 시간표나 손으로 넣은 시간표를 쓴다.
"""
import json
from datetime import date, datetime, timedelta

import store

MIDDLE_REFRESH_MINUTES = 30
HIGH_REFRESH_MINUTES = 40
DAY_NAMES = ("월", "화", "수", "목", "금")


class ComciganError(Exception):
    pass


# ---------------------------------------------------------------- 학교 찾기
def search_school(keyword):
    """학교 이름으로 찾는다. [{"local_code","region","name","school_code"}, …]"""
    try:
        from pycomcigan import get_school_code
    except ImportError:
        raise ComciganError("시간표 라이브러리가 들어 있지 않습니다.")
    try:
        got = get_school_code(keyword or "")
    except Exception as e:
        raise ComciganError("컴시간알리미에 연결하지 못했습니다: %s" % e)
    out = []
    for row in got or []:
        try:
            out.append({"local_code": row[0], "region": row[1],
                        "name": row[2], "school_code": row[3]})
        except (IndexError, TypeError):
            continue
    return out


# ------------------------------------------------------------- 받아 오기
def _fetch_by_code(school_code, local_code=0, school_name="", week_num=0):
    """학교 코드만으로 받는다. 이름은 같은 학교가 여럿일 때 엉뚱한 곳을 집을 수 있다."""
    from pycomcigan import TimeTable
    codes = TimeTable._get_comcigan_codes()
    data = TimeTable._fetch_timetable_data(int(school_code), int(week_num), codes)
    tt = TimeTable.__new__(TimeTable)
    tt._initialize_from_data(data, int(local_code or 0), school_name or "",
                             int(school_code), codes)
    return tt


def _monday(week_num=0):
    today = date.today()
    mon = today - timedelta(days=today.weekday())
    return (mon + timedelta(days=7 * int(week_num or 0))).isoformat()


def fetch(school_name=None, school_code=None, local_code=None, week_num=0):
    """컴시간에서 받아 우리 꼴로 바꾼다. 실패하면 ComciganError.

    {"school", "classes": {"1-5": {요일(1=월): [{"period","subject","teacher","replaced"}]}},
     "받은날", "월요일"}
    """
    cfg = store.load()
    school_name = school_name or cfg["school_name"]
    code = str(school_code if school_code is not None else cfg["school_code"] or "").strip()
    local = str(local_code if local_code is not None else cfg["local_code"] or "").strip()
    if not school_name and not code:
        raise ComciganError("학교를 먼저 고르세요.")
    try:
        from pycomcigan import TimeTable
    except ImportError:
        raise ComciganError("시간표 라이브러리가 들어 있지 않습니다.")

    tt = None
    if code:
        try:
            tt = _fetch_by_code(int(code), int(local or 0), school_name, week_num)
        except Exception as e:
            store.log("코드로 받기 실패, 이름으로 물러섬: %r" % e)
            tt = None
    if tt is None:
        if not school_name:
            raise ComciganError("시간표를 받지 못했습니다. 학교를 다시 골라 주세요.")
        try:
            tt = TimeTable(school_name, week_num=week_num)
        except Exception as e:
            raise ComciganError("시간표를 받지 못했습니다: %s" % e)

    classes = {}
    for grade in range(1, len(tt.timetable)):
        for room in range(1, len(tt.timetable[grade])):
            cells = {}
            for day in range(1, 6):
                try:
                    times = tt.timetable[grade][room][day]
                except (IndexError, TypeError):
                    times = []
                one = []
                for p in times or []:
                    subject = (getattr(p, "subject", "") or "").strip()
                    if not subject:
                        continue
                    one.append({"period": getattr(p, "period", 0),
                                "subject": subject,
                                "teacher": (getattr(p, "teacher", "") or "").strip(),
                                "replaced": bool(getattr(p, "replaced", False))})
                if one:
                    cells[day] = one
            if cells:
                classes["%d-%d" % (grade, room)] = cells
    if not classes:
        raise ComciganError("시간표가 비어 있습니다. 학교를 확인하세요.")
    return {"school": school_name, "week": week_num, "classes": classes,
            "받은날": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "월요일": _monday(week_num)}


# --------------------------------------------------------------- 내 시간표
def parse_rooms(text):
    """「2-3, 3-1」 → {"2-3", "3-1"}. 쉼표·공백·줄바꿈 어느 것으로 나눠도 된다."""
    import re
    return {m.replace(" ", "") for m in re.findall(r"\d+\s*-\s*\d+", text or "")}


def my_periods(data, teacher, exclude=(), subjects=()):
    """전 반을 훑어 내 수업만. {요일(1=월): [{period, subject, room, replaced}]}

    컴시간이 준 이름이 내 이름의 앞부분일 때만 나로 본다(한쪽 방향만).
        내 이름 정유경 · 컴시간 「정유」   → 나
        내 이름 정유경 · 컴시간 「정유리」 → 남
    같은 두 글자를 쓰는 다른 선생님이 있으면 두 가지로 가른다.
        subjects  내가 가르치는 과목만(정미지=수학, 정미자=과학이면 수학만 고르면 된다)
        exclude   과목까지 같을 때, 남의 반을 직접 뺀다
    """
    teacher = (teacher or "").strip()
    out = {d: [] for d in range(1, 6)}
    if not teacher or not data:
        return out
    exclude, subjects = set(exclude or ()), set(subjects or ())
    for room, days in (data.get("classes") or {}).items():
        if room in exclude:
            continue
        for day, cells in days.items():
            for c in cells:
                name = (c.get("teacher") or "").strip()
                if len(name) < 2 or not teacher.startswith(name):
                    continue
                if subjects and (c.get("subject") or "") not in subjects:
                    continue
                out[int(day)].append({"period": c.get("period", 0),
                                      "subject": c.get("subject", ""),
                                      "room": room,
                                      "replaced": bool(c.get("replaced"))})
    for day in out:
        out[day].sort(key=lambda x: x["period"])
    return out


def conflicts(mine):
    """같은 시간에 두 반 이상에 들어가는 칸. [(요일, 교시, [반, …])].
    한 사람이 동시에 두 반에 들어갈 수는 없으니(합반 수업은 예외), 이런 칸이 보이면
    이름이 같은 다른 선생님이 섞였다는 뜻이다."""
    out = []
    for day in sorted(mine):
        at = {}
        for c in mine[day]:
            at.setdefault(c["period"], set()).add(c["room"])
        for p in sorted(at):
            if len(at[p]) > 1:
                out.append((day, p, sorted(at[p], key=_room_key)))
    return out


def _room_key(room):
    try:
        g, c = room.split("-")
        return int(g), int(c)
    except ValueError:
        return 99, 0


def sorted_rooms(mine):
    """my_periods 결과에 나오는 반을 학년·반 순으로."""
    return sorted({c["room"] for cells in mine.values() for c in cells}, key=_room_key)


def subject_counts(mine):
    """my_periods 결과에서 과목별 주당 시간. [(과목, 시간)] 많은 순. 이름이 겹치는지 가릴 때 쓴다."""
    n = {}
    for cells in mine.values():
        for c in cells:
            n[c["subject"]] = n.get(c["subject"], 0) + 1
    return sorted(n.items(), key=lambda kv: (-kv[1], kv[0]))


def matched_names(data, teacher):
    """내 이름과 맞은 컴시간 이름들(보통 한 개). 확인 화면에 보여 준다."""
    teacher = (teacher or "").strip()
    names = set()
    for days in ((data or {}).get("classes") or {}).values():
        for cells in days.values():
            for c in cells:
                n = (c.get("teacher") or "").strip()
                if len(n) >= 2 and teacher.startswith(n):
                    names.add(n)
    return sorted(names)


def preview_lines(mine):
    """확인 화면용. 「월 2교시 1-4 수학」 줄들."""
    lines = []
    for d in range(1, 6):
        for c in mine.get(d, []):
            lines.append("%s %d교시  %s  %s" % (DAY_NAMES[d - 1], c["period"], c["room"], c["subject"]))
    return lines


# --------------------------------------------------------------- 담아 두기
def cached():
    return store.load().get("cache") or None


def refresh_minutes(school_name=None):
    n = (school_name or store.load()["school_name"]).replace(" ", "")
    return HIGH_REFRESH_MINUTES if ("고등학교" in n or n.endswith("고")) else MIDDLE_REFRESH_MINUTES


def is_stale(now=None):
    cfg = store.load()
    data = cfg.get("cache")
    if not data or data.get("월요일") != _monday(0) or not cfg.get("fetched_at"):
        return True
    try:
        at = datetime.strptime(cfg["fetched_at"], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return True
    return ((now or datetime.now()) - at) >= timedelta(minutes=refresh_minutes(cfg["school_name"]))


def refresh(force=False):
    """받아서 담아 둔다. 못 받으면 ComciganError — 부르는 쪽이 옛것을 그대로 쓴다."""
    if not force and not is_stale():
        return False
    data = fetch()
    store.update(cache=data, fetched_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return True


# ----------------------------------------------------------------- 오늘 수업
def parse_manual(text):
    """직접 입력 칸 「1-4 수학」 → ("1-4", "수학"). 비면 None."""
    parts = (text or "").split(None, 1)
    if not parts:
        return None
    return parts[0], (parts[1].strip() if len(parts) > 1 else "")


def lessons_on(day=None):
    """그날 내 수업. {교시: {"room","subject","replaced"}}. 토·일은 빈 것.

    이번 주 컴시간 시간표가 있으면 그것, 없으면 손으로 넣은 시간표. 지난주 것을 이번
    주 것처럼 알리면 없는 것보다 나쁘므로 이번 주 것만 쓴다.
    """
    day = day or date.today()
    wd = day.weekday()
    if wd > 4:
        return {}
    cfg = store.load()
    out = {}
    data = cfg.get("cache")
    if data and data.get("월요일") == _monday(0):
        for c in my_periods(data, cfg["teacher"], parse_rooms(cfg.get("exclude_rooms")),
                             cfg.get("my_subjects") or ()).get(wd + 1, []):
            p = int(c.get("period") or 0)
            if p:
                out[p] = {"room": c["room"], "subject": c["subject"], "replaced": c["replaced"]}
    if out:
        return out
    for key, text in (cfg.get("manual") or {}).items():
        try:
            d, p = (int(x) for x in key.split("-"))
        except ValueError:
            continue
        cell = parse_manual(text)
        if d == wd and cell:
            out[p] = {"room": cell[0], "subject": cell[1], "replaced": False}
    return out
