import os
import platform
import shutil
from pathlib import Path
from typing import Optional

_BROWSER_CANDIDATES = {
    "Darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ],
    "Windows": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ],
    "Linux": [
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        "/usr/bin/microsoft-edge",
    ],
}

_BROWSER_COMMANDS = (
    "google-chrome",
    "chromium",
    "chromium-browser",
    "microsoft-edge",
    "brave-browser",
)

def detect_browser_executable() -> str:
    system = platform.system()
    for candidate in _BROWSER_CANDIDATES.get(system, []):
        if os.path.exists(candidate):
            return candidate
    for command in _BROWSER_COMMANDS:
        resolved = shutil.which(command)
        if resolved:
            return resolved
    return ""

def resolve_browser_executable(browser_path: str) -> Optional[str]:
    browser_path = browser_path.strip()
    if not browser_path:
        return None

    path = Path(browser_path).expanduser()
    if path.is_dir() and path.suffix == ".app":
        executable = path / "Contents" / "MacOS" / path.stem
        if executable.exists():
            return str(executable)

    if path.exists():
        return str(path)

    return None

