# -*- coding: utf-8 -*-
"""설정 창의 모양. 흰 바탕에 파랑 한 가지 색, 둥근 단추, 얇은 선.

Tk 의 기본 단추는 각져서 그림으로 둥근 단추를 만든다. 입력칸·선택칸은 ttk 의 clam 모양을 다듬는다.
글씨체는 「프리텐다드」가 fonts 폴더에 있으면 그것을, 없으면 윈도우 「맑은 고딕」을 쓴다.
"""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

import fonts

BG = "#ffffff"
SURFACE = "#f6f7f9"
LINE = "#e5e8eb"
TEXT = "#191f28"
MUTED = "#6b7684"
ACCENT = "#3182f6"
ACCENT_HOVER = "#1b64da"
ACCENT_DOWN = "#1957c2"
ERR = "#e03131"
OK = "#0b8a5a"
SECOND = "#f2f4f6"
SECOND_HOVER = "#e5e8eb"
SECOND_DOWN = "#d9dde2"
SECOND_TEXT = "#4e5968"
DISABLED = "#eceff2"
DISABLED_TEXT = "#aab2bb"

_family = None


def family():
    """쓸 글씨체. 프리텐다드(fonts 폴더)가 있으면 그것, 없으면 맑은 고딕."""
    global _family
    if _family is None:
        _family = "맑은 고딕"
        for _label, fam, _path in fonts._load():
            if fam.lower().startswith("pretendard"):
                _family = fam
                break
    return _family


def font(size=11, bold=False):
    return (family(), size, "bold" if bold else "normal")


# ------------------------------------------------------------------ 둥근 그림
_img_cache = {}


def rounded_image(w, h, radius, fill, bg):
    """매끈한 둥근 사각형 그림(크게 그려 줄여서 가장자리를 부드럽게)."""
    key = (w, h, radius, fill, bg)
    if key not in _img_cache:
        s = 4
        im = Image.new("RGB", (w * s, h * s), bg)
        ImageDraw.Draw(im).rounded_rectangle((0, 0, w * s - 1, h * s - 1), radius=radius * s, fill=fill)
        _img_cache[key] = ImageTk.PhotoImage(im.resize((w, h), Image.LANCZOS))
    return _img_cache[key]


class Button(tk.Label):
    """둥근 단추. ttk.Button 처럼 config(text=, state=)·state([...])·instate([...]) 를 쓸 수 있다.

    kind: "primary"(파랑 · 가장 중요한 동작) · "secondary"(옅은 회색)
    """

    def __init__(self, parent, text="", command=None, kind="secondary", size=11,
                 padx=20, pady=10, radius=11, bg=BG, **kw):
        super().__init__(parent, bd=0, highlightthickness=0, cursor="hand2", compound="center",
                         bg=bg, takefocus=1, **kw)
        self._text, self._command, self._kind = text, command, kind
        self._padx, self._pady, self._radius, self._bg = padx, pady, radius, bg
        self._font = tkfont.Font(family=family(), size=size, weight="bold" if kind == "primary" else "normal")
        self._disabled = self._hover = self._down = False
        super().configure(font=self._font)
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, down=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(down=True))
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Return>", lambda e: self._fire())
        self.bind("<space>", lambda e: self._fire())
        self._redraw()

    # --- ttk 와 같은 쓰임새
    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        redraw = False
        if "text" in kw:
            self._text, redraw = kw.pop("text"), True
        if "command" in kw:
            self._command = kw.pop("command")
        if "state" in kw:
            self._disabled, redraw = kw.pop("state") == "disabled", True
        if kw:
            super().configure(**kw)
        if redraw:
            self._redraw()

    config = configure

    def state(self, spec=None):
        if spec is None:
            return ("disabled",) if self._disabled else ()
        for s in spec:
            if s in ("disabled", "!disabled"):
                self._disabled = (s == "disabled")
        self._redraw()

    def instate(self, spec):
        return all(self._disabled if s == "disabled" else (not self._disabled if s == "!disabled" else False)
                   for s in spec)

    # --- 모양
    def _set(self, **kw):
        for k, v in kw.items():
            setattr(self, "_" + k, v)
        self._redraw()

    def _release(self, _e):
        was_down = self._down
        self._set(down=False)
        if was_down and self._hover:
            self._fire()

    def _fire(self):
        if not self._disabled and self._command:
            self._command()

    def _redraw(self):
        if self._disabled:
            fill, fg, cur = DISABLED, DISABLED_TEXT, "arrow"
        elif self._kind == "primary":
            fill = ACCENT_DOWN if self._down else (ACCENT_HOVER if self._hover else ACCENT)
            fg, cur = "white", "hand2"
        else:
            fill = SECOND_DOWN if self._down else (SECOND_HOVER if self._hover else SECOND)
            fg, cur = SECOND_TEXT, "hand2"
        w = self._font.measure(self._text) + 2 * self._padx
        h = self._font.metrics("linespace") + 2 * self._pady
        super().configure(image=rounded_image(w, h, self._radius, fill, self._bg), text=self._text,
                          fg=fg, cursor=cur)


# ------------------------------------------------------------------ ttk 모양
def setup_styles(win):
    """ttk 의 입력칸·선택칸·글자를 흰 바탕 · 얇은 선 · 파랑 강조로 맞춘다."""
    st = ttk.Style(win)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    f = family()
    st.configure(".", font=(f, 11), background=BG, foreground=TEXT)
    st.configure("TFrame", background=BG)
    st.configure("TLabel", background=BG, foreground=TEXT)
    st.configure("TSeparator", background=LINE)
    st.configure("TCombobox", arrowsize=24, background=SECOND)         # 화살표 칸을 넓고 옅은 회색으로
    st.map("TCombobox", background=[("active", SECOND_HOVER), ("pressed", SECOND_DOWN)])
    for name in ("TEntry", "TCombobox"):
        st.configure(name, fieldbackground=BG, background=BG, foreground=TEXT, bordercolor="#d0d5dd",
                     lightcolor="#d0d5dd", darkcolor="#d0d5dd", padding=(10, 7), arrowcolor=MUTED)
        st.map(name, bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
               darkcolor=[("focus", ACCENT)], fieldbackground=[("readonly", BG)],
               foreground=[("readonly", TEXT)], selectbackground=[("readonly", BG)],
               selectforeground=[("readonly", TEXT)])
    for name in ("TCheckbutton", "TRadiobutton"):
        st.configure(name, background=BG, foreground=TEXT, indicatorbackground=BG,
                     indicatorforeground=ACCENT, bordercolor="#c5cbd3", focuscolor=BG, padding=(2, 3))
        st.map(name, background=[("active", BG)], indicatorbackground=[("selected", ACCENT), ("active", "#eef4ff")],
               indicatorforeground=[("selected", "white")], bordercolor=[("selected", ACCENT)])
    st.layout("Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
        ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    st.configure("Vertical.TScrollbar", background="#d0d5dd", troughcolor=SURFACE, bordercolor=SURFACE,
                 lightcolor="#d0d5dd", darkcolor="#d0d5dd", gripcount=0, width=8)
    st.map("Vertical.TScrollbar", background=[("active", "#c5cbd3")])
    win.option_add("*TCombobox*Listbox.font", (f, 11))
    win.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    win.option_add("*TCombobox*Listbox.selectForeground", "white")
    win.option_add("*TCombobox*Listbox.background", BG)


def tweak_title_bar(win):
    """윈도우 11 이면 제목줄을 흰색·진한 글씨로 맞춘다(윈도우 10 은 기본이 이미 흰색이라 그대로)."""
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        dwm = ctypes.windll.dwmapi
        for attr, rgb in ((35, 0x00FFFFFF), (36, 0x00281F19)):       # 제목줄 색 · 제목 글자색 (BGR)
            c = ctypes.c_int(rgb)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(c), ctypes.sizeof(c))
    except Exception:
        pass


class Chip(tk.Label):
    """둥근 선택 칩. variable 이 BooleanVar 면 켜고 끄는 칩, value 를 주면 여럿 중 하나 고르는 칩.
    켜지면 파랑, 꺼져 있으면 옅은 회색."""

    def __init__(self, parent, text, variable, value=None, command=None, size=11,
                 padx=16, pady=8, radius=10, bg=BG):
        super().__init__(parent, bd=0, highlightthickness=0, cursor="hand2", compound="center",
                         bg=bg, takefocus=1)
        self._text, self._var, self._value, self._command = text, variable, value, command
        self._padx, self._pady, self._radius, self._bg = padx, pady, radius, bg
        self._hover = False
        self._font = tkfont.Font(family=family(), size=size)
        self._font_on = tkfont.Font(family=family(), size=size, weight="bold")
        self._trace = variable.trace_add("write", lambda *a: self._safe_redraw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", lambda e: self._click())
        self.bind("<space>", lambda e: self._click())
        self.bind("<Destroy>", self._on_destroy)
        self._redraw()

    def _on(self):
        return bool(self._var.get()) if self._value is None else self._var.get() == self._value

    def _click(self):
        if self._value is None:
            self._var.set(not self._var.get())
        else:
            self._var.set(self._value)
        if self._command:
            self._command()

    def _set_hover(self, v):
        self._hover = v
        self._redraw()

    def _on_destroy(self, e):
        if e.widget is self:
            try:
                self._var.trace_remove("write", self._trace)
            except Exception:
                pass

    def _safe_redraw(self):
        try:
            self._redraw()
        except tk.TclError:
            pass

    def _redraw(self):
        on = self._on()
        f = self._font_on if on else self._font
        if on:
            fill, fg = (ACCENT_HOVER if self._hover else ACCENT), "white"
        else:
            fill, fg = (SECOND_HOVER if self._hover else SECOND), SECOND_TEXT
        w = max(self._font_on.measure(self._text), f.measure(self._text)) + 2 * self._padx
        h = f.metrics("linespace") + 2 * self._pady
        super().configure(image=rounded_image(w, h, self._radius, fill, self._bg), text=self._text,
                          fg=fg, font=f)


class Combo(ttk.Combobox):
    """고르는 칸. 화살표만이 아니라 칸 어디를 눌러도 목록이 열린다(화살표 칸이 좁아 누르기 힘들다는 의견)."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._open)

    def _open(self, _e):
        if str(self.cget("state")) == "readonly":
            self.focus_set()
            self.tk.call("ttk::combobox::Post", str(self))
            return "break"
