"""
Each respondent's survey with the AI assistant as the owner's web view shows it: the
chat, the assistant's edits and everything the respondent did, in one order.

Built from three downloads: the interaction trace, which gives the order, the
messages, which give the text, and the edits, which give the ones the trace can't have
(rejected, or never reported by the browser).
"""

from typing import Any, Dict, Iterable, List, Optional, Tuple

# Every row has these, then its kind's own fields.
COMMON_FIELDS = (
    "response_uuid",
    "is_preview",
    "position",
    "kind",
    "at",
    "page_id",
    "turn",
    "session",
    "seq",
    "placed",
)

KIND_FIELDS: Dict[str, Tuple[str, ...]] = {
    "page_shown": ("page_key",),
    "page_submitted": ("page_key",),
    "answer": (
        "question",
        "value",
        "draft_type",
        "draft_version",
        "saved",
        "changes",
        "draft_write",
        "value_omitted",
        "chars",
    ),
    "message": ("text",),
    "message_refused": ("refused",),
    "assistant_edit": (
        "edit",
        "question",
        "value",
        "draft_type",
        "draft_version",
        "outcome",
        "reason",
        "draft_write",
    ),
    "edit_undone": ("edit", "question", "value"),
    "edit_rejected": (
        "edit",
        "question",
        "value",
        "draft_type",
        "draft_version",
        "rejection",
    ),
    "reply": ("text", "status", "ended", "error_kind", "notice"),
    "not_recorded": ("question", "rejected_type", "reason", "chars"),
}

# The assistant's rows that follow a message before its reply, when a reply has to
# be placed without the trace.
_AFTER_MESSAGE = ("assistant_edit", "edit_undone")


class _Turn:
    """One turn's text and edits, from the messages and edits downloads."""

    def __init__(self) -> None:
        self.message: Optional[dict] = None
        self.texts: List[dict] = []
        self.notice: Optional[dict] = None
        self.last: Optional[dict] = None
        self.sent: List[dict] = []
        self.rejected: List[dict] = []

    def reply_fields(self) -> Dict[str, Any]:
        """The reply's text and how the server finished it; nulls for a turn not
        listed yet."""
        if self.last is None:
            return {"text": None, "status": None, "notice": None, "error_kind": None}
        if self.notice is not None:
            status = "failed"
        elif any(part["status"] == "interrupted" for part in self.texts):
            status = "interrupted"
        else:
            status = "complete"
        return {
            "text": (
                "".join(part["text"] for part in self.texts) if self.texts else None
            ),
            "status": status,
            "notice": self.notice["text"] if self.notice else None,
            "error_kind": self.notice["error_kind"] if self.notice else None,
        }


class AssistantConversations:
    """Builds the rows of ``Coop.get_all_human_survey_assistant_conversations``."""

    @staticmethod
    def build(
        interactions: List[dict], messages: List[dict], edits: List[dict]
    ) -> List[dict]:
        """Every response's rows, responses in the order their first session began,
        each response's in ``position`` order."""
        trace: Dict[str, List[dict]] = {}
        for row in interactions:
            trace.setdefault(row["response_uuid"], []).append(row)
        turns: Dict[str, Dict[str, _Turn]] = {}
        for row in messages:
            turn = turns.setdefault(row["response_uuid"], {}).setdefault(
                row["turn"], _Turn()
            )
            turn.last = row
            if row["kind"] == "respondent_message":
                turn.message = row
            elif row["kind"] == "assistant_text":
                turn.texts.append(row)
            elif row["kind"] == "notice":
                turn.notice = row
        for edit in edits:
            turn = turns.setdefault(edit["response_uuid"], {}).setdefault(
                edit["turn"], _Turn()
            )
            (
                turn.rejected if edit["server_outcome"] == "rejected" else turn.sent
            ).append(edit)
        by_edit = {edit["edit"]: edit for edit in edits}

        responses = list(dict.fromkeys([*trace, *turns]))
        responses.sort(
            key=lambda uuid: AssistantConversations.first_started(trace.get(uuid))
        )
        out = []
        for uuid in responses:
            rows = AssistantConversations.response(
                trace.get(uuid, []), turns.get(uuid, {}), by_edit
            )
            for position, row in enumerate(rows):
                row["position"] = position
                out.append(AssistantConversations.shape(row))
        return out

    @staticmethod
    def first_started(rows: Optional[List[dict]]) -> Tuple[int, str]:
        """A response's sort key: when its first session began; after those, ones
        with no trace, in the order they were listed."""
        started = [
            row["session_started_at"]
            for row in rows or []
            if row.get("session_started_at")
        ]
        return (0, min(started)) if started else (1, "")

    @staticmethod
    def ordered(rows: List[dict]) -> List[dict]:
        """A response's trace in the order it happened: by when each session began,
        then within one by ``seq``. A session with no start goes last."""
        return sorted(
            rows,
            key=lambda row: (
                row.get("session_started_at") is None,
                row.get("session_started_at") or "",
                row["session"],
                row["seq"],
            ),
        )

    @staticmethod
    def response(
        trace: List[dict], turns: Dict[str, _Turn], by_edit: Dict[str, dict]
    ) -> List[dict]:
        """One response's rows, the trace first, then what only the other downloads
        hold placed into it."""
        rows: List[dict] = []
        reported = set()
        for event in AssistantConversations.ordered(trace):
            row = AssistantConversations.from_trace(event, turns, by_edit)
            if event["type"] in ("assistant.edit_applied", "assistant.edit_skipped"):
                reported.add(event["edit"])
            rows.append(row)

        for turn_uuid, turn in turns.items():
            AssistantConversations.place_turn(rows, turn_uuid, turn, reported)
        return rows

    @staticmethod
    def from_trace(
        event: dict, turns: Dict[str, _Turn], by_edit: Dict[str, dict]
    ) -> dict:
        """A trace row as a conversation row."""
        row: Dict[str, Any] = {
            "response_uuid": event["response_uuid"],
            "is_preview": event["is_preview"],
            "at": event["at"],
            "page_id": event["page_id"],
            "turn": None,
            "session": event["session"],
            "seq": event["seq"],
            "placed": "trace",
        }
        kind = event["type"]
        if kind in ("page.shown", "page.submitted"):
            row.update(
                kind="page_shown" if kind == "page.shown" else "page_submitted",
                page_key=event["page_key"],
            )
        elif kind == "form.edited":
            row.update(
                kind="answer",
                question=event["question"],
                value=event["value"],
                draft_type=event["draft_type"],
                draft_version=event["draft_version"],
                saved=event["closed_by"],
                changes=event["change_count"],
                draft_write=event["draft_write"],
                value_omitted=event["value_omitted"],
                chars=event["chars"],
            )
        elif kind == "chat.message_sent":
            if event.get("refused"):
                row.update(kind="message_refused", refused=event["refused"])
            else:
                turn = turns.get(event.get("turn") or "")
                message = turn.message if turn else None
                row.update(
                    kind="message",
                    turn=event.get("turn"),
                    text=message["text"] if message else None,
                )
        elif kind == "chat.reply_ended":
            turn = turns.get(event.get("turn") or "") or _Turn()
            row.update(kind="reply", turn=event.get("turn"), **turn.reply_fields())
            # How the respondent saw it end, from their browser; the server's error
            # kind when the turn failed, else the browser's.
            row.update(
                ended=event["status"],
                error_kind=row["error_kind"] or event["error_kind"],
            )
        elif kind in ("assistant.edit_applied", "assistant.edit_skipped"):
            edit = by_edit.get(event["edit"]) or {}
            skipped = kind == "assistant.edit_skipped"
            row.update(
                kind="assistant_edit",
                turn=edit.get("turn"),
                edit=event["edit"],
                question=event["question"],
                # A skip says only why: its value and shape are the edit's.
                value=edit.get("value") if skipped else event["value"],
                draft_type=edit.get("draft_type") if skipped else event["draft_type"],
                draft_version=(
                    edit.get("draft_version") if skipped else event["draft_version"]
                ),
                outcome="skipped" if skipped else "applied",
                reason=event.get("reason"),
                draft_write=None if skipped else event["draft_write"],
            )
        elif kind == "assistant.edit_undone":
            edit = by_edit.get(event["edit"]) or {}
            row.update(
                kind="edit_undone",
                turn=edit.get("turn"),
                edit=event["edit"],
                question=event["question"],
                value=event["value"],
            )
        else:
            row.update(
                kind="not_recorded",
                question=event["question"],
                rejected_type=event["rejected_type"],
                reason=event["reason"],
                chars=event["chars"],
            )
        return row

    @staticmethod
    def place_turn(
        rows: List[dict], turn_uuid: str, turn: _Turn, reported: set
    ) -> None:
        """Place what the trace lacks of one turn:

        - its message, if the trace never got it: just before its reply if the trace
          has that (``before_reply``), else at the end (``end``);
        - edits the browser never reported, and its reply if the trace has no ending,
          after the message and the edits that followed it (``after_message``, or
          ``end`` when the message was placed there too). An edit whose Undo is in
          the trace goes just before its Undo, as ``applied``: the fill was lost,
          but the form took it;
        - its rejected edits just before its reply (``before_reply``).
        """
        source = turn.message or turn.last or (turn.sent + turn.rejected)[0]
        base = {
            "response_uuid": source["response_uuid"],
            "is_preview": source["is_preview"],
            "page_id": source["page_id"],
            "turn": turn_uuid,
            "session": None,
            "seq": None,
        }

        def find(kind: str) -> Optional[int]:
            return next(
                (
                    i
                    for i, row in enumerate(rows)
                    if row["kind"] == kind and row["turn"] == turn_uuid
                ),
                None,
            )

        message_at, reply_at = find("message"), find("reply")
        placed = "after_message"
        if message_at is None:
            message = {
                **base,
                "kind": "message",
                "at": turn.message["at"] if turn.message else None,
                "text": turn.message["text"] if turn.message else None,
            }
            if reply_at is not None:
                rows.insert(reply_at, {**message, "placed": "before_reply"})
                message_at, reply_at = reply_at, reply_at + 1
            else:
                placed = "end"
                rows.append({**message, "placed": placed})
                message_at = len(rows) - 1

        insert = message_at + 1
        while (
            insert < len(rows)
            and rows[insert]["kind"] in _AFTER_MESSAGE
            and rows[insert]["turn"] == turn_uuid
        ):
            insert += 1
        for edit in turn.sent:
            if edit["edit"] in reported:
                continue
            undone_at = next(
                (
                    i
                    for i, row in enumerate(rows)
                    if row["kind"] == "edit_undone" and row["edit"] == edit["edit"]
                ),
                None,
            )
            at = insert if undone_at is None else min(insert, undone_at)
            rows.insert(
                at,
                {
                    **base,
                    "kind": "assistant_edit",
                    "at": edit["at"],
                    "page_id": edit["page_id"],
                    "placed": placed,
                    "edit": edit["edit"],
                    "question": edit["question"],
                    "value": edit["value"],
                    "draft_type": edit["draft_type"],
                    "draft_version": edit["draft_version"],
                    # Undone, so the form took it; otherwise the browser never
                    # said what the form did with it.
                    "outcome": "sent" if undone_at is None else "applied",
                    "reason": None,
                    "draft_write": None,
                },
            )
            if reply_at is not None and reply_at >= at:
                reply_at += 1
            insert += 1

        if reply_at is None and turn.last is not None:
            rows.insert(
                insert,
                {
                    **base,
                    "kind": "reply",
                    "at": turn.last["at"],
                    "placed": placed,
                    "ended": None,
                    **turn.reply_fields(),
                },
            )
            reply_at = insert
        # A turn not listed yet has no reply to go before: its rejected edits follow
        # what's placed of it.
        before = reply_at if reply_at is not None else insert
        for offset, edit in enumerate(turn.rejected):
            rows.insert(
                before + offset,
                {
                    **base,
                    "kind": "edit_rejected",
                    "at": edit["at"],
                    "page_id": edit["page_id"],
                    "placed": "before_reply",
                    "edit": edit["edit"],
                    "question": edit["question"],
                    "value": edit["value"],
                    "draft_type": edit["draft_type"],
                    "draft_version": edit["draft_version"],
                    "rejection": edit["rejection"],
                },
            )

    @staticmethod
    def shape(row: dict) -> dict:
        """The row with the common fields, then its kind's, each present."""
        fields: Iterable[str] = (*COMMON_FIELDS, *KIND_FIELDS[row["kind"]])
        return {field: row.get(field) for field in fields}
