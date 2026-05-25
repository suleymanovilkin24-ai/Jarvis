"""
Sistem bilgisi - Windows icin psutil tabanli.
"""

import datetime
import socket
import subprocess

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def sys_info(query: str) -> str:
    query = (query or "all").lower().strip()
    results = []
    if query in ("battery", "pil", "all"):
        results.append(_battery())
    if query in ("cpu", "islemci", "işlemci", "all"):
        results.append(_cpu())
    if query in ("ram", "bellek", "memory", "all"):
        results.append(_ram())
    if query in ("disk", "depolama", "all"):
        results.append(_disk())
    if query in ("time", "saat", "zaman", "all"):
        results.append(f"Saat: {datetime.datetime.now().strftime('%H:%M:%S')}")
    if query in ("date", "tarih", "all"):
        results.append(f"Tarih: {datetime.datetime.now().strftime('%d %B %Y, %A')}")
    if query in ("network", "ag", "ağ", "wifi", "all"):
        results.append(_network())
    if not results:
        results.append(f"Bilinmeyen sorgu: {query}. battery/cpu/ram/disk/time/date/network/all kullanin.")
    return "\n".join(r for r in results if r)


def _battery() -> str:
    if HAS_PSUTIL:
        bat = psutil.sensors_battery()
        if bat:
            status = "Sarj oluyor" if bat.power_plugged else "Pilde"
            return f"Pil: %{bat.percent:.0f} - {status}"
    return "Pil bilgisi alinamadi."


def _cpu() -> str:
    if HAS_PSUTIL:
        usage = psutil.cpu_percent(interval=0.5)
        count = psutil.cpu_count(logical=True)
        freq = psutil.cpu_freq()
        freq_str = f", {freq.current:.0f} MHz" if freq else ""
        return f"CPU: %{usage:.1f} kullanim - {count} cekirdek{freq_str}"
    return "CPU bilgisi alinamadi."


def _ram() -> str:
    if HAS_PSUTIL:
        vm = psutil.virtual_memory()
        total = vm.total / (1024**3)
        used = vm.used / (1024**3)
        return f"RAM: {used:.1f}GB / {total:.1f}GB kullanimda (%{vm.percent:.0f})"
    return "RAM bilgisi alinamadi."


def _disk() -> str:
    if HAS_PSUTIL:
        root = "C:\\"
        du = psutil.disk_usage(root)
        total = du.total / (1024**3)
        used = du.used / (1024**3)
        free = du.free / (1024**3)
        return f"Disk ({root}): {used:.1f}GB kullanildi, {free:.1f}GB bos (toplam {total:.1f}GB)"
    return "Disk bilgisi alinamadi."


def _network() -> str:
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip and not ip.startswith("127."):
            return f"Ag: IP {ip}"
    except Exception:
        pass
    try:
        result = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.splitlines():
            if "SSID" in line and "BSSID" not in line and ":" in line:
                return f"WiFi: {line.split(':', 1)[1].strip()} bagli"
    except Exception:
        pass
    return "Ag baglantisi bulunamadi."
