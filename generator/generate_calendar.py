#!/usr/bin/env python3
import hashlib
import json
import os
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

NOTION_VERSION = "2026-03-11"
DATA_SOURCE_ID = os.environ.get("NOTION_DATA_SOURCE_ID", "55ef2eed-c99a-44a1-8973-fcd1f918eb1f")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
TZ = ZoneInfo("Europe/Madrid")
DAYS = 30
DAY_START_MINUTE = 8 * 60
DAY_END_MINUTE = 23 * 60
EVENT_MINUTES = 15
CALENDAR_NAME = "Spanish Vocabulary"

STAGE_SHARES = {
    "new": 0.55,
    "learning": 0.30,
    "familiar": 0.12,
    "mastered": 0.03,
}

def notion_request(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Notion API error {exc.code}: {body}") from exc

def query_all_pages():
    if not NOTION_TOKEN:
        raise RuntimeError("NOTION_TOKEN is missing. Add it as a GitHub Actions repository secret.")

    url = f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query"
    pages = []
    cursor = None

    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        result = notion_request(url, payload)
        pages.extend(x for x in result.get("results", []) if x.get("object") == "page")
        if not result.get("has_more"):
            break
        cursor = result.get("next_cursor")
        if not cursor:
            break

    return pages

def plain_rich_text(items):
    return "".join(x.get("plain_text", "") for x in (items or [])).strip()

def property_value(prop):
    if not prop:
        return None
    kind = prop.get("type")
    if kind in ("title", "rich_text"):
        return plain_rich_text(prop.get(kind))
    if kind == "select":
        value = prop.get("select")
        return value.get("name") if value else None
    if kind == "multi_select":
        return [x.get("name") for x in prop.get("multi_select", []) if x.get("name")]
    if kind == "checkbox":
        return bool(prop.get("checkbox"))
    if kind == "created_time":
        return prop.get("created_time")
    if kind == "last_edited_time":
        return prop.get("last_edited_time")
    if kind == "unique_id":
        value = prop.get("unique_id") or {}
        prefix = value.get("prefix") or ""
        number = value.get("number")
        return f"{prefix}{number}" if number is not None else None
    return prop.get(kind)

def parse_added(value):
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def cards_from_pages(pages):
    cards = []
    for page in pages:
        props = page.get("properties", {})
        spanish = property_value(props.get("Spanish")) or ""
        if not spanish:
            continue
        if property_value(props.get("Exclude from Calendar")) is True:
            continue

        cards.append({
            "page_id": page["id"],
            "spanish": spanish,
            "english": property_value(props.get("English")) or "",
            "examples": property_value(props.get("Examples")) or "",
            "forms": property_value(props.get("Conjugation / Forms")) or "",
            "notes": property_value(props.get("Usage Notes")) or "",
            "type": property_value(props.get("Type")) or "",
            "categories": property_value(props.get("Categories")) or [],
            "source": property_value(props.get("Source / Context")) or "",
            "card_id": property_value(props.get("Card ID")) or "",
            "retention": property_value(props.get("Retention")) or "New",
            "added": parse_added(property_value(props.get("Added"))),
        })
    cards.sort(key=lambda x: (x["added"], x["spanish"].casefold(), x["page_id"]))
    return cards

def stage_for(card, on_date):
    # Retention is manually controlled in Notion.
    # Blank/unknown values intentionally fall back to New.
    added_date = card["added"].astimezone(TZ).date()
    age = max(0, (on_date - added_date).days)
    raw = str(card.get("retention") or "New").strip().lower()
    stage = {
        "new": "new",
        "learning": "learning",
        "familiar": "familiar",
        "mastered": "mastered",
    }.get(raw, "new")
    return stage, age

def allocate_stage_counts(groups, slots):
    present = [s for s, values in groups.items() if values]
    if not present:
        return {}
    if len(present) == 1:
        return {present[0]: slots}

    total_share = sum(STAGE_SHARES[s] for s in present)
    exact = {s: slots * STAGE_SHARES[s] / total_share for s in present}
    counts = {s: int(exact[s]) for s in present}
    remaining = slots - sum(counts.values())

    for s in sorted(present, key=lambda x: (exact[x] - counts[x], STAGE_SHARES[x]), reverse=True):
        if remaining <= 0:
            break
        counts[s] += 1
        remaining -= 1

    return counts

def smooth_stage_sequence(counts, slots):
    if not counts:
        return []
    current = {s: 0 for s in counts}
    sequence = []
    for _ in range(slots):
        for s in counts:
            current[s] += counts[s]
        chosen = max(current, key=lambda s: (current[s], STAGE_SHARES[s], s))
        sequence.append(chosen)
        current[chosen] -= slots
    return sequence

def build_schedule(cards):
    if not cards:
        return []

    start_date = datetime.now(TZ).date()
    slot_times = []
    minute = DAY_START_MINUTE
    while minute < DAY_END_MINUTE:
        slot_times.append(time(minute // 60, minute % 60))
        minute += EVENT_MINUTES

    global_count = defaultdict(int)
    last_order = defaultdict(lambda: -10**9)
    previous_page = None
    order = 0
    schedule = []

    for day_offset in range(DAYS):
        current_date = start_date + timedelta(days=day_offset)
        groups = defaultdict(list)
        stage_meta = {}

        for card in cards:
            stage, age = stage_for(card, current_date)
            groups[stage].append(card)
            stage_meta[card["page_id"]] = (stage, age)

        counts = allocate_stage_counts(groups, len(slot_times))
        stage_sequence = smooth_stage_sequence(counts, len(slot_times))
        day_count = defaultdict(int)

        for slot_time, stage in zip(slot_times, stage_sequence):
            candidates = groups[stage]
            filtered = [c for c in candidates if c["page_id"] != previous_page]
            if filtered:
                candidates = filtered

            def score(card):
                pid = card["page_id"]
                # Strongly spread appearances within the same day, then across the feed.
                return (
                    day_count[pid],
                    global_count[pid],
                    last_order[pid],
                    card["added"],
                    card["spanish"].casefold(),
                )

            card = min(candidates, key=score)
            pid = card["page_id"]
            stage_name, age = stage_meta[pid]
            start_dt = datetime.combine(current_date, slot_time, tzinfo=TZ)
            schedule.append({
                "start": start_dt,
                "end": start_dt + timedelta(minutes=EVENT_MINUTES),
                "card": card,
                "stage": stage_name,
                "age": age,
            })
            day_count[pid] += 1
            global_count[pid] += 1
            last_order[pid] = order
            previous_page = pid
            order += 1

    return schedule

def compact(text, limit):
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"

def event_summary(item):
    card = item["card"]
    es = compact(card["spanish"], 42)
    en = compact(card["english"], 34)
    stage = item["stage"]

    if stage == "new":
        return compact(f"{es} — {en}" if en else es, 78)
    if stage == "learning":
        return compact(f"{es} — ?", 78)
    if en:
        return compact(f"{en} → ?", 78)
    return compact(f"{es} — ?", 78)

def split_learning_text(value):
    """Split multiline or pipe-separated Notion learning text into clean items."""
    if not value:
        return []
    text = str(value).replace("\r\n", "\n").strip()
    # Newlines are preferred in Notion. " | " is supported as a compact fallback.
    chunks = []
    for line in text.split("\n"):
        chunks.extend(line.split(" | "))
    return [x.strip(" •-*\t") for x in chunks if x.strip(" •-*\t")]

def event_description(item):
    card = item["card"]
    examples = split_learning_text(card["examples"])
    forms = split_learning_text(card["forms"])
    notes = split_learning_text(card["notes"])

    lines = []

    # The event title already carries the recall prompt. Notes should be study material,
    # not scheduling metadata.
    if card["type"].lower() == "verb":
        if forms:
            lines.append("CONJUGACIÓN")
            lines.extend(f"• {form}" for form in forms)
        if examples:
            if lines:
                lines.append("")
            lines.append("EN CONTEXTO")
            lines.extend(f"• {example}" for example in examples)
    else:
        if examples:
            lines.append("EN CONTEXTO")
            lines.extend(f"• {example}" for example in examples)
        if forms:
            if lines:
                lines.append("")
            lines.append("FORMAS ÚTILES")
            lines.extend(f"• {form}" for form in forms)

    # Usage notes are kept only when they teach something that examples/forms do not.
    if notes:
        if lines:
            lines.append("")
        lines.append("MATIZ")
        lines.extend(f"• {note}" for note in notes)

    # Fallback for sparse entries.
    if not lines:
        if card["english"]:
            lines.append(f"{card['spanish']} — {card['english']}")
        else:
            lines.append(card["spanish"])

    return "\n".join(lines)

def ics_escape(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )

def fold_line(line, max_octets=75):
    physical = []
    current = ""
    first = True
    for char in line:
        allowance = max_octets if first else max_octets - 1
        if current and len((current + char).encode("utf-8")) > allowance:
            physical.append(("" if first else " ") + current)
            current = char
            first = False
        else:
            current += char
    physical.append(("" if first else " ") + current)
    return "\r\n".join(physical)

def stable_uid(item):
    start = item["start"].strftime("%Y%m%dT%H%M")
    seed = f"{item['card']['page_id']}|{start}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
    return f"{digest}@spanish-vocabulary-calendar"

def render_ics(schedule):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Spanish Vocabulary Calendar//Notion Feed//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{CALENDAR_NAME}",
        "X-WR-TIMEZONE:Europe/Madrid",
        "BEGIN:VTIMEZONE",
        "TZID:Europe/Madrid",
        "X-LIC-LOCATION:Europe/Madrid",
        "BEGIN:DAYLIGHT",
        "TZOFFSETFROM:+0100",
        "TZOFFSETTO:+0200",
        "TZNAME:CEST",
        "DTSTART:19700329T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
        "END:DAYLIGHT",
        "BEGIN:STANDARD",
        "TZOFFSETFROM:+0200",
        "TZOFFSETTO:+0100",
        "TZNAME:CET",
        "DTSTART:19701025T030000",
        "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]

    for item in schedule:
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{stable_uid(item)}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;TZID=Europe/Madrid:{item['start'].strftime('%Y%m%dT%H%M%S')}",
            f"DTEND;TZID=Europe/Madrid:{item['end'].strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{ics_escape(event_summary(item))}",
            f"DESCRIPTION:{ics_escape(event_description(item))}",
            "TRANSP:TRANSPARENT",
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(fold_line(line) for line in lines) + "\r\n"

def main():
    pages = query_all_pages()
    cards = cards_from_pages(pages)
    schedule = build_schedule(cards)

    site = Path("site")
    site.mkdir(parents=True, exist_ok=True)
    output = site / "spanish-vocabulary.ics"
    output.write_bytes(render_ics(schedule).encode("utf-8"))

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vocabulary_entries": len(cards),
        "calendar_events": len(schedule),
        "days": DAYS,
        "timezone": "Europe/Madrid",
    }
    (site / "status.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))

if __name__ == "__main__":
    main()
