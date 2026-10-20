# -*- coding: utf-8 -*-
"""설치 파일 만들기: python build.py
version.py 의 버전으로 PyInstaller → Inno Setup 순서로 빌드하고, 릴리스에 붙일 SHA256 을 출력한다."""
import hashlib
import os
import subprocess
import sys

import version

ISCC = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    os.chdir(HERE)
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm", "DontMissClass.spec"])
    subprocess.check_call([ISCC, "/DAppVer=" + version.__version__, "installer.iss"])
    out = os.path.join("installer_out", "%s%s.exe" % (version.INSTALLER_PREFIX, version.__version__))
    h = hashlib.sha256()
    with open(out, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    print("\n설치 파일:", os.path.abspath(out))
    print("릴리스 본문에 이 줄을 넣으세요(자동 업데이트가 검증에 씁니다):")
    print("SHA256: " + h.hexdigest())


if __name__ == "__main__":
    main()
