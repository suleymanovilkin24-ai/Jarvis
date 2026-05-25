"""
TTS (Text-to-Speech) - Windows SAPI/pyttsx3 uzerinden calisir.
"""

import threading


VOICE_HINT = "Turkish"


def _build_engine():
    import pyttsx3

    engine = pyttsx3.init("sapi5")
    for voice in engine.getProperty("voices") or []:
        name = str(getattr(voice, "name", "") or "")
        languages = " ".join(str(x) for x in getattr(voice, "languages", []) or [])
        if "tr" in languages.lower() or "turkish" in name.lower() or "tolga" in name.lower():
            engine.setProperty("voice", voice.id)
            break
    return engine


def speak_text(text: str, on_done=None, blocking: bool = False):
    """
    Metni sesli olarak okur.
    on_done: okuma bitince cagrilacak fonksiyon (opsiyonel)
    blocking: True ise bitene kadar bekler
    """
    if not text or not text.strip():
        if on_done:
            on_done()
        return

    max_len = 500
    if len(text) > max_len:
        text = text[:max_len] + "..."

    def _run():
        try:
            engine = _build_engine()
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass
        if on_done:
            on_done()

    if blocking:
        _run()
    else:
        threading.Thread(target=_run, daemon=True).start()


def get_available_voices() -> list[str]:
    """Windows SAPI seslerini listeler."""
    try:
        engine = _build_engine()
        return [str(getattr(voice, "name", "") or getattr(voice, "id", "")) for voice in engine.getProperty("voices") or []]
    except Exception:
        return []
