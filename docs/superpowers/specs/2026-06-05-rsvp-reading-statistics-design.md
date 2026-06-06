# Spec 3: Reading Statistics

**Date:** 2026-06-05
**Status:** Draft (awaiting user review)
**Scope:** Spec 3 — first feature spec (1 of 5 from the original code review's feature list)
**Branch:** `feature/reading-statistics` (off main)
**Target PR:** Single PR with 3 atomic commits

## Context

The original code review listed 5 features: reading statistics, theme presets,
text-to-speech, settings export/import, and chunk mode. Per the brainstorming
decomposition, each is a separate spec. This spec covers reading statistics
only. The other 4 features will follow in their own cycles.

## Scope

**In scope (Spec 3 — this document):**

| # | Item |
|---|------|
| 1 | New `StatsManager` and data model (`SessionRecord`, `DocumentStats`, `AllTimeStats`, `StatsData`) in `rsvp/core/stats.py` |
| 2 | Engine signal integration via `StatsRecorder` so sessions are captured automatically as the user reads |
| 3 | Modal "Reading Statistics" dialog (`rsvp/ui/stats_dialog.py`) opened from a new "View → Statistics" menu item |
| 4 | Tests for stats accumulation, persistence, and dialog rendering |
| 5 | CHANGELOG entry under `[Unreleased]` |

**Out of scope (later specs):**

- Spec 4+ — Theme presets, text-to-speech, settings export/import, chunk mode
- Per-day trend histograms (charting without a charting lib is ugly; defer)
- "Share stats" / export-to-CSV (defer; can be added via the export/import spec)
- Cloud sync (deliberately not on the roadmap)
- Settings reset also wiping stats (intentionally separate lifecycles)

## Design Decisions (from brainstorming)

1. **UI surface:** Modal dialog opened from "View → Statistics" menu. Same
   pattern as `SettingsDialog`, `TextInputDialog`.
2. **Metric scope:** All-time totals + per-document breakdown + recent
   sessions (last 30). No per-day chart for now.
3. **Storage:** Separate `stats.json` in the same config dir as
   `settings.json`. Different lifecycle from settings (stats don't get
   wiped on settings reset).

## Data Model

```python
# rsvp/core/stats.py

@dataclass
class SessionRecord:
    """A single reading session, from load_text to pause/stop/finish."""
    source: str | None         # file path, URL, or None for paste/clipboard
    source_type: str           # "file" | "url" | "paste" | "clipboard"
    started_at: datetime
    ended_at: datetime
    words_read: int
    avg_wpm: float             # words_read / (duration_minutes)
    peak_wpm: int
    finished: bool             # True if engine emitted "finished" signal

@dataclass
class DocumentStats:
    """Aggregated stats for a single source (file/URL)."""
    source: str
    source_type: str
    words_read: int
    total_time_seconds: float
    sessions_count: int
    last_read: datetime

@dataclass
class AllTimeStats:
    """Totals across all time."""
    total_words_read: int = 0
    total_time_seconds: float = 0.0
    sessions_count: int = 0

    @property
    def lifetime_avg_wpm(self) -> float:
        if self.total_time_seconds <= 0:
            return 0.0
        return self.total_words_read / (self.total_time_seconds / 60.0)

@dataclass
class StatsData:
    """Top-level container persisted to stats.json."""
    all_time: AllTimeStats
    per_document: dict[str, DocumentStats]   # keyed by source
    recent_sessions: list[SessionRecord]     # most recent first, max 30
```

## Recording Mechanism

A new `StatsRecorder` class subscribes to `RSVPEngine` signals and feeds
session records to `StatsManager`. Pattern mirrors `DocumentLoader` (also
takes the engine and a settings-like collaborator).

**Engine signals used:**
- `word_changed` — increment words-read count
- `state_changed` — detect play/pause transitions to start/stop the session
- `progress_changed` — track peak WPM (compared to current `engine.wpm`)
- `finished` — mark the session as finished=True

**Session lifecycle:**
1. `RSVPEngine.load_text()` is called → `StatsRecorder` ends any active
   session (finalizing it as a `SessionRecord` if words were consumed)
2. `RSVPEngine.play()` after a load → start a new session
3. `RSVPEngine.pause()` or `RSVPEngine.stop()` → end the active session
4. `RSVPEngine.finished` signal → end the active session with `finished=True`
5. Words counted via the `word_changed` signal; a session with 0 words
   is dropped (not recorded)

**Zero-words and zero-duration guards:**
- Sessions with `words_read == 0` are not recorded (avoids noise from
  instant pause / accidental load)
- Sessions with `ended_at == started_at` are not recorded (no time elapsed)

**Peak WPM:** sampled from the `wpm` property whenever the engine emits
`word_changed`. The max across the session is the `peak_wpm`.

**Source identification:** the recorder tracks `current_source` (str | None)
and `current_source_type` (str). MainWindow sets these via
`StatsRecorder.set_source(source, source_type)` when a document is loaded.

## Storage

**File:** `{config_dir}/stats.json` (same dir as `settings.json`)

**Format:** JSON with `dataclasses.asdict()` for serialization. ISO 8601
strings for `datetime` fields (custom encoder/decoder).

**Backup on corruption:** Same pattern as settings — if JSON parsing
fails, copy to `stats.json.bak`, reset to defaults, and expose
`was_reset()` for UI notification (analogous to `SettingsManager`).

**Recent sessions cap:** 30 entries. New sessions are inserted at
position 0; the list is truncated to 30 on every write.

**Per-document cap:** unbounded (one entry per distinct source). For a
personal reader this is fine; in practice a single user will accumulate
dozens-to-hundreds of files over years.

## UI

**Menu item:** `Help → Reading Statistics` (sits next to "Keyboard Shortcuts" and "About").

> Note: the brainstorming decision said "View → Statistics", but the
> existing Help menu is the natural home for read-only information dialogs
> (Shortcuts, About). The "View" menu is for view toggles (always on top,
> fullscreen). Switching to Help is a small UX improvement.

**Dialog layout (3 sections in a vertical splitter):**

```
+---------------------------------------+
|  Reading Statistics              [X]  |
+---------------------------------------+
|  All Time                             |
|  Total words read:  142,831           |
|  Total time:        8h 23m            |
|  Sessions:          87                |
|  Lifetime avg WPM:  284               |
+---------------------------------------+
|  Top Documents (by words)             |
|  +--------+------+-------+----------+ |
|  | Source | Type | Words | Sessions | |
|  +--------+------+-------+----------+ |
|  | book.md| file |  8240 |    3     | |
|  | ...    | ...  |  ...  |   ...    | |
|  +--------+------+-------+----------+ |
+---------------------------------------+
|  Recent Sessions                      |
|  +----------+----+-----+-----+-----+ |
|  | When     |WPM |Words |Type |Done?| |
|  +----------+----+-----+-----+-----+ |
|  | 2026-... | 300 |  120|file |  Y  | |
|  | ...      | ... |  ... | ... | ... | |
|  +----------+----+-----+-----+-----+ |
+---------------------------------------+
|         [Reset Statistics...]  [Close] |
+---------------------------------------+
```

**Behavior:**
- "Close" closes the dialog (read-only, no save)
- "Reset Statistics..." opens a confirmation dialog (`QMessageBox.question`):
  "This will permanently delete all reading statistics. Continue?"
  → On yes, clear `StatsData` and save

## Architecture

```
main.py → MainWindow(settings, stats_manager)
              │
              ├─ RSVPEngine(settings)
              ├─ WordDisplayWidget(settings)
              ├─ BookmarkController(settings, ...)
              ├─ DocumentLoader(settings, ..., on_loaded=set_stats_source)
              └─ StatsRecorder(engine, stats_manager)
                     │
                     └─ StatsManager(stats.json)
```

**`MainWindow` is the composition root.** It creates:
- `SettingsManager` (existing)
- `StatsManager` (new, Spec 3)
- `RSVPEngine` (passes settings)
- `StatsRecorder` (passes engine + stats_manager)
- All child widgets (passes settings where needed)

**`DocumentLoader.on_loaded` hook** is extended: when a document is
loaded, `MainWindow._on_document_loaded` also calls
`self._stats_recorder.set_source(source, "file")` or `"url"` depending
on whether the source is a URL.

**`StatsDialog`** is constructed on demand and receives the
`StatsManager` (read-only access to the data).

## File-Level Changes

| File | Change |
|------|--------|
| `rsvp/core/stats.py` | New — dataclasses + `StatsManager` |
| `rsvp/core/stats_recorder.py` | New — engine signal subscriber |
| `rsvp/core/__init__.py` | Export `StatsManager`, `StatsData` |
| `rsvp/core/rsvp_engine.py` | No change (signals are sufficient) |
| `rsvp/ui/main_window.py` | Construct `StatsManager` + `StatsRecorder`; add menu item; create `StatsDialog` on click |
| `rsvp/ui/menu_builder.py` | Add "Help → Reading Statistics" action |
| `rsvp/ui/stats_dialog.py` | New — modal dialog with 3 sections + reset |
| `tests/test_stats.py` | New — accumulate, persist, render, reset |
| `tests/test_stats_recorder.py` | New — signal-driven session recording |
| `tests/test_ui_stats_dialog.py` | New — smoke test for dialog rendering |
| `CHANGELOG.md` | Add "Reading statistics" entry under `[Unreleased]` |
| `rsvp.spec` | No change (no new bundled files) |

## Per-Item Design

### Item 1 — `rsvp/core/stats.py`

**`StatsManager`:**

```python
class StatsManager:
    """Loads, saves, and accumulates reading statistics."""

    def __init__(self) -> None:
        self._data = StatsData(all_time=AllTimeStats(), per_document={}, recent_sessions=[])
        self._config_path = self._get_config_path()
        self._was_reset = False
        self.load()

    @property
    def data(self) -> StatsData:
        return self._data

    def record_session(self, record: SessionRecord) -> None:
        """Append a session to recent_sessions, update per-doc + all-time."""
        ...

    def reset(self) -> None:
        """Clear all data and save."""
        ...

    def was_reset(self) -> bool:
        ...

    def save(self) -> None:
        ...
```

**Key methods (pseudocode):**

```python
def record_session(self, record: SessionRecord) -> None:
    # Update all-time totals
    self._data.all_time.total_words_read += record.words_read
    self._data.all_time.total_time_seconds += (record.ended_at - record.started_at).total_seconds()
    self._data.all_time.sessions_count += 1

    # Update per-document (only if source is identifiable)
    if record.source:
        doc = self._data.per_document.get(record.source)
        if doc is None:
            doc = DocumentStats(
                source=record.source,
                source_type=record.source_type,
                words_read=0,
                total_time_seconds=0.0,
                sessions_count=0,
                last_read=record.ended_at,
            )
            self._data.per_document[record.source] = doc
        doc.words_read += record.words_read
        doc.total_time_seconds += (record.ended_at - record.started_at).total_seconds()
        doc.sessions_count += 1
        doc.last_read = record.ended_at

    # Prepend to recent_sessions, cap at 30
    self._data.recent_sessions.insert(0, record)
    self._data.recent_sessions = self._data.recent_sessions[:30]

    self.save()
```

**Datetime JSON serialization:**

```python
def _stats_to_dict(data: StatsData) -> dict:
    return {
        "all_time": asdict(data.all_time),
        "per_document": {
            src: {**asdict(d), "last_read": d.last_read.isoformat()}
            for src, d in data.per_document.items()
        },
        "recent_sessions": [
            {**asdict(s),
             "started_at": s.started_at.isoformat(),
             "ended_at": s.ended_at.isoformat()}
            for s in data.recent_sessions
        ],
    }
```

### Item 2 — `rsvp/core/stats_recorder.py`

**`StatsRecorder`:**

```python
class StatsRecorder(QObject):
    """Subscribes to RSVPEngine signals and records sessions to StatsManager."""

    def __init__(self, engine: RSVPEngine, stats_manager: StatsManager) -> None:
        super().__init__()
        self._engine = engine
        self._stats = stats_manager
        self._current_source: str | None = None
        self._current_source_type: str = "unknown"
        self._session_start: datetime | None = None
        self._words_in_session: int = 0
        self._peak_wpm: int = 0
        self._session_finished: bool = False
        self._was_playing: bool = False

        # Subscribe
        engine.word_changed.connect(self._on_word_changed)
        engine.state_changed.connect(self._on_state_changed)
        engine.finished.connect(self._on_finished)

    def set_source(self, source: str | None, source_type: str) -> None:
        """Called when MainWindow loads a new document. Ends any active session first."""
        self._end_session()
        self._current_source = source
        self._current_source_type = source_type

    def _on_word_changed(self, word: Word | None) -> None:
        if word is not None and self._was_playing:
            self._words_in_session += 1
            self._peak_wpm = max(self._peak_wpm, self._engine.wpm)

    def _on_state_changed(self) -> None:
        if self._engine.is_playing and not self._was_playing:
            self._begin_session()
        elif not self._engine.is_playing and self._was_playing:
            self._end_session()
        self._was_playing = self._engine.is_playing

    def _on_finished(self) -> None:
        self._session_finished = True
        self._end_session()

    def _begin_session(self) -> None:
        self._session_start = datetime.now()
        self._words_in_session = 0
        self._peak_wpm = self._engine.wpm
        self._session_finished = False

    def _end_session(self) -> None:
        if self._session_start is None or self._words_in_session == 0:
            self._session_start = None
            return
        ended = datetime.now()
        duration = (ended - self._session_start).total_seconds()
        if duration <= 0:
            self._session_start = None
            return
        record = SessionRecord(
            source=self._current_source,
            source_type=self._current_source_type,
            started_at=self._session_start,
            ended_at=ended,
            words_read=self._words_in_session,
            avg_wpm=self._words_in_session / (duration / 60.0),
            peak_wpm=self._peak_wpm,
            finished=self._session_finished,
        )
        self._stats.record_session(record)
        self._session_start = None
```

**Edge cases handled:**
- Loading a new document ends the previous session (via `set_source`)
- Pause ends the session
- Stop ends the session
- "finished" signal ends with `finished=True`
- Resuming play after pause starts a new session
- Closing the app while a session is active: MainWindow calls
  `stats_recorder.shutdown()` in `closeEvent` to finalize the session

### Item 3 — `rsvp/ui/stats_dialog.py`

Standard PyQt6 dialog. Three `QGroupBox` sections, two `QTableWidget`s,
two `QPushButton`s (Reset / Close). Read-only — no editing.

**Reset flow:**
1. User clicks "Reset Statistics..."
2. `QMessageBox.question` with warning text
3. On yes: `stats_manager.reset()`; re-render the dialog sections

**Testability:** the dialog takes `StatsManager` via constructor (DI from Spec 2
pattern). Tests construct the manager with an in-memory `StatsData` and verify
the dialog renders the right numbers.

### Item 4 — Tests

**`tests/test_stats.py`** — pure logic:
- `test_record_session_updates_all_time`
- `test_record_session_creates_per_document_entry`
- `test_record_session_updates_existing_per_document_entry`
- `test_recent_sessions_capped_at_30`
- `test_recent_sessions_most_recent_first`
- `test_lifetime_avg_wpm_zero_when_no_time`
- `test_lifetime_avg_wpm_correct`
- `test_persistence_round_trip` (save → load → equal data)
- `test_corrupt_file_resets_to_defaults` (with backup)
- `test_reset_clears_data`

**`tests/test_stats_recorder.py`** — signal-driven:
- `test_begin_session_on_play`
- `test_end_session_on_pause`
- `test_session_dropped_when_zero_words`
- `test_session_dropped_when_zero_duration`
- `test_finished_session_marked_finished`
- `test_set_source_ends_active_session`
- `test_word_changed_increments_count`
- `test_peak_wpm_tracked`

**`tests/test_ui_stats_dialog.py`** — smoke:
- `test_dialog_renders_with_empty_stats`
- `test_dialog_renders_with_populated_stats`
- `test_reset_button_clears_data` (with `QMessageBox.question` patched to return Yes)

## Commit Plan (3 atomic commits)

```
feat: add reading statistics — core data model and StatsManager
feat: add StatsRecorder — engine signal integration for session tracking
feat: add reading statistics dialog and menu item
```

**Rationale for ordering:**
1. **Data model first:** StatsManager + dataclasses are pure logic, no
   Qt dependencies. Easiest to review and test in isolation.
2. **Recorder second:** Wires the data model to the engine via signals.
   Depends on StatsManager; doesn't depend on UI.
3. **Dialog third:** Wires the data model to the UI. Depends on
   StatsManager; doesn't depend on Recorder.

**CHANGELOG entry** is added as part of commit 1 (the most
user-visible thing in the spec is the feature itself; documenting
its existence belongs with the data model).

## Testing Strategy

- 273 existing tests + ~21 new (10 stats + 8 recorder + 3 dialog) = 294
- All tests use the existing `tmp_path` / `qapp` fixtures
- `StatsManager` tests bypass `__init__` via `__new__` + manual attrs
  (same pattern as SettingsManager tests after Spec 2)
- `StatsRecorder` tests use the real `RSVPEngine` (it's already cheap
  to construct and well-tested)

## Risk and Mitigation

| Risk | Mitigation |
|------|------------|
| Recording overhead in the hot word-display path | Only an integer increment and a max comparison per word; no I/O. Bounded. |
| Stats file grows unbounded over years | Per-doc dict grows slowly (one entry per distinct source). Recent sessions cap at 30. Acceptable. |
| Closing the app while a session is active loses the in-progress session | MainWindow's `closeEvent` calls `stats_recorder.shutdown()` to finalize. Tested. |
| Datetime serialization breaks across Python versions | ISO 8601 strings via `datetime.isoformat()` / `fromisoformat()` — standard, portable. |
| `word_changed` fires on initial load with the first word before play | `_begin_session` resets `words_in_session = 0`; only counts after play starts. |
| User wants to keep stats when resetting settings | Stats are intentionally separate (different file, different lifecycle). |
| `recent_sessions` could grow to 30 in one test run, masking cap behavior | Test exercises 31 inserts and asserts the cap. |

## Out of Scope (Explicitly)

- Per-day trend chart (requires a charting library or a hand-rolled text histogram; defer)
- CSV / JSON export of stats (defer to settings export/import spec)
- Cloud sync
- "Achievement" / milestone notifications (e.g., "you've read 1M words!")
- Per-paragraph or per-sentence WPM breakdowns
- Heatmap / streak tracking
- Stats backup before destructive actions (relies on JSON file copy)
- Stats reset wiping settings, or vice versa (intentionally separate)

## Success Criteria

- [ ] `StatsManager` persists to `stats.json` in the platform-specific config dir
- [ ] Engine load → play → pause → play → stop sequence records 2 sessions
- [ ] Recent sessions list is capped at 30, most recent first
- [ ] Per-document stats aggregate correctly across multiple sessions
- [ ] "Help → Reading Statistics" menu item opens the dialog
- [ ] Dialog shows all-time totals, top documents (by words), and recent sessions
- [ ] "Reset Statistics..." button clears data after confirmation
- [ ] `pytest -q` passes (~294 tests, 21 new)
- [ ] `ruff check rsvp/ tests/` passes
- [ ] `mypy rsvp/` passes
- [ ] `rg "except Exception" rsvp/` returns no matches
- [ ] CHANGELOG entry under `[Unreleased]` mentions the new feature
- [ ] All 3 items above landed in the named atomic commits
- [ ] `rsvp/core/stats.py` and `rsvp/ui/stats_dialog.py` have no new bare excepts
