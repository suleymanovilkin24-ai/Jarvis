"""
Uygulama acma - Windows uygulamalari, URL protokolleri ve PATH uzerinden calisir.
"""

from actions.windows_utils import APP_ALIASES, open_app_target


def open_app(app_name: str) -> str:
    """Uygulamayi acar, basari/hata mesaji dondurur."""
    if not app_name:
        return "Uygulama adi belirtilmedi."

    normalized = app_name.lower().strip()
    resolved = APP_ALIASES.get(normalized, app_name)

    try:
        ok, detail = open_app_target(resolved)
        if ok:
            return f"{resolved} acildi."
        return f"'{app_name}' bulunamadi veya acilamadi: {detail}"
    except Exception as exc:
        return f"Hata: {exc}"
