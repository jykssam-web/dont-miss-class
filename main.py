# -*- coding: utf-8 -*-
"""놓치지마수업 — 내 수업이 시작하는 때 크게 알려 주는 작은 프로그램.

실행
    main.py              처음이면 설정 마법사, 아니면 설정 창을 연다
    main.py --background 창 없이 트레이에서 조용히 지킨다(윈도우 시작 때 이렇게 켜진다)
    main.py --demo       테스트 알림을 바로 띄운다
"""
import ctypes
import datetime as dt
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox

import alert_window
import autostart
import comcigan
import schedule
import store
import updater
import version

LATE_GRACE_MIN = 3          # 절전에서 깨어 늦게 확인해도 이 안이면 알린다
REFRESH_CHECK_SEC = 300     # 시간표를 새로 받을 때가 됐는지 보는 간격
UPDATE_CHECK_HOURS = 6      # 새 버전이 있는지 보는 간격
UPDATE_QUIET_MIN = 10       # 수업 시작 앞뒤 이 시간 안에는 설치(재시작)하지 않는다


def _single_instance():
    """이미 켜져 있으면 False. 이름 붙은 뮤텍스로 가린다."""
    try:
        h = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\DontMissClass_Mutex")
        if ctypes.windll.kernel32.GetLastError() == 183:    # ERROR_ALREADY_EXISTS
            return False
        _single_instance.handle = h          # 닫히지 않게 붙들어 둔다
    except Exception:
        pass
    return True


def _dpi():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class App:
    def __init__(self, background, demo):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.report_callback_exception = lambda *a: store.log("화면 오류: %r" % (a[1],))
        self.q = queue.Queue()               # 트레이 스레드 → 화면 스레드
        self.fired = set()                   # (날짜, 교시) 이미 알린 것
        self.wizard = None
        self.cfg = store.load()
        self.last_error = ""
        self.icon = None
        self.pending_update = None            # 내려받아 검증까지 마친 설치 파일 경로
        self._update_busy = False
        self._start_tray()
        self.root.after(300, self._drain)
        self.root.after(1000, self._tick)
        self.root.after(2000, self._refresh_loop)
        self.root.after(60 * 1000, self._update_loop)
        self.root.after(90 * 1000, self._install_when_quiet)

        if not self.cfg["configured"]:
            self.open_settings(first_run=True)
        elif not background:
            self.open_settings(first_run=False)
        if demo:
            self.root.after(500, self.test_alert)

    # ------------------------------------------------------------ 감시
    def _tick(self):
        try:
            self._check_due()
        except Exception as e:
            store.log("감시 오류: %r" % e)
        self.root.after(1000, self._tick)

    def _check_due(self):
        cfg = self.cfg
        if not cfg["configured"] or not cfg["enabled"] or not cfg["times"]:
            return
        now = dt.datetime.now()
        today = now.date()
        self.fired = {k for k in self.fired if k[0] == today}      # 지난 날 기록은 버린다
        now_min = now.hour * 60 + now.minute
        for i, t in enumerate(cfg["times"], 1):
            start = schedule.to_min(t)
            if start is None or (today, i) in self.fired:
                continue
            late = now_min - start
            if 0 <= late < LATE_GRACE_MIN:
                self.fired.add((today, i))
                lesson = comcigan.lessons_on(today).get(i)
                if lesson:
                    alert_window.show(self.root, i, t, lesson, cfg["sound"])

    def _refresh_loop(self):
        """컴시간 시간표를 백그라운드에서 새로 받는다. 못 받으면 옛것을 그대로 쓴다."""
        if self.cfg["configured"] and self.cfg["school_name"] and (comcigan.is_stale()):
            threading.Thread(target=self._refresh_once, daemon=True).start()
        self.root.after(REFRESH_CHECK_SEC * 1000, self._refresh_loop)

    def _refresh_once(self, force=False):
        try:
            comcigan.refresh(force=force)
            self.last_error = ""
        except Exception as e:
            self.last_error = str(e)
            store.log("시간표 갱신 실패: %s" % e)

    # ------------------------------------------------------------ 자동 업데이트
    def _update_loop(self):
        self.check_update()
        self.root.after(UPDATE_CHECK_HOURS * 3600 * 1000, self._update_loop)

    def check_update(self):
        if not updater.can_self_update() or self._update_busy or self.pending_update:
            return
        self._update_busy = True
        threading.Thread(target=self._update_once, daemon=True).start()

    def _update_once(self):
        try:
            info = updater.check()
            if info:
                store.log("새 버전 %s 발견 (현재 %s)" % (info["version"], version.__version__))
                self.pending_update = updater.download(info)
        except Exception as e:
            store.log("업데이트 실패: %s" % e)
        finally:
            self._update_busy = False

    def _quiet_now(self):
        """수업 알림이 막 울렸거나 곧 울릴 때는 재시작하지 않는다."""
        now = dt.datetime.now()
        nm = now.hour * 60 + now.minute
        for t in self.cfg["times"]:
            s = schedule.to_min(t)
            if s is not None and -UPDATE_QUIET_MIN <= nm - s <= UPDATE_QUIET_MIN:
                return False
        return not any(w.winfo_exists() for w in self.root.winfo_children()
                       if isinstance(w, tk.Toplevel) and w is not self.wizard)

    def _install_when_quiet(self):
        try:
            if self.pending_update and self._quiet_now() and not (self.wizard and self.wizard.winfo_exists()):
                path, self.pending_update = self.pending_update, None
                updater.install(path)
        except Exception as e:
            store.log("업데이트 설치 실패: %r" % e)
        self.root.after(60 * 1000, self._install_when_quiet)

    def update_now(self):
        """트레이의 「업데이트 확인」. 결과를 말풍선으로 알려 준다."""
        if not updater.can_self_update():
            self._balloon("설치판에서만 업데이트할 수 있어요.")
            return
        self._balloon("새 버전이 있는지 확인하고 있어요…")
        def work():
            try:
                info = updater.check()
                if not info:
                    self._balloon("최신 버전(%s)을 쓰고 계세요." % version.__version__)
                    return
                self.pending_update = updater.download(info)
                self._balloon("새 버전 %s을(를) 받았어요. 수업이 없는 때에 자동으로 설치돼요." % info["version"])
            except Exception as e:
                store.log("업데이트 실패: %s" % e)
                self._balloon("업데이트하지 못했어요. 잠시 뒤 다시 시도해 주세요.")
        threading.Thread(target=work, daemon=True).start()

    def _balloon(self, text):
        try:
            if self.icon is not None:
                self.icon.notify(text, "놓치지마수업")
        except Exception:
            pass

    # ------------------------------------------------------------ 화면 조작
    def open_settings(self, first_run=None):
        if self.wizard is not None and self.wizard.winfo_exists():
            self.wizard.lift()
            self.wizard.focus_force()
            return
        from wizard import Wizard
        if first_run is None:                       # 아직 설정을 마친 적 없으면 「처음 설정」
            first_run = not store.load()["configured"]
        self.wizard = Wizard(self.root, on_done=self._settings_done, on_test_alert=self._demo_with_sound,
                             on_cancel=self._settings_closed, first_run=first_run)

    def _settings_done(self, cfg):
        self.cfg = cfg
        self.fired = set()
        threading.Thread(target=self._refresh_once, kwargs={"force": True}, daemon=True).start()
        self._update_tray()
        messagebox.showinfo("놓치지마수업", "설정을 마쳤어요.\n수업이 시작될 때 알려 드릴게요.\n"
                            "프로그램은 화면 오른쪽 아래 종 모양 아이콘으로 계속 켜져 있습니다.")

    def _settings_closed(self):
        """설정 창의 닫기(X)는 프로그램을 끄지 않는다. 트레이에 남아 있고, 끄려면 트레이 메뉴의 「종료」.
        처음 설정을 마치지 않고 닫았으면 트레이에서 다시 열 수 있다고 한 번 알려 준다."""
        self.cfg = store.load()
        self._update_tray()
        if not self.cfg["configured"] and self.icon is not None:
            try:
                self.icon.notify("아직 설정이 끝나지 않았어요. 이 아이콘을 눌러 설정을 마치면 알림이 시작돼요.",
                                 "놓치지마수업")
            except Exception:
                pass

    def test_alert(self):
        self._demo_with_sound(self.cfg["sound"])

    def _demo_with_sound(self, sound, font=None):
        t = (self.cfg["times"] or ["08:50"])[0]
        alert_window.show(self.root, 1, t, {"room": "1-4", "subject": "수학", "replaced": True}, sound, font)

    def refresh_now(self):
        threading.Thread(target=self._refresh_once, kwargs={"force": True}, daemon=True).start()

    def toggle_enabled(self):
        self.cfg = store.update(enabled=not self.cfg["enabled"])
        self._update_tray()

    # ------------------------------------------------------------ 트레이
    def _next_text(self):
        cfg = self.cfg
        if not cfg["configured"]:
            return "설정이 필요합니다"
        if not cfg["enabled"]:
            return "알림이 꺼져 있습니다"
        now = dt.datetime.now()
        lessons = comcigan.lessons_on(now.date())
        nm = now.hour * 60 + now.minute
        for i, t in enumerate(cfg["times"], 1):
            s = schedule.to_min(t)
            if s is not None and s > nm and i in lessons:
                l = lessons[i]
                return "다음 수업: %d교시 %s %s" % (i, t, l["room"])
        return "오늘 남은 수업이 없습니다"

    def _start_tray(self):
        try:
            import pystray
            import icon
            menu = pystray.Menu(
                pystray.MenuItem(lambda item: self._next_text(), None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("설정 열기", lambda: self.q.put(self.open_settings), default=True),
                pystray.MenuItem("알림 켜기", lambda: self.q.put(self.toggle_enabled),
                                 checked=lambda item: self.cfg["enabled"]),
                pystray.MenuItem("테스트 알림", lambda: self.q.put(self.test_alert)),
                pystray.MenuItem("시간표 지금 새로 받기", lambda: self.q.put(self.refresh_now)),
                pystray.MenuItem("업데이트 확인 (v%s)" % version.__version__, lambda: self.q.put(self.update_now)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("종료", lambda: self.q.put(self.quit)),
            )
            self.icon = pystray.Icon("DontMissClass", icon.make_image(64), "놓치지마수업", menu)
            self.icon.run_detached()
        except Exception as e:
            store.log("트레이 시작 실패: %r" % e)
            self.icon = None

    def _update_tray(self):
        if self.icon is not None:
            try:
                self.icon.update_menu()
            except Exception:
                pass

    def _drain(self):
        try:
            while True:
                self.q.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(200, self._drain)

    def quit(self):
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
        self.root.after(0, self.root.destroy)

    def run(self):
        self.root.mainloop()


def main():
    args = set(sys.argv[1:])
    _dpi()
    if not _single_instance():
        if "--background" not in args:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("놓치지마수업", "이미 실행 중입니다.\n화면 오른쪽 아래 종 모양 아이콘을 눌러 설정을 여세요.")
        return
    App(background="--background" in args, demo="--demo" in args).run()


if __name__ == "__main__":
    main()
