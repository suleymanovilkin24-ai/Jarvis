"""
WhatsApp mesaj gonderme - Windows Desktop URL scheme veya WhatsApp Web ile calisir.
"""

from __future__ import annotations

import json
import re
import unicodedata
import urllib.parse
from pathlib import Path

from actions.windows_utils import copy_to_clipboard, open_app_target, open_url, press_hotkey, press_key, wait
from memory.memory_manager import load_memory, update_memory


AUTO_SEND_DELAY_SECONDS = 2.4
BASE_DIR = Path(__file__).resolve().parent.parent
PHONEBOOK_FILE = BASE_DIR / "memory" / "phone_book.json"


def _normalize_phone(phone_number: str) -> str:
    digits = re.sub(r"\D+", "", phone_number or "")
    if len(digits) == 11 and digits.startswith("0"):
        digits = "90" + digits[1:]
    elif len(digits) == 10:
        digits = "90" + digits
    if len(digits) < 8 or len(digits) > 15:
        raise ValueError("Telefon numarasi uluslararasi formatta olmali. Orn: +905551112233")
    return digits


def _normalize_lookup(text: str) -> str:
    text = (text or "").strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ı", "i")
    text = re.sub(r"\s+", " ", text)
    return text


def _contact_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _normalize_lookup(name)).strip("_") or "contact"


def _load_contacts() -> dict:
    contacts = load_memory().get("whatsapp_contacts", {})
    return contacts if isinstance(contacts, dict) else {}


def _load_phone_book() -> dict:
    try:
        if PHONEBOOK_FILE.exists():
            return json.loads(PHONEBOOK_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_phone_book(phone_book: dict):
    PHONEBOOK_FILE.parent.mkdir(parents=True, exist_ok=True)
    PHONEBOOK_FILE.write_text(json.dumps(phone_book, indent=2, ensure_ascii=False), encoding="utf-8")


def _contact_candidates() -> list[dict]:
    candidates = []
    for source_name, source in (("whatsapp", _load_contacts()), ("phone_book", _load_phone_book())):
        if not isinstance(source, dict):
            continue
        for key, entry in source.items():
            if not isinstance(entry, dict):
                continue
            item = dict(entry)
            item.setdefault("display_name", key)
            item["_source"] = source_name
            item["_key"] = key
            candidates.append(item)
    return candidates


def _match_score(needle: str, candidate: str) -> int:
    candidate_norm = _normalize_lookup(candidate)
    if not candidate_norm:
        return 0
    if candidate_norm == needle:
        return 300
    if candidate_norm.startswith(needle) or needle.startswith(candidate_norm):
        return 220
    if needle in candidate_norm:
        return 160
    parts = needle.split()
    if parts and all(part in candidate_norm for part in parts):
        return 120
    return 0


def _find_contact(recipient_name: str) -> dict | None:
    needle = _normalize_lookup(recipient_name)
    if not needle:
        return None
    best_match = None
    best_score = 0
    for entry in _contact_candidates():
        names = [entry.get("display_name", ""), entry.get("_key", "")]
        aliases = entry.get("aliases", [])
        if isinstance(aliases, list):
            names.extend(str(alias) for alias in aliases)
        elif aliases:
            names.append(str(aliases))
        for name in names:
            score = _match_score(needle, name)
            if score > best_score:
                best_score = score
                best_match = entry
    return best_match


def save_whatsapp_contact(display_name: str, phone_number: str, aliases: str = "") -> str:
    if not display_name or not display_name.strip():
        return "Kisi adi bos olamaz."
    try:
        normalized_phone = _normalize_phone(phone_number)
    except ValueError as exc:
        return str(exc)

    alias_list = [part.strip() for part in aliases.split(",") if part.strip()] if aliases else []
    key = _contact_key(display_name)
    update_memory(
        {
            "whatsapp_contacts": {
                key: {
                    "value": f"+{normalized_phone}",
                    "display_name": display_name.strip(),
                    "aliases": alias_list,
                }
            }
        }
    )
    if alias_list:
        return f"{display_name.strip()} WhatsApp kisilerine kaydedildi. Takma adlar: {', '.join(alias_list)}"
    return f"{display_name.strip()} WhatsApp kisilerine kaydedildi."


def _unfold_vcf_lines(text: str) -> list[str]:
    unfolded = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def import_phone_book_from_vcf(vcf_path: str) -> str:
    source = Path(vcf_path).expanduser()
    if not source.exists():
        return f"Rehber dosyasi bulunamadi: {source}"
    try:
        text = source.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return f"Rehber dosyasi okunamadi: {exc}"

    entries = {}
    current_lines = []
    imported = 0
    skipped = 0

    def _flush_card(lines: list[str]):
        nonlocal imported, skipped
        display_name = ""
        aliases = []
        numbers = []
        for line in lines:
            upper = line.upper()
            if upper.startswith("FN:"):
                display_name = line.split(":", 1)[1].strip()
            elif upper.startswith("N:") and not display_name:
                parts = [part.strip() for part in line.split(":", 1)[1].split(";") if part.strip()]
                if parts:
                    display_name = " ".join(reversed(parts[:2])).strip()
            elif "TEL" in upper and ":" in line:
                numbers.append(line.split(":", 1)[1].strip())
        if not display_name or not numbers:
            skipped += 1
            return
        normalized_numbers = []
        for raw_number in numbers:
            try:
                normalized_numbers.append("+" + _normalize_phone(raw_number))
            except ValueError:
                continue
        if not normalized_numbers:
            skipped += 1
            return
        if " " in display_name:
            aliases.extend(part for part in display_name.split() if len(part) > 1)
        entries[_contact_key(display_name)] = {
            "display_name": display_name,
            "value": normalized_numbers[0],
            "numbers": normalized_numbers,
            "aliases": sorted({alias for alias in aliases if _normalize_lookup(alias) != _normalize_lookup(display_name)}),
            "source": "vcf_import",
        }
        imported += 1

    for line in _unfold_vcf_lines(text):
        upper = line.upper()
        if upper == "BEGIN:VCARD":
            current_lines = []
        elif upper == "END:VCARD":
            _flush_card(current_lines)
            current_lines = []
        else:
            current_lines.append(line)

    phone_book = _load_phone_book()
    phone_book.update(entries)
    _save_phone_book(phone_book)
    return f"{imported} rehber kisisi ice aktarildi, {skipped} kayit atlandi."


def _copy_to_clipboard(text: str) -> None:
    copy_to_clipboard(text)


def _auto_send_with_keys() -> tuple[bool, str]:
    wait(AUTO_SEND_DELAY_SECONDS)
    return press_key("enter")


def _open_whatsapp_desktop_via_scheme(phone_number: str, message: str) -> tuple[bool, str]:
    encoded_message = urllib.parse.quote(message.strip())
    url = f"whatsapp://send?phone={phone_number}&text={encoded_message}"
    try:
        if not open_url(url):
            return False, "WhatsApp URL scheme acilamadi."
    except Exception as exc:
        return False, f"WhatsApp Desktop acilamadi: {exc}"
    return True, "WhatsApp Desktop sohbeti acildi."


def _open_whatsapp_desktop_by_name(recipient_name: str, message: str, send_now: bool) -> tuple[bool, str]:
    ok, detail = open_app_target("whatsapp")
    if not ok:
        return False, f"WhatsApp Desktop acilamadi: {detail}"
    try:
        _copy_to_clipboard(recipient_name.strip())
        wait(1.2)
        ok, detail = press_hotkey("ctrl", "f")
        if ok:
            wait(0.2)
            press_hotkey("ctrl", "a")
            press_hotkey("ctrl", "v")
            wait(0.9)
            ok, detail = press_key("enter")
        if not ok:
            return False, detail
        _copy_to_clipboard(message.strip())
        wait(0.7)
        ok, detail = press_hotkey("ctrl", "v")
        if ok and send_now:
            wait(0.3)
            ok, detail = press_key("enter")
        if not ok:
            return False, detail
    except Exception as exc:
        return False, f"WhatsApp otomasyonu tamamlanamadi: {exc}"
    if send_now:
        return True, f"WhatsApp Desktop uzerinden {recipient_name.strip()} kisisine mesaj gonderildi."
    return True, f"WhatsApp Desktop uzerinden {recipient_name.strip()} icin taslak mesaj acildi."


def _open_whatsapp_web(phone_number: str, message: str) -> tuple[bool, str]:
    encoded_message = urllib.parse.quote(message.strip())
    url = f"https://web.whatsapp.com/send?phone={phone_number}&text={encoded_message}"
    try:
        open_url(url)
    except Exception as exc:
        return False, f"WhatsApp Web acilamadi: {exc}"
    return True, "default browser"


def send_whatsapp_message(
    message: str,
    phone_number: str = "",
    recipient_name: str = "",
    send_now: bool = False,
    app_target: str = "auto",
) -> str:
    if not message or not message.strip():
        return "Mesaj bos olamaz."

    app_target = (app_target or "auto").strip().lower()
    if app_target not in {"auto", "desktop", "web"}:
        app_target = "auto"

    normalized_phone = ""
    if phone_number and phone_number.strip():
        try:
            normalized_phone = _normalize_phone(phone_number)
        except ValueError as exc:
            return str(exc)

    resolved_name = recipient_name.strip() if recipient_name else ""
    contact = _find_contact(resolved_name) if resolved_name else None
    contact_source = ""

    if contact and not normalized_phone:
        stored_phone = str(contact.get("value", "")).strip()
        try:
            normalized_phone = _normalize_phone(stored_phone)
        except ValueError:
            normalized_phone = ""
        resolved_name = str(contact.get("display_name", resolved_name)).strip() or resolved_name
        contact_source = contact.get("_source", "")

    if resolved_name and normalized_phone and (contact is None or contact.get("_source") == "phone_book"):
        alias_list = contact.get("aliases", []) if isinstance(contact, dict) else []
        aliases = ", ".join(str(alias) for alias in alias_list) if alias_list else ""
        save_whatsapp_contact(resolved_name, normalized_phone, aliases=aliases)

    if app_target in {"auto", "desktop"}:
        if normalized_phone:
            ok, detail = _open_whatsapp_desktop_via_scheme(normalized_phone, message)
            if ok:
                source_note = " (rehberden bulundu)" if contact_source == "phone_book" else ""
                label = resolved_name or f"+{normalized_phone}"
                if not send_now:
                    return f"WhatsApp Desktop icinde {label}{source_note} icin taslak mesaj acildi."
                ok_send, send_detail = _auto_send_with_keys()
                if ok_send:
                    return f"WhatsApp Desktop uzerinden {label}{source_note} kisisine mesaj gonderildi."
                return f"WhatsApp Desktop sohbeti acildi ama otomatik gonderim tamamlanamadi: {send_detail}."
            if app_target == "desktop" and not resolved_name:
                return f"WhatsApp Desktop acilirken hata oldu: {detail}"

        if resolved_name:
            ok, detail = _open_whatsapp_desktop_by_name(resolved_name, message, send_now)
            if ok:
                return detail
            if app_target == "desktop":
                return f"WhatsApp Desktop kisi adina gore acilirken hata oldu: {detail}"

    if not normalized_phone:
        if resolved_name:
            return (
                f"'{resolved_name}' icin kayitli bir telefon numarasi bulamadim. "
                "Once kisiyi numarasiyla kaydet."
            )
        return "WhatsApp mesaji icin kisi adi veya telefon numarasi gerekli."

    ok, detail = _open_whatsapp_web(normalized_phone, message)
    if not ok:
        return detail

    source_note = " (rehberden bulundu)" if contact_source == "phone_book" else ""
    label = resolved_name or f"+{normalized_phone}"
    if not send_now:
        return f"WhatsApp sohbeti {detail} icinde {label}{source_note} icin taslak mesajla acildi. Gondermek icin Enter'a bas."

    ok_send, send_detail = _auto_send_with_keys()
    if ok_send:
        return f"WhatsApp Web uzerinden {label}{source_note} kisisine mesaj gonderildi."

    return f"WhatsApp Web sohbeti acildi ama otomatik gonderim tamamlanamadi: {send_detail}."
