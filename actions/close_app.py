import psutil

PROCESS_MAP = {
    "chrome":     ["chrome.exe"],
    "notepad":    ["notepad.exe"],
    "calculator": ["calc.exe", "calculator.exe"],
    "discord":    ["discord.exe"],
    "spotify":    ["spotify.exe"],
    "code":       ["code.exe"],
    "vs code":    ["code.exe"],
    "telegram":   ["telegram.exe"],
    "whatsapp":   ["whatsapp.exe"],
    "firefox":    ["firefox.exe"],
    "edge":       ["msedge.exe"],
    "zoom":       ["zoom.exe"],
    "slack":      ["slack.exe"],
    "steam":      ["steam.exe"],
}

def close_app(app_name: str) -> str:
    name = app_name.lower().strip()
    matched_key = None
    for key in PROCESS_MAP:
        if key in name or name in key:
            matched_key = key
            break
    if not matched_key:
        return f"'{app_name}' taninmadi."
    proc_names = [p.lower() for p in PROCESS_MAP[matched_key]]
    closed_count = 0
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() in proc_names:
                proc.terminate()
                closed_count += 1
        except:
            pass
    if closed_count > 0:
        return f"{matched_key.title()} baglandı ({closed_count} proses)."
    else:
        return f"{matched_key.title()} artiq aciq deyil."
