"""Append-only messages with normalized optional reply targets."""

from edsl.sharedstate import Command, Machine, T, append, choose, current, expr, field, input_, local, map_sequence, record, state_field

author = input_("author").stripped()
message = input_("message").stripped()
raw_reply = choose(input_("reply_to") == None, "", input_("reply_to").stripped())  # noqa: E711
reply = choose(
    (raw_reply == "") | expr("contains", ("none", "new", "new message", "n/a"), raw_reply.casefolded()),
    None,
    raw_reply,
)
public_messages = map_sequence(
    field("messages"), item="entry",
    value_expr=record(
        author=local("entry").get("author"),
        message=local("entry").get("message"),
        reply_to=local("entry").get("reply_to"),
    ),
)
SPEC = Machine(
    name="SharedMessageBoard", constants={},
    fields={"messages": state_field(T.sequence(T.map()), [])},
    commands={
        "add": Command(
            inputs={"author": T.text(), "message": T.text(), "reply_to": T.optional(T.text())},
            require=(author.length() > 0) & (message.length() > 0),
            effects=(append("messages", record(author=author, message=message, reply_to=reply, interview=current("interview_id"))),),
        )
    },
    view={"messages": public_messages, "message_count": field("messages").length()},
)
