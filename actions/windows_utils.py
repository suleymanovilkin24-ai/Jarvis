from __future__ import annotations

import os
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - Windows only
    winreg = None


LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", ""))
APPDATA = Path(os.environ.get("APPDATA", ""))
PROGRAMFILES = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
PROGRAMFILES_X86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))


APP_ALIASES = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "explorer": "explorer.exe",
    "finder": "explorer.exe",
    "files": "explorer.exe",
    "dosyalar": "explorer.exe",
    "spotify": "spotify.exe",
    "vscode": "Code.exe",
    "vs code": "Code.exe",
    "code": "Code.exe",
    "notion": "Notion.exe",
    "slack": "slack.exe",
    "discord": "Discord.exe",
    "whatsapp": "whatsapp:",
    "telegram": "Telegram.exe",
    "zoom": "Zoom.exe",
    "mail": "outlook.exe",
    "outlook": "outlook.exe",
    "calendar": "outlookcal:",
    "takvim": "outlookcal:",
    "notes": "onenote.exe",
    "notlar": "onenote.exe",
    "music": "mswindowsmusic:",
    "muzik": "mswindowsmusic:",
    "photos": "ms-photos:",
    "fotograflar": "ms-photos:",
    "maps": "bingmaps:",
    "haritalar": "bingmaps:",
    "calculator": "calc.exe",
    "hesap makinesi": "calc.exe",
    "settings": "ms-settings:",
    "ayarlar": "ms-settings:",
    "task manager": "taskmgr.exe",
    "activity monitor": "taskmgr.exe",
    "paint": "mspaint.exe",
    "notepad": "notepad.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "figma": "Figma.exe",
    "postman": "Postman.exe",
    "docker": "Docker Desktop.exe",
}


KNOWN_APP_PATHS = {
    "Code.exe": [
        LOCALAPPDATA / "Programs" / "Microsoft VS Code" / "Code.exe",
        PROGRAMFILES / "Microsoft VS Code" / "Code.exe",
    ],
    "Discord.exe": [LOCALAPPDATA / "Discord" / "Update.exe"],
    "Figma.exe": [LOCALAPPDATA / "Figma" / "Figma.exe"],
    "Notion.exe": [LOCALAPPDATA / "Programs" / "Notion" / "Notion.exe"],
    "Postman.exe": [LOCALAPPDATA / "Postman" / "Postman.exe"],
    "Spotify.exe": [APPDATA / "Spotify" / "Spotify.exe"],
    "WhatsApp.exe": [
        LOCALAPPDATA / "WhatsApp" / "WhatsApp.exe",
        PROGRAMFILES / "WindowsApps",
    ],
    "Zoom.exe": [APPDATA / "Zoom" / "bin" / "Zoom.exe"],
    "Docker Desktop.exe": [PROGRAMFILES / "Docker" / "Docker" / "Docker Desktop.exe"],
    "chrome.exe": [
        PROGRAMFILES / "Google" / "Chrome" / "Application" / "chrome.exe",
        PROGRAMFILES_X86 / "Google" / "Chrome" / "Application" / "chrome.exe",
    ],
    "firefox.exe": [
        PROGRAMFILES / "Mozilla Firefox" / "firefox.exe",
        PROGRAMFILES_X86 / "Mozilla Firefox" / "firefox.exe",
    ],
    "msedge.exe": [PROGRAMFILES_X86 / "Microsoft" / "Edge" / "Application" / "msedge.exe"],
}


def open_url(url: str) -> bool:
    try:
        os.startfile(url)  # type: ignore[attr-defined]
        return True
    except Exception:
        return webbrowser.open(url, new=2)


def copy_to_clipboard(text: str) -> None:
    try:
        import pyperclip

        pyperclip.copy(text)
        return
    except Exception:
        pass

    command = ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"]
    subprocess.run(command, input=text, text=True, check=True, timeout=5)


def press_hotkey(*keys: str) -> tuple[bool, str]:
    try:
        import pyautogui

        pyautogui.hotkey(*keys)
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def press_key(key: str) -> tuple[bool, str]:
    try:
        import pyautogui

        pyautogui.press(key)
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def type_text(text: str) -> tuple[bool, str]:
    try:
        import pyautogui

        pyautogui.write(text)
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def wait(seconds: float) -> None:
    time.sleep(max(0.0, seconds))


def find_executable(app_name: str) -> str | None:
    target = app_name.strip()
    resolved = APP_ALIASES.get(target.lower(), target)

    if resolved.endswith(":"):
        return resolved

    path = Path(resolved).expanduser()
    if path.exists():
        return str(path)

    found = shutil.which(resolved)
    if found:
        return found

    for candidate in KNOWN_APP_PATHS.get(resolved, []):
        if candidate.is_file():
            return str(candidate)

    registry_match = _find_app_path_in_registry(resolved)
    if registry_match:
        return registry_match

    return None


def open_app_target(app_name: str) -> tuple[bool, str]:
    target = app_name.strip()
    resolved = APP_ALIASES.get(target.lower(), target)

    if resolved.endswith(":"):
        return open_url(resolved), resolved

    executable = find_executable(target)
    try:
        if executable:
            subprocess.Popen([executable], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, executable

        os.startfile(resolved)  # type: ignore[attr-defined]
        return True, resolved
    except Exception as exc:
        return False, str(exc)


def _find_app_path_in_registry(exe_name: str) -> str | None:
    if winreg is None:
        return None

    subkeys = (
        rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}",
        rf"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}",
    )
    roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    for root in roots:
        for subkey in subkeys:
            try:
                with winreg.OpenKey(root, subkey) as key:
                    value, _ = winreg.QueryValueEx(key, "")
                    if value and Path(value).exists():
                        return value
            except OSError:
                continue
    return None
