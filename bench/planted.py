"""Everything the loop benchmark plants: the bench_* files in the workspace, the Contacts and
Messages world, and what each app toolkit's read tools answer under bench/worlds.apps_world —
Finder's selection, the browser's front tab, the Shortcuts list, Reminders, Notes, Calendar,
Mail, the knowledge base and the web. Tasks (bench/tasks.py) ask about it; nothing here is the
user's."""

from __future__ import annotations

from datetime import datetime, timedelta

# ── the planted files ────────────────────────────────────────────────────────────────────────

_LONG_FILLER = ("The reservoir log records water levels, weather and the birds seen on each visit. "
                "Levels held steady through the week and the weather stayed overcast. ")
_LONG_MID = "On Thursday the bird seen at the reservoir was a kestrel, hunting over the north bank. "
# ~30k chars on ONE line with the fact past the midpoint: the head+tail clamp
# (nodes/tools._MAX_OBSERVATION) drops it from a read — pivot loop item 6, compress, don't clip
# — and a search must show the match, not the start of the line.
LONG_TEXT = _LONG_FILLER * 110 + _LONG_MID + _LONG_FILLER * 90

FIXTURES = {
    "bench_notes.txt": ("Dentist appointment moved to the 14th.\n"
                        "The gate code for the garage is 4471.\n"),
    "bench_a.txt": "Invoice 7731 — paid.\nReference 120.\n",
    "bench_b.txt": "Order 7731 shipped.\nReference 45.\n",
    "bench_lease_summary.txt": ("Lease summary: the apartment lease ends in March; "
                                "rent is due on the 1st.\n"),
    "bench_expenses.txt": ("Expenses this week:\ncoffee 12.50\ngroceries 48.00\n"
                           "parking 7.25\nutilities 130.00\n"),
    "bench_edit.txt": "Status: draft\nOwner: me\n",
    "bench_draft.txt": "Draft agenda: budget, hiring, offsite.\n",
    "bench_long.txt": LONG_TEXT,
}


# ── the planted messaging world (bench/worlds.messaging_world) ───────────────────────────────
# Who is in Contacts, which group chats Messages knows, one climbing-chat history. Sam is in
# four groups, so "text Sam" must still mean Sam alone.

MSG_CARDS = [
    {"name": "Sam Lee", "phones": [{"label": "mobile", "value": "+1 555 010 2000"}]},
    {"name": "Alex Kim", "emails": [{"label": "home", "value": "alex@example.com"}]},
    {"name": "Jo Park", "phones": [{"label": "mobile", "value": "+1 555 000 0004"}]},
    {"name": "Priya Nair", "phones": [{"label": "mobile", "value": "+1 555 000 0005"}]},
    {"name": "Jordan Wu", "phones": [{"label": "mobile", "value": "+1 555 000 0006"}]},
]
MSG_GROUPS = [
    ("any;+;chatf111", "Lee family", [("+15550000001", "Mom"), ("+15550000002", "Dad"),
                                      ("+15550102000", "Sam Lee")]),
    ("any;+;chatf222", "Kim family", [("alex@example.com", "Alex Kim"), ("+15550000007", "Min Kim")]),
    ("any;+;chat5a11", "", [("+15550102000", "Sam Lee"), ("alex@example.com", "Alex Kim")]),
    ("any;+;chat5a12", "", [("+15550102000", "Sam Lee"), ("alex@example.com", "Alex Kim"),
                            ("+15550000004", "Jo Park")]),
    ("any;+;chat70c1", "Climbing crew", [("alex@example.com", "Alex Kim"),
                                         ("+15550000004", "Jo Park"), ("+15550102000", "Sam Lee")]),
]
MSG_HISTORY = [  # (sender handle or None for me, text, minutes ago) in the climbing chat
    ("+15550000004", "Gym or crag this weekend?", 300),
    ("alex@example.com", "Crag! I'll bring the rope on Saturday", 240),
    (None, "Count me in", 200),
]


# ── the planted apps (bench/worlds.apps_world) ───────────────────────────────────────────────

FINDER_SELECTION = ["bench_b.txt"]

BROWSER_TAB = {
    "browser": "Safari", "url": "https://example.com/bench-weeknight-bread",
    "title": "Weeknight bread — a quick loaf",
    "text": ("Weeknight bread. Mix flour, water, salt and yeast; rest for an hour. Shape the loaf "
             "and bake it for 22 minutes, until the crust is deep brown. Cool before slicing."),
}

SHORTCUTS = ["Log Water", "Morning Routine", "Start Focus Timer", "Share ETA"]


def _today() -> datetime:
    """Today's first minute by the tools' own clock (notify.now), so a pinned clock moves the
    planted events with the window the calendar tool reads."""
    import notify
    return notify.now().replace(hour=0, minute=0, second=0, microsecond=0)


REMINDERS = [
    {"id": "x-apple-reminder://bench-1", "list": "Groceries", "title": "Oat milk"},
    {"id": "x-apple-reminder://bench-2", "list": "Groceries", "title": "Coffee beans"},
    {"id": "x-apple-reminder://bench-3", "list": "Errands", "title": "Return library books"},
]

NOTES = [
    {"id": "x-coredata://bench/ICNote/p1", "title": "Home", "folder": "Notes",
     "modified": "2026-10-01T09:00", "body": "Wifi network: Juniper\nThe bins go out on Tuesday "
                                             "night.\nPlumber: Ray, 555 0142"},
    {"id": "x-coredata://bench/ICNote/p2", "title": "Shopping", "folder": "Notes",
     "modified": "2026-10-03T18:30", "body": "eggs\nbread\ntomatoes"},
]


def events() -> list[dict]:
    """Two events relative to today: the dentist tomorrow morning, lunch the day after."""
    d = _today()
    return [
        {"calendar": "Personal", "uid": "bench-ev-1", "title": "Dentist",
         "start": d + timedelta(days=1, hours=9, minutes=30), "end": d + timedelta(days=1, hours=10, minutes=30),
         "location": "Smile Dental"},
        {"calendar": "Work", "uid": "bench-ev-2", "title": "Lunch with Sam",
         "start": d + timedelta(days=2, hours=12), "end": d + timedelta(days=2, hours=13),
         "location": ""},
    ]



MAIL = [
    {"id": "101", "from": "Dana Reyes <dana@example.com>", "to": "me@example.com",
     "subject": "Invoice 2219", "date": "2026-10-06T08:15", "unread": True,
     "body": "Hi — attached is invoice 2219. The total is $1,240, due on the 30th. Thanks, Dana"},
    {"id": "102", "from": "Bench Weekly <news@example.com>", "to": "me@example.com",
     "subject": "This week's digest", "date": "2026-10-05T07:00", "unread": False,
     "body": "Ten links for your weekend."},
]

KNOWLEDGE = {
    "bench-office-handbook.md": ("Office handbook. The front door code is 7290. Visitors sign in "
                                 "at reception. The kitchen is cleaned on Fridays."),
    "bench-travel-policy.md": ("Travel policy. Book flights at least 14 days ahead. Hotels up to "
                               "$180 a night are approved without a manager."),
}

WEB_RESULTS = [
    {"title": "Saturn Café — Lisbon", "url": "https://example.com/saturn-cafe",
     "content": "Saturn Café in Lisbon opens at 8:30 every morning and closes at 18:00."},
    {"title": "Lisbon cafés guide", "url": "https://example.com/lisbon-cafes",
     "content": "A guide to the city's cafés, from pastelarias to specialty coffee."},
]

WEB_PAGES = {
    "https://example.com/saturn-cafe": "Saturn Café, Rua Augusta 12, Lisbon. Open daily 8:30–18:00.",
    "https://example.com/bench-focaccia": ("Focaccia. Proof the dough twice, dimple it with oiled "
                                           "fingers and bake at 230°C for 20 minutes."),
}
