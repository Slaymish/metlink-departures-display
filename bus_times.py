#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


DEFAULT_STOP_ID = "7958"
DEFAULT_LIMIT = 2
API_URL = "https://api.opendata.metlink.org.nz/v1/stop-predictions"
GTFS_STOPS_URL = "https://api.opendata.metlink.org.nz/v1/gtfs/stops"

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH = os.path.join(_SCRIPT_DIR, ".env")
_ENV_CACHE: dict[str, str] | None = None


@dataclass(frozen=True)
class DepartureView:
    service_id: str
    headsign: str
    minutes_away: int | None
    time_str: str
    status: str | None


def _parse_iso(dt: str | None) -> datetime | None:
    if not dt:
        return None
    # API returns ISO-8601 with timezone offset, e.g. 2026-01-16T22:35:00+13:00
    return datetime.fromisoformat(dt)


def _minutes_until(now: datetime, when: datetime) -> int:
    delta = when - now
    # Clamp negative values to 0 so we don’t show “-1 min” for imminent arrivals.
    minutes = int(delta.total_seconds() // 60)
    return max(0, minutes)


def _load_env_file(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    out[key] = value
    except FileNotFoundError:
        return {}
    return out


def _get_env() -> dict[str, str]:
    global _ENV_CACHE
    if _ENV_CACHE is None:
        _ENV_CACHE = _load_env_file(_ENV_PATH)
    return _ENV_CACHE


def _get_setting(name: str) -> str | None:
    v = os.environ.get(name)
    if v:
        return v
    return _get_env().get(name)


def _get_api_key() -> str | None:
    return _get_setting("METLINK_API_KEY")


def _get_default_stop_id() -> str:
    return _get_setting("METLINK_STOP_ID") or DEFAULT_STOP_ID


def _get_default_limit() -> int:
    raw = _get_setting("METLINK_LIMIT")
    if not raw:
        return DEFAULT_LIMIT
    try:
        v = int(raw)
    except ValueError:
        return DEFAULT_LIMIT
    return max(1, v)


def _pick_time(dep: dict[str, Any]) -> tuple[datetime | None, str]:
    # Prefer expected if present, else aimed.
    expected = _parse_iso(dep.get("expected"))
    aimed = _parse_iso(dep.get("aimed"))
    chosen = expected or aimed
    if not chosen:
        return None, "--:--"
    return chosen, chosen.strftime("%H:%M")


def _format_status(status: str | None) -> str:
    if not status:
        return "scheduled"
    return status


def _eta_str(minutes_away: int | None) -> str:
    if minutes_away is None:
        return "--"
    if minutes_away <= 0:
        return "Due"
    if minutes_away == 1:
        return "1min"
    return f"{minutes_away}min"


def _truncate(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


class _Style:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def sign(self, s: str) -> str:
        if not self.enabled:
            return s
        # Amber-ish foreground, bold. Avoid forcing background color.
        return "\x1b[1m\x1b[38;5;214m" + s + "\x1b[0m"


def render_sign_text(
    *,
    stop_label: str,
    stop_id: str,
    views: list[DepartureView],
    limit: int,
    styled: bool,
) -> str:
    style = _Style(styled)

    # LED-sign style layout (similar to a stop display):
    # ROUTE (4) | DEST (24) | ETA (6)
    route_w = 4
    dest_w = 24
    eta_w = 6

    lines: list[str] = []
    if not views:
        lines.append(style.sign("--"))
        lines.append(style.sign("Time " + datetime.now(timezone.utc).astimezone().strftime("%H:%M")))
        return "\n".join(lines)

    for v in views[:limit]:
        route = _truncate(v.service_id, route_w).ljust(route_w)
        dest = _truncate(v.headsign or stop_label, dest_w).ljust(dest_w)
        eta = _truncate(_eta_str(v.minutes_away), eta_w).rjust(eta_w)
        lines.append(style.sign(f"{route} {dest} {eta}"))

    lines.append(style.sign("Time " + datetime.now(timezone.utc).astimezone().strftime("%H:%M")))
    return "\n".join(lines)


def fetch_predictions(*, api_key: str, stop_id: str, limit: int) -> dict[str, Any]:
    url = f"{API_URL}?stop_id={stop_id}&limit={limit}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "accept": "application/json",
            "x-api-key": api_key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        raise RuntimeError(f"HTTP {e.code} from Metlink API: {body.strip()}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error calling Metlink API: {e}") from e

    import json

    return json.loads(raw)


def fetch_stops(*, api_key: str) -> list[dict[str, Any]]:
    req = urllib.request.Request(
        GTFS_STOPS_URL,
        method="GET",
        headers={
            "accept": "application/json",
            "x-api-key": api_key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        raise RuntimeError(f"HTTP {e.code} from Metlink API: {body.strip()}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error calling Metlink API: {e}") from e

    import json

    data = json.loads(raw)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        return data["data"]
    raise RuntimeError("Unexpected response shape from /v1/gtfs/stops")


def to_views(payload: dict[str, Any]) -> tuple[str, list[DepartureView]]:
    if "error" in payload:
        raise RuntimeError(str(payload["error"]))

    stop_name = payload.get("departures", [{}])[0].get("name")
    # stop_name is often something like “MelroseRd (41)”; keep it, but don’t rely on it.
    stop_label = stop_name or f"Stop {payload.get('stop_id', '')}".strip() or "Stop"

    now = datetime.now(timezone.utc).astimezone()

    views: list[DepartureView] = []
    for d in payload.get("departures", [])[:]:
        departure = d.get("departure") or {}
        chosen_dt, time_str = _pick_time(departure)
        minutes_away = _minutes_until(now, chosen_dt) if chosen_dt else None

        views.append(
            DepartureView(
                service_id=str(d.get("service_id") or d.get("route_short_name") or "?"),
                headsign=str(d.get("trip_headsign") or d.get("destination", {}).get("name") or ""),
                minutes_away=minutes_away,
                time_str=time_str,
                status=d.get("status"),
            )
        )

    return stop_label, views


def _stop_id_from_row(row: dict[str, Any]) -> str:
    # GTFS typically uses stop_id/stop_name; handle a few likely shapes.
    for key in ("stop_id", "id", "stopId"):
        if key in row and row[key] is not None:
            return str(row[key])
    return ""


def _stop_name_from_row(row: dict[str, Any]) -> str:
    for key in ("stop_name", "name", "stopName"):
        if key in row and row[key] is not None:
            return str(row[key])
    # Fallback: sometimes there’s a stop_desc
    if row.get("stop_desc"):
        return str(row["stop_desc"])
    return ""


def pick_stop_interactive(*, api_key: str, query: str | None = None) -> tuple[str, str]:
    stops = fetch_stops(api_key=api_key)
    rows: list[tuple[str, str]] = []
    for s in stops:
        stop_id = _stop_id_from_row(s)
        name = _stop_name_from_row(s)
        if stop_id:
            rows.append((stop_id, name))

    if query:
        q = query.casefold()
        rows = [(sid, name) for (sid, name) in rows if q in sid.casefold() or q in (name or "").casefold()]

    if not rows:
        if query:
            raise RuntimeError(f"No stops matched: {query!r}")
        raise RuntimeError("No stops returned from /v1/gtfs/stops")

    for i, (sid, name) in enumerate(rows, start=1):
        label = f"{sid} {name}".strip()
        print(f"{i:4d}) {label}")

    while True:
        try:
            choice = input("Select stop number: ").strip()
        except EOFError:
            raise RuntimeError("No selection made")

        if not choice:
            continue
        if not choice.isdigit():
            print("Please enter a number.")
            continue
        idx = int(choice)
        if idx < 1 or idx > len(rows):
            print(f"Please enter a number between 1 and {len(rows)}.")
            continue
        stop_id, name = rows[idx - 1]
        return stop_id, (name or f"Stop {stop_id}")


def main(argv: list[str]) -> int:
    # Keep default usage simple:
    # - bus-times            -> show default stop
    # - bus-times 7958       -> show stop 7958
    # - bus-times pick       -> interactive stop picker
    parser = argparse.ArgumentParser(prog="bus-times")
    parser.add_argument("arg", nargs="?", default=_get_default_stop_id(), help="Stop id, or 'pick'")
    parser.add_argument("query", nargs="?", default=None, help="Filter for 'pick' (optional)")
    parser.add_argument(
        "--limit",
        type=int,
        default=_get_default_limit(),
        help="Number of departures to show (default: 2 or METLINK_LIMIT)",
    )
    parser.add_argument("--no-style", action="store_true", help="Disable coloured sign-style output")

    args = parser.parse_args(argv)

    style_enabled = (not args.no_style) and sys.stdout.isatty() and (os.environ.get("NO_COLOR") is None)

    api_key = _get_api_key()
    if not api_key:
        print("Missing METLINK_API_KEY.", file=sys.stderr)
        print("Set it as an env var, or create a .env next to this script:", file=sys.stderr)
        print(f"  {_ENV_PATH}", file=sys.stderr)
        print("With contents:", file=sys.stderr)
        print("  METLINK_API_KEY=...your key...", file=sys.stderr)
        return 2

    if str(args.arg).lower() == "pick":
        stop_id, stop_label = pick_stop_interactive(api_key=api_key, query=args.query)
        print(f"Selected stop_id: {stop_id}")
    else:
        stop_id = str(args.arg)
        stop_label = ""

    payload = fetch_predictions(api_key=api_key, stop_id=stop_id, limit=int(args.limit))
    inferred_label, views = to_views(payload)
    if not stop_label:
        stop_label = inferred_label

    print(
        render_sign_text(
            stop_label=stop_label,
            stop_id=stop_id,
            views=views,
            limit=int(args.limit),
            styled=style_enabled,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
