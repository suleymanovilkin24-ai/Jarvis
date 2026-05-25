"""
Medya oynatma - YouTube, Spotify URI ve Windows medya protokolleri.
"""

from __future__ import annotations

import urllib.parse

from actions.browser import browser_control
from actions.windows_utils import find_executable, open_url, press_key, wait


def _play_youtube(query: str) -> str:
    return browser_control("play_youtube", query=query)


def _play_spotify(query: str, autoplay: bool = True) -> str:
    if not find_executable("spotify"):
        return "Spotify yuklu gorunmuyor."

    encoded_query = urllib.parse.quote(query.strip())
    search_url = f"spotify:search:{encoded_query}"
    if not open_url(search_url):
        return "Spotify acilamadi."

    if not autoplay:
        return f"Spotify icinde '{query}' aramasi acildi."

    wait(2.0)
    ok, detail = press_key("enter")
    if ok:
        wait(0.5)
        press_key("space")
        return f"Spotify'da oynatma baslatildi: {query}"
    return f"Spotify aramasi acildi ama otomatik oynatma tamamlanamadi: {detail}"


def _play_windows_music(query: str, autoplay: bool = True) -> str:
    encoded_query = urllib.parse.quote(query.strip())
    url = f"mswindowsmusic://search/?term={encoded_query}"
    if open_url(url):
        return f"Windows muzik uygulamasinda '{query}' aramasi acildi."
    return "Windows muzik uygulamasi acilamadi."


def play_media(query: str, provider: str = "auto", autoplay: bool = True) -> str:
    if not query or not query.strip():
        return "Calinacak icerik belirtilmedi."

    normalized_provider = (provider or "auto").strip().lower()
    if normalized_provider in {"yt", "youtube music"}:
        normalized_provider = "youtube"
    elif normalized_provider in {"apple music", "music", "apple_music", "windows_music"}:
        normalized_provider = "windows_music"

    if normalized_provider == "spotify":
        return _play_spotify(query, autoplay=autoplay)
    if normalized_provider == "windows_music":
        return _play_windows_music(query, autoplay=autoplay)
    if normalized_provider == "youtube":
        return _play_youtube(query)

    result = _play_spotify(query, autoplay=autoplay)
    if "yuklu gorunmuyor" not in result and "acilamadi" not in result:
        return result
    return _play_youtube(query)
