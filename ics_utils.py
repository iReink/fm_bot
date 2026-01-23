from __future__ import annotations

from datetime import datetime, timedelta


def _escape_ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _format_description(description: str, price) -> str:
    description = description or ""
    price_line = f"Цена: {price}" if price is not None else ""
    text = "\n".join(filter(None, [description, price_line]))
    return _escape_ics_text(text)


def build_event_ics(event_row, duration_minutes: int = 120) -> tuple[str, bytes]:
    event_id, name, description, price, address, _, date_str, time_str = event_row
    start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = start_dt.strftime("%Y%m%dT%H%M%S")
    dtend = end_dt.strftime("%Y%m%dT%H%M%S")
    uid = f"{event_id}-{dtstart}@fm_bot"

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//fm_bot//event calendar//RU",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{dtstart}",
        f"DTEND:{dtend}",
        f"SUMMARY:{_escape_ics_text(name)}",
        f"DESCRIPTION:{_format_description(description, price)}",
        f"LOCATION:{_escape_ics_text(address)}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    content = "\r\n".join(lines) + "\r\n"
    filename = f"event_{event_id}.ics"
    return filename, content.encode("utf-8")
