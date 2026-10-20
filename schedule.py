# -*- coding: utf-8 -*-
"""교시 시각 계산. 1교시 시작 + 수업 길이 + 쉬는 시간 10분으로 채우고,
어느 교시를 고치면 그 뒤 교시만 따라 바뀐다(점심시간은 학교마다 달라서)."""
import re

MAX_PERIODS = 9
DEFAULT_COUNT = 7
BREAK_MIN = 10
LESSON_CHOICES = (40, 45, 50)


def first_start_choices():
    """1교시 시작 시각 후보. 8:20부터 9:30까지 5분 단위."""
    return ["%02d:%02d" % (m // 60, m % 60) for m in range(8 * 60 + 20, 9 * 60 + 31, 5)]


def to_min(t):
    t = norm_time(t)
    if not t:
        return None
    return int(t[:2]) * 60 + int(t[3:])


def from_min(v):
    return "%02d:%02d" % (v // 60 % 24, v % 60)


def norm_time(t):
    """「9:05」「09:05」「0905」「9시 5분」 → 「09:05」. 못 읽으면 ""."""
    s = str(t or "").strip()
    m = re.fullmatch(r"(\d{1,2})\s*[:시.]\s*(\d{1,2})\s*분?", s) or re.fullmatch(r"(\d{1,2})(\d{2})", s)
    if not m:
        return ""
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return ""
    return "%02d:%02d" % (h, mi)


def lesson_minutes_for(school_name):
    """학교 이름으로 고른 수업 길이의 처음 값. 초 40 · 중 45 · 고 50. 모르면 45."""
    n = (school_name or "").replace(" ", "")
    if "초등학교" in n or n.endswith("초"):
        return 40
    if "고등학교" in n or n.endswith("고"):
        return 50
    return 45


def fill(first, lesson=45, count=DEFAULT_COUNT, brk=BREAK_MIN):
    """1교시 시각에서 count 교시까지 채운다. ["08:50", "09:45", …]"""
    a = to_min(first)
    if a is None:
        raise ValueError("1교시 시작 시각을 확인해 주세요.")
    if int(lesson) <= 0 or not 1 <= int(count) <= MAX_PERIODS:
        raise ValueError("수업 길이와 교시 수를 확인해 주세요.")
    step = int(lesson) + int(brk)
    return [from_min(a + i * step) for i in range(int(count))]


def cascade(times, index, new_time, lesson=45, brk=BREAK_MIN):
    """index(0부터) 교시의 시작을 new_time 으로 고치고, 그 뒤 교시를 **같은 만큼 밀어** 준다.
    앞 교시는 그대로 둔다. 시각을 못 읽으면 ValueError.

    뒤 교시를 처음부터 다시 세지 않고 밀기만 하므로, 앞서 점심·조회 때문에 늦춰 둔 뒤쪽 교시의
    틈(예: 6교시 앞의 긴 쉬는 시간)이 앞 교시를 고쳐도 지워지지 않는다. 기본값(쉬는 시간 10분)
    상태에서는 다시 세는 것과 결과가 같다. lesson·brk 는 예전 호출과 맞추려고 남겨 둔 인자다."""
    t = norm_time(new_time)
    if not t:
        raise ValueError("시각을 「9:05」처럼 적어 주세요.")
    delta = to_min(t) - to_min(times[index])
    out = list(times)
    out[index] = t
    for i in range(index + 1, len(out)):
        out[i] = from_min(to_min(out[i]) + delta)
    return out


def add_period(times, lesson=45, brk=BREAK_MIN):
    """마지막 교시 뒤에 한 교시를 더한다. 이미 9교시면 그대로."""
    out = list(times)
    if len(out) >= MAX_PERIODS or not out:
        return out
    out.append(from_min(to_min(out[-1]) + int(lesson) + int(brk)))
    return out


def remove_last(times):
    """마지막 교시를 뺀다. 1교시는 남긴다."""
    return list(times[:-1]) if len(times) > 1 else list(times)


def lunch_note(times, lesson):
    """각 교시 사이에서 가장 긴 틈을 점심으로 보고 한 줄로 알려 준다. 없으면 ""."""
    best = None
    for i in range(1, len(times)):
        end = to_min(times[i - 1]) + int(lesson)
        gap = to_min(times[i]) - end
        if gap > BREAK_MIN + 5 and (best is None or gap > best[0]):
            best = (gap, i, from_min(end), times[i])
    if not best:
        return ""
    gap, i, a, b = best
    return "점심 %s~%s (%d분) · %d교시와 %d교시 사이" % (a, b, gap, i, i + 1)
