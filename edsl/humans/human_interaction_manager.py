from __future__ import annotations

"""Human-centric interaction helpers (messaging, payments, etc.).

This module houses :class:`HumanInteractionManager`, a small service class that
provides pragmatic interactions—such as paying a participant or messaging them—
for a :class:`~edsl.humans.human.Human` instance.  The default implementation
keeps dependencies to an absolute minimum (it only prints to stdout) so that
it is safe to use in demos and unit-tests.  For production use you are
expected to subclass and override the placeholder methods with real
integrations (Stripe, Twilio, Sendgrid, Coop, …).
"""

from typing import Optional, TYPE_CHECKING, List, Dict

from .exceptions import HumanContactInfoError

from dataclasses import dataclass

from datetime import datetime

if TYPE_CHECKING:  # pragma: no cover – avoid runtime circular import
    from .human import Human


class HumanInteractionManager:
    """Service/utility class for operational interactions with a :class:`Human`.

    Parameters
    ----------
    human : Human
        The human participant this manager will interact with.
    backend : str, optional
        Free-form identifier of the concrete backend used by this manager.
    """

    def __init__(self, human: "Human", *, backend: Optional[str] = None) -> None:
        self.human: "Human" = human
        self.backend: Optional[str] = backend

        # participant subsystems
        self.inbox = Inbox(human)
        self.wallet = Wallet(human)
        self.study_manager = StudyManager(human)

    # ------------------------------------------------------------------
    # Helper / validation utilities
    # ------------------------------------------------------------------
    def _require_contact_method(self) -> None:
        """Ensure at least one contact method is available before sending."""
        if not any(self.human.contact_info.values()):
            raise HumanContactInfoError(
                "Unable to contact Human – no contact methods have been provided."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def send_message(self, message: str, *, study_id: Optional[str] = None) -> None:
        """Send an arbitrary *message* to the participant.

        By default this prints to *stdout*.  Override for real transports.
        """
        self._require_contact_method()
        self.inbox.receive_message(message, study_id=study_id)

    def send_study(self, study_id: str, *, intro_text: Optional[str] = None) -> None:
        """Invite the participant to a study (identified by *study_id*)."""
        self._require_contact_method()
        # queue in manager
        self.study_manager.queue_study(study_id)
        # notify via inbox
        intro = intro_text or "You have been invited to participate in study "
        self.inbox.receive_message(f"{intro}{study_id}", study_id=study_id)

    def make_payment(self, ep_credits: float) -> None:
        """Pay the participant a number of Expected Parrot credits.

        Stub implementation prints a confirmation.  Sub-class for real billing.
        """
        self._require_contact_method()
        self.wallet.deposit(ep_credits)

    def list_past_studies(self) -> List[str]:
        """Proxy through to :py:meth:`Human.list_past_studies`."""
        return self.study_manager.list_past_studies()

    # Expose inbox retrieval through manager
    def get_messages(self, *, study_id: Optional[str] = None, direction: str | None = None, purge: bool = False):
        return self.inbox.get_messages(study_id=study_id, direction=direction, purge=purge)

    # Study workflow shortcuts
    def accept_study(self, study_id: str) -> None:
        self.study_manager.accept_study(study_id)

    def list_pending_studies(self) -> List[str]:
        return self.study_manager.list_pending_studies()

    # ------------------------------------------------------------------
    # Misc dunder helpers
    # ------------------------------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover – convenience only
        cls_name = self.__class__.__name__
        return f"{cls_name}(human={self.human!r}, backend={self.backend!r})"


# ---------------------------------------------------------------------------
# Auxiliary helper objects that model state for a participant
# ---------------------------------------------------------------------------


class Inbox:
    """Inbox maintains sent and received message logs with timestamps."""

    def __init__(self, human: "Human") -> None:
        self.human = human
        self.received: List[Message] = []
        self.sent: List[Message] = []

    # ------------------- incoming (system → human) -------------------
    def receive_message(self, message: str, study_id: Optional[str] = None, sender: str = "system") -> None:
        msg = Message(
            content=message,
            timestamp=datetime.utcnow(),
            sender=sender,
            recipient=self.human.name or "human",
            study_id=study_id,
        )
        self.received.append(msg)
        printable = f"[{study_id}] {message}" if study_id else message
        print(f"[INBOX] ({self.human.name or 'Unnamed'}) ← {printable}")

    # ------------------- outgoing (human → system) -------------------
    def send_message(self, message: str, study_id: Optional[str] = None, recipient: str = "system") -> None:
        msg = Message(
            content=message,
            timestamp=datetime.utcnow(),
            sender=self.human.name or "human",
            recipient=recipient,
            study_id=study_id,
        )
        self.sent.append(msg)
        printable = f"[{study_id}] {message}" if study_id else message
        print(f"[OUTBOX] ({self.human.name or 'Unnamed'}) → {printable}")

    # ------------------- querying -------------------
    def get_messages(
        self,
        *,
        study_id: Optional[str] = None,
        direction: str | None = None,  # 'received', 'sent', or None for both
        purge: bool = False,
    ) -> List[Message]:
        """Retrieve messages with optional filtering.

        direction: 'received', 'sent', or None for both.
        """
        pools = []
        if direction in (None, "received"):
            pools.append(self.received)
        if direction in (None, "sent"):
            pools.append(self.sent)

        selected = [m for pool in pools for m in pool if study_id is None or m.study_id == study_id]

        if purge:
            def _keep(msg_list):
                return [m for m in msg_list if not (study_id is None or m.study_id == study_id)]

            if direction in (None, "received"):
                self.received = _keep(self.received)
            if direction in (None, "sent"):
                self.sent = _keep(self.sent)

        return selected


class Wallet:
    """Simple wallet storing Expected Parrot credit balance."""

    def __init__(self, human: "Human") -> None:
        self.human = human
        self.balance: float = 0.0

    def deposit(self, credits: float) -> None:
        if credits <= 0:
            raise ValueError("ep_credits must be positive")
        self.balance += credits
        print(
            f"[WALLET] {credits:.2f} EP credits added to {self.human.name or 'Unnamed'} (new balance: {self.balance:.2f})"
        )


class StudyManager:
    """Manages study invitations and accepted studies for a participant."""

    def __init__(self, human: "Human") -> None:
        self.human = human
        self._pending: List[str] = []
        self._accepted: List[str] = []

    # --------------------------- queue / accept ---------------------------
    def queue_study(self, study_id: str) -> None:
        self._pending.append(study_id)
        print(f"[STUDY] Queued study '{study_id}' for {self.human.name or 'Unnamed'} (awaiting accept)")

    def accept_study(self, study_id: str) -> None:
        if study_id in self._pending:
            self._pending.remove(study_id)
            self._accepted.append(study_id)
            print(f"[STUDY] {self.human.name or 'Unnamed'} accepted study '{study_id}'")
        else:
            print(f"[STUDY] Study '{study_id}' not found in queue for {self.human.name or 'Unnamed'}")

    # --------------------------- query helpers ---------------------------
    def list_past_studies(self) -> List[str]:
        return list(self._accepted)
    
    def list_pending_studies(self) -> List[str]:
        return list(self._pending)


# ---------------------------------------------------------------------------
# Message dataclass
# ---------------------------------------------------------------------------


@dataclass
class Message:
    content: str
    timestamp: datetime
    sender: str
    recipient: str
    study_id: Optional[str] = None 