"""
Windows hatirlatici araci - Microsoft Outlook Tasks uzerinden calisir.
"""

from __future__ import annotations

import datetime as dt
import re

from actions.calendar import _outlook_namespace


TR_WEEKDAYS = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
TR_MONTHS = ["", "Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran", "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik"]


def _normalize_query(query: str) -> tuple[str, int]:
    q = (query or "").strip().lower()
    if any(token in q for token in ("bugun", "today")):
        return "today", 8
    if any(token in q for token in ("geciken", "gecmis", "overdue")):
        return "overdue", 8
    if any(token in q for token in ("siradaki", "sıradaki", "next")):
        return "next", 1
    if any(token in q for token in ("hepsi", "tum", "tüm", "all", "listele")):
        return "all", 10
    return "upcoming", 8


def _normalize_due_iso(due_iso: str) -> tuple[dt.datetime | None, bool]:
    raw = (due_iso or "").strip()
    if not raw:
        return None, False
    candidates = (
        ("%Y-%m-%dT%H:%M:%S", False),
        ("%Y-%m-%dT%H:%M", False),
        ("%Y-%m-%d %H:%M:%S", False),
        ("%Y-%m-%d %H:%M", False),
        ("%d.%m.%Y %H:%M", False),
        ("%Y-%m-%d", True),
        ("%d.%m.%Y", True),
    )
    if raw.endswith("Z"):
        try:
            return dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None), False
        except ValueError:
            pass
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", raw):
        try:
            return dt.datetime.fromisoformat(raw).replace(tzinfo=None), False
        except ValueError:
            pass
    for fmt, is_all_day in candidates:
        try:
            parsed = dt.datetime.strptime(raw, fmt)
            return parsed, is_all_day
        except ValueError:
            continue
    raise ValueError("Animsatici tarihi gecersiz. due_iso icin 'YYYY-MM-DD' veya 'YYYY-MM-DDTHH:MM' kullan.")


def _get_tasks() -> list[dict]:
    _, namespace = _outlook_namespace()
    tasks = namespace.GetDefaultFolder(13).Items  # olFolderTasks
    items = []
    for item in tasks:
        try:
            completed = bool(item.Complete)
            due = item.DueDate
            due_dt = due.replace(tzinfo=None) if due else None
            items.append(
                {
                    "title": str(item.Subject or "Adsiz animsatici"),
                    "list_name": "Outlook Tasks",
                    "notes": str(item.Body or ""),
                    "completed": completed,
                    "priority": int(getattr(item, "Importance", 1) or 1),
                    "due": due_dt,
                    "all_day": True,
                }
            )
        except Exception:
            continue
    items.sort(key=lambda item: (item["due"] is None, item["due"] or dt.datetime.max, item["title"].lower()))
    return items


def _day_label(when: dt.datetime, now: dt.datetime) -> str:
    today = now.date()
    target = when.date()
    if target == today:
        return "bugun"
    if target == today + dt.timedelta(days=1):
        return "yarin"
    return f"{when.day} {TR_MONTHS[when.month]} {TR_WEEKDAYS[when.weekday()]}"


def _format_due(item: dict, now: dt.datetime) -> str:
    if not item.get("due"):
        return "zaman atanmamis"
    due = item["due"]
    if item.get("all_day"):
        return f"{_day_label(due, now)} tum gun"
    return f"{_day_label(due, now)} {due.strftime('%H:%M')}"


def _format_reminder_line(item: dict, now: dt.datetime) -> str:
    parts = [f"{_format_due(item, now)} - {item['title']}"]
    if item.get("list_name"):
        parts.append(f"[{item['list_name']}]")
    if item.get("priority", 1) >= 2:
        parts.append("(yuksek oncelik)")
    return " ".join(parts)


def get_reminders(query: str = "upcoming", limit: int = 8, list_name: str = "") -> str:
    mode, default_limit = _normalize_query(query)
    limit = max(1, min(20, int(limit or default_limit)))
    try:
        reminders = [item for item in _get_tasks() if not item["completed"]]
    except Exception as exc:
        return f"Animsaticilar okunamadi: {exc}"

    now = dt.datetime.now()
    today = now.date()
    if mode == "today":
        reminders = [item for item in reminders if item.get("due") and item["due"].date() == today]
    elif mode == "overdue":
        reminders = [item for item in reminders if item.get("due") and item["due"].date() < today]
    elif mode in {"upcoming", "next"}:
        reminders = [item for item in reminders if not item.get("due") or item["due"].date() >= today]

    reminders = reminders[:limit]
    if not reminders:
        if mode == "today":
            return "Bugun icin animsatici gorunmuyor."
        if mode == "overdue":
            return "Geciken animsatici gorunmuyor."
        if mode == "next":
            return "Siradaki animsaticiyi bulamadim."
        if mode == "all":
            return "Kayitli acik animsatici gorunmuyor."
        return "Yaklasan animsatici gorunmuyor."

    if mode == "next":
        return f"Siradaki animsatici: {_format_reminder_line(reminders[0], now)}."
    header = {
        "today": f"Bugun icin {len(reminders)} animsatici buldum:",
        "overdue": f"Gecikmis {len(reminders)} animsatici buldum:",
        "all": f"Acik {len(reminders)} animsatici buldum:",
    }.get(mode, f"Yaklasan {len(reminders)} animsatici buldum:")
    return "\n".join([header, *(f"- {_format_reminder_line(item, now)}" for item in reminders)])


def add_reminder(
    title: str,
    due_iso: str = "",
    notes: str = "",
    list_name: str = "",
    priority: str = "",
    all_day: bool = False,
) -> str:
    if not title or not title.strip():
        return "Animsatici basligi bos olamaz."
    try:
        due, inferred_all_day = _normalize_due_iso(due_iso)
        outlook, _ = _outlook_namespace()
        task = outlook.CreateItem(3)  # olTaskItem
        task.Subject = title.strip()
        task.Body = (notes or "").strip()
        if due:
            task.DueDate = due
            task.ReminderSet = True
            task.ReminderTime = due
        pr = (priority or "").strip().lower()
        task.Importance = 2 if pr == "high" else 0 if pr == "low" else 1
        task.Save()
        created = {
            "title": title.strip(),
            "list_name": list_name or "Outlook Tasks",
            "notes": notes or "",
            "priority": task.Importance,
            "due": due,
            "all_day": bool(all_day) or inferred_all_day,
        }
        return f"Animsatici eklendi: {_format_due(created, dt.datetime.now())} - {created['title']} [{created['list_name']}]"
    except Exception as exc:
        return f"Animsatici eklenemedi: {exc}"
