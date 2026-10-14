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
