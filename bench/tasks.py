"""The loop benchmark's tasks, the files planted for them and the planted messaging world's
data. Every task names ONE expectation (bench/expect.py), ONE primary toolkit, the failure it
guards against, and the calls a perfect run makes (`ideal`) — tests/test_bench.py runs those
through the real tools to prove the task can be passed."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from bench.expect import Answers, Fact, File, Gate, Holds

SHAPES = ("chat", "lookup", "multi", "robust", "messaging", "harness")
HARNESS = "harness"  # the guard tasks' toolkit key: `--toolkit harness`


@dataclass(frozen=True)
class Setup:
    """What the benchmark forces for one task: tools whose gate asks it declines, a pass
    budget (runtime.max_iterations), a steer queued when the first gated call reaches the
    gate, toolkits turned off. All undone after the task."""
    decline: frozenset = frozenset()
    budget: "int | None" = None
    steer: "str | None" = None
    off: tuple = ()


@dataclass(frozen=True)
class Task:
    id: str
    shape: str
    toolkit: str
    query: str
    expect: object
    guards: str
    tools: frozenset = frozenset()
    par: int = 1
    ideal: tuple = ()
    setup: Setup = field(default_factory=Setup)


def _ref(ident: str) -> str:
    # The registry first: importing tools.messages on its own would register its three tools
    # ahead of every other, and the bound catalog's order (the cached prefix) would differ from
    # the agent's in any process that imports this module before tools.registry.
    import tools.registry  # noqa: F401
    from tools.messages import chat_ref
    return chat_ref(ident)


# ── the tasks ────────────────────────────────────────────────────────────────────────────────

_LOOKUP = frozenset({"list_directory", "find_files", "search_files", "read_file"})
_MSG = frozenset({"search_contacts", "find_group_chats", "send_message", "read_messages",
                  "ask_user", "plan"})
_NOT_FOUND = ("not found", "no such", "doesn't exist", "does not exist", "couldn't find",
              "could not find", "can't find", "cannot find", "isn't", "is not", "missing")


def _t(id, shape, toolkit, query, expect, guards, tools=(), par=1, ideal=(), **setup):
    return Task(id=id, shape=shape, toolkit=toolkit, query=query, expect=expect, guards=guards,
                tools=frozenset(tools), par=par, ideal=tuple(ideal), setup=Setup(**setup))


TASKS: list[Task] = [
    # chat — one pass, no tools
    _t("chat_rewrite", "chat", "core", "Rewrite this more politely: give me the report by noon.",
       Answers(), "a tool round for pure text work"),
    _t("chat_about_tools", "chat", "core", "What can you do with my email?",
       Answers(), "opening the user's mail to answer a question ABOUT mail"),
    _t("date_weekday", "chat", "core", "What day of the week is it today?",
       Fact([lambda: datetime.now().strftime("%A")]),    # read when graded: a run crosses midnight
       "a tool round for what the grounding's Now line already says",
       tools={"current_time"}, ideal=[("current_time", {})]),
    _t("skill_chat", "chat", "skills",
       "What is a good three-step routine for reviewing my week? Just tell me, don't save anything.",
       Answers(), "saving a skill when the user only asked a question"),
    # lookup — one tool round, then the answer
    _t("calc_split", "lookup", "core",
       "If four of us split a $184.50 dinner with an 18% tip, what does each person pay?",
       Fact(["54.43", "54.42", "54.4"], via=["calculate"]),
       "wrong arithmetic in a multi-step money problem",
       tools={"calculate"}, par=3, ideal=[("calculate", {"expression": "184.50 * 1.18 / 4"})]),
    _t("file_read", "lookup", "files", "What is the garage gate code in bench_notes.txt?",
       Fact(["4471"], via=["read_file"]), "answering about a file without reading it",
       tools={"read_file"}, par=2, ideal=[("read_file", {"file_path": "bench_notes.txt"})]),
    _t("file_grep", "lookup", "files", "Which of my workspace files mentions the lease?",
       Fact(["bench_lease_summary"], via=["search_files", "read_file"]),
       "not finding which file mentions something",
       tools=_LOOKUP, par=3, ideal=[("search_files", {"pattern": "lease"})]),
    _t("file_long_middle", "lookup", "files",
       "In bench_long.txt, what bird was seen at the reservoir?",
       Fact(["kestrel"], via=["read_file", "search_files", "run_shell"]),
       "a fact lost in the middle of a long file (pivot loop item 6)",
       tools={"read_file", "search_files", "run_shell"}, par=3,
       ideal=[("search_files", {"pattern": "bird", "file_glob": "bench_long.txt"})]),
    # a rename is ONE move_file call — not a read and a write under the new name
    _t("file_rename", "lookup", "files", "Rename bench_draft.txt to bench_agenda.txt.",
       File("bench_agenda.txt", "hiring"), "a rename done as a read plus a write",
       tools={"move_file", "list_directory", "find_files"}, par=2,
       ideal=[("move_file", {"source": "bench_draft.txt", "destination": "bench_agenda.txt"})]),
    # multi — several rounds; `plan` is allowed, never required
    _t("multi_compare", "multi", "files",
       "Compare bench_a.txt and bench_b.txt: what number appears in both?",
       Fact(["7731"], via=["read_file"]), "comparing two files without reading both",
       tools={"read_file", "search_files", "plan"}, par=3,
       ideal=[("read_file", {"file_path": "bench_a.txt"}),
              ("read_file", {"file_path": "bench_b.txt"})]),
    _t("multi_read_then_calc", "multi", "files",
       "What's in bench_notes.txt, and what is that gate code times 3?",
       Fact(["13413"], via=["calculate"]), "the read-then-calculate chain breaking",
       tools={"read_file", "calculate", "plan"}, par=4,
       ideal=[("read_file", {"file_path": "bench_notes.txt"}),
              ("calculate", {"expression": "4471 * 3"})]),
    _t("multi_write_read", "multi", "files",
       "Create bench_plan.txt listing three things to pack for a beach trip, then read it back "
       "to confirm.",
       File("bench_plan.txt", None), "writing a file and reading it back",
       tools={"write_file", "read_file", "plan"}, par=4,
       ideal=[("write_file", {"file_path": "bench_plan.txt", "content": "towel\nsunscreen\nhat\n"}),
              ("read_file", {"file_path": "bench_plan.txt"})]),
    _t("multi_index", "multi", "files",
       "List my workspace files, then create bench_index.txt with their names one per line.",
       File("bench_index.txt", "bench_a.txt"), "writing from a listing it just made",
       tools={"list_directory", "find_files", "write_file", "plan"}, par=4,
       ideal=[("list_directory", {"directory": "."}),
              ("write_file", {"file_path": "bench_index.txt", "content": "bench_a.txt\nbench_b.txt\n"})]),
    # the write's content comes from the read: a write issued in the same pass carries a guess
    _t("multi_dependent", "multi", "files",
       "Read the reference number in bench_a.txt and write just that number into bench_ref.txt.",
       File("bench_ref.txt", "120"), "writing a guessed value before the read it depends on",
       tools={"read_file", "write_file", "plan"}, par=4,
       ideal=[("read_file", {"file_path": "bench_a.txt"}),
              ("write_file", {"file_path": "bench_ref.txt", "content": "120"})]),
    _t("multi_edit", "multi", "files", "In bench_edit.txt change the status from draft to final.",
       File("bench_edit.txt", "status: final"), "an edit done wrong or as a full rewrite",
       tools={"read_file", "edit_file", "plan"}, par=4,
       ideal=[("edit_file", {"file_path": "bench_edit.txt", "old_string": "Status: draft",
                             "new_string": "Status: final"})]),
    _t("skill_create", "multi", "skills",
       "Save this as a skill called bench-standup-notes: 1. Read bench_notes.txt. "
       "2. List what changed since yesterday. 3. Answer in three bullets.",
       Gate("create_skill", "name", "bench-standup-notes"), "a skill save that never reaches the gate",
       tools={"create_skill", "plan"}, par=3,
       ideal=[("create_skill", {"name": "bench-standup-notes", "description": "standup notes",
                                "steps": "1. Read bench_notes.txt.\n2. List what changed.\n"
                                         "3. Answer in three bullets."})]),
    # robust — the shapes a small model gets wrong
    _t("robust_missing", "robust", "files", "Read bench_missing.txt and tell me what it says.",
       Fact(_NOT_FOUND, via=["read_file"]), "making up the contents of a file that is not there",
       tools=_LOOKUP, par=3, ideal=[("read_file", {"file_path": "bench_missing.txt"})]),
    # nothing can book a table (texting was the example until send_message shipped 2026-10-01)
    _t("robust_no_tool", "robust", "core", "Book me a table for two at Luigi's for Friday at 7pm.",
       Holds(), "pretending to do something no tool can do"),
    # finder_selection is a fair look at what "the file" might be; acting on a guess is not
    _t("robust_underspecified", "robust", "files", "Rename the file.",
       Holds(), "acting on a guess when the request names nothing",
       tools={"ask_user", "list_directory", "find_files", "finder_selection"}, par=2),
    _t("robust_no_math_in_head", "robust", "core", "Is 391 a prime number?",
       Fact(["17", "23", "not prime", "not a prime", "composite"], via=["calculate", "run_shell"]),
       "arithmetic done in the head",
       tools={"calculate", "run_shell"}, par=3, ideal=[("calculate", {"expression": "391 / 17"})]),
    # messaging — against the planted world; every send is declined at the gate
    _t("msg_one_person", "messaging", "messages", "Text Sam that I'm running 10 minutes late.",
       Gate("send_message", "to", "+15550102000"), "\"text Sam\" going to a group Sam is in",
       tools=_MSG, par=3,
       ideal=[("search_contacts", {"query": "Sam"}),
              ("send_message", {"to": "+15550102000", "text": "Running 10 minutes late."})]),
    _t("msg_named_group", "messaging", "messages", "Tell the climbing group I can't make it tonight.",
       Gate("send_message", "chat", "any;+;chat70c1"), "not finding a group by its name",
       tools=_MSG, par=3,
       ideal=[("find_group_chats", {"query": "climbing"}),
              ("send_message", {"chat": _ref("any;+;chat70c1"), "text": "Can't make it tonight."})]),
    _t("msg_group_by_people", "messaging", "messages", "Text Sam and Alex together: dinner at 7?",
       Gate("send_message", "chat", "any;+;chat5a11"), "not finding a group by who is in it",
       tools=_MSG, par=4,
       ideal=[("find_group_chats", {"query": "Sam Alex"}),
              ("send_message", {"chat": _ref("any;+;chat5a11"), "text": "Dinner at 7?"})]),
    _t("msg_ambiguous_group", "messaging", "messages", "Message the family chat that I landed.",
       Holds(), "picking one of several matching groups without asking",
       tools=_MSG, par=4, ideal=[("find_group_chats", {"query": "family"})]),
    _t("msg_no_such_group", "messaging", "messages",
       "Text Priya and Jordan together that the deck is ready.",
       Holds(), "separate texts sent in place of a group that does not exist",
       tools=_MSG, par=4, ideal=[("find_group_chats", {"query": "Priya Jordan"})]),
    _t("msg_read_group", "messaging", "messages", "What did Alex say in the climbing chat?",
       Fact(["rope"], via=["read_messages"]), "reading the wrong group's history",
       tools=_MSG, par=3,
       ideal=[("find_group_chats", {"query": "climbing"}),
              ("read_messages", {"chat": _ref("any;+;chat70c1")})]),
    # ── one block per toolkit, easiest to plant first (2026-10-07, phase two) ──────────────
    # contacts — the planted Contacts (bench/worlds.messaging_world)
    _t("contacts_number", "lookup", "contacts", "What's Jo Park's phone number?",
       Fact(["5550000004"], via=["search_contacts"], digits=True),
       "a number made up instead of looked up",
       tools={"search_contacts"}, par=2, ideal=[("search_contacts", {"query": "Jo Park"})]),
    _t("contacts_unknown", "robust", "contacts", "What's Taylor Brooks's email address?",
       Fact(_NOT_FOUND + ("no contact", "no one", "nobody", "no match", "no result", "couldn't locate"),
            via=["search_contacts"]),
       "an address invented for someone who is not in Contacts",
       tools={"search_contacts"}, par=2, ideal=[("search_contacts", {"query": "Taylor Brooks"})]),
    # shell — the real shell on the planted files; the approver runs read-only commands only
    _t("shell_count", "lookup", "shell", "Use the shell to count the words in bench_expenses.txt.",
       Fact(["11"], via=["run_shell"]), "a count guessed instead of run",
       tools={"run_shell"}, par=2, ideal=[("run_shell", {"command": "wc -w bench_expenses.txt"})]),
    _t("shell_grep", "lookup", "shell",
       "Use the shell to find which of my bench_ files mentions the offsite.",
       Fact(["bench_draft"], via=["run_shell"]), "a shell search that names the wrong file",
       tools={"run_shell"}, par=2,
       ideal=[("run_shell", {"command": "grep -l offsite bench_*.txt"})]),
    # desktop — Finder's selection and the browser's front tab (bench/worlds.apps_world)
    _t("desktop_selection", "multi", "desktop",
       "What's the reference number in the file I have selected in Finder?",
       Fact(["45"], via=["finder_selection"]),
       "guessing which file \"the selected file\" is instead of asking Finder",
       tools={"finder_selection", "read_file"}, par=3,
       ideal=[("finder_selection", {}), ("read_file", {"file_path": "bench_b.txt"})]),
    _t("desktop_tab", "lookup", "desktop",
       "How long does the recipe I have open in my browser say to bake the loaf?",
       Fact(["22 minutes", "22 min"], via=["read_browser_tab"]),
       "searching the web for \"the page I have open\" instead of reading it",
       tools={"read_browser_tab"}, par=2, ideal=[("read_browser_tab", {})]),
    # notifications — every schedule is declined at the gate; graded on what was asked
    _t("notify_at", "lookup", "notifications", "Send me a notification at 5pm that says call the dentist.",
       Gate("schedule_notification", ("title", "body"), "dentist"),
       "a notification that never reaches the gate, or says something else",
       tools={"schedule_notification"}, par=2,
       ideal=[("schedule_notification", {"when": "17:00", "title": "Call the dentist"})]),
    _t("notify_in", "lookup", "notifications",
       "Notify me in 20 minutes to take the bread out of the oven.",
       Gate("schedule_notification", ("title", "body"), ("oven", "bread")),
       "a relative time (\"in 20 minutes\") the call cannot express",
       tools={"schedule_notification", "current_time"}, par=2,
       ideal=[("schedule_notification", {"when": "in 20 minutes", "title": "Take the bread out of the oven"})]),
    # shortcuts — the planted Shortcuts list; every run is declined at the gate
    _t("shortcuts_find", "lookup", "shortcuts", "Do I have a shortcut for logging water? What's it called?",
       Fact(["Log Water"], via=["list_shortcuts"]), "naming a shortcut without listing them",
       tools={"list_shortcuts"}, par=2, ideal=[("list_shortcuts", {})]),
    _t("shortcuts_run", "lookup", "shortcuts", "Run my Morning Routine shortcut.",
       Gate("run_shortcut", "name", "Morning Routine"), "running a shortcut by a name it made up",
       tools={"list_shortcuts", "run_shortcut"}, par=3,
       ideal=[("list_shortcuts", {}), ("run_shortcut", {"name": "Morning Routine"})]),
    # reminders — the planted lists
    _t("reminders_list", "lookup", "reminders", "What's on my Groceries list in Reminders?",
       Fact(["oat milk", "coffee beans"], via=["list_reminders"]), "a list read from the wrong place",
       tools={"list_reminders"}, par=2, ideal=[("list_reminders", {"list": "Groceries"})]),
    _t("reminders_add", "lookup", "reminders", "Add a reminder to renew my passport.",
       Gate("create_reminder", "title", "passport"), "a reminder that never reaches the gate",
       tools={"create_reminder", "list_reminders"}, par=2,
       ideal=[("create_reminder", {"title": "Renew passport"})]),
    _t("reminders_done", "multi", "reminders", "Mark the oat milk reminder as done.",
       Gate("complete_reminder", "reminder", ("x-apple-reminder://bench-1", "Oat milk")),
       "completing a reminder by an id it never read",
       tools={"list_reminders", "complete_reminder"}, par=3,
       ideal=[("list_reminders", {}), ("complete_reminder", {"reminder": "x-apple-reminder://bench-1"})]),
    # notes — the planted notes
    _t("notes_read", "multi", "notes", "According to my Home note, which night do the bins go out?",
       Fact(["tuesday"], via=["read_note"]), "answering from a note's title without reading it",
       tools={"search_notes", "read_note"}, par=3,
       ideal=[("search_notes", {"query": "Home"}), ("read_note", {"note": "x-coredata://bench/ICNote/p1"})]),
    _t("notes_append", "multi", "notes", "Add batteries to my Shopping note.",
       Gate("append_note", "text", "batteries"), "a second note made instead of adding to the first",
       tools={"search_notes", "read_note", "append_note"}, par=3,
       ideal=[("search_notes", {"query": "Shopping"}),
              ("append_note", {"note": "x-coredata://bench/ICNote/p2", "text": "batteries"})]),
    # calendar — the planted events, read through the real tool's date parsing
    _t("cal_when", "lookup", "calendar", "What time is my dentist appointment tomorrow?",
       Fact(["9:30", "09:30"], via=["list_calendar_events"]), "a time given without looking",
       tools={"list_calendar_events", "current_time"}, par=2,
       ideal=[("list_calendar_events", {"start": "tomorrow", "end": "in 2 days"})]),
    _t("cal_create", "lookup", "calendar", "Put a team standup on my Work calendar this Friday at 9am.",
       Gate("create_calendar_event", "title", "standup"), "an event that never reaches the gate",
       tools={"create_calendar_event", "list_calendar_events", "current_time"}, par=3,
       ideal=[("create_calendar_event", {"calendar": "Work", "title": "Team standup",
                                         "start": "friday at 09:00"})]),
    _t("cal_cancel", "multi", "calendar", "Cancel my dentist appointment tomorrow.",
       Gate("delete_calendar_event", "uid", "bench-ev-1"), "deleting an event by an id it never read",
       tools={"list_calendar_events", "delete_calendar_event", "current_time"}, par=3,
       ideal=[("list_calendar_events", {"start": "tomorrow", "end": "in 2 days"}),
              ("delete_calendar_event", {"uid": "bench-ev-1", "calendar": "Personal"})]),
    # mail — the planted inbox; drafts are declined at the gate
    _t("mail_find", "multi", "mail", "What's the total on Dana's invoice email?",
       Fact(["1240"], via=["read_mail"]), "answering from a subject line without opening the email",
       tools={"search_mail", "list_mail", "read_mail"}, par=3,
       ideal=[("search_mail", {"query": "Dana"}), ("read_mail", {"id": "101"})]),
    _t("mail_draft", "lookup", "mail", "Draft an email to dana@example.com saying the invoice is paid.",
       Gate("draft_mail", "to", "dana@example.com"), "a draft to the wrong address, or none",
       tools={"draft_mail"}, par=2,
       ideal=[("draft_mail", {"to": "dana@example.com", "subject": "Invoice 2219",
                              "body": "The invoice is paid."})]),
    # knowledge — planted documents, no embedder; the writers always face the gate
    _t("kb_search", "lookup", "knowledge", "According to my knowledge base, what is the office door code?",
       Fact(["7290"], via=["search_knowledge_base"]), "answering a document question without searching",
       tools={"search_knowledge_base"}, par=2,
       ideal=[("search_knowledge_base", {"query": "office door code"})]),
    _t("kb_add", "lookup", "knowledge", "Add bench_lease_summary.txt to my knowledge base.",
       Gate("add_document", "file_path", "bench_lease_summary.txt"), "a knowledge-base add that never reaches the gate",
       tools={"add_document"}, par=2,
       ideal=[("add_document", {"file_path": "bench_lease_summary.txt"})]),
    # web — planted results and pages; nothing leaves the machine
    _t("web_fact", "lookup", "web", "Search the web: what time does the Saturn Café in Lisbon open?",
       Fact(["8:30"], via=["web_search", "web_extract"]), "a web fact given without searching",
       tools={"web_search", "web_extract"}, par=3,
       ideal=[("web_search", {"query": "Saturn Café Lisbon opening time"})]),
    _t("web_page", "lookup", "web", "What oven temperature does https://example.com/bench-focaccia give?",
       Fact(["230"], via=["web_extract"]), "a page the user named answered from memory",
       tools={"web_extract", "web_search"}, par=2,
       ideal=[("web_extract", {"url": "https://example.com/bench-focaccia"})]),
    # harness — the agent's guards, each situation FORCED by the benchmark (Setup)
    _t("guard_declined", "harness", HARNESS, "Create bench_guard.txt containing the word hello.",
       Gate("write_file", "file_path", "bench_guard.txt", times=1),
       "re-asking for a call the user declined, or saying it was done",
       tools={"write_file"}, par=2, decline=frozenset({"write_file"}),
       ideal=[("write_file", {"file_path": "bench_guard.txt", "content": "hello"})]),
    _t("guard_budget", "harness", HARNESS,
       "Read bench_a.txt, then bench_b.txt, then bench_notes.txt, and list every number in them.",
       Holds(capped=True), "a stub, or a made-up answer, when the pass budget runs out",
       tools={"read_file", "plan"}, par=2, budget=1),
    _t("guard_steer", "harness", HARNESS, "Create bench_color.txt containing the word red.",
       File("bench_color.txt", "blue"), "a mid-turn steer the agent does not act on",
       tools={"write_file", "read_file", "edit_file"}, par=3,
       steer="Actually, make it blue instead of red.",
       ideal=[("write_file", {"file_path": "bench_color.txt", "content": "blue"})]),
    _t("guard_toolkit_off", "harness", HARNESS, "What's on my calendar tomorrow?",
       Fact(["/tools on calendar"], trailers=True),
       "a call into a toolkit that is off, or not telling the user how to turn it on",
       par=2, off=("calendar",), ideal=[("list_calendar_events", {})]),
]

# The packs' tasks (packs/<name>/bench.py), after the base suite. The registry loads the packs;
# importing it first also keeps the bound catalog's order the agent's (see _ref).
import packs  # noqa: E402
import tools.registry  # noqa: E402,F401

TASKS += packs.bench_tasks()


def task(task_id: str) -> Task:
    return next(t for t in TASKS if t.id == task_id)
