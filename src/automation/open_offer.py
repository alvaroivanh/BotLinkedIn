"""Open a job-offer URL in the system browser's private/incognito window.

Some portals (e.g. Computrabajo) block the user's normal browser session with an
anti-bot 403. A private/incognito window has no cookies or extensions, so it's a
clean session that loads fine. We launch the user's installed browser (Chrome,
Edge or Brave) directly in private mode — more reliable than a bundled headless
browser and matches the "incognito" behaviour the user expects.
"""

import os
import shutil
import subprocess
import sys

# (private-mode flag, candidate executable paths) in preference order.
_CANDIDATES = [
    ("--incognito", [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]),
    ("--inprivate", [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]),
    ("--incognito", [
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    ]),
]


def find_browser():
    """Return (exe_path, private_flag) for the first available browser, or (None, None)."""
    for flag, paths in _CANDIDATES:
        for path in paths:
            if path and os.path.isfile(path):
                return path, flag
    # Fall back to anything on PATH.
    for name, flag in (("chrome", "--incognito"), ("msedge", "--inprivate"), ("brave", "--incognito")):
        exe = shutil.which(name)
        if exe:
            return exe, flag
    return None, None


def open_incognito(url: str) -> bool:
    """Open `url` in a private/incognito window. Returns False if no browser found."""
    exe, flag = find_browser()
    if not exe:
        return False
    subprocess.Popen([exe, flag, url], close_fds=True)
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ok = open_incognito(sys.argv[1])
        sys.exit(0 if ok else 1)
