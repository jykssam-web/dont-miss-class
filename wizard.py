# -*- coding: utf-8 -*-
"""첫 설치 튜토리얼 겸 설정 창. 같은 창을 설정에서 다시 연다(저장된 값이 미리 채워진다).

    1 학교 찾기  →  2 내 수업 확인  →  3 교시 시각  →  4 소리·자동 실행
"""
import os
import queue
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import autostart
import comcigan
import fonts
import schedule
import sounds
import store

import ui

FONT = ui.family()
ACCENT, MUTED, ERR, OK, TEXT = ui.ACCENT, ui.MUTED, ui.ERR, ui.OK, ui.TEXT
STEP_TITLES = ("학교 찾기", "내 수업 확인", "교시 시작 시각", "소리와 자동 실행")


class Wizard(tk.Toplevel):
    def __init__(self, root, on_done, on_test_alert, on_cancel=None, first_run=True):
        super().__init__(root)
        self.root_ = root
        self.on_done = on_done
        self.on_test_alert = on_test_alert
        self.on_cancel = on_cancel
        self.first_run = first_run
        self.title("놓치지마수업")
        self.configure(bg="white")
        self.resizable(False, False)
        w, h = 660, 700
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, max(10, (sh - h) // 2 - 20)))
        try:
            from PIL import ImageTk
            import icon
            self._icon = ImageTk.PhotoImage(icon.make_image(64))
            self.iconphoto(True, self._icon)
        except Exception:
            pass

        ui.setup_styles(self)

        cfg = store.load()
        self.school = {"name": cfg["school_name"], "school_code": cfg["school_code"],
                       "local_code": cfg["local_code"]}
        self.teacher = cfg["teacher"]
        self.data = cfg.get("cache")            # 마지막으로 받은 시간표
        self.manual = dict(cfg.get("manual") or {})
        self.exclude = cfg.get("exclude_rooms") or ""
        self.subjects = set(cfg.get("my_subjects") or [])
        self.my_tid = cfg.get("my_tid")                 # 컴시간 교사 번호 — 같은 이름 속에서 나를 가른다
        self.my_sample = cfg.get("my_sample")
        self.font = cfg.get("font") or ""
        self.lesson = int(cfg["lesson_min"] or 45)
        self.times = list(cfg["times"] or [])
        self.first = self.times[0] if self.times else "08:50"
        self.sound = cfg["sound"]
        self.autostart = tk.BooleanVar(value=bool(cfg["autostart"]))
        self.name_checked = ""                  # 확인을 마친 이름. 이름을 바꾸면 비워진다
        self.found_count = 0
        if self.data and self.teacher:           # 설정을 다시 여는 경우: 지난번 확인을 이어 쓴다
            n = len(comcigan.preview_lines(comcigan.my_periods(
                self.data, self.teacher, comcigan.parse_rooms(self.exclude), self.subjects, self.my_tid)))
            if n:
                self.found_count, self.name_checked = n, self.teacher
        self._rebuilding = False
        self._q = queue.Queue()
        self.step = 0

        # 머리: 작은 제목 · 큰 단계 이름 · 가는 진행 막대(흰 바탕)
        head = tk.Frame(self, bg=ui.BG)
        head.pack(fill="x", padx=30, pady=(24, 4))
        top = tk.Frame(head, bg=ui.BG)
        top.pack(fill="x")
        tk.Label(top, text="놓치지마수업 · " + ("처음 설정" if first_run else "설정"), bg=ui.BG, fg=MUTED,
                 font=(FONT, 10)).pack(side="left")
        self.lbl_count = tk.Label(top, bg=ui.BG, fg=MUTED, font=(FONT, 10))
        self.lbl_count.pack(side="right")
        self.lbl_step = tk.Label(head, bg=ui.BG, fg=TEXT, font=(FONT, 21, "bold"), anchor="w")
        self.lbl_step.pack(fill="x", pady=(8, 12))
        self.bar = tk.Canvas(head, height=8, bg=ui.BG, highlightthickness=0)
        self.bar.pack(fill="x")
        self.bar.bind("<Configure>", lambda e: self._draw_bar())

        # 바닥: 먼저 붙여야 내용이 길어도 단추가 안 잘린다
        foot = tk.Frame(self, bg=ui.BG)
        foot.pack(side="bottom", fill="x", padx=30, pady=(12, 22))
        tk.Frame(self, bg=ui.LINE, height=1).pack(side="bottom", fill="x")
        self.body = ttk.Frame(self, padding=(30, 16, 30, 6))
        self.body.pack(fill="both", expand=True)
        self.btn_back = ui.Button(foot, text="이전", command=self.back)
        self.btn_back.pack(side="left")
        self.btn_next = ui.Button(foot, text="다음", command=self.next, kind="primary", padx=34)
        self.btn_next.pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.after(100, self._poll)
        self._show(0)
        ui.tweak_title_bar(self)

    # ------------------------------------------------------------ 공통
    def _poll(self):
        """백그라운드 일이 끝났으면 화면 쪽에서 받는다(tkinter 는 다른 스레드에서 못 만진다)."""
        try:
            while True:
                done, result = self._q.get_nowait()
                done(result)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(100, self._poll)

    def _bg(self, fn, done):
        def work():
            try:
                res = ("ok", fn())
            except Exception as e:          # 화면 쪽에서 문구로 바꿔 보여 준다
                res = ("err", e)
            self._q.put((done, res))
        threading.Thread(target=work, daemon=True).start()

    def _clear(self):
        for c in self.body.winfo_children():
            c.destroy()

    def _label(self, text, color=None, size=11, bold=False, pady=(0, 6), wrap=580, **kw):
        lb = tk.Label(self.body, text=text, bg="white", fg=color or TEXT, justify="left",
                      anchor="w", wraplength=wrap, font=(FONT, size, "bold" if bold else "normal"), **kw)
        lb.pack(fill="x", pady=pady)
        return lb

    def _show(self, n):
        self.step = n
        self._clear()
        self.lbl_step.config(text=STEP_TITLES[n])
        self.lbl_count.config(text="%d / 4" % (n + 1))
        self._draw_bar()
        self.btn_back.state(["!disabled"] if n > 0 else ["disabled"])
        self.btn_next.config(text="완료" if n == 3 else "다음")
        self.btn_next.state(["!disabled"])
        [self._page_school, self._page_name, self._page_times, self._page_alert][n]()

    def _draw_bar(self):
        """진행 막대: 지나온 단계와 지금 단계는 파랑, 남은 단계는 옅은 회색."""
        w = self.bar.winfo_width()
        if w < 20:
            return
        self.bar.delete("all")
        gap, cap = 10, 4
        seg = (w - 3 * gap) / 4.0
        for i in range(4):
            x0 = i * (seg + gap)
            self.bar.create_line(x0 + cap, 4, x0 + seg - cap, 4, width=2 * cap, capstyle="round",
                                 fill=ACCENT if i <= self.step else ui.LINE)

    def back(self):
        if self.step > 0:
            self._show(self.step - 1)

    def next(self):
        if self.step == 2 and not self._commit_pending_entry():
            return
        if self.step < 3:
            self._show(self.step + 1)
        else:
            self._finish()

    def _cancel(self):
        self.destroy()
        if self.on_cancel:
            self.on_cancel()

    # --------------------------------------------------- 1 학교 찾기
    def _page_school(self):
        self._label("컴시간알리미에 등록된 학교를 검색합니다.", bold=True, size=13)
        self._label("학교 이름의 일부만 적어도 됩니다. (예: 서전중)", MUTED)
        row = ttk.Frame(self.body)
        row.pack(fill="x", pady=(4, 8))
        self.var_q = tk.StringVar(value="" if not self.school["name"] else self.school["name"])
        ent = ttk.Entry(row, textvariable=self.var_q, font=(FONT, 13))
        ent.pack(side="left", fill="x", expand=True, ipady=3)
        ent.bind("<Return>", lambda e: self._search())
        ent.focus_set()
        ui.Button(row, text="검색", command=self._search).pack(side="left", padx=(8, 0))

        self.lst = tk.Listbox(self.body, height=9, font=(FONT, 12), activestyle="none",
                              exportselection=False, relief="flat", bd=0, bg=ui.SURFACE, fg=TEXT,
                              highlightthickness=1, highlightbackground=ui.LINE, highlightcolor=ACCENT,
                              selectbackground=ACCENT, selectforeground="white")
        self.lst.pack(fill="both", expand=True)
        self.lst.bind("<<ListboxSelect>>", lambda e: self._pick_school())
        self.lbl_status = self._label("", MUTED, pady=(8, 0))
        self.results = []
        if self.school["name"]:
            self.lbl_status.config(text="현재 설정: %s. 다른 학교로 바꾸려면 다시 검색하세요." % self.school["name"],
                                   fg=OK)
        self._update_next()

    def _search(self):
        kw = self.var_q.get().strip()
        if not kw:
            self.lbl_status.config(text="학교 이름을 적어 주세요.", fg=ERR)
            return
        self.lbl_status.config(text="찾는 중…", fg=MUTED)
        self.lst.delete(0, "end")

        def done(res):
            if not self._alive("lst"):
                return
            kind, val = res
            if kind == "err":
                self.lbl_status.config(text=str(val), fg=ERR)
                return
            self.results = val
            if not val:
                self.lbl_status.config(text="찾지 못했습니다. 이름을 줄여서 다시 검색해 보세요.", fg=ERR)
                return
            for r in val:
                self.lst.insert("end", "%s   %s" % (r["name"], r["region"]))
            self.lbl_status.config(text="학교를 눌러 고르세요. (%d곳)" % len(val), fg=MUTED)
            if len(val) == 1:
                self.lst.selection_set(0)
                self._pick_school()
        self._bg(lambda: comcigan.search_school(kw), done)

    def _pick_school(self):
        sel = self.lst.curselection()
        if not sel or sel[0] >= len(self.results):
            return
        r = self.results[sel[0]]
        if str(r["school_code"]) != str(self.school["school_code"]):
            self.data = None                   # 학교가 바뀌면 옛 시간표는 버린다
            self.name_checked = ""
            self.my_tid, self.my_sample = None, None
        self.school = {"name": r["name"], "school_code": r["school_code"], "local_code": r["local_code"]}
        self.lesson = schedule.lesson_minutes_for(r["name"]) if not self.times else self.lesson
        self.lbl_status.config(text="선택: %s" % r["name"], fg=OK)
        self._update_next()

    # --------------------------------------------------- 2 내 수업 확인
    def _page_name(self):
        self._label("선생님 이름을 적어 주세요.", bold=True, size=13)
        self._label("컴시간은 이름을 두 글자로 줄여 줘요(정유경 → 정유). 같은 이름의 선생님이 계시면 어느 분인지 물어볼게요.", MUTED)
        row = ttk.Frame(self.body)
        row.pack(fill="x", pady=(2, 8))
        self.var_name = tk.StringVar(value=self.teacher)
        ent = ttk.Entry(row, textvariable=self.var_name, font=(FONT, 13), width=14)
        ent.pack(side="left", ipady=3)
        ent.bind("<Return>", lambda e: self._check_name())
        ent.bind("<KeyRelease>", lambda e: self._name_edited())
        ent.focus_set()
        ui.Button(row, text="내 수업 찾기", command=self._check_name).pack(side="left", padx=(8, 0))
        ui.Button(row, text="컴시간 없이 직접 입력", command=self._open_manual).pack(side="right")

        self.lbl_status = self._label("", MUTED, pady=(0, 6))
        self.subj_frame = ttk.Frame(self.body)      # 이름이 같은 선생님이 있을 때만 채워진다
        self.subj_frame.pack(fill="x")
        # 반 고르기는 평소엔 접어 두고, 남의 수업이 섞였다는 신호가 있으면 저절로 펼친다.
        # 목록은 길어질 수 있어 맨 아래에 두고, 고르는 칸은 그 위에 둔다(화면이 모자라도 잘리지 않게).
        self.rooms_open = bool(self.exclude)
        self.btn_rooms = ui.Button(self.body, command=self._toggle_rooms)    # 반이 있을 때만 보인다
        self.room_frame = ttk.Frame(self.body)
        self.room_frame.pack(fill="x", pady=(0, 6))
        box = ttk.Frame(self.body)
        box.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(box)
        sb.pack(side="right", fill="y")
        self.txt = tk.Text(box, height=8, font=(FONT, 11), relief="flat", bd=0, state="disabled", fg=TEXT,
                           highlightthickness=1, highlightbackground=ui.LINE, highlightcolor=ui.LINE,
                           yscrollcommand=sb.set, bg=ui.SURFACE, padx=14, pady=10)
        self.txt.pack(side="left", fill="both", expand=True)
        sb.config(command=self.txt.yview)
        if self.name_checked == self.teacher and self.data and self.teacher:
            self._render_preview()
        elif self.manual:
            self._set_text("직접 입력한 시간표가 있습니다. (%d칸)" % len(self.manual))
        self._update_next()

    def _name_edited(self):
        if self.var_name.get().strip() != self.name_checked:
            self.found_count = 0
            self._update_next()

    def _set_text(self, text):
        self.txt.config(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", text)
        self.txt.config(state="disabled")

    def _check_name(self):
        name = self.var_name.get().strip()
        if len(name) < 2:
            self.lbl_status.config(text="이름을 두 글자 이상 적어 주세요.", fg=ERR)
            return
        if name != self.teacher:                 # 다른 이름이면 전에 고른 「내 수업」은 버린다
            self.my_tid, self.my_sample = None, None
        self.teacher = name
        if self.data and self.data.get("school") == self.school["name"] and \
                self.data.get("월요일") == comcigan._monday(0):
            self._after_fetch(("ok", self.data))
            return
        self.lbl_status.config(text="컴시간에서 시간표를 받는 중…", fg=MUTED)
        self._set_text("")
        s = self.school
        self._bg(lambda: comcigan.fetch(s["name"], s["school_code"], s["local_code"]), self._after_fetch)

    def _after_fetch(self, res):
        if not self._alive("txt"):
            return
        kind, val = res
        if kind == "err":
            self.lbl_status.config(text="%s\n컴시간이 안 될 때는 오른쪽 위 「직접 입력」으로 시간표를 넣을 수 있어요." % val,
                                   fg=ERR)
            return
        self.data = val
        self.name_checked = self.teacher
        self._render_preview()
        self._update_next()

    def _toggle_rooms(self):
        self.rooms_open = not self.rooms_open
        if self.data and self.name_checked == self.teacher:
            self._render_preview()

    def _room_toggled(self):
        """꺼 둔 반 = 내 수업이 아닌 반. 켜 둔 반만 남긴다."""
        self.exclude = ", ".join(r for r, v in self.room_vars.items() if not v.get())
        self.after_idle(self._render_preview)

    def _subject_toggled(self):
        self.subjects = {k for k, v in self.subj_vars.items() if v.get()}
        self.after_idle(self._render_preview)       # 누른 단추를 그 자리에서 지우지 않게

    def _person_picked(self):
        tid = self.var_person.get()
        p = next((p for p in self._people if p["tid"] == tid), None)
        if p is None:
            return
        self.my_tid = tid
        self.my_sample = {"subject": p["sample"][0], "room": p["sample"][1]}
        self.after_idle(self._render_preview)       # 누른 단추를 그 자리에서 지우지 않게

    def _render_people(self):
        """컴시간 교사 번호로 같은 이름의 사람들을 갈라, 사람마다 대표 수업 하나만 보여 주고 고르게 한다."""
        people = self._people = comcigan.candidates(self.data, self.teacher)
        for c in self.subj_frame.winfo_children():
            c.destroy()
        self.subj_frame.configure(height=1)
        self._draw_rooms([])                         # 반 고르기는 번호가 없을 때의 예비 방법
        if not people:
            self.found_count, self.my_tid = 0, None
            self.lbl_status.config(
                text="「%s」로 된 수업을 찾지 못했습니다. 컴시간에 적힌 이름과 같은지 확인하거나 직접 입력해 주세요." % self.teacher,
                fg=ERR)
            self._set_text("")
            self._update_next()
            return
        if len(people) == 1:
            p = people[0]
            self.my_tid = p["tid"]
            self.my_sample = {"subject": p["sample"][0], "room": p["sample"][1]}
        else:
            self.my_tid = comcigan.resolve_my_tid(
                self.data, {"teacher": self.teacher, "my_sample": self.my_sample, "my_tid": self.my_tid})
            tk.Label(self.subj_frame, text="「%s」 이름의 선생님이 %d분 계세요. 선생님이 수업하시는 건 어느 것인가요?" % (
                people[0]["name"], len(people)), bg="white", fg=TEXT, font=(FONT, 11, "bold"),
                     wraplength=580, justify="left").pack(anchor="w")
            row = ttk.Frame(self.subj_frame)
            row.pack(fill="x", pady=(4, 6))
            self.var_person = tk.IntVar(value=-1 if self.my_tid is None else self.my_tid)
            for p in people:
                ui.Chip(row, text="%s %s" % p["sample"], variable=self.var_person, value=p["tid"],
                        command=self._person_picked, size=12, padx=18, pady=9).pack(side="left", padx=(0, 8))
        if self.my_tid is None:
            self.found_count = 0
            self.lbl_status.config(text="수업하시는 것을 골라 주세요. 고르면 그 선생님의 시간표만 남깁니다.", fg=ERR)
            self._set_text("")
            self._update_next()
            return
        lines = comcigan.preview_lines(comcigan.my_periods(self.data, self.teacher, tid=self.my_tid))
        self.found_count = len(lines)
        self.lbl_status.config(
            text="컴시간에서 「%s」로 표시된 수업 주 %d시간을 찾았어요. 내 수업이 맞나요?" % (people[0]["name"], len(lines)),
            fg=OK)
        self._set_text("\n".join(lines))
        self._update_next()

    def _render_preview(self):
        if comcigan.has_ids(self.data):
            self._render_people()
            return
        rooms = comcigan.parse_rooms(self.exclude)
        base = comcigan.my_periods(self.data, self.teacher, rooms)       # 과목을 거르기 전
        counts = comcigan.subject_counts(base)
        names = comcigan.matched_names(self.data, self.teacher)

        # 이름 한 개에 과목이 여럿 나오면 → 이름이 같은 다른 선생님이 있거나 내가 여러 과목을 가르친다.
        # 어느 쪽이든 내 과목을 직접 고르게 한다(정미지=수학 · 정미자=과학처럼 과목이 갈린다).
        for c in self.subj_frame.winfo_children():
            c.destroy()
        self.subj_frame.configure(height=1)
        multi = len(counts) > 1
        if multi:
            self.subjects &= {k for k, _ in counts}
            self.subj_vars = {}
            tk.Label(self.subj_frame, text="내가 가르치는 과목을 고르세요 (여러 과목이면 모두)", bg="white", fg=TEXT,
                     font=(FONT, 11, "bold")).pack(anchor="w")
            row = ttk.Frame(self.subj_frame)
            row.pack(fill="x", pady=(2, 6))
            for k, n in counts:
                v = tk.BooleanVar(value=k in self.subjects)
                self.subj_vars[k] = v
                ui.Chip(row, text="%s (주 %d시간)" % (k, n), variable=v,
                        command=self._subject_toggled).pack(side="left", padx=(0, 8))
        else:
            self.subjects = set()

        mine = comcigan.my_periods(self.data, self.teacher, rooms, self.subjects)
        lines = comcigan.preview_lines(mine)
        all_lines = comcigan.preview_lines(base)
        conflicts = comcigan.conflicts(mine)
        picking = not (multi and not self.subjects)
        # 한 사람이 같은 시간에 두 반에 못 들어간다. 그런 칸이 보이거나 시간이 너무 많으면
        # 이름이 겹친 다른 선생님이 섞인 것이니 반 고르기를 저절로 펼친다.
        if picking and (conflicts or len(lines) > 30):
            self.rooms_open = True
        pool = comcigan.my_periods(self.data, self.teacher, (), self.subjects)
        self._draw_rooms(comcigan.sorted_rooms(pool) if picking else [])
        if multi and not self.subjects:
            self.found_count = 0
            self.lbl_status.config(
                text="「%s」 이름으로 %d개 과목이 나와요. 내 과목에 체크하면 내 수업만 남깁니다." % (
                    ", ".join(names), len(counts)), fg=ERR)
            self._set_text("\n".join(all_lines))
            self._update_next()
            return
        self.found_count = len(lines)
        if not lines:
            self.lbl_status.config(
                text="「%s」로 된 수업을 찾지 못했습니다. 컴시간에 적힌 이름과 같은지 확인하거나 직접 입력해 주세요." % self.teacher,
                fg=ERR)
            self._set_text("")
        elif conflicts:
            d, p, rs = conflicts[0]
            self.lbl_status.config(
                text="같은 시간에 두 반에 들어가는 칸이 있어요(%s %d교시 %s). 같은 이름의 다른 선생님 수업이 섞인 거예요. "
                     "내 반만 켜 두세요. (합반 수업이면 그대로)" % (comcigan.DAY_NAMES[d - 1], p, "·".join(rs)), fg=ERR)
            self._set_text("\n".join(lines))
        elif len(lines) > 30:
            # 한 선생님의 주당 수업은 보통 이보다 훨씬 적다. 이름이 겹친 다른 선생님 수업이 섞였다는 신호.
            self.lbl_status.config(
                text="주 %d시간은 한 분 수업으로는 너무 많아요. 같은 이름(「%s」)의 다른 선생님 수업이 섞인 것 같아요. "
                     "내 반만 켜 두세요." % (len(lines), ", ".join(names)), fg=ERR)
            self._set_text("\n".join(lines))
        else:
            self.lbl_status.config(
                text="컴시간에서 「%s」로 표시된 수업 주 %d시간을 찾았어요. 내 수업이 맞나요?" % (
                    ", ".join(names), len(lines)), fg=OK)
            self._set_text("\n".join(lines))
        self._update_next()

    def _draw_rooms(self, room_list):
        """내 반 고르기. 켜 있으면 내 수업, 끄면 남의 수업으로 뺀다."""
        for c in self.room_frame.winfo_children():
            c.destroy()
        self.room_frame.configure(height=1)
        if not room_list:
            self.btn_rooms.pack_forget()
            return
        self.btn_rooms.pack(anchor="w", pady=(0, 4), before=self.room_frame)
        self.btn_rooms.config(text=("내 반 고르기 ▴" if self.rooms_open else
                                                    "남의 수업이 섞였나요? 내 반 고르기 ▾"))
        if not self.rooms_open:
            return
        out = comcigan.parse_rooms(self.exclude)
        self.room_vars = {}
        grid = ttk.Frame(self.room_frame)
        grid.pack(fill="x")
        for i, r in enumerate(room_list):
            v = tk.BooleanVar(value=r not in out)
            self.room_vars[r] = v
            ui.Chip(grid, text=r, variable=v, command=self._room_toggled, size=10, padx=14, pady=6).grid(
                row=i // 7, column=i % 7, sticky="w", padx=(0, 6), pady=3)

    def _open_manual(self):
        ManualDialog(self, self.manual, self._manual_saved)

    def _manual_saved(self, manual):
        self.manual = manual
        if self._alive("txt"):
            self._set_text("직접 입력한 시간표를 저장했어요. (%d칸)" % len(manual) if manual else "")
            self.lbl_status.config(text="컴시간 대신 직접 입력한 시간표로 알려 드립니다." if manual else "", fg=OK)
        self._update_next()

    # --------------------------------------------------- 3 교시 시각
    def _page_times(self):
        self._label("1교시 시작과 수업 길이를 고르면 나머지 교시가 자동으로 채워져요.", MUTED, pady=(0, 6))
        top = ttk.Frame(self.body)
        top.pack(fill="x", pady=(0, 4))
        ttk.Label(top, text="1교시 시작").pack(side="left")
        self.var_first = tk.StringVar(value=self.first)
        cb = ui.Combo(top, textvariable=self.var_first, values=schedule.first_start_choices(),
                          width=7, state="readonly", font=(FONT, 12))
        cb.pack(side="left", padx=(8, 22))
        cb.bind("<<ComboboxSelected>>", lambda e: self._refill())
        ttk.Label(top, text="수업 길이").pack(side="left")
        self.var_lesson = tk.IntVar(value=self.lesson)
        for m in schedule.LESSON_CHOICES:
            ui.Chip(top, text="%d분" % m, variable=self.var_lesson, value=m,
                    command=self._refill).pack(side="left", padx=(8, 0))

        self.lbl_hint = self._label("점심이나 다른 일정 때문에 늦게 시작하는 교시는 그 교시의 시각을 고치세요. 몇 곳이든 고칠 수 "
                                    "있고, 고친 교시부터 뒤 교시가 같이 밀려요. 숫자만 쳐도(예: 1315) 13:15가 돼요.",
                                    MUTED, pady=(12, 8))
        bar = ttk.Frame(self.body)
        bar.pack(fill="x")
        ui.Button(bar, text="교시 추가", command=self._add).pack(side="left")
        ui.Button(bar, text="마지막 교시 빼기", command=self._remove).pack(side="left", padx=8)
        # 반영됐다는 안내는 칸 바로 위에 둔다(교시가 늘어 화면 아래가 가려져도 보이게)
        self.lbl_err = self._label("", ERR, pady=(8, 6))
        self.rows = tk.Frame(self.body, bg=ui.SURFACE)           # 옅은 회색 판 위에 두 칸씩
        self.rows.pack(fill="x", pady=(0, 6))
        self.lbl_lunch = self._label("", MUTED, pady=(2, 0))
        if not self.times:
            self._refill()
        else:
            self._rebuild_rows()

    def _refill(self):
        self.first = self.var_first.get()
        self.lesson = int(self.var_lesson.get())
        count = len(self.times) or schedule.DEFAULT_COUNT
        self.times = schedule.fill(self.first, self.lesson, count)
        self._rebuild_rows()

    def _rebuild_rows(self, focus=None):
        # 입력칸이 지워질 때 날아오는 FocusOut 이 다시 계산을 일으키지 않게 막는다.
        self._rebuilding = True
        for c in self.rows.winfo_children():
            c.destroy()
        self.row_vars = []
        self.row_entries = {}
        # 한 줄에 두 교시씩(1·2 / 3·4 / 5·6 / 7·8 …). 교시가 늘면 줄이 아래로 늘어난다.
        for i, t in enumerate(self.times):
            r, base = i // 2, (0 if i % 2 == 0 else 3)
            tk.Label(self.rows, text="%d교시" % (i + 1), bg=ui.SURFACE, fg=TEXT, font=(FONT, 12),
                     width=5, anchor="w").grid(row=r, column=base, padx=(22, 6), pady=4, sticky="w")
            var = tk.StringVar(value=t)
            self.row_vars.append(var)
            if i == 0:
                tk.Label(self.rows, text=t, bg=ui.SURFACE, fg=TEXT, font=(FONT, 12, "bold"),
                         width=7, anchor="w").grid(row=r, column=base + 1, padx=(8, 0), sticky="w")
            else:
                e = ttk.Entry(self.rows, textvariable=var, width=7, font=(FONT, 12))
                e.grid(row=r, column=base + 1, sticky="w")
                e.bind("<Return>", lambda ev, k=i: self._commit(k, refocus=True))
                e.bind("<FocusOut>", lambda ev, k=i: self._commit(k))
                e.bind("<KeyRelease>", lambda ev, k=i: self._typing(k))
                self.row_entries[i] = e
        self.rows.grid_columnconfigure(2, minsize=60)
        self.rows.grid_rowconfigure(0, pad=0)
        self.lbl_lunch.config(text=schedule.lunch_note(self.times, self.lesson))
        self.after_idle(lambda: setattr(self, "_rebuilding", False))
        if focus is not None and focus in self.row_entries:      # 입력하던 칸에서 계속 칠 수 있게
            self.row_entries[focus].focus_set()
            self.row_entries[focus].icursor("end")

    _FULL_TIME = re.compile(r"^\d{1,2}:\d{2}$|^\d{4}$|^[89]\d{2}$")      # 「12:20」「9:05」「1220」처럼 끝까지 친 것만

    def _typing(self, index):
        """시각을 끝까지 치면 잠깐 뒤 저절로 반영한다(엔터를 몰라도 되게). 치는 도중의 「12:2」는 기다린다."""
        if getattr(self, "_typing_job", None):
            self.after_cancel(self._typing_job)
            self._typing_job = None
        if index < len(self.row_vars) and self._FULL_TIME.match(self.row_vars[index].get().strip()):
            self._typing_job = self.after(450, lambda: self._commit(index, refocus=True))

    def _notice(self, text, color):
        """아래 안내 줄. 반영됐다는 알림은 몇 초 뒤 사라진다."""
        if getattr(self, "_notice_job", None):
            self.after_cancel(self._notice_job)
            self._notice_job = None
        self.lbl_err.config(text=text, fg=color)
        if text and color == OK:
            self._notice_job = self.after(6000, lambda: self._alive("lbl_err") and self.lbl_err.config(text=""))

    def _commit(self, index, refocus=False):
        """index 교시의 칸을 고쳤으면 그 뒤 교시를 다시 센다."""
        if self._rebuilding or not self._alive("rows") or index >= len(self.times) \
                or index >= len(self.row_vars):
            return True
        text = self.row_vars[index].get()
        if schedule.norm_time(text) == self.times[index]:
            self.row_vars[index].set(self.times[index])
            return True
        try:
            self.times = schedule.cascade(self.times, index, text, self.lesson)
        except ValueError as e:
            self._notice("%d교시: %s" % (index + 1, e), ERR)
            self.row_vars[index].set(self.times[index])
            return False
        later = ["%d" % (i + 1) for i in range(index + 1, len(self.times))]
        self._notice("%d교시를 %s로 바꿨어요.%s" % (
            index + 1, self.times[index],
            (" %s교시도 자동으로 다시 계산했어요." % "·".join(later)) if later else ""), OK)
        self._rebuild_rows(focus=index if refocus else None)
        return True

    def _commit_pending_entry(self):
        """다음으로 넘어가기 전에, 커서가 남아 있는 칸의 값을 반영한다."""
        for i in range(1, len(self.times)):
            if not self._commit(i):
                return False
        return True

    def _add(self):
        if len(self.times) >= schedule.MAX_PERIODS:
            self._notice("교시는 %d교시까지 둘 수 있어요." % schedule.MAX_PERIODS, ERR)
            return
        self.times = schedule.add_period(self.times, self.lesson)
        self._rebuild_rows()

    def _remove(self):
        self.times = schedule.remove_last(self.times)
        self._rebuild_rows()

    # --------------------------------------------------- 4 소리·자동 실행
    def _page_alert(self):
        self._label("알림 소리", bold=True, size=13, pady=(0, 6))
        self.sound_opts = [("소리 없음", "")] + sounds.builtin()
        labels = [l for l, _ in self.sound_opts] + ["내 파일 고르기…"]
        cur = sounds.label_for(self.sound)
        if cur not in labels:
            labels.insert(len(labels) - 1, cur)
        self.var_sound = tk.StringVar(value=cur)
        row = ttk.Frame(self.body)
        row.pack(fill="x", pady=(0, 6))
        self.cb_sound = ui.Combo(row, textvariable=self.var_sound, values=labels, state="readonly",
                                     width=24, font=(FONT, 12))
        self.cb_sound.pack(side="left")
        self.cb_sound.bind("<<ComboboxSelected>>", lambda e: self._sound_changed())
        ui.Button(row, text="들어보기", command=lambda: sounds.play(self.sound)).pack(side="left", padx=10)

        self._label("알림 글씨체", bold=True, size=13, pady=(18, 6))
        self.font_opts = fonts.choices()
        cur = next((l for l, f in self.font_opts if f == fonts.family(self.font)), self.font_opts[0][0])
        self.var_font = tk.StringVar(value=cur)
        row = ttk.Frame(self.body)
        row.pack(fill="x", pady=(0, 6))
        cbf = ui.Combo(row, textvariable=self.var_font, values=[l for l, _ in self.font_opts],
                           state="readonly", width=24, font=(FONT, 12))
        cbf.pack(side="left")
        cbf.bind("<<ComboboxSelected>>", lambda e: self._font_changed())
        ui.Button(row, text="알림 미리보기", command=self._test).pack(side="left", padx=10)
        self._font_changed()

        self._label("윈도우를 켜면 자동으로 실행", bold=True, size=13, pady=(18, 6))
        ui.Chip(self.body, text="컴퓨터를 켤 때 자동으로 실행합니다 (권장)",
                variable=self.autostart, padx=18, pady=9).pack(anchor="w")
        self._label("꺼 두면 프로그램을 직접 켜지 않은 날은 알림이 오지 않아요.", MUTED, pady=(8, 0))

    def _sound_changed(self):
        label = self.var_sound.get()
        if label == "내 파일 고르기…":
            path = filedialog.askopenfilename(parent=self, title="알림 소리 파일 (wav)",
                                              filetypes=[("wav 소리 파일", "*.wav")])
            if path:
                self.sound = path
            self.var_sound.set(sounds.label_for(self.sound))
            vals = list(self.cb_sound["values"])
            if self.var_sound.get() not in vals:
                vals.insert(len(vals) - 1, self.var_sound.get())
                self.cb_sound["values"] = vals
        else:
            for l, p in self.sound_opts:
                if l == label:
                    self.sound = p
            if label.startswith("내 파일:"):
                pass            # 이미 고른 내 파일 그대로
        sounds.play(self.sound)

    def _font_changed(self):
        label = self.var_font.get()
        self.font = next((f for l, f in self.font_opts if l == label), "")

    def _test(self):
        self.on_test_alert(self.sound, self.font)

    # --------------------------------------------------- 마무리
    def _update_next(self):
        ok = True
        if self.step == 0:
            ok = bool(self.school["name"])
        elif self.step == 1:
            ok = (self.found_count > 0 and self.name_checked == self.teacher) or bool(self.manual)
        if hasattr(self, "btn_next"):
            self.btn_next.state(["!disabled"] if ok else ["disabled"])

    def _alive(self, attr):
        """백그라운드 결과가 돌아왔을 때 그 화면이 아직 떠 있는지."""
        w = getattr(self, attr, None)
        try:
            return bool(w) and self.winfo_exists() and w.winfo_exists()
        except tk.TclError:
            return False

    def _finish(self):
        ok = autostart.set_enabled(self.autostart.get())
        if self.autostart.get() and not ok:
            messagebox.showwarning("자동 실행", "자동 실행 등록이 안 됐습니다. 보안 프로그램이 막았을 수 있어요.\n"
                                   "알림은 프로그램이 켜져 있을 때만 옵니다.", parent=self)
        person_mode = comcigan.has_ids(self.data) and self.my_tid is not None
        cfg = store.update(
            configured=True, enabled=True,
            school_name=self.school["name"], school_code=str(self.school["school_code"]),
            local_code=str(self.school["local_code"]), teacher=self.teacher,
            # 교사 번호로 사람을 갈랐으면 과목·반 빼기는 필요 없다(번호가 없는 옛 자료일 때만 쓴다).
            exclude_rooms="" if person_mode else self.exclude,
            my_subjects=[] if person_mode else sorted(self.subjects),
            my_tid=self.my_tid if person_mode else None,
            my_sample=self.my_sample if person_mode else None, font=self.font,
            lesson_min=int(self.lesson), times=list(self.times), sound=self.sound,
            autostart=bool(self.autostart.get()), manual=self.manual,
            cache=self.data if self.data else None,
            fetched_at=(self.data or {}).get("받은날", ""))
        self.destroy()
        self.on_done(cfg)


class ManualDialog(tk.Toplevel):
    """컴시간이 안 될 때 시간표를 손으로 넣는다. 칸에 「1-4 수학」처럼 적는다."""

    def __init__(self, parent, manual, on_save):
        super().__init__(parent)
        self.title("시간표 직접 입력")
        self.configure(bg="white")
        self.transient(parent)
        self.on_save = on_save
        self.grab_set()
        tk.Label(self, text="내 수업이 있는 칸에 「반 과목」을 적으세요. (예: 1-4 수학)  없는 칸은 비워 두세요.",
                 bg="white", fg=MUTED, font=(FONT, 11), padx=18, pady=12).grid(row=0, column=0, columnspan=6, sticky="w")
        for c, d in enumerate(comcigan.DAY_NAMES):
            tk.Label(self, text=d, bg="white", font=(FONT, 12, "bold")).grid(row=1, column=c + 1, pady=(0, 4))
        self.vars = {}
        for p in range(1, schedule.MAX_PERIODS + 1):
            tk.Label(self, text="%d교시" % p, bg="white", font=(FONT, 11)).grid(row=p + 1, column=0, padx=(18, 6), pady=2)
            for d in range(5):
                v = tk.StringVar(value=manual.get("%d-%d" % (d, p), ""))
                self.vars[(d, p)] = v
                ttk.Entry(self, textvariable=v, width=11, font=(FONT, 11)).grid(row=p + 1, column=d + 1, padx=3, pady=2)
        bar = tk.Frame(self, bg="white")
        bar.grid(row=schedule.MAX_PERIODS + 3, column=0, columnspan=6, pady=14)
        ui.Button(bar, text="저장", kind="primary", padx=30, command=self._save).pack(side="left", padx=6)
        ui.Button(bar, text="취소", command=self.destroy).pack(side="left", padx=6)

    def _save(self):
        out = {}
        for (d, p), v in self.vars.items():
            if comcigan.parse_manual(v.get()):
                out["%d-%d" % (d, p)] = v.get().strip()
        self.destroy()
        self.on_save(out)
