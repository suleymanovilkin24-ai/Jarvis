
"""
JARVIS Windows - Gercek zamanli sesli yardimci cekirdegi
Alp Unlu tarafindan yapilmistir - @alppunlu
Windows ortamina uyarlanmis calisma akisi
"""

import asyncio
import datetime
import threading
import traceback
import os
import re
from pathlib import Path

try:
    import pyaudio  # type: ignore[reportMissingModuleSource]
except ImportError:
    print("Warning: PyAudio not available. Audio features will be limited.")
    pyaudio = None

from google import genai  # type: ignore[reportMissingImports]
from google.genai import types  # type: ignore[reportMissingImports]

from app_config import get_app_config_value
from ui import JarvisUI
from memory.memory_manager import load_memory, update_memory, delete_memory, format_memory_for_prompt
from actions.open_app import open_app
from actions.close_app import close_app
from actions.sys_info  import sys_info
from actions.calendar import get_calendar_events, add_calendar_event, delete_calendar_event
from actions.reminders import get_reminders, add_reminder
from actions.browser   import browser_control
from actions.shell     import shell_run
from actions.whatsapp  import send_whatsapp_message, save_whatsapp_contact
from actions.media     import play_media
from actions.weather   import get_weather_summary
from actions.screen_vision import analyze_screen
from actions.youtube_stats import get_youtube_channel_report
from actions.tts import speak_text

# -- Paths -------------------------------------------------------------------
BASE_DIR    = Path(__file__).resolve().parent
PROMPT_PATH = BASE_DIR / "core" / "prompt.txt"

CONTROL_TOKEN_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

# -- Model -------------------------------------------------------------------
LIVE_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"

# -- Audio -------------------------------------------------------------------
if pyaudio:
    FORMAT = pyaudio.paInt16
else:
    FORMAT = 16

CHANNELS         = 1
SEND_SAMPLE_RATE = 16000
RECV_SAMPLE_RATE = 24000
CHUNK_SIZE       = 1024
MIC_DEVICE_INDEX = 1   # Realtek mikrofon - lazim olsa deyish

pya = pyaudio.PyAudio() if pyaudio else None

# -- Tool tanimlari ----------------------------------------------------------
TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": "Windows'ta herhangi bir uygulamayi acar. Spotify, Chrome, Terminal, Explorer, VS Code vb.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Uygulama adi (orn. 'Spotify', 'Chrome', 'Terminal')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
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
    },
    {
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
    },
    {
        "name": "sys_info",
        "description": "Sistem bilgisi alir: pil durumu, CPU, RAM, disk, saat, tarih, ag baglantisi.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "battery | cpu | ram | disk | time | date | network | all"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_weather",
        "description": (
            "Anlik hava durumunu ozetler. Varsayilan konum Istanbul'dur. "
            "Kullanici hava durumunu, sicakligi veya yagmur durumunu sordugunda kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "location": {
                    "type": "STRING",
                    "description": "Sehir veya konum. Bos birakilirsa Istanbul kullanilir."
                }
            }
        }
    },
    {
        "name": "get_calendar_events",
        "description": (
            "Outlook/Windows takvimini okur. "
            "Bugun, yarin, siradaki etkinlik veya yaklasan ajandayi ozetler. "
            "Kullanici toplanti, takvim, ajanda, etkinlik veya gunluk programini sordugunda kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": (
                        "today | tomorrow | next | agenda | week veya dogal dilde "
                        "'onumuzdeki 30 gun', '2 hafta', 'bu ay', 'gelecek ay'"
                    )
                },
                "limit": {
                    "type": "NUMBER",
                    "description": "Maksimum etkinlik sayisi"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_calendar_event",
        "description": (
            "Outlook/Windows takvimine yeni etkinlik ekler. "
            "Kullanici toplanti, randevu, takvime ekleme veya etkinlik olusturma isterse kullan. "
            "Baslangic tarihini gercek tarih/saat olarak ver; bitis verilmezse varsayilan sure kullanilir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Etkinlik basligi."},
                "start_iso": {"type": "STRING", "description": "Baslangic tarih/saat. ISO veya yyyy-MM-dd HH:mm formatinda."},
                "end_iso": {"type": "STRING", "description": "Bitis tarih/saat. Opsiyonel."},
                "location": {"type": "STRING", "description": "Etkinlik konumu. Opsiyonel."},
                "notes": {"type": "STRING", "description": "Etkinlik notlari. Opsiyonel."},
                "calendar_name": {"type": "STRING", "description": "Eklenecek takvim adi. Opsiyonel."},
                "all_day": {"type": "BOOLEAN", "description": "true ise tum gun etkinligi olusturur."}
            },
            "required": ["title", "start_iso"]
        }
    },
    {
        "name": "delete_calendar_event",
        "description": "Outlook/Windows takviminden etkinlik siler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Silinecek etkinlik basligi."},
                "start_iso": {"type": "STRING", "description": "Opsiyonel tarih/saat."},
                "calendar_name": {"type": "STRING", "description": "Opsiyonel takvim adi"},
                "delete_all_matches": {"type": "BOOLEAN", "description": "true ise eslesen tum etkinlikleri siler"}
            },
            "required": ["title"]
        }
    },
    {
        "name": "get_reminders",
        "description": "Outlook/Windows animsaticilar listesini okur.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "today | upcoming | overdue | all | next"},
                "limit": {"type": "NUMBER", "description": "Maksimum animsatici sayisi"},
                "list_name": {"type": "STRING", "description": "Belirli bir animsatici listesi adi"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_reminder",
        "description": "Outlook/Windows animsaticilarina yeni bir animsatici ekler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Animsatici basligi"},
                "due_iso": {"type": "STRING", "description": "Opsiyonel tarih/saat."},
                "notes": {"type": "STRING", "description": "Opsiyonel not"},
                "list_name": {"type": "STRING", "description": "Opsiyonel animsatici listesi"},
                "priority": {"type": "STRING", "description": "low | medium | high"},
                "all_day": {"type": "BOOLEAN", "description": "Tum gun animsatici ise true"}
            },
            "required": ["title"]
        }
    },
    {
        "name": "browser_control",
        "description": "Tarayicide URL acar, Google'da arama yapar veya YouTube'da ilk sonucu dogrudan oynatir.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "open_url | search | play_youtube"},
                "url":    {"type": "STRING", "description": "Acilacak URL (open_url icin)"},
                "query":  {"type": "STRING", "description": "Arama sorgusu (search veya play_youtube icin)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "shell_run",
        "description": "Windows terminal komutu calistirir.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "Calistirilacak komut"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "play_media",
        "description": "YouTube, Spotify veya Apple Music'te sarki, muzik veya video acar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Sarki, sanatci, album veya video arama ifadesi"},
                "provider": {"type": "STRING", "description": "auto | youtube | spotify | apple_music"},
                "autoplay": {"type": "BOOLEAN", "description": "true ise mumkunse dogrudan oynatir"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_youtube_channel_report",
        "description": "YouTube kanalinin public istatistiklerini ve son videolarin performansini raporlar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Dogal dilde analiz istegi."},
                "handle": {"type": "STRING", "description": "Opsiyonel kanal handle'i veya ID'si."},
                "video_limit": {"type": "NUMBER", "description": "Analize dahil edilecek son video sayisi. Varsayilan 6."}
            },
            "required": ["query"]
        }
    },
    {
        "name": "analyze_screen",
        "description": "Aktif pencerenin ekran goruntusunu alip Gemini vision ile analiz eder.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Kullanicinin ekranla ilgili sorusu."},
                "target": {"type": "STRING", "description": "Su an sadece active_window desteklenir."}
            },
            "required": ["query"]
        }
    },
    {
        "name": "save_memory",
        "description": "Kullanici hakkinda onemli bilgiyi kalici bellege kaydeder.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {"type": "STRING", "description": "identity | preferences | projects | notes"},
                "key":   {"type": "STRING", "description": "Kisa anahtar"},
                "value": {"type": "STRING", "description": "Deger (Ingilizce)"}
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "delete_memory",
        "description": "Kalici hafizadaki bir kaydi siler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {"type": "STRING", "description": "Kaydin kategorisi."},
                "key": {"type": "STRING", "description": "Silinecek anahtar."},
                "match_text": {"type": "STRING", "description": "Kaydi bulmak icin kullanilacak dogal dil parcasi."}
            }
        }
    },
    {
        "name": "send_whatsapp_message",
        "description": "WhatsApp Desktop veya WhatsApp Web uzerinden mesaj gonderir.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "recipient_name": {"type": "STRING", "description": "Kisi adi."},
                "phone_number": {"type": "STRING", "description": "Uluslararasi telefon numarasi."},
                "message": {"type": "STRING", "description": "Gonderilecek mesaj icerigi"},
                "app_target": {"type": "STRING", "description": "desktop | web | auto."},
                "send_now": {"type": "BOOLEAN", "description": "true ise mesaji otomatik gonderir"}
            },
            "required": ["message"]
        }
    },
    {
        "name": "save_whatsapp_contact",
        "description": "Sik kullanilan bir WhatsApp kisisini kalici bellege kaydeder.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "display_name": {"type": "STRING", "description": "Kaydedilecek kisi adi."},
                "phone_number": {"type": "STRING", "description": "Uluslararasi telefon numarasi."},
                "aliases": {"type": "STRING", "description": "Virgille ayrilmis alternatif hitaplar."}
            },
            "required": ["display_name", "phone_number"]
        }
    }
]


def get_api_key() -> str:
    return str(get_app_config_value("gemini_api_key", "") or "")


def load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "Sen JARVIS'sin - Windows'ta calisan kisisel AI asistani. "
            "Kullanici Azerbaycanca, Turkce veya Ingilizce konusabilir. Hangi dilde konusulursa o dilde yanitla. Kisa ve net yanitlar ver. "
            "Araclari kullanarak gorevleri tamamla, asla taklit etme."
        )


class JarvisLive:
    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()

        self.ui.on_text_command         = self._on_text_command
        self.ui.on_pause_toggle         = self._on_pause_toggle
        self.ui.on_effects_state_change = self._on_effects_state_change
        self._paused = False

    def _on_pause_toggle(self, paused: bool):
        self._paused = paused

    def _on_effects_state_change(self, enabled: bool):
        pass

    def _focus_ui_section_for_tool(self, tool_name: str, args: dict):
        if tool_name == "sys_info":
            query = str(args.get("query", "")).strip().lower()
            if query in {"time", "saat", "zaman", "date", "tarih"}:
                self.ui.focus_panel("time", duration_ms=5200)
            else:
                self.ui.focus_panel("system", duration_ms=5200)
        elif tool_name == "get_weather":
            self.ui.focus_panel("weather", duration_ms=5600)

    def _on_text_command(self, text: str):
        if self._paused:
            return
        self.ui.write_log(f"Siz: {text}")
        if not self._loop or not self.session:
            self.ui.write_log("ERR: JARVIS baglantisi henuz hazir degil.")
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    async def _interrupt_audio(self):
        try:
            if self.audio_in_queue:
                while not self.audio_in_queue.empty():
                    try:
                        self.audio_in_queue.get_nowait()
                    except Exception:
                        break
            if self.session:
                await self.session.send_realtime_input(audio_stream_end=True)
            self.set_speaking(False)
        except Exception:
            pass

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        else:
            self.ui.set_state("LISTENING")

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} - {short}")
        self.ui.write_debug(f"{tool_name}: {short}", level="ERROR")
        self.ui.set_state("ERROR")

    @staticmethod
    def _result_looks_like_error(result) -> bool:
        text = str(result or "").strip().lower()
        if not text:
            return False
        error_markers = (
            "hata", "error", "alinamadi", "bulunamadi",
            "acilamadi", "tamamlanamadi", "gecersiz",
            "izin gerekiyor", "izin gerekli", "baglanti", "gerekli.",
        )
        return any(marker in text for marker in error_markers)

    @staticmethod
    def _should_play_success_sfx(tool_name: str, args: dict, result) -> bool:
        action_tools = {
            "open_app", "add_calendar_event", "add_reminder",
            "delete_calendar_event", "remove_calendar_event",
        }
        if tool_name in action_tools:
            return True
        if tool_name == "send_whatsapp_message":
            text = str(result or "").lower()
            if bool(args.get("send_now", False)):
                return "gonderildi" in text
            return False
        return False

    @staticmethod
    def _clean_transcript_text(text: str) -> tuple[str, bool]:
        raw = str(text or "")
        had_noise = False
        if CONTROL_TOKEN_RE.search(raw):
            had_noise = True
            raw = CONTROL_TOKEN_RE.sub(" ", raw)
        cleaned = []
        for ch in raw:
            if ch in "\n\r\t" or ord(ch) >= 32:
                cleaned.append(ch)
            else:
                had_noise = True
        normalized = " ".join("".join(cleaned).split())
        return normalized.strip(), had_noise

    def _build_config(self) -> types.LiveConnectConfig:
        memory  = load_memory()
        mem_str = format_memory_for_prompt(memory)
        sys_p   = load_system_prompt()
        now     = datetime.datetime.now()
        time_ctx = f"[SU ANKI ZAMAN]\n{now.strftime('%A, %d %B %Y - %H:%M')}\n\n"

        parts = [time_ctx]
        if mem_str:
            parts.append(mem_str + "\n\n")
        parts.append(sys_p)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=str(get_app_config_value("voice", "Fenrir") or "Fenrir")
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})
        print(f"[JARVIS] TOOL: {name} {args}")
        self.ui.set_state("THINKING")

        loop   = asyncio.get_event_loop()
        result = "Tamam."
        had_exception = False

        try:
            if name == "save_memory":
                cat = args.get("category", "notes")
                key = args.get("key", "")
                val = args.get("value", "")
                if key and val:
                    update_memory({cat: {key: {"value": val}}})
                result = "ok"

            elif name == "delete_memory":
                result = delete_memory(
                    args.get("category", ""),
                    args.get("key", ""),
                    args.get("match_text", ""),
                )

            elif name == "close_app":
                r = await loop.run_in_executor(None, lambda: close_app(args.get("app_name", "")))
                result = r or "Baglandi."

            elif name == "open_app":
                r = await loop.run_in_executor(None, lambda: open_app(args.get("app_name", "")))
                result = r or f"{args.get('app_name')} acildi."

            elif name == "sys_info":
                self._focus_ui_section_for_tool(name, args)
                r = await loop.run_in_executor(None, lambda: sys_info(args.get("query", "all")))
                result = r or "Bilgi alindi."

            elif name == "get_weather":
                self._focus_ui_section_for_tool(name, args)
                r = await loop.run_in_executor(None, lambda: get_weather_summary(args.get("location") or None))
                result = r or "Hava durumu bilgisi alindi."

            elif name == "get_calendar_events":
                r = await loop.run_in_executor(
                    None,
                    lambda: get_calendar_events(args.get("query", "today"), int(args.get("limit", 6) or 6)),
                )
                result = r or "Takvim bilgisi alindi."

            elif name == "add_calendar_event":
                r = await loop.run_in_executor(
                    None,
                    lambda: add_calendar_event(
                        args.get("title", ""), args.get("start_iso", ""),
                        args.get("end_iso", ""), args.get("notes", ""),
                        args.get("location", ""), args.get("calendar_name", ""),
                        bool(args.get("all_day", False)),
                    ),
                )
                result = r or "Takvim etkinligi eklendi."

            elif name == "delete_calendar_event":
                r = await loop.run_in_executor(
                    None,
                    lambda: delete_calendar_event(
                        args.get("title", ""), args.get("start_iso", ""),
                        args.get("calendar_name", ""), bool(args.get("delete_all_matches", False)),
                    ),
                )
                result = r or "Takvim etkinligi silindi."

            elif name == "get_reminders":
                r = await loop.run_in_executor(
                    None,
                    lambda: get_reminders(
                        args.get("query", "upcoming"), int(args.get("limit", 8) or 8),
                        args.get("list_name", ""),
                    ),
                )
                result = r or "Animsatici bilgisi alindi."

            elif name == "add_reminder":
                r = await loop.run_in_executor(
                    None,
                    lambda: add_reminder(
                        args.get("title", ""), args.get("due_iso", ""),
                        args.get("notes", ""), args.get("list_name", ""),
                        args.get("priority", ""), bool(args.get("all_day", False)),
                    ),
                )
                result = r or "Animsatici eklendi."

            elif name == "browser_control":
                r = await loop.run_in_executor(
                    None, lambda: browser_control(args.get("action"), args.get("url"), args.get("query")))
                result = r or "Tamam."

            elif name == "shell_run":
                r = await loop.run_in_executor(None, lambda: shell_run(args.get("command", "")))
                result = r or "Komut calistirildi."

            elif name == "play_media":
                r = await loop.run_in_executor(
                    None,
                    lambda: play_media(
                        args.get("query", ""), args.get("provider", "auto"),
                        bool(args.get("autoplay", True)),
                    ),
                )
                result = r or "Medya oynatma baslatildi."

            elif name == "get_youtube_channel_report":
                r = await loop.run_in_executor(
                    None,
                    lambda: get_youtube_channel_report(
                        args.get("query", "overview"), args.get("handle", ""),
                        int(args.get("video_limit", 6) or 6),
                    ),
                )
                result = r or "YouTube kanal raporu alindi."

            elif name == "analyze_screen":
                r = await loop.run_in_executor(
                    None,
                    lambda: analyze_screen(
                        args.get("query", "Ekranda ne var?"), args.get("target", "active_window"),
                    ),
                )
                result = r or "Ekran analizi tamamlandi."

            elif name == "send_whatsapp_message":
                r = await loop.run_in_executor(
                    None,
                    lambda: send_whatsapp_message(
                        args.get("message", ""), args.get("phone_number", ""),
                        args.get("recipient_name", ""), bool(args.get("send_now", False)),
                        args.get("app_target", "auto"),
                    ),
                )
                result = r or "WhatsApp islemi tamamlandi."

            elif name == "save_whatsapp_contact":
                r = await loop.run_in_executor(
                    None,
                    lambda: save_whatsapp_contact(
                        args.get("display_name", ""), args.get("phone_number", ""),
                        args.get("aliases", ""),
                    ),
                )
                result = r or "WhatsApp kisisi kaydedildi."

            else:
                result = f"Bilinmeyen arac: {name}"

        except Exception as e:
            result = f"Hata: {e}"
            had_exception = True
            traceback.print_exc()
            self.speak_error(name, e)

        tool_failed = self._result_looks_like_error(result)
        if tool_failed:
            if not had_exception:
                self.ui.set_state("ERROR")
        elif self._should_play_success_sfx(name, args, result):
            self.ui.play_success_sfx()

        if not tool_failed and not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[JARVIS] RESULT: {name} -> {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        """Mikrofondan gelen sesi Gemini'ye gonderir."""
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)
    async def _listen_audio(self):
        import sounddevice as sd
        import numpy as np
        print("[JARVIS] Mikrofon aciliyor (sounddevice)...")
        loop = asyncio.get_running_loop()
        print("[JARVIS] Mikrofon hazir. Dinliyorum...")
        def callback(indata, frames, time, status):
            data = indata.tobytes()
            loop.call_soon_threadsafe(self.out_queue.put_nowait, {"data": data, "mime_type": "audio/pcm"})
        with sd.InputStream(samplerate=SEND_SAMPLE_RATE, channels=1, dtype="int16", blocksize=CHUNK_SIZE, device=MIC_DEVICE_INDEX, callback=callback, latency="low"):
            while True:
                await asyncio.sleep(0.1)
            print(f"[JARVIS] Mikrofon hatasi: {e}")
            traceback.print_exc()

    async def _play_audio(self):
        """Gemini den gelen sesi hoparlorden calar."""
        import sounddevice as sd
        import numpy as np
        print("[JARVIS] Ses cikisi aciliyor (sounddevice)...")
        print("[JARVIS] Ses cikisi hazir.")
        stream = sd.OutputStream(samplerate=RECV_SAMPLE_RATE, channels=1, dtype="int16")
        stream.start()
        try:
            while True:
                chunk = await self.audio_in_queue.get()
                self.set_speaking(True)
                audio_array = np.frombuffer(chunk, dtype=np.int16)
                await asyncio.to_thread(stream.write, audio_array)
        except Exception as e:
            print(f"[JARVIS] Ses calma hatasi: {e}")
            traceback.print_exc()
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()
            self.set_speaking(False)

    async def _receive_responses(self):
        """Gemini'den gelen yanitlari islir."""
        while True:
            try:
                async for response in self.session.receive():
                    # Ses verisi
                    if hasattr(response, 'data') and response.data:
                        await self.audio_in_queue.put(response.data)
                        continue

                    # Server content
                    sc = getattr(response, 'server_content', None)
                    if sc:
                        # Transkript
                        ot = getattr(sc, 'output_transcription', None)
                        if ot and getattr(ot, 'text', None):
                            text, _ = self._clean_transcript_text(ot.text)
                            if text:
                                self.ui.write_log(f"JARVIS: {text}")

                        it = getattr(sc, 'input_transcription', None)
                        if it and getattr(it, 'text', None):
                            text, _ = self._clean_transcript_text(it.text)
                            if text:
                                self.ui.write_log(f"Siz: {text}")

                        # Model turn complete
                        if getattr(sc, 'turn_complete', False):
                            self.set_speaking(False)

                        # Audio chunks
                        model_turn = getattr(sc, 'model_turn', None)
                        if model_turn:
                            for part in getattr(model_turn, 'parts', []):
                                inline = getattr(part, 'inline_data', None)
                                if inline and getattr(inline, 'data', None):
                                    await self.audio_in_queue.put(inline.data)

                    # Tool calls
                    tc = getattr(response, 'tool_call', None)
                    if tc:
                        responses = []
                        for fc in tc.function_calls:
                            fr = await self._execute_tool(fc)
                            responses.append(fr)
                        await self.session.send_tool_response(function_responses=responses)

            except Exception as e:
                print(f"[JARVIS] Yanit hatasi: {e}")
                self.set_speaking(False)
                break

    async def run(self):
        api_key = get_api_key()
        client  = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
        config  = self._build_config()

        while True:
            try:
                self.ui.write_log("SYS: JARVIS hazir. Dinliyorum...")
                self.ui.set_state("CONNECTING")

                self.audio_in_queue = asyncio.Queue()
                self.out_queue      = asyncio.Queue()
                self._loop          = asyncio.get_event_loop()

                async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
                    self.session = session
                    self.ui.set_state("LISTENING")
                    print("[JARVIS] Baglandi.")

                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._listen_audio())
                        tg.create_task(self._play_audio())
                        tg.create_task(self._send_realtime())
                        tg.create_task(self._receive_responses())

            except Exception as e:
                print(f"[JARVIS] Baglanti hatasi: {e}")
                self.ui.write_log(f"ERR: JARVIS baglantisi kesildi - {e}")
                self.ui.set_state("ERROR")
                print("[JARVIS] 3 saniyede yeniden baglaniyor...")
                await asyncio.sleep(3)


def main():
    
    import winreg, sys
    try:
        _path = os.path.abspath(sys.argv[0])
        _py = sys.executable.replace("python.exe", "pythonw.exe")
        _key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
            0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(_key, "Jarvis", 0, winreg.REG_SZ, _py + " " + _path)
        winreg.CloseKey(_key)
        print("[JARVIS] Startup-a elave edildi.")
    except Exception as _e:
        print("[JARVIS] Startup xetasi:", _e)

    if os.environ.get("TERM_PROGRAM") == "vscode":
        print("[JARVIS] VS Code icinden baslatildi.")

    ui = JarvisUI()
    # Acilis sesi
    import subprocess, sys
    _sfx = str(Path(__file__).resolve().parent / "SFX" / "Start.mp3")
    subprocess.Popen(["powershell","-WindowStyle","Hidden","-Command", f"Add-Type -AssemblyName presentationCore; $m=[System.Windows.Media.MediaPlayer]::new(); $m.Open([uri]\"    ui = JarvisUI()sfx\"); $m.Play(); Start-Sleep -s 4"], start_new_session=True)

    def runner():
        ui.wait_for_api_key()
        jarvis = JarvisLive(ui)
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            print("\nKapatiliyor...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()








