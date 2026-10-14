# -*- coding: utf-8 -*-
"""그림 한 장을 그대로 화면에 얹는 창(윈도우 전용). 투명한 부분은 뒤 화면이 비쳐서
둥근 모서리와 그림자가 매끈하게 나온다. 누르면 닫힌다.

Tk 의 창은 모서리를 투명하게 못 만들어서 윈도우 기능(layered window)을 직접 쓴다.
창은 Tk 와 같은 스레드에서 만들어, Tk 의 메시지 순환이 이 창의 클릭도 처리한다.
"""
import ctypes
import ctypes.wintypes as wt

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

WS_POPUP = 0x80000000
WS_EX_TOPMOST, WS_EX_TOOLWINDOW, WS_EX_LAYERED = 0x8, 0x80, 0x80000
WM_DESTROY, WM_CLOSE, WM_KEYDOWN = 0x2, 0x10, 0x100
WM_LBUTTONDOWN, WM_RBUTTONDOWN = 0x201, 0x204
VK_RETURN, VK_SPACE, VK_ESCAPE = 0x0D, 0x20, 0x1B
SW_SHOW = 5
HWND_TOPMOST = wt.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_SHOWWINDOW = 0x1, 0x2, 0x40
ULW_ALPHA = 2
IDC_HAND = 32649
ARM_MS = 700                 # 뜬 직후 이 시간 안의 클릭은 무시한다(다른 창을 누르던 손이 닿아 바로 꺼지지 않게)

CLASS_NAME = "DontMissClassAlert"


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON), ("hCursor", wt.HANDLE),
                ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR), ("hIconSm", wt.HICON)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
user32.CreateWindowExW.restype = wt.HWND
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wt.ATOM
user32.LoadCursorW.argtypes = [wt.HINSTANCE, wt.LPCWSTR]
user32.LoadCursorW.restype = wt.HANDLE
user32.GetDC.argtypes = [wt.HWND]
user32.GetDC.restype = wt.HDC
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.UpdateLayeredWindow.argtypes = [wt.HWND, wt.HDC, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE),
                                       wt.HDC, ctypes.POINTER(wt.POINT), wt.COLORREF,
                                       ctypes.POINTER(BLENDFUNCTION), wt.DWORD]
user32.UpdateLayeredWindow.restype = wt.BOOL
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.DestroyWindow.argtypes = [wt.HWND]
user32.IsWindow.argtypes = [wt.HWND]
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, wt.UINT, ctypes.POINTER(ctypes.c_void_p),
                                   wt.HANDLE, wt.DWORD]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.SelectObject.argtypes = [wt.HDC, wt.HANDLE]
gdi32.SelectObject.restype = wt.HANDLE
gdi32.DeleteObject.argtypes = [wt.HANDLE]
gdi32.DeleteDC.argtypes = [wt.HDC]
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HINSTANCE
kernel32.GetTickCount64.restype = ctypes.c_ulonglong

_windows = {}        # hwnd -> {"born": 시각, "on_close": 함수}
_registered = False
_proc_ref = None     # 파이썬이 창 처리 함수를 치워 버리지 않게 붙들어 둔다


def _wndproc(hwnd, msg, wparam, lparam):
    info = _windows.get(hwnd)
    if msg in (WM_LBUTTONDOWN, WM_RBUTTONDOWN):
        if info and kernel32.GetTickCount64() - info["born"] >= ARM_MS:
            user32.DestroyWindow(hwnd)
        return 0
    if msg == WM_KEYDOWN and wparam in (VK_RETURN, VK_SPACE, VK_ESCAPE):
        user32.DestroyWindow(hwnd)
        return 0
    if msg == WM_CLOSE:
        user32.DestroyWindow(hwnd)
        return 0
    if msg == WM_DESTROY:
        info = _windows.pop(hwnd, None)
        if info and info["on_close"]:
            try:
                info["on_close"]()
            except Exception:
                pass
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def _register():
    global _registered, _proc_ref
    if _registered:
        return
    _proc_ref = WNDPROC(_wndproc)
    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.lpfnWndProc = _proc_ref
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.hCursor = user32.LoadCursorW(None, ctypes.cast(IDC_HAND, wt.LPCWSTR))
    wc.lpszClassName = CLASS_NAME
    if not user32.RegisterClassExW(ctypes.byref(wc)):
        raise OSError("창 종류를 등록하지 못했습니다.")
    _registered = True


def _bgra_premultiplied(img):
    """RGBA 그림 → 윈도우가 요구하는 「알파를 미리 곱한 BGRA」 바이트."""
    from PIL import Image
    r, g, b, a = img.convert("RGBa").split()
    return Image.merge("RGBA", (b, g, r, a)).tobytes()


def show(img, x, y, on_close=None):
    """RGBA 그림을 화면 (x, y) 에 창으로 띄운다. 창 핸들을 돌려준다. 못 만들면 예외."""
    _register()
    w, h = img.size
    hwnd = user32.CreateWindowExW(WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW, CLASS_NAME, "놓치지마수업",
                                  WS_POPUP, x, y, w, h, None, None, kernel32.GetModuleHandleW(None), None)
    if not hwnd:
        raise OSError("창을 만들지 못했습니다.")
    _windows[hwnd] = {"born": kernel32.GetTickCount64(), "on_close": on_close}
    try:
        _paint(hwnd, img, x, y)
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW)
        user32.ShowWindow(hwnd, SW_SHOW)
        user32.SetForegroundWindow(hwnd)       # 안 되어도(다른 창이 잡고 있으면) 클릭으로 닫을 수 있다
    except Exception:
        _windows.pop(hwnd, None)
        user32.DestroyWindow(hwnd)
        raise
    return hwnd


def _paint(hwnd, img, x, y):
    w, h = img.size
    screen_dc = user32.GetDC(None)
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    bmi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, w * h * 4, 0, 0, 0, 0)
    bits = ctypes.c_void_p()
    bmp = gdi32.CreateDIBSection(screen_dc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    try:
        if not bmp or not bits:
            raise OSError("그림 메모리를 만들지 못했습니다.")
        data = _bgra_premultiplied(img)
        ctypes.memmove(bits, data, len(data))
        old = gdi32.SelectObject(mem_dc, bmp)
        pt_dst, size, pt_src = wt.POINT(x, y), wt.SIZE(w, h), wt.POINT(0, 0)
        blend = BLENDFUNCTION(0, 0, 255, 1)      # AC_SRC_OVER, 그림 자체의 알파 사용
        ok = user32.UpdateLayeredWindow(hwnd, screen_dc, ctypes.byref(pt_dst), ctypes.byref(size),
                                        mem_dc, ctypes.byref(pt_src), 0, ctypes.byref(blend), ULW_ALPHA)
        gdi32.SelectObject(mem_dc, old)
        if not ok:
            raise OSError("창에 그림을 얹지 못했습니다.")
    finally:
        if bmp:
            gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)


def is_open(hwnd):
    return bool(user32.IsWindow(hwnd))


def close(hwnd):
    if user32.IsWindow(hwnd):
        user32.DestroyWindow(hwnd)
