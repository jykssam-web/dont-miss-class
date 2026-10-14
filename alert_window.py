# -*- coding: utf-8 -*-
"""수업 알림 창. 교시가 시작하는 때 크게 뜨고, 누를 때까지 닫히지 않는다(창 아무 곳이나 누르면 닫힘).

기본은 모서리가 둥글고 그림자가 있는 그림 창(native_window). 그 창을 못 만드는 PC에서는
Tk 창(_show_tk)으로 물러선다."""
import tkinter as tk
import tkinter.font as tkfont

import fonts
import sounds
import store

BG = "#0f2a4a"
FG = "#ffffff"
SUB = "#b9cdea"
ACCENT = "#ffb020"

_open = []          # 떠 있는 알림. 겹쳐 뜨면 조금씩 비껴 놓는다


def _fit_size(font, text, max_px, start, weight="bold"):
    """글이 max_px 안에 들어오는 가장 큰 글자 크기(pt). 긴 반 이름이 와도 넘치지 않게."""
    size = start
    while size > 24:
        if tkfont.Font(family=font, size=size, weight=weight).measure(text) <= max_px:
            break
        size -= 4
    return size


def show(root, period, time_text, lesson, sound_path="", font=None):
    """알림 창을 하나 띄운다. lesson = {"room","subject","replaced"}
    font 를 안 주면 설정에 저장된 글씨체를 쓴다. 닫을 때 쓸 창 핸들을 돌려준다."""
    family = fonts.family(store.load()["font"] if font is None else font)
    try:
        return _show_round(root, period, time_text, lesson, sound_path, family)
    except Exception as e:                  # 그림 창이 안 되면 예전 모양이라도 띄운다
        store.log("둥근 알림 창 실패, Tk 창으로 물러섬: %r" % e)
        return _show_tk(root, period, time_text, lesson, sound_path, family)


def _show_round(root, period, time_text, lesson, sound_path, family):
    import alert_render
    import native_window
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
    img, _margin = alert_render.render(period, time_text, lesson, family, scale, sw)
    off = int(28 * scale) * len(_open)
    x = (sw - img.width) // 2 + off
    y = max(0, (sh - img.height) // 2 - int(20 * scale)) + off
    holder = {}

    def closed():
        if holder.get("h") in _open:
            _open.remove(holder["h"])
        if not _open:
            sounds.stop()

    holder["h"] = native_window.show(img, x, y, on_close=closed)
    _open.append(holder["h"])
    sounds.play(sound_path)
    return holder["h"]


def _show_tk(root, period, time_text, lesson, sound_path, family):
    FONT = family
    win = tk.Toplevel(root)
    win.title("놓치지마수업")
    win.configure(bg=BG)
    win.attributes("-topmost", True)
    win.resizable(False, False)
    try:                                  # 제목줄 아이콘을 기본 깃털 대신 종 모양으로
        from PIL import ImageTk
        import icon
        win._icon = ImageTk.PhotoImage(icon.make_image(32))
        win.iconphoto(False, win._icon)
    except Exception:
        pass

    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w = min(1000, int(sw * 0.74))

    room = (lesson.get("room") or "").strip()
    subject = (lesson.get("subject") or "").strip()
    big = ("%s 수업입니다" % room) if room else ("%s 수업입니다" % (subject or "수업"))
    big_size = _fit_size(FONT, big, w - 80, 64)

    # 안내 문구를 먼저 아래에 붙여 두면, 화면이 작아도 항상 보인다.
    tk.Label(win, text="화면 아무 곳이나 누르면 닫힙니다", bg=BG, fg=SUB,
             font=(FONT, 16)).pack(side="bottom", pady=(10, 26))

    tk.Label(win, text="%d교시 · %s" % (period, time_text), bg=BG, fg=SUB,
             font=(FONT, 24)).pack(pady=(36, 0))
    tk.Label(win, text=big, bg=BG, fg=FG, font=(FONT, big_size, "bold")).pack(pady=(10, 0), expand=True)
    if subject and room:
        tk.Label(win, text=subject, bg=BG, fg=SUB, font=(FONT, 30)).pack()
    if lesson.get("replaced"):
        tk.Label(win, text="  바뀐 수업  ", bg=ACCENT, fg="#3a2500",
                 font=(FONT, 24, "bold")).pack(pady=(14, 0))

    # 높이는 내용에 맞추고 화면 가운데에 놓는다. 겹쳐 뜨는 알림은 조금씩 비껴 둔다.
    win.update_idletasks()
    h = min(win.winfo_reqheight() + 30, int(sh * 0.9))
    off = 28 * len(_open)
    win.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2 + off, max(0, (sh - h) // 2 - 20 + off)))

    # 누를 때까지 닫히지 않는다. 엔터·스페이스·창 닫기(X)도 닫기로 본다.
    win.protocol("WM_DELETE_WINDOW", lambda: close(win))
    win.bind("<Return>", lambda e: close(win))
    win.bind("<space>", lambda e: close(win))
    # 창 어디를 눌러도 닫는다. 뜨는 순간 다른 창을 누르던 손이 닿아 바로 꺼지지 않게 0.7초는 무시한다.
    armed = {"on": False}
    win.after(700, lambda: armed.update(on=True))

    def click(_e):
        if armed["on"]:
            close(win)

    def bind_all(w):
        w.bind("<Button-1>", click)
        for c in w.winfo_children():
            bind_all(c)
    bind_all(win)
    _open.append(win)

    win.lift()
    win.focus_force()
    # 다른 창에 가려지지 않게 한 번 더 위로 올린다.
    win.after(150, lambda: (win.lift(), win.attributes("-topmost", True)))
    sounds.play(sound_path)
    return win


def close(win):
    if isinstance(win, int):                # 그림 창(핸들)
        import native_window
        native_window.close(win)            # 닫히면서 목록 정리·소리 멈춤은 closed() 가 한다
        return
    if win in _open:
        _open.remove(win)
    if not _open:
        sounds.stop()
    try:
        win.destroy()
    except tk.TclError:
        pass
