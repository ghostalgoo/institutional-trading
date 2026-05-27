#!/usr/bin/env python3
"""Static site + economic calendar API for the Institutional Trading sales page."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("TRADING_DATA_DIR", ROOT)).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
PARIS = ZoneInfo("Europe/Paris") if ZoneInfo else timezone(timedelta(hours=2))
TRADING_ECONOMICS_URL = "https://api.tradingeconomics.com/calendar/country/united%20states"
FOREX_FACTORY_URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json",
]
CALENDAR_CACHE_SECONDS = 300
CALENDAR_CACHE: dict[str, Any] = {"expires_at": None, "payload": None}
ACCESS_REQUESTS_FILE = DATA_DIR / "access_requests.json"
PAYPAL_EVENTS_FILE = DATA_DIR / "paypal_events.json"
DONATIONS_FILE = DATA_DIR / "donations.json"
ANALYTICS_FILE = DATA_DIR / "analytics.json"
SITE_CONFIG_FILE = DATA_DIR / "site_config.json"
CHAT_MESSAGES_FILE = DATA_DIR / "chat_messages.json"
VIP_MESSAGES_FILE = DATA_DIR / "vip_messages.json"
CLIENT_SESSIONS_FILE = DATA_DIR / "client_sessions.json"
ACCESS_REQUESTS_LOCK = threading.Lock()
DEFAULT_ADMIN_PASSWORD = "ghostadmin"
DEFAULT_ADMIN_ACCESS_KEY = "audin-private-2026"
ADMIN_PASSWORD = os.environ.get("TRADING_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
ADMIN_ACCESS_KEY = os.environ.get("TRADING_ADMIN_KEY", DEFAULT_ADMIN_ACCESS_KEY)
ADMIN_PASSWORDS = {value for value in {ADMIN_PASSWORD, DEFAULT_ADMIN_PASSWORD} if value}
ADMIN_ACCESS_KEYS = {value for value in {ADMIN_ACCESS_KEY, DEFAULT_ADMIN_ACCESS_KEY} if value}
PAYPAL_WEBHOOK_ID = os.environ.get("PAYPAL_WEBHOOK_ID", "")
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_API_BASE = os.environ.get("PAYPAL_API_BASE", "https://api-m.paypal.com")
PAYPAL_ALLOW_UNVERIFIED = os.environ.get("PAYPAL_WEBHOOK_ALLOW_UNVERIFIED", "").lower() in {"1", "true", "yes"}
PAYPAL_PRICE_EUR = 49.99
PAYPAL_PAYMENT_URL = os.environ.get("TRADING_PAYPAL_URL", "https://www.paypal.com/ncp/payment/DCVU8JTEY7GJ4")
PAYPAL_PAYMENT_URLS = {
    "gold": "https://www.paypal.com/ncp/payment/DCVU8JTEY7GJ4",
    "nasdaq": "https://www.paypal.com/ncp/payment/VMTBQ5G9EMWTU",
    "btc": "https://www.paypal.com/ncp/payment/SB6UU4KPJ974A",
}
PRODUCT_LABELS = {
    "btc": "BTC Institutional Setup - 49,99 EUR / mois",
    "gold": "Gold Institutional Setup - 49,99 EUR / mois",
    "nasdaq": "Nasdaq Institutional Setup - 49,99 EUR / mois",
}
DONATION_EMAIL = os.environ.get("TRADING_DONATION_EMAIL", "Mehdi.parisville@outlook.com")
DONATION_URL = os.environ.get(
    "TRADING_DONATION_URL",
    f"https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business={quote(DONATION_EMAIL)}&currency_code=EUR&item_name=Institutional%20Trading%20Donation&custom=donation",
)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_STATE_TABLE = os.environ.get("SUPABASE_STATE_TABLE", "site_state")
SUPABASE_ENABLED = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)
SUPABASE_TIMEOUT_SECONDS = 8


def now_paris() -> datetime:
    return datetime.now(PARIS).replace(microsecond=0)


def format_date_label(value: datetime) -> str:
    weekdays = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    months = ["jan", "fev", "mar", "avr", "mai", "juin", "juil", "aout", "sep", "oct", "nov", "dec"]
    return f"{weekdays[value.weekday()]} {value.day:02d} {months[value.month - 1]}"


def parse_provider_date(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.startswith("/Date(") and text.endswith(")/"):
        try:
            millis = int(text[6:-2].split("+", 1)[0].split("-", 1)[0])
            return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).astimezone(PARIS)
        except ValueError:
            return None
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(PARIS)


def markets_for_event(title: str, category: str) -> list[str]:
    haystack = f"{title} {category}".lower()
    markets = {"macro"}
    if any(word in haystack for word in ["cpi", "inflation", "ppi", "pce", "fed", "fomc", "rate", "yields", "payroll", "unemployment", "claims"]):
        markets.add("gold")
    if any(word in haystack for word in ["cpi", "ppi", "pce", "fed", "fomc", "retail", "payroll", "unemployment", "claims", "sentiment"]):
        markets.add("btc")
    if any(word in haystack for word in ["retail", "industrial", "pmi", "ism", "gdp", "sentiment", "confidence", "fed", "fomc", "payroll", "claims"]):
        markets.add("indices")
    return sorted(markets)


def relevant_event(title: str, category: str) -> bool:
    haystack = f"{title} {category}".lower()
    keywords = [
        "cpi",
        "consumer price",
        "ppi",
        "producer price",
        "pce",
        "inflation",
        "fomc",
        "fed",
        "interest rate",
        "non farm",
        "payroll",
        "unemployment",
        "jobless",
        "retail sales",
        "industrial production",
        "ism",
        "pmi",
        "gdp",
        "consumer sentiment",
        "consumer confidence",
    ]
    return any(keyword in haystack for keyword in keywords)


def event_copy(title: str, markets: list[str]) -> tuple[str, str, str]:
    haystack = title.lower()
    if any(word in haystack for word in ["cpi", "inflation", "ppi", "pce"]):
        return (
            "Inflation = taux, dollar, volatilite",
            "Verifier le consensus puis la reaction DXY / US10Y. Gold et BTC peuvent partir vite si les taux reels bougent.",
            "Attendre la premiere impulsion, puis chercher reprise ou invalidation sur niveau propre.",
        )
    if any(word in haystack for word in ["fed", "fomc", "rate"]):
        return (
            "Fed = volatilite taux / dollar",
            "Le marche lit le ton hawkish ou dovish. Impact direct sur Gold, Nasdaq, BTC et rendements US.",
            "Ne pas courir la premiere bougie. Lire le deuxieme mouvement et la confirmation inter-marche.",
        )
    if any(word in haystack for word in ["payroll", "unemployment", "jobless"]):
        return (
            "Emploi US = gros catalyseur",
            "Comparer emploi, chomage et salaires. La reaction peut changer si les sous-composantes se contredisent.",
            "Surveiller dollar, rendements et Nasdaq avant de valider un signal BTC ou Gold.",
        )
    if any(word in haystack for word in ["retail", "sentiment", "confidence"]):
        return (
            "Consommation = regime de risque",
            "Les chiffres consommateurs donnent le ton risk-on / risk-off pour indices et BTC.",
            "Verifier si Nasdaq confirme le mouvement. Gold reste sensible au dollar et aux taux.",
        )
    return (
        "Catalyseur macro a surveiller",
        "Verifier consensus, chiffre publie, dollar, rendements US et reaction des indices.",
        "Attendre que la volatilite initiale se calme avant de prendre le signal.",
    )


def accent_for(markets: list[str], tag: str) -> str:
    if tag in {"High impact", "Impact fort"}:
        return "green"
    if "gold" in markets and "btc" not in markets:
        return "gold"
    if "btc" in markets and "gold" not in markets:
        return "blue"
    return "green"


def normalize_te_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    title = str(raw.get("Event") or raw.get("event") or raw.get("Category") or "Evenement marche").strip()
    category = str(raw.get("Category") or raw.get("category") or "").strip()
    date = parse_provider_date(raw.get("Date") or raw.get("date") or raw.get("LastUpdate"))
    if not date or not relevant_event(title, category):
        return None
    markets = markets_for_event(title, category)
    importance = str(raw.get("Importance") or raw.get("importance") or "")
    tag = "Impact fort" if importance == "3" or any(word in title.lower() for word in ["cpi", "fomc", "payroll", "pce"]) else "Macro"
    expected_title, expected, reaction = event_copy(title, markets)
    source_url = raw.get("URL") or raw.get("SourceURL") or "https://tradingeconomics.com/calendar"
    window = "Gold / BTC" if {"gold", "btc"}.issubset(markets) else "XAUUSD" if "gold" in markets else "BTC / Indices" if "btc" in markets else "Session US"
    return {
        "id": f"te-{raw.get('CalendarId') or raw.get('Ticker') or date.isoformat()}",
        "date": date.isoformat(),
        "dateLabel": format_date_label(date),
        "timeLabel": f"{date:%H:%M} Paris",
        "title": title,
        "copy": f"{category or 'Macro US'} : impact potentiel sur {', '.join(markets).replace('macro, ', '')}.",
        "source": source_url,
        "markets": markets,
        "window": window,
        "tag": tag,
        "accent": accent_for(markets, tag),
        "expectedTitle": expected_title,
        "expected": expected,
        "reaction": reaction,
    }


def normalize_ff_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    title = str(raw.get("title") or "Evenement marche").strip()
    country = str(raw.get("country") or "").strip().upper()
    impact = str(raw.get("impact") or "").strip()
    date = parse_provider_date(raw.get("date"))
    if country != "USD" or not date or impact not in {"High", "Medium"}:
        return None
    if not relevant_event(title, "USD"):
        return None

    markets = markets_for_event(title, "USD")
    tag = "Impact fort" if impact == "High" else "Macro"
    expected_title, expected, reaction = event_copy(title, markets)
    forecast = str(raw.get("forecast") or "").strip() or "n/a"
    previous = str(raw.get("previous") or "").strip() or "n/a"
    window = "Gold / BTC" if {"gold", "btc"}.issubset(markets) else "XAUUSD" if "gold" in markets else "BTC / Indices" if "btc" in markets else "Session US"
    return {
        "id": f"ff-{country}-{title}-{date.isoformat()}",
        "date": date.isoformat(),
        "dateLabel": format_date_label(date),
        "timeLabel": f"{date:%H:%M} Paris",
        "title": title,
        "copy": f"Forecast {forecast} / previous {previous}. Impact potentiel sur {', '.join(markets).replace('macro, ', '')}.",
        "source": "https://www.forexfactory.com/calendar",
        "markets": markets,
        "window": window,
        "tag": tag,
        "accent": accent_for(markets, tag),
        "expectedTitle": expected_title,
        "expected": expected,
        "reaction": reaction,
    }


def fetch_trading_economics() -> list[dict[str, Any]]:
    api_key = os.environ.get("TRADING_ECONOMICS_KEY", "guest:guest")
    url = f"{TRADING_ECONOMICS_URL}?c={quote(api_key, safe=':')}&importance=3"
    request = Request(url, headers={"User-Agent": "InstitutionalTradingCalendar/1.0"})
    with urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        return []
    start = now_paris() - timedelta(days=1)
    end = now_paris() + timedelta(days=45)
    events = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        event = normalize_te_event(raw)
        if not event:
            continue
        event_date = parse_provider_date(event["date"])
        if event_date and start <= event_date <= end:
            events.append(event)
    return sorted(events, key=lambda item: item["date"])[:18]


def fetch_forex_factory() -> list[dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) InstitutionalTradingCalendar/1.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.forexfactory.com/",
    }
    last_error: Exception | None = None
    payload: Any = []
    for url in FOREX_FACTORY_URLS:
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
            last_error = None
            break
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            last_error = error
    if last_error:
        raise last_error
    if not isinstance(payload, list):
        return []
    start = now_paris() - timedelta(hours=12)
    end = now_paris() + timedelta(days=14)
    events = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        event = normalize_ff_event(raw)
        if not event:
            continue
        event_date = parse_provider_date(event["date"])
        if event_date and start <= event_date <= end:
            events.append(event)
    return sorted(events, key=lambda item: item["date"])[:18]


def fallback_events() -> list[dict[str, Any]]:
    def next_weekday(weekday: int, hour: int, minute: int = 30, min_days: int = 0) -> datetime:
        base = now_paris()
        days = (weekday - base.weekday()) % 7
        if days < min_days:
            days += 7
        candidate = (base + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= base + timedelta(hours=2):
            candidate += timedelta(days=7)
        return candidate

    events = [
        (next_weekday(3, 14, 30), "Inscriptions chomage US", "Emploi US, dollar, rendements et reaction indices.", "https://www.dol.gov/ui/data.pdf", ["macro", "gold", "btc", "indices"], "Gold / BTC", "Impact fort", "green"),
        (next_weekday(2, 20, 0, 1), "Communication Fed", "Ton Fed, taux, dollar et risque de volatilite sur Gold, BTC et Nasdaq.", "https://www.federalreserve.gov/newsevents/calendar.htm", ["macro", "gold", "btc", "indices"], "Fed / taux", "Macro", "gold"),
        (next_weekday(4, 15, 45, 2), "PMI US / croissance", "Activite US et sentiment marche : surveiller indices, DXY et rendements.", "https://www.spglobal.com/marketintelligence/en/mi/products/pmi.html", ["macro", "gold", "indices"], "Session US", "Macro", "blue"),
        (next_weekday(1, 14, 30, 3), "Inflation US", "Inflation et taux reels : catalyseur majeur pour Gold, BTC et indices.", "https://www.bls.gov/schedule/news_release/cpi.htm", ["macro", "gold", "btc", "indices"], "Gold / BTC", "Impact fort", "green"),
    ]
    output = []
    for index, (date, title, copy, source, markets, window, tag, accent) in enumerate(events):
        expected_title, expected, reaction = event_copy(title, markets)
        output.append({
            "id": f"fallback-{index}",
            "date": date.isoformat(),
            "dateLabel": format_date_label(date),
            "timeLabel": f"{date:%H:%M} Paris",
            "title": title,
            "copy": copy,
            "source": source,
            "markets": markets,
            "window": window,
            "tag": tag,
            "accent": accent,
            "expectedTitle": expected_title,
            "expected": expected,
            "reaction": reaction,
        })
    return sorted(output, key=lambda item: item["date"])


def calendar_payload() -> dict[str, Any]:
    cached_payload = CALENDAR_CACHE.get("payload")
    cached_expires = CALENDAR_CACHE.get("expires_at")
    if isinstance(cached_payload, dict) and isinstance(cached_expires, datetime) and now_paris() < cached_expires:
        return cached_payload

    provider = "fallback"
    status = "local_fallback"
    events: list[dict[str, Any]] = []

    try:
        if os.environ.get("TRADING_ECONOMICS_KEY"):
            events = fetch_trading_economics()
            provider = "tradingeconomics"
            status = "live"
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        status = f"tradingeconomics_unavailable: {error.__class__.__name__}"

    if not events:
        try:
            events = fetch_forex_factory()
            if events:
                provider = "forexfactory"
                status = "live"
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            status = f"forexfactory_unavailable: {error.__class__.__name__}"

    if not events:
        events = fallback_events()

    payload = {
        "provider": provider,
        "status": status,
        "updated_at": now_paris().isoformat(),
        "timezone": "Europe/Paris",
        "events": events,
    }
    CALENDAR_CACHE["payload"] = payload
    CALENDAR_CACHE["expires_at"] = now_paris() + timedelta(seconds=CALENDAR_CACHE_SECONDS)
    return payload


def clean_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return " ".join(text.split())[:limit]


def clean_image_data(value: Any) -> str:
    text = str(value or "").strip()
    if not text.startswith("data:image/"):
        return ""
    header, separator, payload = text.partition(",")
    if separator != "," or ";base64" not in header:
        return ""
    if len(text) > 5_500_000:
        return ""
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
    if not payload or any(char not in allowed for char in payload[:2000]):
        return ""
    return text


def supabase_table_name() -> str:
    return "".join(char for char in SUPABASE_STATE_TABLE if char.isalnum() or char == "_") or "site_state"


def supabase_request(method: str, path: str, payload: Any | None = None, prefer: str = "") -> Any:
    if not SUPABASE_ENABLED:
        return None
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    request = Request(
        f"{SUPABASE_URL}/rest/v1/{path.lstrip('/')}",
        data=body,
        headers=headers,
        method=method,
    )
    with urlopen(request, timeout=SUPABASE_TIMEOUT_SECONDS) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else None


def load_remote_state(key: str) -> Any | None:
    if not SUPABASE_ENABLED:
        return None
    try:
        table = supabase_table_name()
        query_key = quote(key, safe="")
        rows = supabase_request("GET", f"{table}?key=eq.{query_key}&select=value&limit=1")
    except Exception:
        return None
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return rows[0].get("value")
    return None


def save_remote_state(key: str, value: Any) -> None:
    if not SUPABASE_ENABLED:
        return
    try:
        table = supabase_table_name()
        body = {
            "key": key,
            "value": value,
            "updated_at": now_paris().isoformat(),
        }
        supabase_request(
            "POST",
            f"{table}?on_conflict=key",
            body,
            prefer="resolution=merge-duplicates,return=minimal",
        )
    except Exception:
        return


def load_state(key: str, path: Path, default: Any, expected_type: type) -> Any:
    remote = load_remote_state(key)
    if isinstance(remote, expected_type):
        return remote
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return payload if isinstance(payload, expected_type) else default


def save_state(key: str, path: Path, payload: Any) -> None:
    try:
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    finally:
        save_remote_state(key, payload)


def load_access_requests() -> list[dict[str, Any]]:
    return load_state("access_requests", ACCESS_REQUESTS_FILE, [], list)


def save_access_requests(requests: list[dict[str, Any]]) -> None:
    save_state("access_requests", ACCESS_REQUESTS_FILE, requests)


def load_paypal_events() -> list[dict[str, Any]]:
    return load_state("paypal_events", PAYPAL_EVENTS_FILE, [], list)


def save_paypal_events(events: list[dict[str, Any]]) -> None:
    save_state("paypal_events", PAYPAL_EVENTS_FILE, events[:250])


def load_donations() -> list[dict[str, Any]]:
    return load_state("donations", DONATIONS_FILE, [], list)


def save_donations(donations: list[dict[str, Any]]) -> None:
    save_state("donations", DONATIONS_FILE, donations[:500])


def load_chat_messages() -> list[dict[str, Any]]:
    return load_state("chat_messages", CHAT_MESSAGES_FILE, [], list)


def save_chat_messages(messages: list[dict[str, Any]]) -> None:
    save_state("chat_messages", CHAT_MESSAGES_FILE, messages[:500])


def load_vip_messages() -> list[dict[str, Any]]:
    return load_state("vip_messages", VIP_MESSAGES_FILE, [], list)


def save_vip_messages(messages: list[dict[str, Any]]) -> None:
    save_state("vip_messages", VIP_MESSAGES_FILE, messages[:800])


def load_client_sessions() -> dict[str, Any]:
    return load_state("client_sessions", CLIENT_SESSIONS_FILE, {}, dict)


def save_client_sessions(sessions: dict[str, Any]) -> None:
    save_state("client_sessions", CLIENT_SESSIONS_FILE, sessions)


def create_chat_message(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    email = clean_text(data.get("email"), 180).lower()
    message = clean_text(data.get("message"), 1200)
    if not email or not message:
        return False, {"ok": False, "error": "missing_fields"}
    item = {
        "id": f"chat-{now_paris():%Y%m%d%H%M%S}-{uuid4().hex[:8]}",
        "created_at": now_paris().isoformat(),
        "sender": "client",
        "status": "open",
        "name": clean_text(data.get("name"), 120),
        "email": email,
        "message": message,
    }
    with ACCESS_REQUESTS_LOCK:
        messages = load_chat_messages()
        messages.insert(0, item)
        save_chat_messages(messages)
    return True, {"ok": True, "message": item}


def reply_chat_message(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    email = clean_text(data.get("email"), 180).lower()
    message = clean_text(data.get("message"), 1200)
    if not email or not message:
        return False, {"ok": False, "error": "missing_fields"}
    item = {
        "id": f"chat-{now_paris():%Y%m%d%H%M%S}-{uuid4().hex[:8]}",
        "created_at": now_paris().isoformat(),
        "sender": "admin",
        "status": "answered",
        "name": "Admin",
        "email": email,
        "message": message,
    }
    with ACCESS_REQUESTS_LOCK:
        messages = load_chat_messages()
        messages.insert(0, item)
        save_chat_messages(messages)
    return True, {"ok": True, "message": item}


def update_chat_status(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    message_id = clean_text(data.get("id"), 100)
    email = clean_text(data.get("email"), 180).lower()
    status = clean_text(data.get("status"), 40) or "open"
    if status not in {"open", "resolved", "deleted"}:
        return False, {"ok": False, "error": "invalid_status"}
    if not message_id and not email:
        return False, {"ok": False, "error": "missing_identifier"}
    now = now_paris().isoformat()
    with ACCESS_REQUESTS_LOCK:
        messages = load_chat_messages()
        changed = 0
        for item in messages:
            if message_id and clean_text(item.get("id"), 100) != message_id:
                continue
            if email and clean_text(item.get("email"), 180).lower() != email:
                continue
            item["status"] = status
            item["updated_at"] = now
            changed += 1
        if not changed:
            return False, {"ok": False, "error": "not_found"}
        save_chat_messages(messages)
    return True, {"ok": True, "updated": changed, "status": status}


def default_site_config() -> dict[str, Any]:
    return {
        "flash": {
            "active": False,
            "title": "",
            "copy": "",
            "cta": "Voir l'offre",
            "url": "#offers",
            "endsAt": "",
        },
        "vip": {
            "announcement": {
                "active": True,
                "title": "Bienvenue dans le VIP Trading Floor",
                "copy": "Retrouvez ici les lives formation, les notes marche et les salons prives reserves aux clients actifs.",
                "cta": "Voir le prochain live",
                "url": "#vip-calendar",
            },
            "events": [
                {
                    "id": "live-default-1",
                    "title": "Live formation : structure, liquidites et execution",
                    "startsAt": "",
                    "duration": "60 min",
                    "setup": "Gold / BTC / Nasdaq",
                    "type": "Formation live",
                    "link": "",
                    "copy": "Session reservee aux membres actifs. Le lien sera publie dans le panel avant le live.",
                }
            ],
            "resources": [
                {"title": "Checklist avant execution", "tag": "Risque", "copy": "Contexte, session, invalidation, taille de position, alerte TradingView."},
                {"title": "BOS / CHOCH / FVG", "tag": "Structure", "copy": "Comprendre la logique de structure et les zones qui comptent."},
                {"title": "Sessions & liquidites", "tag": "Timing", "copy": "Adapter la lecture entre London, New York, Asia, BTC 24/7 et indices."},
            ],
            "rooms": ["general", "gold", "btc", "nasdaq", "macro", "formation"],
        },
    }


def load_site_config() -> dict[str, Any]:
    payload = load_state("site_config", SITE_CONFIG_FILE, default_site_config(), dict)
    config = default_site_config()
    if isinstance(payload, dict):
        flash = payload.get("flash")
        if isinstance(flash, dict):
            config["flash"].update({key: flash.get(key, config["flash"][key]) for key in config["flash"]})
        vip = payload.get("vip")
        if isinstance(vip, dict):
            announcement = vip.get("announcement")
            if isinstance(announcement, dict):
                config["vip"]["announcement"].update({
                    key: clean_text(announcement.get(key), 500) if key != "active" else bool(announcement.get(key))
                    for key in config["vip"]["announcement"]
                })
            events = vip.get("events")
            if isinstance(events, list):
                config["vip"]["events"] = events[:30]
            resources = vip.get("resources")
            if isinstance(resources, list):
                config["vip"]["resources"] = resources[:20]
            rooms = vip.get("rooms")
            if isinstance(rooms, list):
                config["vip"]["rooms"] = [clean_text(room, 40) for room in rooms if clean_text(room, 40)][:12] or config["vip"]["rooms"]
    return config


def save_site_config(config: dict[str, Any]) -> None:
    save_state("site_config", SITE_CONFIG_FILE, config)


def parse_local_datetime(value: Any) -> datetime | None:
    text = clean_text(value, 80)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PARIS)
    return parsed.astimezone(PARIS)


def public_flash_payload() -> dict[str, Any]:
    flash = dict(load_site_config().get("flash", {}))
    ends_at = parse_local_datetime(flash.get("endsAt"))
    if not flash.get("active") or not clean_text(flash.get("title"), 90):
        flash["active"] = False
    if ends_at and ends_at <= now_paris():
        flash["active"] = False
    return flash


def public_vip_payload() -> dict[str, Any]:
    vip = load_site_config().get("vip", default_site_config()["vip"])
    events = vip.get("events") if isinstance(vip.get("events"), list) else []
    resources = vip.get("resources") if isinstance(vip.get("resources"), list) else []
    rooms = vip.get("rooms") if isinstance(vip.get("rooms"), list) else default_site_config()["vip"]["rooms"]
    clean_events = []
    for event in events[:30]:
        if not isinstance(event, dict):
            continue
        clean_events.append({
            "id": clean_text(event.get("id"), 80) or f"event-{uuid4().hex[:8]}",
            "title": clean_text(event.get("title"), 140),
            "startsAt": clean_text(event.get("startsAt"), 80),
            "duration": clean_text(event.get("duration"), 40),
            "setup": clean_text(event.get("setup"), 80),
            "type": clean_text(event.get("type"), 80),
            "link": clean_text(event.get("link"), 400),
            "copy": clean_text(event.get("copy"), 500),
        })
    return {
        "announcement": vip.get("announcement") if isinstance(vip.get("announcement"), dict) else default_site_config()["vip"]["announcement"],
        "events": clean_events,
        "resources": [item for item in resources[:20] if isinstance(item, dict)],
        "rooms": [clean_text(room, 40) for room in rooms if clean_text(room, 40)][:12],
        "messages": [
            message for message in load_vip_messages()
            if isinstance(message, dict) and message.get("status") != "deleted"
        ][:120],
    }


def load_analytics() -> dict[str, Any]:
    payload = load_state("analytics", ANALYTICS_FILE, {"sessions": {}, "events": []}, dict)
    if not isinstance(payload, dict):
        return {"sessions": {}, "events": []}
    sessions = payload.get("sessions") if isinstance(payload.get("sessions"), dict) else {}
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    return {"sessions": sessions, "events": events}


def save_analytics(payload: dict[str, Any]) -> None:
    sessions = payload.get("sessions") if isinstance(payload.get("sessions"), dict) else {}
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    save_state("analytics", ANALYTICS_FILE, {"sessions": sessions, "events": events[:2500]})


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 120_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected = encoded.split("$", 3)
        iterations = int(iterations_text)
    except (ValueError, AttributeError):
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), iterations).hex()
    return hmac.compare_digest(digest, expected)


def normalize_referral_code(value: Any) -> str:
    text = clean_text(value, 40).upper()
    return "".join(char for char in text if char.isalnum())[:18]


def make_referral_code(name: str, tradingview: str, requests: list[dict[str, Any]]) -> str:
    seed = normalize_referral_code(tradingview or name)[:8] or "TRADING"
    existing = {normalize_referral_code(item.get("referralCode")) for item in requests}
    candidate = f"TI{seed}"
    if candidate not in existing:
        return candidate
    for index in range(2, 1000):
        candidate = f"TI{seed}{index}"
        if candidate not in existing:
            return candidate
    return f"TI{uuid4().hex[:10].upper()}"


def referral_summary(requests: list[dict[str, Any]], item: dict[str, Any]) -> dict[str, Any]:
    code = normalize_referral_code(item.get("referralCode"))
    approved = [
        child for child in requests
        if normalize_referral_code(child.get("usedReferralCode")) == code and child.get("status") == "approved"
    ]
    pending = [
        child for child in requests
        if normalize_referral_code(child.get("usedReferralCode")) == code and child.get("status") == "pending"
    ]
    count = len(approved)
    if count >= 10:
        reward = "1 mois gratuit"
        next_target = 10
        remaining = 0
    elif count >= 5:
        reward = "Bot a -50%"
        next_target = 10
        remaining = 10 - count
    else:
        reward = "Aucun palier atteint"
        next_target = 5
        remaining = 5 - count
    return {
        "code": code,
        "approvedCount": count,
        "pendingCount": len(pending),
        "nextTarget": next_target,
        "remaining": remaining,
        "reward": reward,
        "rules": [
            {"target": 5, "reward": "Bot a -50%"},
            {"target": 10, "reward": "1 mois gratuit"},
        ],
    }


def default_subscription_end() -> str:
    return (now_paris() + timedelta(days=30)).replace(microsecond=0).isoformat()


def normalize_subscription_end(value: Any) -> str:
    text = clean_text(value, 60)
    if not text:
        return ""
    try:
        if len(text) == 10:
            parsed = datetime.fromisoformat(text).replace(hour=23, minute=59, second=59, tzinfo=PARIS)
        else:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=PARIS)
            parsed = parsed.astimezone(PARIS)
        return parsed.replace(microsecond=0).isoformat()
    except ValueError:
        return ""


def days_remaining(subscription_end: str) -> int:
    parsed = parse_provider_date(subscription_end)
    if not parsed:
        return 0
    delta = parsed - now_paris()
    return max(0, int(delta.total_seconds() // 86400))


def extend_subscription(item: dict[str, Any], event: dict[str, Any], transaction_id: str) -> None:
    current_end = parse_provider_date(item.get("subscriptionEnd"))
    start_from = current_end if current_end and current_end > now_paris() else now_paris()
    new_end = (start_from + timedelta(days=30)).replace(microsecond=0)
    now = now_paris().isoformat()
    item["status"] = "approved"
    item["subscriptionStart"] = item.get("subscriptionStart") or now
    item["subscriptionEnd"] = new_end.isoformat()
    item["lastPaymentAt"] = now
    item["lastPayPalEventId"] = clean_text(event.get("id"), 120)
    item["lastPayPalTransactionId"] = clean_text(transaction_id, 120)
    item["updated_at"] = now
    history = item.get("paymentHistory")
    if not isinstance(history, list):
        history = []
    history.insert(0, {
        "at": now,
        "eventId": clean_text(event.get("id"), 120),
        "transactionId": clean_text(transaction_id, 120),
        "source": "paypal_webhook",
    })
    item["paymentHistory"] = history[:24]


def paypal_url_for_product(product: str) -> str:
    text = clean_text(product, 240).lower()
    if "+" in text or "par setup" in text or "setups" in text:
        return "#offers"
    if "nasdaq" in text:
        return PAYPAL_PAYMENT_URLS["nasdaq"]
    if "btc" in text:
        return PAYPAL_PAYMENT_URLS["btc"]
    if "gold" in text:
        return PAYPAL_PAYMENT_URLS["gold"]
    return PAYPAL_PAYMENT_URL


def normalize_products(data: dict[str, Any]) -> list[str]:
    raw_products = data.get("products")
    values: list[str] = []
    if isinstance(raw_products, list):
        values.extend(clean_text(item, 180) for item in raw_products)
    elif isinstance(raw_products, str):
        values.append(clean_text(raw_products, 320))
    values.append(clean_text(data.get("product"), 320))
    haystack = " ".join(values).lower()
    selected = [label for key, label in PRODUCT_LABELS.items() if key in haystack]
    if selected:
        return selected[:3]
    fallback = clean_text(data.get("product"), 320)
    return [fallback] if fallback else []


def product_summary(products: list[str]) -> str:
    if not products:
        return "Institutional Trading Setup - 49,99 EUR / mois"
    if len(products) == 1:
        return products[0]
    names = []
    for product in products:
        text = product.lower()
        if "btc" in text:
            names.append("BTC")
        elif "gold" in text:
            names.append("Gold")
        elif "nasdaq" in text:
            names.append("Nasdaq")
    if names:
        return f"{' + '.join(names)} Institutional Setups - 49,99 EUR / mois par setup"
    return clean_text(" + ".join(products), 320)


def public_client_payload(item: dict[str, Any]) -> dict[str, Any]:
    subscription_end = str(item.get("subscriptionEnd") or "")
    requests = load_access_requests()
    product = item.get("product", "Institutional Trading Setup - 49,99 EUR / mois")
    products = item.get("products") if isinstance(item.get("products"), list) else normalize_products({"product": product})
    return {
        "id": item.get("id"),
        "status": item.get("status", "pending"),
        "name": item.get("name", ""),
        "email": item.get("email", ""),
        "tradingview": item.get("tradingview", ""),
        "product": product,
        "products": products,
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
        "subscriptionStart": item.get("subscriptionStart", ""),
        "subscriptionEnd": subscription_end,
        "daysRemaining": days_remaining(subscription_end),
        "paypalUrl": paypal_url_for_product(product),
        "donationUrl": DONATION_URL,
        "referral": referral_summary(requests, item),
        "setups": [
            {"name": "BTC Institutional Setup", "market": "BTC", "session": "24/7", "wr": "85.3%", "pf": "2.98"},
            {"name": "Gold Institutional Setup", "market": "Gold", "session": "London / New York / Asia", "wr": "83.0%", "pf": "2.70"},
            {"name": "Nasdaq Institutional Setup", "market": "US100", "session": "London / New York / Asia", "wr": "81.3%", "pf": "3.40"},
        ],
    }


def client_session_key(item: dict[str, Any]) -> str:
    email = clean_text(item.get("email"), 180).lower()
    if email:
        return email
    return clean_text(item.get("id"), 120) or f"client-{uuid4().hex[:8]}"


def product_count_for_item(item: dict[str, Any]) -> int:
    products = item.get("products") if isinstance(item.get("products"), list) else normalize_products(item)
    if products:
        return max(1, min(3, len(products)))
    text = clean_text(item.get("product"), 320).lower()
    markets = [name for name in ("btc", "gold", "nasdaq") if name in text]
    return max(1, len(markets))


def client_remaining_minutes(subscription_end: Any) -> int:
    parsed = parse_provider_date(subscription_end)
    if not parsed:
        return 0
    return max(0, int((parsed - now_paris()).total_seconds() // 60))


def record_client_session(item: dict[str, Any], source: str = "login") -> dict[str, Any]:
    now = now_paris()
    payload = public_client_payload(item)
    session = {
        "id": clean_text(item.get("id"), 120),
        "name": clean_text(item.get("name"), 120),
        "email": clean_text(item.get("email"), 180),
        "tradingview": clean_text(item.get("tradingview"), 120),
        "status": clean_text(item.get("status"), 40),
        "product": clean_text(item.get("product"), 320),
        "products": item.get("products") if isinstance(item.get("products"), list) else payload.get("products", []),
        "subscriptionEnd": clean_text(item.get("subscriptionEnd"), 80),
        "daysRemaining": payload.get("daysRemaining", 0),
        "lastSeen": now.isoformat(),
        "source": clean_text(source, 40) or "login",
    }
    sessions = load_client_sessions()
    sessions[client_session_key(item)] = session
    cutoff = now - timedelta(days=30)
    sessions = {
        key: value for key, value in sessions.items()
        if isinstance(value, dict) and (parse_provider_date(value.get("lastSeen")) or now) >= cutoff
    }
    save_client_sessions(sessions)
    return session


def admin_client_overview() -> dict[str, Any]:
    requests = load_access_requests()
    sessions = load_client_sessions()
    now = now_paris()
    online_cutoff = now - timedelta(minutes=3)
    clients: list[dict[str, Any]] = []
    for item in requests:
        if not isinstance(item, dict):
            continue
        payload = public_client_payload(item)
        key = client_session_key(item)
        session = sessions.get(key) if isinstance(sessions.get(key), dict) else {}
        last_seen = clean_text(session.get("lastSeen"), 80)
        last_seen_dt = parse_provider_date(last_seen)
        subscription_end = clean_text(item.get("subscriptionEnd"), 80)
        remaining_minutes = client_remaining_minutes(subscription_end)
        online = bool(last_seen_dt and last_seen_dt >= online_cutoff)
        status = clean_text(item.get("status"), 40) or "pending"
        clients.append({
            "id": clean_text(item.get("id"), 120),
            "created_at": clean_text(item.get("created_at"), 80),
            "updated_at": clean_text(item.get("updated_at"), 80),
            "status": status,
            "name": clean_text(item.get("name"), 120),
            "email": clean_text(item.get("email"), 180),
            "tradingview": clean_text(item.get("tradingview"), 120),
            "product": clean_text(item.get("product"), 320),
            "products": item.get("products") if isinstance(item.get("products"), list) else payload.get("products", []),
            "subscriptionStart": clean_text(item.get("subscriptionStart"), 80),
            "subscriptionEnd": subscription_end,
            "daysRemaining": payload.get("daysRemaining", 0),
            "minutesRemaining": remaining_minutes,
            "online": online,
            "lastSeen": last_seen,
            "lastSeenSource": clean_text(session.get("source"), 40),
            "productCount": product_count_for_item(item),
        })
    clients.sort(key=lambda item: (
        0 if item.get("online") else 1,
        0 if item.get("status") == "approved" and item.get("minutesRemaining", 0) > 0 else 1,
        item.get("daysRemaining", 0),
        item.get("name", ""),
    ))
    approved_active = [item for item in clients if item.get("status") == "approved" and item.get("minutesRemaining", 0) > 0]
    expiring = [item for item in approved_active if item.get("daysRemaining", 0) <= 7]
    expired = [item for item in clients if item.get("status") == "approved" and item.get("minutesRemaining", 0) <= 0]
    return {
        "ok": True,
        "clients": clients,
        "metrics": {
            "total": len(clients),
            "online": sum(1 for item in clients if item.get("online")),
            "active": len(approved_active),
            "pending": sum(1 for item in clients if item.get("status") == "pending"),
            "expiring": len(expiring),
            "expired": len(expired),
        },
        "updated_at": now.isoformat(),
    }


def create_access_request(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    required = {
        "name": clean_text(data.get("name"), 120),
        "email": clean_text(data.get("email"), 180),
        "tradingview": clean_text(data.get("tradingview"), 120),
        "paymentProof": clean_text(data.get("paymentProof"), 400),
        "clientPassword": clean_text(data.get("clientPassword"), 200),
    }
    missing = [label for label, value in required.items() if not value]
    if missing:
        return False, {"ok": False, "error": "missing_fields", "fields": missing}
    if len(required["clientPassword"]) < 6:
        return False, {"ok": False, "error": "password_too_short"}

    products = normalize_products(data)
    now = now_paris().isoformat()
    item = {
        "id": f"req-{now_paris():%Y%m%d%H%M%S}-{uuid4().hex[:8]}",
        "created_at": now,
        "updated_at": now,
        "status": "pending",
        "name": required["name"],
        "email": required["email"],
        "tradingview": required["tradingview"],
        "paymentProof": required["paymentProof"],
        "paymentProofImage": clean_image_data(data.get("paymentProofImage")),
        "passwordHash": hash_password(required["clientPassword"]),
        "product": product_summary(products),
        "products": products,
        "message": clean_text(data.get("message"), 1200),
        "adminNote": "",
        "subscriptionStart": "",
        "subscriptionEnd": "",
    }
    with ACCESS_REQUESTS_LOCK:
        requests = load_access_requests()
        used_referral = normalize_referral_code(data.get("referralCode"))
        item["referralCode"] = make_referral_code(required["name"], required["tradingview"], requests)
        item["usedReferralCode"] = used_referral
        item["referrerId"] = ""
        if used_referral:
            for referrer in requests:
                if normalize_referral_code(referrer.get("referralCode")) == used_referral:
                    item["referrerId"] = clean_text(referrer.get("id"), 120)
                    break
        requests.insert(0, item)
        save_access_requests(requests)
    return True, {"ok": True, "request": item}


def create_admin_access_request(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    payload = dict(data)
    payload["name"] = clean_text(payload.get("name"), 120) or "Client"
    payload["email"] = clean_text(payload.get("email"), 180)
    payload["tradingview"] = clean_text(payload.get("tradingview"), 120)
    payload["paymentProof"] = clean_text(payload.get("paymentProof"), 400) or clean_text(payload.get("transactionId"), 180) or "Ajout manuel admin"
    payload["clientPassword"] = clean_text(payload.get("clientPassword"), 200) or secrets.token_urlsafe(9)
    ok, result = create_access_request(payload)
    if not ok:
        return ok, result

    request_id = result.get("request", {}).get("id")
    status = clean_text(data.get("status"), 40) or "pending"
    if status not in {"pending", "approved", "rejected"}:
        status = "pending"
    admin_note = clean_text(data.get("adminNote"), 800)
    months = clean_text(data.get("months"), 10)
    days = 30
    try:
        days = max(1, min(365, int(float(months) * 30)))
    except (TypeError, ValueError):
        days = 30
    subscription_end = (now_paris() + timedelta(days=days)).replace(microsecond=0).isoformat()
    updated, payload_result = update_access_request_status({
        "id": request_id,
        "status": status,
        "adminNote": admin_note or "Ajout manuel admin. Envoyer le mot de passe client separement.",
        "subscriptionEnd": subscription_end,
    })
    if not updated:
        return True, result
    payload_result["clientPassword"] = payload["clientPassword"]
    return True, payload_result


def create_donation(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    return False, {"ok": False, "error": "payment_required", "donationUrl": DONATION_URL}


def update_site_config(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    config = load_site_config()
    flash = config.get("flash") if isinstance(config.get("flash"), dict) else default_site_config()["flash"]
    flash["active"] = bool(data.get("active"))
    flash["title"] = clean_text(data.get("title"), 90)
    flash["copy"] = clean_text(data.get("copy"), 180)
    flash["cta"] = clean_text(data.get("cta"), 40) or "Profiter de l'offre"
    flash["url"] = clean_text(data.get("url"), 400) or "#offers"
    flash["endsAt"] = clean_text(data.get("endsAt"), 80)
    if not flash["active"]:
        flash["title"] = ""
        flash["copy"] = ""
        flash["endsAt"] = ""
    config["flash"] = flash
    save_site_config(config)
    return True, {"ok": True, "config": config}


def update_vip_config(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    config = load_site_config()
    vip = config.get("vip") if isinstance(config.get("vip"), dict) else default_site_config()["vip"]
    action = clean_text(data.get("action"), 40) or "announcement"
    if action == "announcement":
        announcement = vip.get("announcement") if isinstance(vip.get("announcement"), dict) else default_site_config()["vip"]["announcement"]
        announcement["active"] = bool(data.get("active", True))
        announcement["title"] = clean_text(data.get("title"), 140) or announcement.get("title", "")
        announcement["copy"] = clean_text(data.get("copy"), 500) or announcement.get("copy", "")
        announcement["cta"] = clean_text(data.get("cta"), 60) or "Voir"
        announcement["url"] = clean_text(data.get("url"), 400) or "#vip-calendar"
        vip["announcement"] = announcement
    elif action == "event":
        events = vip.get("events") if isinstance(vip.get("events"), list) else []
        event_id = clean_text(data.get("id"), 80) or f"live-{now_paris():%Y%m%d%H%M%S}-{uuid4().hex[:6]}"
        event = {
            "id": event_id,
            "title": clean_text(data.get("title"), 140) or "Live formation VIP",
            "startsAt": clean_text(data.get("startsAt"), 80),
            "duration": clean_text(data.get("duration"), 40) or "60 min",
            "setup": clean_text(data.get("setup"), 80) or "Gold / BTC / Nasdaq",
            "type": clean_text(data.get("type"), 80) or "Formation live",
            "link": clean_text(data.get("link"), 400),
            "copy": clean_text(data.get("copy"), 500),
            "created_at": now_paris().isoformat(),
        }
        events = [item for item in events if not (isinstance(item, dict) and clean_text(item.get("id"), 80) == event_id)]
        vip["events"] = [event] + events
    elif action == "delete_event":
        event_id = clean_text(data.get("id"), 80)
        events = vip.get("events") if isinstance(vip.get("events"), list) else []
        vip["events"] = [item for item in events if not (isinstance(item, dict) and clean_text(item.get("id"), 80) == event_id)]
    elif action == "resource":
        resources = vip.get("resources") if isinstance(vip.get("resources"), list) else []
        resource = {
            "title": clean_text(data.get("title"), 120) or "Ressource VIP",
            "tag": clean_text(data.get("tag"), 40) or "VIP",
            "copy": clean_text(data.get("copy"), 500),
            "url": clean_text(data.get("url"), 400),
        }
        vip["resources"] = [resource] + resources[:19]
    else:
        return False, {"ok": False, "error": "invalid_action"}
    config["vip"] = vip
    save_site_config(config)
    return True, {"ok": True, "vip": public_vip_payload()}


def track_visit(data: dict[str, Any], headers: Any, client_ip: str) -> dict[str, Any]:
    session_id = clean_text(data.get("sessionId"), 80) or f"s-{uuid4().hex}"
    page = clean_text(data.get("page"), 180) or "/"
    now = now_paris()
    now_iso = now.isoformat()
    analytics = load_analytics()
    sessions = analytics["sessions"]
    current = sessions.get(session_id) if isinstance(sessions.get(session_id), dict) else {}
    sessions[session_id] = {
        "id": session_id,
        "firstSeen": current.get("firstSeen") or now_iso,
        "lastSeen": now_iso,
        "page": page,
        "ip": client_ip,
        "userAgent": clean_text(headers.get("User-Agent", ""), 240),
    }
    analytics["events"].insert(0, {"at": now_iso, "sessionId": session_id, "page": page})
    cutoff = now - timedelta(days=14)
    analytics["events"] = [
        event for event in analytics["events"][:2500]
        if (parse_provider_date(event.get("at")) or now) >= cutoff
    ]
    save_analytics(analytics)
    return {"ok": True, "sessionId": session_id}


def analytics_summary() -> dict[str, Any]:
    analytics = load_analytics()
    now = now_paris()
    online_cutoff = now - timedelta(minutes=5)
    today_key = now.strftime("%Y-%m-%d")
    sessions = list(analytics["sessions"].values())
    online = [
        item for item in sessions
        if (parse_provider_date(item.get("lastSeen")) or datetime.fromtimestamp(0, PARIS)) >= online_cutoff
    ]
    events_today = [
        item for item in analytics["events"]
        if (parse_provider_date(item.get("at")) or now).strftime("%Y-%m-%d") == today_key
    ]
    pages: dict[str, int] = {}
    for event in events_today:
        page = clean_text(event.get("page"), 180) or "/"
        pages[page] = pages.get(page, 0) + 1
    top_pages = [{"page": page, "views": views} for page, views in sorted(pages.items(), key=lambda item: item[1], reverse=True)[:8]]
    return {
        "ok": True,
        "online": len(online),
        "visitorsToday": len({clean_text(item.get("sessionId"), 80) for item in events_today}),
        "pageViewsToday": len(events_today),
        "totalVisitors": len(sessions),
        "topPages": top_pages,
        "onlineSessions": sorted(online, key=lambda item: item.get("lastSeen", ""), reverse=True)[:20],
        "updated_at": now.isoformat(),
    }


def update_donation_status(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    donation_id = clean_text(data.get("id"), 80)
    status = clean_text(data.get("status"), 40) or "pending"
    if status not in {"pending", "confirmed", "rejected"}:
        return False, {"ok": False, "error": "invalid_status"}
    with ACCESS_REQUESTS_LOCK:
        donations = load_donations()
        for item in donations:
            if item.get("id") == donation_id:
                item["status"] = status
                item["adminNote"] = clean_text(data.get("adminNote"), 800)
                item["updated_at"] = now_paris().isoformat()
                save_donations(donations)
                return True, {"ok": True, "donation": item}
    return False, {"ok": False, "error": "not_found"}


def update_access_request_status(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    request_id = clean_text(data.get("id"), 80)
    status = clean_text(data.get("status"), 40) or "pending"
    if status not in {"pending", "approved", "rejected"}:
        return False, {"ok": False, "error": "invalid_status"}
    with ACCESS_REQUESTS_LOCK:
        requests = load_access_requests()
        for item in requests:
            if item.get("id") == request_id:
                subscription_end = normalize_subscription_end(data.get("subscriptionEnd"))
                item["status"] = status
                item["adminNote"] = clean_text(data.get("adminNote"), 800)
                if subscription_end:
                    item["subscriptionEnd"] = subscription_end
                elif status == "approved" and not item.get("subscriptionEnd"):
                    item["subscriptionEnd"] = default_subscription_end()
                if status == "approved" and not item.get("subscriptionStart"):
                    item["subscriptionStart"] = now_paris().isoformat()
                item["updated_at"] = now_paris().isoformat()
                save_access_requests(requests)
                return True, {"ok": True, "request": item}
    return False, {"ok": False, "error": "not_found"}


def find_client_for_login(data: dict[str, Any]) -> dict[str, Any] | None:
    email = clean_text(data.get("email"), 180).lower()
    password = clean_text(data.get("password"), 200)
    tradingview = clean_text(data.get("tradingview"), 120).lower()
    if not email or not (password or tradingview):
        return None

    requests = load_access_requests()
    for item in requests:
        if clean_text(item.get("email"), 180).lower() != email:
            continue
        stored_password = clean_text(item.get("passwordHash"), 500)
        if stored_password:
            if verify_password(password, stored_password):
                return item
        elif tradingview and clean_text(item.get("tradingview"), 120).lower() == tradingview:
            return item
    return None


def client_login(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    if not clean_text(data.get("email"), 180) or not (clean_text(data.get("password"), 200) or clean_text(data.get("tradingview"), 120)):
        return False, {"ok": False, "error": "missing_fields"}
    item = find_client_for_login(data)
    if item:
        session = record_client_session(item, "login")
        return True, {"ok": True, "client": public_client_payload(item), "vip": public_vip_payload(), "session": session}
    return False, {"ok": False, "error": "not_found"}


def client_ping(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    item = find_client_for_login(data)
    if not item:
        return False, {"ok": False, "error": "unauthorized"}
    session = record_client_session(item, "heartbeat")
    return True, {"ok": True, "client": public_client_payload(item), "vip": public_vip_payload(), "session": session}


def create_vip_message(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    item = find_client_for_login(data)
    if not item:
        return False, {"ok": False, "error": "unauthorized"}
    if item.get("status") != "approved":
        return False, {"ok": False, "error": "not_approved"}
    if client_remaining_minutes(item.get("subscriptionEnd")) <= 0:
        return False, {"ok": False, "error": "subscription_expired"}
    message = clean_text(data.get("message"), 1000)
    if not message:
        return False, {"ok": False, "error": "missing_message"}
    allowed_rooms = set(public_vip_payload().get("rooms", [])) or {"general"}
    room = clean_text(data.get("room"), 40).lower() or "general"
    if room not in allowed_rooms:
        room = "general"
    payload = {
        "id": f"vip-{now_paris():%Y%m%d%H%M%S}-{uuid4().hex[:8]}",
        "created_at": now_paris().isoformat(),
        "status": "open",
        "room": room,
        "sender": "client",
        "kind": "chat",
        "priority": False,
        "market": "",
        "grade": "",
        "title": "",
        "name": clean_text(item.get("name"), 80) or "VIP",
        "email": clean_text(item.get("email"), 180),
        "products": item.get("products") if isinstance(item.get("products"), list) else normalize_products(item),
        "message": message,
    }
    with ACCESS_REQUESTS_LOCK:
        messages = load_vip_messages()
        messages.insert(0, payload)
        save_vip_messages(messages)
    record_client_session(item, "message")
    return True, {"ok": True, "message": payload, "vip": public_vip_payload()}


def create_admin_vip_message(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    message = clean_text(data.get("message"), 1000)
    if not message:
        return False, {"ok": False, "error": "missing_message"}
    allowed_rooms = set(public_vip_payload().get("rooms", [])) or {"general"}
    room = clean_text(data.get("room"), 40).lower() or "general"
    if room not in allowed_rooms:
        room = "general"
    kind = clean_text(data.get("kind"), 30) or "announcement"
    if kind not in {"announcement", "setup", "note", "chat"}:
        kind = "announcement"
    pinned = bool(data.get("pinned"))
    payload = {
        "id": f"vip-{now_paris():%Y%m%d%H%M%S}-{uuid4().hex[:8]}",
        "created_at": now_paris().isoformat(),
        "status": "pinned" if pinned else "open",
        "room": room,
        "sender": "admin",
        "kind": kind,
        "priority": bool(data.get("priority")),
        "market": clean_text(data.get("market"), 40),
        "grade": clean_text(data.get("grade"), 20),
        "title": clean_text(data.get("title"), 120),
        "name": "Admin",
        "email": "",
        "products": ["Admin"],
        "message": message,
    }
    with ACCESS_REQUESTS_LOCK:
        messages = load_vip_messages()
        messages.insert(0, payload)
        save_vip_messages(messages)
    return True, {"ok": True, "message": payload, "vip": public_vip_payload()}


def update_vip_message_status(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    message_id = clean_text(data.get("id"), 100)
    status = clean_text(data.get("status"), 30) or "open"
    if status not in {"open", "pinned", "deleted"}:
        return False, {"ok": False, "error": "invalid_status"}
    changed = 0
    with ACCESS_REQUESTS_LOCK:
        messages = load_vip_messages()
        for message in messages:
            if clean_text(message.get("id"), 100) == message_id:
                message["status"] = status
                message["updated_at"] = now_paris().isoformat()
                changed += 1
        if not changed:
            return False, {"ok": False, "error": "not_found"}
        save_vip_messages(messages)
    return True, {"ok": True, "vip": public_vip_payload()}


def deep_find_email(value: Any) -> str:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in {"email", "email_address", "payer_email"}:
                text = clean_text(child, 180)
                if "@" in text:
                    return text
        for child in value.values():
            found = deep_find_email(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = deep_find_email(child)
            if found:
                return found
    return ""


def deep_find_amount(value: Any) -> tuple[str, float | None]:
    if isinstance(value, dict):
        currency = clean_text(value.get("currency_code") or value.get("currency"), 12).upper()
        raw_amount = value.get("value") or value.get("amount")
        if currency and raw_amount is not None:
            try:
                return currency, float(str(raw_amount).replace(",", "."))
            except ValueError:
                pass
        for child in value.values():
            found_currency, found_amount = deep_find_amount(child)
            if found_currency or found_amount is not None:
                return found_currency, found_amount
    if isinstance(value, list):
        for child in value:
            found_currency, found_amount = deep_find_amount(child)
            if found_currency or found_amount is not None:
                return found_currency, found_amount
    return "", None


def paypal_transaction_id(event: dict[str, Any]) -> str:
    resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
    candidates = [
        resource.get("id"),
        resource.get("sale_id"),
        resource.get("capture_id"),
        event.get("resource_id"),
        event.get("id"),
    ]
    for value in candidates:
        text = clean_text(value, 120)
        if text:
            return text
    return ""


def paypal_event_allowed(event_type: str, currency: str, amount: float | None) -> tuple[bool, str]:
    paid_events = {
        "PAYMENT.CAPTURE.COMPLETED",
        "PAYMENT.SALE.COMPLETED",
        "CHECKOUT.ORDER.COMPLETED",
        "BILLING.SUBSCRIPTION.PAYMENT.SUCCEEDED",
    }
    if event_type not in paid_events:
        return False, "event_not_payment_success"
    if currency and currency != "EUR":
        return False, "currency_not_eur"
    if amount is not None and amount <= 0:
        return False, "invalid_amount"
    return True, "ok"


def collect_paypal_text(value: Any) -> str:
    parts: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            if isinstance(child, (dict, list)):
                nested = collect_paypal_text(child)
                if nested:
                    parts.append(nested)
            elif isinstance(child, (str, int, float)):
                text = clean_text(child, 220)
                if text:
                    parts.append(text)
    elif isinstance(value, list):
        for child in value:
            nested = collect_paypal_text(child)
            if nested:
                parts.append(nested)
    return " ".join(parts)[:3000]


def paypal_payment_is_donation(event: dict[str, Any], amount: float | None) -> bool:
    text = collect_paypal_text(event).lower()
    markers = ("donation", "contribution", "soutien", "support_app", "site_support_app", "tip")
    return any(marker in text for marker in markers) or (amount is not None and amount + 0.01 < PAYPAL_PRICE_EUR)


def record_paypal_donation(
    donations: list[dict[str, Any]],
    event: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    transaction_id = clean_text(result.get("transaction_id"), 120)
    event_id = clean_text(result.get("id"), 120)
    for item in donations:
        if transaction_id and clean_text(item.get("transaction_id"), 120) == transaction_id:
            return item
        if event_id and clean_text(item.get("paypalEventId"), 120) == event_id:
            return item
    payer_email = clean_text(result.get("payer_email"), 180)
    amount = result.get("amount")
    now = now_paris().isoformat()
    item = {
        "id": f"don-{now_paris():%Y%m%d%H%M%S}-{uuid4().hex[:8]}",
        "created_at": now,
        "updated_at": now,
        "status": "confirmed",
        "name": payer_email.split("@")[0] if payer_email else "PayPal",
        "email": payer_email,
        "amount": round(float(amount or 0), 2),
        "currency": clean_text(result.get("currency"), 12) or "EUR",
        "message": "Don confirme par PayPal",
        "transaction_id": transaction_id,
        "paypalEventId": event_id,
        "event_type": clean_text(result.get("event_type"), 120),
        "verified": bool(result.get("verified")),
        "verification_status": clean_text(result.get("verification_status"), 80),
        "source": "paypal_webhook",
    }
    donations.insert(0, item)
    return item


def paypal_oauth_token() -> str:
    token = base64.b64encode(f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}".encode("utf-8")).decode("ascii")
    body = b"grant_type=client_credentials"
    request = Request(
        f"{PAYPAL_API_BASE}/v1/oauth2/token",
        data=body,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return clean_text(payload.get("access_token"), 500)


def verify_paypal_webhook(headers: Any, event: dict[str, Any]) -> tuple[bool, str]:
    if PAYPAL_ALLOW_UNVERIFIED:
        return True, "local_unverified_allowed"
    if not (PAYPAL_WEBHOOK_ID and PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET):
        return False, "verification_not_configured"
    token = paypal_oauth_token()
    verify_payload = {
        "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID", ""),
        "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME", ""),
        "cert_url": headers.get("PAYPAL-CERT-URL", ""),
        "auth_algo": headers.get("PAYPAL-AUTH-ALGO", ""),
        "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG", ""),
        "webhook_id": PAYPAL_WEBHOOK_ID,
        "webhook_event": event,
    }
    request = Request(
        f"{PAYPAL_API_BASE}/v1/notifications/verify-webhook-signature",
        data=json.dumps(verify_payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("verification_status") == "SUCCESS", clean_text(payload.get("verification_status"), 80)


def process_paypal_webhook(event: dict[str, Any], headers: Any) -> dict[str, Any]:
    event_id = clean_text(event.get("id"), 120)
    event_type = clean_text(event.get("event_type"), 120)
    resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
    payer_email = deep_find_email(resource or event).lower()
    currency, amount = deep_find_amount(resource or event)
    transaction_id = paypal_transaction_id(event)
    verified, verification_status = verify_paypal_webhook(headers, event)
    allowed, allow_reason = paypal_event_allowed(event_type, currency, amount)
    result = {
        "id": event_id or f"paypal-{now_paris():%Y%m%d%H%M%S}-{uuid4().hex[:8]}",
        "received_at": now_paris().isoformat(),
        "event_type": event_type,
        "transaction_id": transaction_id,
        "payer_email": payer_email,
        "currency": currency,
        "amount": amount,
        "verified": verified,
        "verification_status": verification_status,
        "matched_request_id": "",
        "matched_donation_id": "",
        "action": "logged",
        "reason": allow_reason,
    }

    with ACCESS_REQUESTS_LOCK:
        paypal_events = load_paypal_events()
        known_ids = {clean_text(item.get("id"), 120) for item in paypal_events}
        if result["id"] in known_ids:
            result["action"] = "duplicate_ignored"
            paypal_events.insert(0, result)
            save_paypal_events(paypal_events)
            return result

        if verified and allowed:
            requests = load_access_requests()
            is_donation = paypal_payment_is_donation(event, amount)
            if payer_email and not is_donation and (amount is None or amount + 0.01 >= PAYPAL_PRICE_EUR):
                for item in requests:
                    if clean_text(item.get("email"), 180).lower() == payer_email:
                        extend_subscription(item, event, transaction_id)
                        result["matched_request_id"] = clean_text(item.get("id"), 120)
                        result["action"] = "subscription_extended"
                        result["reason"] = "matched_by_paypal_email"
                        save_access_requests(requests)
                        break
            if not result["matched_request_id"]:
                if is_donation:
                    donations = load_donations()
                    donation = record_paypal_donation(donations, event, result)
                    save_donations(donations)
                    result["matched_donation_id"] = clean_text(donation.get("id"), 120)
                    result["action"] = "donation_recorded"
                    result["reason"] = "donation_payment"
                else:
                    result["action"] = "unmatched_payment"
                    result["reason"] = "paypal_email_not_found"
        elif not verified:
            result["reason"] = verification_status

        paypal_events.insert(0, result)
        save_paypal_events(paypal_events)
    return result


class InstitutionalTradingHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Password")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Password")
        self.end_headers()

    def is_admin(self) -> bool:
        password = self.headers.get("X-Admin-Password", "")
        return any(hmac.compare_digest(password, allowed) for allowed in ADMIN_PASSWORDS)

    def read_json_body(self) -> dict[str, Any]:
        raw = self.read_body_text()
        if not raw:
            return {}
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}

    def read_body_text(self) -> str:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 6_000_000:
            return ""
        return self.rfile.read(length).decode("utf-8")

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        if path in {"/ops", "/ops/"}:
            self.path = "/admin.html"
            super().do_GET()
            return
        if path == "/admin.html":
            owner_key = parse_qs(parsed_url.query).get("owner", [""])[0]
            if not any(hmac.compare_digest(owner_key, allowed) for allowed in ADMIN_ACCESS_KEYS):
                self.send_error(404)
                return
        if path == "/api/health":
            self.send_json({"ok": True, "updated_at": now_paris().isoformat()})
            return
        if path == "/api/calendar":
            self.send_json(calendar_payload())
            return
        if path == "/api/admin/access-requests":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            self.send_json({"ok": True, "requests": load_access_requests(), "updated_at": now_paris().isoformat()})
            return
        if path == "/api/admin/paypal-events":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            self.send_json({"ok": True, "events": load_paypal_events(), "updated_at": now_paris().isoformat()})
            return
        if path == "/api/admin/donations":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            donations = load_donations()
            total_confirmed = sum(float(item.get("amount") or 0) for item in donations if item.get("status") == "confirmed")
            self.send_json({"ok": True, "donations": donations, "totalConfirmed": round(total_confirmed, 2), "updated_at": now_paris().isoformat()})
            return
        if path == "/api/admin/analytics":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            self.send_json(analytics_summary())
            return
        if path == "/api/admin/site-config":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            self.send_json({"ok": True, "config": load_site_config(), "updated_at": now_paris().isoformat()})
            return
        if path == "/api/admin/chat":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            self.send_json({"ok": True, "messages": load_chat_messages(), "updated_at": now_paris().isoformat()})
            return
        if path == "/api/admin/vip":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            self.send_json({"ok": True, "vip": public_vip_payload(), "updated_at": now_paris().isoformat()})
            return
        if path == "/api/admin/client-overview":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            self.send_json(admin_client_overview())
            return
        if path == "/api/chat/thread":
            email = clean_text(parse_qs(parsed_url.query).get("email", [""])[0], 180).lower()
            messages = [
                item for item in load_chat_messages()
                if clean_text(item.get("email"), 180).lower() == email and item.get("status") != "deleted"
            ] if email else []
            self.send_json({"ok": True, "messages": list(reversed(messages[-60:]))})
            return
        if path == "/api/public-config":
            self.send_json({"ok": True, "paypalUrl": PAYPAL_PAYMENT_URL, "donationUrl": DONATION_URL, "donationEmail": DONATION_EMAIL, "flash": public_flash_payload()})
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/paypal/webhook":
            try:
                raw = self.read_body_text()
                event = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self.send_json({"ok": False, "error": "invalid_json"}, 400)
                return
            if not isinstance(event, dict):
                self.send_json({"ok": False, "error": "invalid_payload"}, 400)
                return
            try:
                result = process_paypal_webhook(event, self.headers)
            except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
                result = {"action": "verification_error", "reason": error.__class__.__name__}
            self.send_json({"ok": True, "result": result}, 202)
            return
        try:
            data = self.read_json_body()
        except json.JSONDecodeError:
            self.send_json({"ok": False, "error": "invalid_json"}, 400)
            return
        if path == "/api/access-requests":
            ok, payload = create_access_request(data)
            self.send_json(payload, 201 if ok else 400)
            return
        if path == "/api/donations":
            ok, payload = create_donation(data)
            self.send_json(payload, 201 if ok else 400)
            return
        if path == "/api/track":
            self.send_json(track_visit(data, self.headers, self.client_address[0]))
            return
        if path == "/api/chat/messages":
            ok, payload = create_chat_message(data)
            self.send_json(payload, 201 if ok else 400)
            return
        if path == "/api/admin/access-requests/status":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            ok, payload = update_access_request_status(data)
            self.send_json(payload, 200 if ok else 400)
            return
        if path == "/api/admin/access-requests/create":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            ok, payload = create_admin_access_request(data)
            self.send_json(payload, 201 if ok else 400)
            return
        if path == "/api/admin/donations/status":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            ok, payload = update_donation_status(data)
            self.send_json(payload, 200 if ok else 400)
            return
        if path == "/api/admin/site-config":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            ok, payload = update_site_config(data)
            self.send_json(payload, 200 if ok else 400)
            return
        if path == "/api/admin/chat/reply":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            ok, payload = reply_chat_message(data)
            self.send_json(payload, 200 if ok else 400)
            return
        if path == "/api/admin/chat/status":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            ok, payload = update_chat_status(data)
            self.send_json(payload, 200 if ok else 400)
            return
        if path == "/api/client/login":
            ok, payload = client_login(data)
            self.send_json(payload, 200 if ok else 404)
            return
        if path == "/api/client/ping":
            ok, payload = client_ping(data)
            self.send_json(payload, 200 if ok else 401)
            return
        if path == "/api/client/vip/message":
            ok, payload = create_vip_message(data)
            self.send_json(payload, 201 if ok else 401)
            return
        if path == "/api/admin/vip/config":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            ok, payload = update_vip_config(data)
            self.send_json(payload, 200 if ok else 400)
            return
        if path == "/api/admin/vip/message":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            ok, payload = create_admin_vip_message(data)
            self.send_json(payload, 201 if ok else 400)
            return
        if path == "/api/admin/vip/message/status":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            ok, payload = update_vip_message_status(data)
            self.send_json(payload, 200 if ok else 400)
            return
        self.send_json({"ok": False, "error": "not_found"}, 404)


def main() -> None:
    parser = argparse.ArgumentParser(description="Institutional Trading static site + calendar API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8795")))
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), InstitutionalTradingHandler)
    print(f"Institutional Trading API server: http://{args.host}:{args.port}/vente.html", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
