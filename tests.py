# -*- coding: utf-8 -*-
"""계산 로직 검사. 실행: python tests.py  (네트워크·화면 없이 돈다)"""
import os
import sys
import tempfile
from datetime import date

os.environ["DMC_HOME"] = tempfile.mkdtemp(prefix="dmc_t_")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import comcigan
import schedule
import store


def eq(a, b, msg=""):
    assert a == b, "%s\n  기대 %r\n  실제 %r" % (msg, b, a)


# --- 1교시 시작 후보: 8:20 ~ 9:00, 5분 단위 9개
c = schedule.first_start_choices()
eq(c[0], "08:20"); eq(c[-1], "09:00"); eq(len(c), 9)

# --- 채우기: 8:50 시작, 45분 수업, 쉬는 시간 10분
t = schedule.fill("08:50", 45, 7)
eq(t, ["08:50", "09:45", "10:40", "11:35", "12:30", "13:25", "14:20"], "fill 45")
eq(schedule.fill("08:30", 40, 3), ["08:30", "09:20", "10:10"], "fill 40")
eq(schedule.fill("09:00", 50, 2), ["09:00", "10:00"], "fill 50")

# --- 점심 때문에 5교시를 고치면 5교시 이후만 바뀐다
t2 = schedule.cascade(t, 4, "13:10", 45)
eq(t2[:4], t[:4], "앞 교시는 그대로")
eq(t2[4:], ["13:10", "14:05", "15:00"], "5교시 이후 재계산")

# --- 4교시를 고치면 4교시 이후가 바뀐다
t3 = schedule.cascade(t, 3, "11:40", 45)
eq(t3[:3], t[:3]); eq(t3[3:], ["11:40", "12:35", "13:30", "14:25"])

# --- 시각 입력 형식
eq(schedule.norm_time("9:5"), "09:05"); eq(schedule.norm_time("1310"), "13:10")
eq(schedule.norm_time("13시 10분"), "13:10"); eq(schedule.norm_time("25:00"), ""); eq(schedule.norm_time("abc"), "")
try:
    schedule.cascade(t, 2, "엉터리")
    raise AssertionError("잘못된 시각을 받아들였다")
except ValueError:
    pass

# --- 교시 추가/빼기, 9교시 상한
t9 = t
for _ in range(5):
    t9 = schedule.add_period(t9, 45)
eq(len(t9), 9, "9교시까지"); eq(schedule.add_period(t9, 45), t9, "9교시 넘지 않음")
eq(schedule.remove_last(["08:50"]), ["08:50"], "1교시는 남김")
eq(len(schedule.remove_last(t)), 6)

# --- 점심 안내
note = schedule.lunch_note(schedule.cascade(t, 4, "13:10", 45), 45)
assert "점심" in note and "4교시와 5교시" in note, note
eq(schedule.lunch_note(t, 45), "", "쉬는 시간뿐이면 점심 안내 없음")

# --- 학교급별 수업 길이
eq(schedule.lesson_minutes_for("서전중학교"), 45)
eq(schedule.lesson_minutes_for("서전초등학교"), 40)
eq(schedule.lesson_minutes_for("서전고등학교"), 50)

# --- 내 수업 고르기: 컴시간은 이름을 두 글자로 준다
def cell(p, subj, teacher, rep=False):
    return {"period": p, "subject": subj, "teacher": teacher, "replaced": rep}

data = {"월요일": comcigan._monday(0), "classes": {
    "1-4": {1: [cell(2, "수학", "정유")], 3: [cell(5, "수학", "정유", True)]},
    "1-5": {1: [cell(3, "수학", "정유")], 2: [cell(1, "국어", "정유리")]},   # 정유리는 남
    "2-1": {1: [cell(4, "과학", "김철")]},
}}
mine = comcigan.my_periods(data, "정유경")
eq([(c["period"], c["room"]) for c in mine[1]], [(2, "1-4"), (3, "1-5")], "월요일 내 수업")
eq(mine[2], [], "정유리 수업은 내 것이 아니다")
eq(mine[3][0]["replaced"], True, "바뀐 수업 표시")
eq(comcigan.matched_names(data, "정유경"), ["정유"])

# --- 이름이 겹친 다른 선생님 반은 뺄 수 있다
eq(comcigan.parse_rooms("2-3, 3 - 1\n1-5"), {"2-3", "3-1", "1-5"})
mine2 = comcigan.my_periods(data, "정유경", {"1-5"})
eq([(c["period"], c["room"]) for c in mine2[1]], [(2, "1-4")], "1-5반을 빼면 1-4만")

# --- 정미지(수학 1-1)와 정미자(과학 1-5): 컴시간에는 둘 다 「정미」. 내 과목을 고르면 갈린다
twin = {"월요일": comcigan._monday(0), "classes": {
    "1-1": {1: [cell(2, "수학", "정미")], 3: [cell(4, "수학", "정미")]},
    "1-5": {1: [cell(2, "과학", "정미")], 2: [cell(3, "과학", "정미", True)]},
}}
allm = comcigan.my_periods(twin, "정미지")
eq(comcigan.subject_counts(allm), [("과학", 2), ("수학", 2)], "과목이 둘 나오면 이름이 겹친 것")
only = comcigan.my_periods(twin, "정미지", subjects={"수학"})
eq([(d, c["period"], c["room"]) for d in only for c in only[d]], [(1, 2, "1-1"), (3, 4, "1-1")], "수학만")
eq(comcigan.subject_counts(comcigan.my_periods(data, "정유경")), [("수학", 3)], "한 과목이면 가를 일 없음")
# 같은 과목 동명이인(둘 다 수학): 같은 시간에 두 반이 보이면 겹친 것 → 내 반만 남기면 갈린다
same = {"월요일": comcigan._monday(0), "classes": {
    "1-1": {1: [cell(2, "수학", "정미")], 3: [cell(4, "수학", "정미")]},
    "1-2": {1: [cell(3, "수학", "정미")]},
    "1-5": {1: [cell(2, "수학", "정미")], 2: [cell(3, "수학", "정미")]},   # 월2는 1-1과 겹침
}}
m = comcigan.my_periods(same, "정미지")
eq(comcigan.conflicts(m), [(1, 2, ["1-1", "1-5"])], "같은 시간 두 반 = 다른 사람")
eq(comcigan.sorted_rooms(m), ["1-1", "1-2", "1-5"])
mine_only = comcigan.my_periods(same, "정미지", exclude={"1-5"})
eq(comcigan.conflicts(mine_only), [], "남의 반(1-5)을 빼면 겹침이 없다")
eq(comcigan.sorted_rooms(mine_only), ["1-1", "1-2"])
eq(comcigan.conflicts(comcigan.my_periods(data, "정유경")), [], "겹침 없는 보통 시간표")
store.update(teacher="정미지", my_subjects=["과학"], cache=twin, manual={})
sci = comcigan.lessons_on(date.fromisoformat(twin["월요일"]))
eq(sci, {2: {"room": "1-5", "subject": "과학", "replaced": False}}, "정미자 쪽(과학)을 고르면 1-5만")
store.update(my_subjects=[], teacher="정유경", cache=data)

# --- 사용자 예시: 정미란(수학 1-1~4) · 정미지(과학 1-1~5) · 정미경(수학 1-7~10). 컴시간 이름은 셋 다 「정미」
def tcell(p, subj, tid, rep=False):
    return {"period": p, "subject": subj, "teacher": "정미", "tid": tid, "replaced": rep}
trio_classes = {}
slot = 0
for room in ("1-1", "1-2", "1-3", "1-4"):          # 정미란 tid 5
    trio_classes[room] = {1: [tcell(1 + slot % 4, "수학", 5)]}
    slot += 1
for i, room in enumerate(("1-1", "1-2", "1-3", "1-4", "1-5")):   # 정미지 tid 6 (1-1은 수학 선생님과 반이 같다)
    trio_classes.setdefault(room, {}).setdefault(2, []).append(tcell(1 + i, "과학", 6))
for i, room in enumerate(("1-7", "1-8", "1-9", "1-10")):         # 정미경 tid 7
    trio_classes[room] = {3: [tcell(1 + i, "수학", 7)]}
trio = {"월요일": comcigan._monday(0), "classes": trio_classes}
assert comcigan.has_ids(trio)
who = comcigan.candidates(trio, "정미지")
eq(sorted((p["tid"], p["sample"]) for p in who),
   [(5, ("수학", "1-1")), (6, ("과학", "1-1")), (7, ("수학", "1-7"))], "사람마다 대표 수업 하나씩")
eq(len({p["sample"] for p in who}), 3, "대표 수업은 서로 달라야 고를 수 있다")
# 정미지(과학 1-1)를 고르면 정미지의 수업만 나온다
cfg_me = {"teacher": "정미지", "my_sample": {"subject": "과학", "room": "1-1"}, "my_tid": 6}
eq(comcigan.resolve_my_tid(trio, cfg_me), 6)
mine3 = comcigan.my_periods(trio, "정미지", tid=6)
eq(sorted({c["subject"] for cs in mine3.values() for c in cs}), ["과학"])
eq(comcigan.sorted_rooms(mine3), ["1-1", "1-2", "1-3", "1-4", "1-5"])
# 다음 학기에 교사 번호가 뒤바뀌어도, 고른 대표 수업(과학 1-1)으로 나를 다시 찾는다
shifted = {"월요일": trio["월요일"], "classes": {
    r: {d: [dict(c, tid={5: 7, 6: 5, 7: 6}[c["tid"]]) for c in cs] for d, cs in days.items()}
    for r, days in trio_classes.items()}}
eq(comcigan.resolve_my_tid(shifted, cfg_me), 5, "번호가 바뀌어도 (과학, 1-1)을 가르치는 사람이 나")
# 대표 수업이 사라졌으면(반 배정이 바뀜) 예전 번호를 쓴다. 둘 다 안 되면 None
gone = {"teacher": "정미지", "my_sample": {"subject": "과학", "room": "3-3"}, "my_tid": 6}
eq(comcigan.resolve_my_tid(trio, gone), 6)
eq(comcigan.resolve_my_tid(trio, {"teacher": "정미지", "my_sample": {"subject": "과학", "room": "3-3"}, "my_tid": 99}), None)
# 한 사람뿐이면 묻지 않는다
solo = {"월요일": trio["월요일"], "classes": {"1-1": {1: [tcell(1, "수학", 5)]}}}
eq(len(comcigan.candidates(solo, "정미란")), 1)
# 이름이 다른 사람(정미소)은 후보에 안 든다
eq([p["tid"] for p in comcigan.candidates({"월요일": "x", "classes": {"1-1": {1: [dict(tcell(1, "수학", 8), teacher="정미소")]}}}, "정미지")], [])
# 옛 저장본(번호 없음)은 번호 방식을 쓰지 않는다
eq(comcigan.has_ids(data), False)

# --- 오늘 수업: 이번 주 캐시가 있으면 그것, 없으면 직접 입력
store.update(teacher="정유경", cache=data, manual={"0-1": "9-9 가짜"})
mon = date.fromisoformat(data["월요일"])
got = comcigan.lessons_on(mon)
eq(sorted(got), [2, 3], "월요일: 캐시를 쓴다")
eq(comcigan.lessons_on(date.fromordinal(mon.toordinal() + 5)), {}, "토요일은 없음")
store.update(cache={"월요일": "2000-01-03", "classes": data["classes"]})
got = comcigan.lessons_on(mon)
eq(got, {1: {"room": "9-9", "subject": "가짜", "replaced": False}}, "지난주 캐시는 안 쓰고 직접 입력으로")

print("검사 통과")
