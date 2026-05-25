import os

# 1. close_app.py yarat
close_app_code = """import psutil

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
"""

with open("actions/close_app.py", "w", encoding="utf-8") as f:
    f.write(close_app_code)
print("OK: close_app.py yaradildi")

# 2. main.py oxu
with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

original = content

# 3. import elave et
if "from actions.close_app import close_app" not in content:
    content = content.replace(
        "from actions.open_app import open_app",
        "from actions.open_app import open_app\nfrom actions.close_app import close_app"
    )
    print("OK: import elave edildi")

# 4. Tool declaration elave et
close_tool = """,{
        "name": "close_app",
        "description": "Windows-da aciq olan uygulamayi baglar. bagla, kapat, close dediginde kullan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Baglanacak uygulama adi"
                }
            },
            "required": ["app_name"]
        }
    }"""

if '"name": "close_app"' not in content:
    idx = content.find("TOOL_DECLARATIONS")
    block_end = content.find("]", idx + 9000)
    ins = content.rfind("}", idx, block_end) + 1
    content = content[:ins] + close_tool + content[ins:]
    print("OK: tool declaration elave edildi")

# 5. executor elave et
if 'elif name == "close_app"' not in content:
    old = 'elif name == "open_app":'
    new = 'elif name == "close_app":\n                r = await loop.run_in_executor(None, lambda: close_app(args.get("app_name", "")))\n                result = r or "Baglandı."\n\n            elif name == "open_app":'
    content = content.replace(old, new)
    print("OK: executor elave edildi")

# 6. Startup registry
if "winreg.SetValueEx" not in content:
    startup = """
    import winreg, sys
    try:
        _path = os.path.abspath(sys.argv[0])
        _py = sys.executable.replace("python.exe", "pythonw.exe")
        _key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run",
            0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(_key, "Jarvis", 0, winreg.REG_SZ, _py + " " + _path)
        winreg.CloseKey(_key)
        print("[JARVIS] Startup-a elave edildi.")
    except Exception as _e:
        print("[JARVIS] Startup xetasi:", _e)
"""
    target = 'if os.environ.get("TERM_PROGRAM") == "vscode":'
    content = content.replace(target, startup + "\n    " + target)
    print("OK: startup elave edildi")

# 7. Azerbaycan dili
if "Azerbaycanca" not in content:
    content = content.replace(
        "Turkce konus.",
        "Kullanici Azerbaycanca, Turkce veya Ingilizce konusabilir. Hangi dilde konusulursa o dilde yanitla."
    )
    print("OK: Azerbaycan dili elave edildi")

# 8. Mikrofon latency
content = content.replace(
    "device=MIC_DEVICE_INDEX, callback=callback)",
    'device=MIC_DEVICE_INDEX, callback=callback, latency="low")'
)
print("OK: mikrofon latency fix edildi")

# Saxla
with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)

print("\nHamisi tamamlandi! Ishlet: python main.py")