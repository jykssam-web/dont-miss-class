# -*- coding: utf-8 -*-
"""자동 업데이트. GitHub 릴리스의 최신 설치 파일을 받아 조용히 설치한다.

흐름: 최신 릴리스 조회 → 내 버전보다 높으면 설치 파일 내려받기 → 릴리스 본문에 적힌 SHA256 과
대조 → 수업 알림에 지장이 없는 때에 /VERYSILENT 로 설치(설치 프로그램이 이 프로그램을 닫고,
설치가 끝나면 --background 로 다시 켠다).
검증을 못 하면(해시가 없거나 다르면) 설치하지 않는다. 못 받아도 프로그램은 그대로 돈다."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

import store
import version

API = "https://api.github.com/repos/%s/releases/latest" % version.GITHUB_REPO
TIMEOUT = 20
MAX_BYTES = 200 * 1024 * 1024
_HOSTS = ("https://github.com/", "https://objects.githubusercontent.com/",
          "https://release-assets.githubusercontent.com/")


class UpdateError(Exception):
    pass


def parse_version(text):
    """「v1.0.2」「1.0.2」 → (1, 0, 2). 못 읽으면 None."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(text or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def is_newer(remote, local=None):
    r, l = parse_version(remote), parse_version(local or version.__version__)
    return bool(r and l and r > l)


def _get(url, accept=None):
    req = urllib.request.Request(url, headers={
        "User-Agent": "DontMissClass/%s" % version.__version__,
        "Accept": accept or "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def find_release(rel):
    """릴리스 JSON → {"version","url","sha256","name"}. 쓸 만한 새 버전이 아니면 None."""
    if not isinstance(rel, dict) or rel.get("draft") or rel.get("prerelease"):
        return None
    tag = rel.get("tag_name")
    if not is_newer(tag):
        return None
    ver = ".".join(str(x) for x in parse_version(tag))
    want = "%s%s.exe" % (version.INSTALLER_PREFIX, ver)
    url = next((a.get("browser_download_url") for a in rel.get("assets") or []
                if a.get("name") == want), None)
    if not url or not url.startswith(_HOSTS):
        return None
    m = re.search(r"sha-?256\s*[:=]\s*([0-9a-fA-F]{64})", rel.get("body") or "", re.I)
    return {"version": ver, "url": url, "sha256": m.group(1).lower() if m else "", "name": want}


def check():
    """최신 릴리스가 내 것보다 새로우면 그 정보, 아니면 None. 연결 실패는 UpdateError."""
    try:
        with _get(API) as r:
            return find_release(json.loads(r.read().decode("utf-8")))
    except Exception as e:
        raise UpdateError("업데이트 확인 실패: %s" % e)


def download(info):
    """설치 파일을 받아 해시를 확인하고 경로를 돌려준다. 해시가 없거나 다르면 UpdateError."""
    if not info["sha256"]:
        raise UpdateError("릴리스에 SHA256 이 없어 설치하지 않습니다.")
    folder = os.path.join(tempfile.gettempdir(), "DontMissClass_update")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, info["name"])
    if os.path.exists(path) and _sha256(path) == info["sha256"]:
        return path
    h, size = hashlib.sha256(), 0
    try:
        with _get(info["url"], "application/octet-stream") as r, open(path + ".part", "wb") as f:
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    raise UpdateError("설치 파일이 비정상적으로 큽니다.")
                h.update(chunk)
                f.write(chunk)
    except UpdateError:
        raise
    except Exception as e:
        raise UpdateError("내려받기 실패: %s" % e)
    if h.hexdigest() != info["sha256"]:
        os.remove(path + ".part")
        raise UpdateError("설치 파일 검증(SHA256)에 실패했습니다.")
    os.replace(path + ".part", path)
    return path


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def can_self_update():
    """묶인 exe 로 설치돼 있을 때만. 소스로 돌리는 중에는 하지 않는다."""
    return bool(getattr(sys, "frozen", False))


def install(path):
    """설치 프로그램을 조용히 띄운다. 설치 프로그램이 이 프로그램을 닫고 새 버전을 다시 켠다."""
    store.log("업데이트 설치 시작: %s" % os.path.basename(path))
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                     creationflags=flags, close_fds=True)
