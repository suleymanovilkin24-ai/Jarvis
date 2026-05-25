"""
Windows takvim araci - Microsoft Outlook COM uzerinden okur/yazar.
"""

from __future__ import annotations

import datetime as dt
import json
import re


TR_WEEKDAYS = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
TR_MONTHS = ["", "Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran", "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik"]


def _outlook_namespace():
    try:
        import win32com.client

        outlook = win32com.client.Dispatch("Outlook.Application")
        return outlook, outlook.GetNamespace("MAPI")
    except Exception as exc:
        raise RuntimeError("Microsoft Outlook ve pywin32 gerekli. `pip install pywin32` ile kurup Outlook hesabini ac.") from exc


def _parse_datetime(value: str, default_duration_minutes: int = 60) -> tuple[dt.datetime, dt.datetime]:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Baslangic tarihi gerekli.")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            start = dt.datetime.strptime(raw, fmt)
            if fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                end = start + dt.timedelta(days=1)
            else:
                end = start + dt.timedelta(minutes=default_duration_minutes)
            return start, end
        except ValueError:
            continue
    try:
        start = dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        return start, start + dt.timedelta(minutes=default_duration_minutes)
    except ValueError as exc:
        raise ValueError("Tarih gecersiz. 'YYYY-MM-DDTHH:MM' veya 'YYYY-MM-DD HH:MM' kullan.") from exc


def _normalize_query(query: str) -> dict:
    q = (query or "today").strip().lower()
    now = dt.datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    month_match = re.search(r"(\d+)\s*(ay|month|months)", q)
    if "gelecek ay" in q or "onumuzdeki ay" in q or "next month" in q:
        start = (today_start.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
        end = (start + dt.timedelta(days=32)).replace(day=1)
        return {"start": start, "end": end, "kind": "range", "header": "Gelecek ay icin {count} etkinlik buldum:", "empty": "Gelecek ay takviminde etkinlik gorunmuyor."}
    if "bu ay" in q or "this month" in q:
        start = today_start.replace(day=1)
        end = (start + dt.timedelta(days=32)).replace(day=1)
        return {"start": start, "end": end, "kind": "range", "header": "Bu ay icin {count} etkinlik buldum:", "empty": "Bu ay takviminde etkinlik gorunmuyor."}
    if month_match:
        months = max(1, min(12, int(month_match.group(1))))
        start = today_start
        end = (today_start.replace(day=1) + dt.timedelta(days=32 * months)).replace(day=1)
        return {"start": start, "end": end, "kind": "range", "header": f"Onumuzdeki {months} ay icin {{count}} etkinlik buldum:", "empty": f"Onumuzdeki {months} ayda takviminde etkinlik gorunmuyor."}

    week_match = re.search(r"(\d+)\s*(hafta|week|weeks)", q)
    if week_match:
        weeks = max(1, min(12, int(week_match.group(1))))
        return {"start": today_start, "end": today_start + dt.timedelta(days=weeks * 7), "kind": "range", "header": f"Onumuzdeki {weeks} hafta icin {{count}} etkinlik buldum:", "empty": f"Onumuzdeki {weeks} haftada takviminde etkinlik gorunmuyor."}

    day_match = re.search(r"(\d+)\s*(gun|gün|day|days)", q)
    if day_match:
        days = max(1, min(365, int(day_match.group(1))))
        return {"start": today_start, "end": today_start + dt.timedelta(days=days), "kind": "range", "header": f"Onumuzdeki {days} gun icin {{count}} etkinlik buldum:", "empty": f"Onumuzdeki {days} gunde takviminde etkinlik gorunmuyor."}

    if any(token in q for token in ("yarin", "tomorrow")):
        start = today_start + dt.timedelta(days=1)
        return {"start": start, "end": start + dt.timedelta(days=1), "kind": "tomorrow", "header": "Yarin icin {count} etkinlik buldum:", "empty": "Yarin takviminde etkinlik gorunmuyor."}
    if any(token in q for token in ("hafta", "week", "7 gun")):
        return {"start": today_start, "end": today_start + dt.timedelta(days=7), "kind": "week", "header": "Onumuzdeki 7 gun icin {count} etkinlik buldum:", "empty": "Onumuzdeki 7 gunde takviminde etkinlik gorunmuyor."}
    if any(token in q for token in ("siradaki", "sıradaki", "sonraki", "next")):
        return {"start": now, "end": now + dt.timedelta(days=365), "kind": "next", "header": "", "empty": "Siradaki takvim etkinligini bulamadim."}
    if any(token in q for token in ("ajanda", "agenda", "yaklasan", "upcoming")):
        return {"start": now, "end": now + dt.timedelta(days=30), "kind": "agenda", "header": "Yaklasan ajandanda {count} etkinlik var:", "empty": "Yaklasan takvim etkinligi gorunmuyor."}
    return {"start": today_start, "end": today_start + dt.timedelta(days=1), "kind": "today", "header": "Bugun icin {count} etkinlik buldum:", "empty": "Bugun takviminde etkinlik gorunmuyor."}


def _day_label(when: dt.datetime, now: dt.datetime) -> str:
    today = now.date()
    target = when.date()
    if target == today:
        return "bugun"
    if target == today + dt.timedelta(days=1):
        return "yarin"
    return f"{when.day} {TR_MONTHS[when.month]} {TR_WEEKDAYS[when.weekday()]}"


def _format_time_range(event: dict, now: dt.datetime) -> str:
    start = event["start"]
    end = event["end"]
    prefix = _day_label(start, now)
    if event["all_day"]:
        return f"{prefix} tum gun"
    return f"{prefix} {start.strftime('%H:%M')}-{end.strftime('%H:%M')}"


def _format_event_line(event: dict, now: dt.datetime) -> str:
    pieces = [f"{_format_time_range(event, now)} - {event['title']}"]
    if event.get("calendar"):
        pieces.append(f"[{event['calendar']}]")
    if event.get("location"):
        pieces.append(f"@ {event['location']}")
    return " ".join(pieces)


def _get_appointments(start: dt.datetime, end: dt.datetime) -> list[dict]:
    _, namespace = _outlook_namespace()
    calendar = namespace.GetDefaultFolder(9)  # olFolderCalendar
    items = calendar.Items
    items.IncludeRecurrences = True
    items.Sort("[Start]")

    restriction = "[Start] < '{end}' AND [End] > '{start}'".format(
        start=start.strftime("%m/%d/%Y %I:%M %p"),
        end=end.strftime("%m/%d/%Y %I:%M %p"),
    )
    try:
        restricted = items.Restrict(restriction)
    except Exception:
        restricted = items

    events = []
    for item in restricted:
        try:
            item_start = item.Start.replace(tzinfo=None)
            item_end = item.End.replace(tzinfo=None)
            if item_end < start or item_start > end:
                continue
            events.append(
                {
                    "start": item_start,
                    "end": item_end,
                    "title": str(item.Subject or "Adsiz etkinlik"),
                    "location": str(item.Location or ""),
                    "calendar": str(getattr(item, "Parent", "") or "Outlook"),
                    "all_day": bool(item.AllDayEvent),
                    "_item": item,
                }
            )
        except Exception:
            continue
    events.sort(key=lambda event: (event["start"], event["title"].lower()))
    return events


def get_calendar_events(query: str = "today", limit: int = 6) -> str:
    window = _normalize_query(query)
    limit = max(1, min(60, int(limit or 6)))
    try:
        events = _get_appointments(window["start"], window["end"])
    except Exception as exc:
        return f"Takvim okunamadi: {exc}"

    now = dt.datetime.now()
    if window["kind"] in {"next", "agenda"}:
        events = [event for event in events if event["end"] >= now]
    if not events:
        return window["empty"]
    if window["kind"] == "next":
        return f"Siradaki etkinlik: {_format_event_line(events[0], now)}."

    selected = events[:limit]
    lines = [str(window["header"]).format(count=len(selected))]
    lines.extend(f"- {_format_event_line(event, now)}" for event in selected)
    return "\n".join(lines)


def add_calendar_event(
    title: str,
    start_iso: str,
    end_iso: str = "",
    notes: str = "",
    location: str = "",
    calendar_name: str = "",
    all_day: bool = False,
) -> str:
    title = (title or "").strip()
    if not title:
        return "Takvime eklemek icin etkinlik basligi gerekli."
    try:
        start, inferred_end = _parse_datetime(start_iso)
        end = _parse_datetime(end_iso)[0] if end_iso and end_iso.strip() else inferred_end
        outlook, _ = _outlook_namespace()
        appt = outlook.CreateItem(1)  # olAppointmentItem
        appt.Subject = title
        appt.Start = start
        appt.End = end
        appt.Body = notes or ""
        appt.Location = location or ""
        appt.AllDayEvent = bool(all_day)
        appt.Save()
        event = {"start": start, "end": end, "title": title, "location": location or "", "calendar": calendar_name or "Outlook", "all_day": bool(all_day)}
        return f"Takvime eklendi: {_format_event_line(event, dt.datetime.now())}."
    except Exception as exc:
        return f"Takvim etkinligi eklenemedi: {exc}"


def delete_calendar_event(
    title: str,
    start_iso: str = "",
    calendar_name: str = "",
    delete_all_matches: bool = False,
) -> str:
    title = (title or "").strip()
    if not title:
        return "Takvimden silmek icin etkinlik basligi gerekli."
    try:
        if start_iso and start_iso.strip():
            start, _ = _parse_datetime(start_iso)
            window_start = start - dt.timedelta(hours=12)
            window_end = start + dt.timedelta(hours=36)
        else:
            window_start = dt.datetime.now() - dt.timedelta(days=30)
            window_end = dt.datetime.now() + dt.timedelta(days=365)
        events = _get_appointments(window_start, window_end)
        matches = [event for event in events if title.lower() in event["title"].lower()]
        if not matches:
            return "Silinecek eslesen etkinlik bulunamadi."
        deleted_lines = []
        for event in matches:
            deleted_lines.append(_format_event_line(event, dt.datetime.now()))
            event["_item"].Delete()
            if not delete_all_matches:
                break
        return "Takvimden silindi: " + " | ".join(deleted_lines)
    except Exception as exc:
        return f"Takvim etkinligi silinemedi: {exc}"


def _run_helper(mode: str, payload: dict | None = None, timeout: int = 20) -> tuple[bool, str]:
    """Backward-compatible shim for older reminder code paths."""
    return False, json.dumps({"ok": False, "detail": "Windows surumunde eski takvim helper'i yok; Outlook COM kullanilir."})
