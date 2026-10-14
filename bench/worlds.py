"""What the loop benchmark plants around a run, and takes away after: the bench_* files in
the workspace, and a Contacts + Messages world the messaging tools read instead of the user's
own (every AppleScript that would still run is refused)."""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bench.planted import FIXTURES, MSG_CARDS, MSG_GROUPS, MSG_HISTORY


class fixtures:
    """Plant FIXTURES in the configured scratch workspace for the suite; remove every bench_*
    file afterwards. Refuses to run over bench_* files already there — they would be the
    user's, or a killed run's (move them aside)."""

    def __enter__(self):
        from core import workspace

        workspace.reset()  # the configured scratch folder, never the folder it was run from
        self.root = workspace.root()
        self.root.mkdir(parents=True, exist_ok=True)
        existing = sorted(p.name for p in self.root.glob("bench_*"))
        if existing:
            raise RuntimeError(
                f"the loop benchmark plants bench_* files in {self.root} and found "
                f"{existing} already there — move them aside first"
            )
        self.reset()
        return self

    def reset(self) -> None:
        """Put every planted file back as it was and remove what tasks wrote — between
        tasks, so one task's rename or edit is not the next task's starting point."""
        self._clear()
        for name, body in FIXTURES.items():
            (self.root / name).write_text(body, encoding="utf-8")

    def _clear(self) -> None:
        # Every bench_* entry here was made by this run: __enter__ refused to start over any.
        # A directory a task made goes too — left behind, it would be the next task's starting
        # point and abort the next run of a `--runs N` batch.
        for p in self.root.glob("bench_*"):
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)

    def __exit__(self, *exc):
        self._clear()
        return False


class messaging_world:
    """Swap the Contacts and Messages seams for the planted world: `search_contacts` reads
    MSG_CARDS, `find_group_chats` and a group send read MSG_GROUPS, `read_messages` a
    throwaway chat.db. Leaving restores the real seams."""

    def __enter__(self):
        import sqlite3
        import tempfile

        from tools import applescript, contacts, messages
        from tools.applescript import FS, GS, RS, US

        self._tmp = tempfile.TemporaryDirectory(prefix="saturn_bench_")
        db_path = Path(self._tmp.name) / "chat.db"
        self._db(sqlite3, db_path)
        listing = "".join(US.join([g, n, "".join(f"{h}{FS}{p}{GS}" for h, p in people)]) + RS
                          for g, n, people in MSG_GROUPS)

        def cards(_script, q):
            q = str(q or "").lower()
            hits = [c for c in MSG_CARDS if q in c["name"].lower()]
            return [dict(c) for c in hits], len(hits)

        def refuse(argv, timeout):
            raise OSError("the benchmark never runs AppleScript against the user's apps")

        self._saved = [(contacts, "_cards", contacts._cards), (contacts, "_all_names", contacts._all_names),
                       (messages, "_groups", messages._groups), (messages, "_db_path", messages._db_path),
                       (applescript, "_run", applescript._run), (applescript, "_platform", applescript._platform)]
        contacts._cards = cards
        contacts._all_names = lambda: [c["name"] for c in MSG_CARDS]
        messages._groups = lambda: messages._parse_groups(listing)
        messages._db_path = lambda: db_path
        applescript._run = refuse
        applescript._platform = lambda: "darwin"
        return self

    @staticmethod
    def _db(sqlite3, path):
        epoch = datetime(2001, 1, 1, tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        db = sqlite3.connect(path)
        db.executescript("""
            CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
            CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, guid TEXT, chat_identifier TEXT, display_name TEXT);
            CREATE TABLE message (ROWID INTEGER PRIMARY KEY, text TEXT, attributedBody BLOB,
                                  handle_id INTEGER, date INTEGER, is_from_me INTEGER);
            CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
            CREATE TABLE chat_handle_join (chat_id INTEGER, handle_id INTEGER);
            INSERT INTO handle VALUES (1, 'alex@example.com'), (2, '+15550000004'), (3, '+15550102000');
            INSERT INTO chat VALUES (1, 'iMessage;+;chat70c1', 'chat70c1', 'Climbing crew');
            INSERT INTO chat_handle_join VALUES (1, 1), (1, 2), (1, 3);
        """)
        handles = {"alex@example.com": 1, "+15550000004": 2}
        for rowid, (sender, text, ago) in enumerate(MSG_HISTORY, 1):
            when = int(((now - timedelta(minutes=ago)) - epoch).total_seconds() * 1_000_000_000)
            db.execute("INSERT INTO message VALUES (?,?,?,?,?,?)",
                       (rowid, text, None, handles.get(sender, 0), when, int(sender is None)))
            db.execute("INSERT INTO chat_message_join VALUES (1, ?)", (rowid,))
        db.commit()
        db.close()

    def __exit__(self, *exc):
        for module, name, value in self._saved:
            setattr(module, name, value)
        self._tmp.cleanup()
        return False


class apps_world:
    """Every read tool of the app toolkits answers from bench/planted.py, in the real tool's
    shape: Finder's selection, the browser tab, the Shortcuts list, Reminders, Notes, Calendar,
    Mail, the knowledge base (no embedder) and the web (no request, no egress record). The
    writes are left as they are — the benchmark's approver declines every one into the user's
    apps — and anything that would still reach AppleScript, the shortcuts command or a
    notification backend is refused. Leaving puts every tool back."""

    def __enter__(self):
        from tools import applescript, shortcuts
        from tools.registry import all_by_name
        import notify

        stand_ins = {
            "finder_selection": _finder_selection, "read_browser_tab": _read_browser_tab,
            "list_shortcuts": _list_shortcuts, "list_reminders": _list_reminders,
            "search_notes": _search_notes, "read_note": _read_note,
            "list_calendar_events": _list_calendar_events, "list_mail": _list_mail,
            "search_mail": _search_mail, "read_mail": _read_mail,
            "search_knowledge_base": _search_knowledge_base, "web_search": _web_search,
            "web_extract": _web_extract,
        }

        def refuse(*_a, **_k):
            raise OSError("the benchmark never reaches the user's apps")

        self._funcs = [(all_by_name[n], all_by_name[n].func) for n in stand_ins]
        self._saved = [(applescript, "_run", applescript._run),
                       (applescript, "_platform", applescript._platform),
                       (shortcuts, "_run", shortcuts._run), (notify, "backend", notify.backend)]
        for name, fn in stand_ins.items():
            all_by_name[name].func = fn
        applescript._run = refuse
        applescript._platform = lambda: "darwin"
        shortcuts._run = refuse
        notify.backend = refuse
        return self

    def __exit__(self, *exc):
        for tool, fn in self._funcs:
            tool.func = fn
        for module, name, value in self._saved:
            setattr(module, name, value)
        return False


# The stand-ins: each takes the real tool's arguments and returns what the real tool would.

def _finder_selection():
    from bench.planted import FINDER_SELECTION
    return {"selected": list(FINDER_SELECTION)}


def _read_browser_tab(browser: str = ""):
    from bench.planted import BROWSER_TAB
    return dict(BROWSER_TAB)


def _list_shortcuts():
    from bench.planted import SHORTCUTS
    return list(SHORTCUTS)


def _list_reminders(list: str = ""):  # noqa: A002 — the real tool's argument name
    from bench.planted import REMINDERS
    from tools.toolspec import ToolError

    name = str(list or "").strip()
    lists = {r["list"].lower() for r in REMINDERS}
    if name and name.lower() not in lists:
        raise ToolError(f"there is no Reminders list named {name!r}")
    items = [dict(r) for r in REMINDERS if not name or r["list"].lower() == name.lower()]
    return items or (f"No open reminders in {name}." if name else "No open reminders.")


def _search_notes(query: str = "", limit: int = 10):
    from bench.planted import NOTES

    q = str(query or "").strip().lower()
    found = [{k: n[k] for k in ("id", "title", "folder", "modified")} for n in NOTES
             if not q or q in n["title"].lower() or q in n["body"].lower()]
    found.sort(key=lambda n: n["modified"], reverse=True)
    if not found:
        return f"No notes match {query!r}." if q else "No notes found."
    return found[:max(1, int(limit or 10))]


def _read_note(note: str):
    from bench.planted import NOTES
    from tools.toolspec import ToolError

    ref = str(note or "").strip()
    if not ref:
        raise ToolError("read_note needs a note id or title")
    hit = (next((n for n in NOTES if n["id"] == ref), None)
           or next((n for n in NOTES if n["title"].lower() == ref.lower()), None)
           or next((n for n in NOTES if ref.lower() in n["title"].lower()), None))
    if hit is None:
        raise ToolError(f"no note matches {ref!r}")
    return dict(hit)


def _list_calendar_events(start: str = "", end: str = "", calendars: str = ""):
    from datetime import timedelta

    import notify
    from bench.planted import events
    from tools import calendar
    from tools.toolspec import ToolError

    try:  # the real tool's own reading of start / end
        today = notify.now().replace(hour=0, minute=0, second=0, microsecond=0)
        d1 = calendar._when(start, today, whole_day=True)
        d2 = calendar._when(end, d1 + timedelta(days=7), whole_day=True)
    except notify.NotifyError as exc:
        raise ToolError(str(exc)) from exc
    if d2 <= d1:
        raise ToolError(f"end {calendar._iso(d2)} is at or before start {calendar._iso(d1)}; "
                        "put the earlier time first")
    names = {n.strip().lower() for n in str(calendars or "").split(",") if n.strip()}
    tz = d1.tzinfo
    out = []
    for e in events():
        s, f = e["start"].replace(tzinfo=tz), e["end"].replace(tzinfo=tz)
        if s <= d2 and f >= d1 and (not names or e["calendar"].lower() in names):
            out.append({"calendar": e["calendar"], "uid": e["uid"], "title": e["title"],
                        "start": calendar._iso(s), "end": calendar._iso(f), "all_day": False,
                        "location": e["location"], "recurring": False})
    if not out:
        return f"No events between {calendar._iso(d1)} and {calendar._iso(d2)}."
    return sorted(out, key=lambda e: e["start"])


def _mail_row(m: dict, mailbox: str) -> dict:
    return {"id": m["id"], "mailbox": mailbox, "from": m["from"], "subject": m["subject"],
            "date": m["date"], "unread": m["unread"], "replied": False}


def _list_mail(mailbox: str = "inbox", limit: int = 10, unread_only: bool = False):
    from bench.planted import MAIL

    box = str(mailbox or "inbox").strip() or "inbox"
    if box.lower() != "inbox":
        return f"No messages in {box}."
    rows = [_mail_row(m, box) for m in MAIL if m["unread"] or not unread_only]
    return rows[:max(1, int(limit or 10))] or f"No messages in {box}."


def _search_mail(query: str, mailbox: str = "inbox", limit: int = 10):
    from bench.planted import MAIL
    from tools.toolspec import ToolError

    q = str(query or "").strip().lower()
    if not q:
        raise ToolError("search_mail needs a non-empty query")
    box = str(mailbox or "inbox").strip() or "inbox"
    rows = [_mail_row(m, box) for m in MAIL
            if box.lower() == "inbox" and (q in m["subject"].lower() or q in m["from"].lower())]
    return rows[:max(1, int(limit or 10))] or f"No messages match {query!r}."


def _read_mail(id, mailbox: str = "inbox"):  # noqa: A002 — the real tool's argument name
    from bench.planted import MAIL
    from tools.toolspec import ToolError

    try:
        mid = int(id)
    except (TypeError, ValueError):
        raise ToolError(f"read_mail needs a numeric message id from list_mail, not {id!r}")
    box = str(mailbox or "inbox").strip() or "inbox"
    hit = next((m for m in MAIL if int(m["id"]) == mid), None)
    if hit is None or box.lower() != "inbox":
        raise ToolError(f"no message with id {mid} in {box}")
    return {"id": hit["id"], "mailbox": box, "from": hit["from"], "to": hit["to"],
            "subject": hit["subject"], "date": hit["date"], "body": hit["body"]}


def _search_knowledge_base(query: str = ""):
    from bench.planted import KNOWLEDGE
    from textutil import doc_source_label

    words = [w for w in str(query or "").lower().split() if len(w) > 2]
    if not words:
        return (f"The knowledge base holds {len(KNOWLEDGE)} documents:\n"
                + "\n".join(f"- {name}" for name in KNOWLEDGE))
    hits = [(name, text) for name, text in KNOWLEDGE.items()
            if any(w in text.lower() or w in name.lower() for w in words)]
    if not hits:
        return "No relevant documents found in the knowledge base."
    return "\n\n".join(doc_source_label(name) + f"\n{text}" for name, text in hits)


def _web_search(query: str):
    from bench.planted import WEB_RESULTS
    return {"query": query, "results": [dict(r) for r in WEB_RESULTS]}


def _web_extract(url: str):
    from bench.planted import WEB_PAGES
    from tools.toolspec import ToolError

    page = WEB_PAGES.get(str(url or "").strip().rstrip("/"))
    if page is None:
        raise ToolError(f"could not fetch {url}: the page did not load")
    return page
