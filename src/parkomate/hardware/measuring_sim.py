"""Measuring-device simulator: sends the JSON packet the real device sends, over the network.

``python -m parkomate measuring-device --to <station IP>`` - run it on any PC (or the same
PC) on the station's Wi-Fi network. It POSTs exactly the confirmed packet format::

    {"station": "STATION-01", "seq": 12, "ts": "2026-10-12T10:15:03Z",
     "v_a": 24.01, "v_b": 5.00, "v_c": 3.30, "t_reg_c": 28.4, "t_amb_c": 27.1}

Presets give a passing packet or one that fails a single limit, so every Testing branch can
be shown with the real Wi-Fi link.
"""

from __future__ import annotations

import json
import random
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

PRESETS: tuple[str, ...] = ("good", "v_a_high", "v_b_low", "v_c_low", "too_hot")
"""Packet kinds: all values in limits, or exactly one value outside its limits."""


def make_packet(
    preset: str, *, station: str, seq: int, rng: random.Random | None = None
) -> dict[str, Any]:
    """One measurement packet. Unknown presets raise ``ValueError``."""
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; one of {', '.join(PRESETS)}")
    rnd = rng or random.Random()
    ambient = round(rnd.uniform(26.0, 28.0), 1)
    packet: dict[str, Any] = {
        "station": station,
        "seq": seq,
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "v_a": round(rnd.uniform(23.95, 24.05), 2),
        "v_b": round(rnd.uniform(4.97, 5.03), 2),
        "v_c": round(rnd.uniform(3.28, 3.32), 2),
        "t_reg_c": round(ambient + rnd.uniform(0.5, 2.0), 1),
        "t_amb_c": ambient,
    }
    if preset == "v_a_high":
        packet["v_a"] = 24.40
    elif preset == "v_b_low":
        packet["v_b"] = 4.70
    elif preset == "v_c_low":
        packet["v_c"] = 3.10
    elif preset == "too_hot":
        packet["t_reg_c"] = round(ambient + 6.0, 1)
    return packet


@dataclass(frozen=True, slots=True)
class SendResult:
    status: int
    """HTTP status from the station (0 = no answer)."""
    message: str


def send_packet(url: str, packet: dict[str, Any], *, timeout_s: float = 5.0) -> SendResult:
    """POST ``packet`` to ``url``; never raises for network problems."""
    body = json.dumps(packet).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - plain http on the bench network by design
        url, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
            return SendResult(response.status, _status_text(response.read()))
    except urllib.error.HTTPError as exc:
        return SendResult(exc.code, _status_text(exc.read()))
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return SendResult(0, str(reason))


def _status_text(raw: bytes) -> str:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return raw.decode("utf-8", errors="replace")[:200]
    return str(data.get("status", "")) if isinstance(data, dict) else str(data)[:200]


def station_url(host: str, port: int, path: str) -> str:
    host = host.strip()
    if host.startswith(("http://", "https://")):
        return host
    return f"http://{host}:{port}{path}"
