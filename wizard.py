# -*- coding: utf-8 -*-
"""첫 설치 튜토리얼 겸 설정 창. 같은 창을 설정에서 다시 연다(저장된 값이 미리 채워진다).

    1 학교 찾기  →  2 내 수업 확인  →  3 교시 시각  →  4 소리·자동 실행
"""
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import autostart
import comcigan
import schedule
import sounds
import store

FONT = "맑은 고딕"
ACCENT = "#1f54a8"
MUTED = "#5b6573"
ERR = "#c0392b"
OK = "#1e7d4f"
STEP_TITLES = ("학교 찾기", "내 수업 확인", "교시 시작 시각", "소리와 자동 실행")


class Wizard(tk.Toplevel):
    def __init__(self, root, on_done, on_test_alert, on_cancel=None, first_run=True):
        super().__init__(root)
        self.root_ = root
        self.on_done = on_done
        self.on_test_alert = on_test_alert
        self.on_cancel = on_cancel
        self.first_run = first_run
        self.title("놓치지마수업 — " + ("처음 설정" if first_run else "설정"))
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

        style = ttk.Style(self)
        style.configure(".", font=(FONT, 11))
        style.configure("TButton", padding=(14, 6))
        style.configure("Big.TButton", font=(FONT, 12, "bold"), padding=(20, 8))
        style.configure("TRadiobutton", background="white")
        style.configure("TCheckbutton", background="white")
        style.configure("TFrame", background="white")
        style.configure("TLabel", background="white")

        cfg = store.load()
        self.school = {"name": cfg["school_name"], "school_code": cfg["school_code"],
                       "local_code": cfg["local_code"]}
        self.teacher = cfg["teacher"]
        self.data = cfg.get("cache")            # 마지막으로 받은 시간표
        self.manual = dict(cfg.get("manual") or {})
        self.exclude = cfg.get("exclude_rooms") or ""
        self.lesson = int(cfg["lesson_min"] or 45)
        self.times = list(cfg["times"] or [])
        self.first = self.times[0] if self.times else "08:50"
        self.sound = cfg["sound"]
        self.autostart = tk.BooleanVar(value=bool(cfg["autostart"]))
        self.name_checked = ""                  # 확인을 마친 이름. 이름을 바꾸면 비워진다
        self.found_count = 0
        if self.data and self.teacher:           # 설정을 다시 여는 경우: 지난번 확인을 이어 쓴다
            n = len(comcigan.preview_lines(comcigan.my_periods(
                self.data, self.teacher, comcigan.parse_rooms(self.exclude))))
            if n:
                self.found_count, self.name_checked = n, self.teacher
        self._rebuilding = False
        self._q = queue.Queue()
        self.step = 0

        # 머리 — 단계 표시
        head = tk.Frame(self, bg=ACCENT)
        head.pack(fill="x")
        self.lbl_step = tk.Label(head, bg=ACCENT, fg="white", font=(FONT, 16, "bold"),
                                 anchor="w", padx=24, pady=16)
        self.lbl_step.pack(fill="x")
        foot = ttk.Frame(self, padding=(26, 8, 26, 20))
        foot.pack(side="bottom", fill="x")          # 먼저 붙여야 내용이 길어도 단추가 안 잘린다
        self.body = ttk.Frame(self, padding=(26, 18, 26, 6))
        self.body.pack(fill="both", expand=True)
        self.btn_back = ttk.Button(foot, text="이전", command=self.back)
        self.btn_back.pack(side="left")
        self.btn_next = ttk.Button(foot, text="다음", style="Big.TButton", command=self.next)
        self.btn_next.pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.after(100, self._poll)
        self._show(0)

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
        lb = tk.Label(self.body, text=text, bg="white", fg=color or "#1d2733", justify="left",
                      anchor="w", wraplength=wrap, font=(FONT, size, "bold" if bold else "normal"), **kw)
        lb.pack(fill="x", pady=pady)
        return lb

    def _show(self, n):
        self.step = n
        self._clear()
        self.lbl_step.config(text="%d / 4  %s" % (n + 1, STEP_TITLES[n]))
        self.btn_back.state(["!disabled"] if n > 0 else ["disabled"])
        self.btn_next.config(text="완료" if n == 3 else "다음")
        self.btn_next.state(["!disabled"])
        [self._page_school, self._page_name, self._page_times, self._page_alert][n]()

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
        ttk.Button(row, text="검색", command=self._search).pack(side="left", padx=(8, 0))

        self.lst = tk.Listbox(self.body, height=9, font=(FONT, 12), activestyle="none",
                              exportselection=False, relief="solid", bd=1,
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
        self.school = {"name": r["name"], "school_code": r["school_code"], "local_code": r["local_code"]}
        self.lesson = schedule.lesson_minutes_for(r["name"]) if not self.times else self.lesson
        self.lbl_status.config(text="선택: %s" % r["name"], fg=OK)
        self._update_next()

    # --------------------------------------------------- 2 내 수업 확인
    def _page_name(self):
        self._label("선생님 이름을 적어 주세요.", bold=True, size=13)
        self._label("컴시간은 이름을 두 글자로 줄여 보여 줘요(정유경 → 정유). 앞 두 글자가 같은 "
                    "선생님이 계시면 남의 수업이 섞일 수 있으니, 아래 목록이 내 수업이 맞는지 확인하세요.", MUTED)
        row = ttk.Frame(self.body)
        row.pack(fill="x", pady=(2, 8))
        self.var_name = tk.StringVar(value=self.teacher)
        ent = ttk.Entry(row, textvariable=self.var_name, font=(FONT, 13), width=14)
        ent.pack(side="left", ipady=3)
        ent.bind("<Return>", lambda e: self._check_name())
        ent.bind("<KeyRelease>", lambda e: self._name_edited())
        ent.focus_set()
        ttk.Button(row, text="내 수업 찾기", command=self._check_name).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="컴시간 없이 직접 입력", command=self._open_manual).pack(side="right")

        self.lbl_status = self._label("", MUTED, pady=(0, 6))
        # 목록은 길어질 수 있어 맨 아래에 두고, 입력칸은 그 위에 둔다(화면이 모자라도 잘리지 않게).
        ex = ttk.Frame(self.body)
        ex.pack(fill="x", pady=(0, 8))
        ttk.Label(ex, text="내 수업이 아닌 반 (있으면)").pack(side="left")
        self.var_excl = tk.StringVar(value=self.exclude)
        ee = ttk.Entry(ex, textvariable=self.var_excl, width=22, font=(FONT, 11))
        ee.pack(side="left", padx=8)
        ee.bind("<KeyRelease>", lambda e: self._exclude_edited())
        tk.Label(ex, text="예: 2-3, 3-1", bg="white", fg=MUTED, font=(FONT, 10)).pack(side="left")
        box = ttk.Frame(self.body)
        box.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(box)
        sb.pack(side="right", fill="y")
        self.txt = tk.Text(box, height=8, font=(FONT, 11), relief="solid", bd=1, state="disabled",
                           yscrollcommand=sb.set, bg="#f7f9fc", padx=10, pady=8)
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

    def _exclude_edited(self):
        self.exclude = self.var_excl.get().strip()
        if self.name_checked == self.teacher and self.data:
            self._render_preview()
            self._update_next()

    def _render_preview(self):
        mine = comcigan.my_periods(self.data, self.teacher, comcigan.parse_rooms(self.exclude))
        lines = comcigan.preview_lines(mine)
        self.found_count = len(lines)
        names = comcigan.matched_names(self.data, self.teacher)
        if not lines:
            self.lbl_status.config(
                text="「%s」로 된 수업을 찾지 못했습니다. 컴시간에 적힌 이름과 같은지 확인하거나 직접 입력해 주세요." % self.teacher,
                fg=ERR)
            self._set_text("")
        elif len(lines) > 30:
            # 한 선생님의 주당 수업은 보통 이보다 훨씬 적다. 이름이 겹친 다른 선생님 수업이 섞였다는 신호.
            self.lbl_status.config(
                text="주 %d시간은 한 분의 수업으로는 너무 많아요. 같은 이름(「%s」)을 쓰는 다른 선생님 수업이 섞인 것 같습니다. "
                     "내 수업이 아닌 반을 아래에 적어 빼 주세요." % (len(lines), ", ".join(names)), fg=ERR)
            self._set_text("\n".join(lines))
        else:
            self.lbl_status.config(
                text="컴시간에서 「%s」로 표시된 수업 주 %d시간을 찾았어요. 내 수업이 맞나요?" % (", ".join(names), len(lines)),
                fg=OK)
            self._set_text("\n".join(lines))

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
        self._label("1교시 시작 시각과 수업 길이를 고르면 나머지 교시는 쉬는 시간 10분으로 채워집니다.", MUTED)
        top = ttk.Frame(self.body)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="1교시 시작").pack(side="left")
        self.var_first = tk.StringVar(value=self.first)
        cb = ttk.Combobox(top, textvariable=self.var_first, values=schedule.first_start_choices(),
                          width=7, state="readonly", font=(FONT, 12))
        cb.pack(side="left", padx=(8, 22))
        cb.bind("<<ComboboxSelected>>", lambda e: self._refill())
        ttk.Label(top, text="수업 길이").pack(side="left")
        self.var_lesson = tk.IntVar(value=self.lesson)
        for m in schedule.LESSON_CHOICES:
            ttk.Radiobutton(top, text="%d분" % m, variable=self.var_lesson, value=m,
                            command=self._refill).pack(side="left", padx=(8, 0))

        self.rows = ttk.Frame(self.body)
        self.rows.pack(fill="x", pady=(4, 4))
        bar = ttk.Frame(self.body)
        bar.pack(fill="x")
        ttk.Button(bar, text="교시 추가", command=self._add).pack(side="left")
        ttk.Button(bar, text="마지막 교시 빼기", command=self._remove).pack(side="left", padx=8)
        self._label("● 는 내 수업이 있는 교시 표시입니다.", MUTED, pady=(6, 0))
        self.lbl_lunch = self._label("", OK, pady=(4, 0))
        self.lbl_hint = self._label("점심시간 때문에 시작 시각이 다른 교시가 있으면 그 교시의 시각을 고치세요. "
                                    "그 교시부터 뒤 교시가 자동으로 다시 계산됩니다.", MUTED, pady=(4, 0))
        self.lbl_err = self._label("", ERR, pady=(4, 0))
        if not self.times:
            self._refill()
        else:
            self._rebuild_rows()

    def _mine_periods(self):
        ps = set()
        if self.data:
            for cs in comcigan.my_periods(self.data, self.teacher, comcigan.parse_rooms(self.exclude)).values():
                ps.update(int(c["period"]) for c in cs)
        for key in self.manual:
            try:
                ps.add(int(key.split("-")[1]))
            except (ValueError, IndexError):
                pass
        return ps

    def _refill(self):
        self.first = self.var_first.get()
        self.lesson = int(self.var_lesson.get())
        count = len(self.times) or schedule.DEFAULT_COUNT
        self.times = schedule.fill(self.first, self.lesson, count)
        self._rebuild_rows()

    def _rebuild_rows(self):
        # 입력칸이 지워질 때 날아오는 FocusOut 이 다시 계산을 일으키지 않게 막는다.
        self._rebuilding = True
        for c in self.rows.winfo_children():
            c.destroy()
        self.row_vars = []
        mine = self._mine_periods()
        # 교시가 많아도 화면이 길어지지 않게 5개씩 두 줄(왼쪽 1~5교시, 오른쪽 6~9교시)로 놓는다.
        for i, t in enumerate(self.times):
            col, r = (0, i) if i < 5 else (4, i - 5)
            ttk.Label(self.rows, text="%d교시" % (i + 1), width=6, font=(FONT, 12)).grid(
                row=r, column=col, pady=3, sticky="w")
            var = tk.StringVar(value=t)
            self.row_vars.append(var)
            if i == 0:
                ttk.Label(self.rows, text=t, font=(FONT, 12, "bold"), width=8).grid(row=r, column=col + 1, sticky="w")
            else:
                e = ttk.Entry(self.rows, textvariable=var, width=7, font=(FONT, 12))
                e.grid(row=r, column=col + 1, sticky="w")
                e.bind("<Return>", lambda ev, k=i: self._commit(k))
                e.bind("<FocusOut>", lambda ev, k=i: self._commit(k))
            tk.Label(self.rows, text="●" if (i + 1) in mine else "", bg="white", fg=ACCENT,
                     font=(FONT, 11), width=2).grid(row=r, column=col + 2, sticky="w")
        self.rows.grid_columnconfigure(3, minsize=30)
        self.lbl_lunch.config(text=schedule.lunch_note(self.times, self.lesson))
        self.after_idle(lambda: setattr(self, "_rebuilding", False))

    def _commit(self, index):
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
            self.lbl_err.config(text="%d교시: %s" % (index + 1, e))
            self.row_vars[index].set(self.times[index])
            return False
        self.lbl_err.config(text="")
        self._rebuild_rows()
        return True

    def _commit_pending_entry(self):
        """다음으로 넘어가기 전에, 커서가 남아 있는 칸의 값을 반영한다."""
        for i in range(1, len(self.times)):
            if not self._commit(i):
                return False
        return True

    def _add(self):
        if len(self.times) >= schedule.MAX_PERIODS:
            self.lbl_err.config(text="교시는 %d교시까지 둘 수 있어요." % schedule.MAX_PERIODS)
            return
        self.times = schedule.add_period(self.times, self.lesson)
        self._rebuild_rows()

    def _remove(self):
        self.times = schedule.remove_last(self.times)
        self._rebuild_rows()

    # --------------------------------------------------- 4 소리·자동 실행
    def _page_alert(self):
        self._label("알림 소리를 고르세요.", bold=True, size=13)
        self.sound_opts = [("소리 없음", "")] + sounds.builtin()
        labels = [l for l, _ in self.sound_opts] + ["내 파일 고르기…"]
        cur = sounds.label_for(self.sound)
        if cur not in labels:
            labels.insert(len(labels) - 1, cur)
        self.var_sound = tk.StringVar(value=cur)
        row = ttk.Frame(self.body)
        row.pack(fill="x", pady=(0, 6))
        self.cb_sound = ttk.Combobox(row, textvariable=self.var_sound, values=labels, state="readonly",
                                     width=26, font=(FONT, 12))
        self.cb_sound.pack(side="left")
        self.cb_sound.bind("<<ComboboxSelected>>", lambda e: self._sound_changed())
        ttk.Button(row, text="들어보기", command=lambda: sounds.play(self.sound)).pack(side="left", padx=8)

        ttk.Separator(self.body).pack(fill="x", pady=14)
        self._label("윈도우를 켜면 자동으로 실행", bold=True, size=13)
        ttk.Checkbutton(self.body, text="컴퓨터를 켤 때 자동으로 실행합니다 (권장)",
                        variable=self.autostart).pack(anchor="w")
        self._label("자동 실행이 꺼져 있으면 프로그램을 직접 켜지 않은 날은 알림이 오지 않아요. "
                    "화면 오른쪽 아래 알림 영역의 종 모양 아이콘으로 계속 실행됩니다.", MUTED, pady=(4, 0))

        ttk.Separator(self.body).pack(fill="x", pady=14)
        self._label("알림이 어떻게 뜨는지 먼저 볼 수 있어요.", bold=True, size=13)
        ttk.Button(self.body, text="테스트 알림 띄워 보기", command=self._test).pack(anchor="w")
        self._label("알림 창은 화면 아무 곳이나 누를 때까지 닫히지 않고, 교체·보강으로 바뀐 수업에는 「바뀐 수업」 표시가 붙습니다.",
                    MUTED, pady=(8, 0))

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

    def _test(self):
        self.on_test_alert(self.sound)

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
        cfg = store.update(
            configured=True, enabled=True,
            school_name=self.school["name"], school_code=str(self.school["school_code"]),
            local_code=str(self.school["local_code"]), teacher=self.teacher,
            exclude_rooms=self.exclude,
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
        ttk.Button(bar, text="저장", style="Big.TButton", command=self._save).pack(side="left", padx=6)
        ttk.Button(bar, text="취소", command=self.destroy).pack(side="left", padx=6)

    def _save(self):
        out = {}
        for (d, p), v in self.vars.items():
            if comcigan.parse_manual(v.get()):
                out["%d-%d" % (d, p)] = v.get().strip()
        self.destroy()
        self.on_save(out)
