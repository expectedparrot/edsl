import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

@dataclass
class StudyPayment:
    study_id: str
    min_amount: int
    actual_amount: Optional[int] = None

# Describes a pending offer sent by the researcher. The respondent must accept
# before `expires_at`. After acceptance, they have `completion_deadline_sec`
# seconds to finish the study.

@dataclass
class StudyOffer:
    study_id: str
    min_amount: int
    expires_at: datetime  # absolute timestamp when offer expires
    completion_deadline_sec: int

@dataclass
class LedgerEntry:
    """Represents a single double-entry book-keeping transaction."""

    timestamp: datetime
    description: str
    debit_account: str
    credit_account: str
    amount: int

class Wallet:
    """A very small double-entry ledger focusing on Cash and Accounts Receivable."""

    CASH = "Cash"
    AR = "Accounts Receivable"
    REVENUE = "Revenue"
    EXTERNAL = "External"  # balancing account for direct deposits / withdrawals

    def __init__(self):
        # Chart of accounts and their running balances
        self._accounts: dict[str, int] = {
            self.CASH: 0,
            self.AR: 0,
            self.REVENUE: 0,
            self.EXTERNAL: 0,
        }

        # Mapping of study_id -> StudyPayment (promised / outstanding receivables)
        self.accounts_receivable: dict[str, StudyPayment] = {}

        # Simple in-memory general ledger
        self._ledger: list[LedgerEntry] = []

        # Paid out / settled studies (for quick reference)
        self.paid_studies: list[str] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post_entry(
        self,
        debit_account: str,
        credit_account: str,
        amount: int,
        description: str,
    ) -> None:
        """Add a double-entry ledger line and mutate account balances."""

        if not isinstance(amount, int) or amount <= 0:
            raise ValueError("Amount must be a positive integer value (whole credits)")

        # Update running balances (debit adds, credit subtracts)
        self._accounts[debit_account] = self._accounts.get(debit_account, 0) + amount
        self._accounts[credit_account] = self._accounts.get(credit_account, 0) - amount

        # Persist entry
        self._ledger.append(
            LedgerEntry(
                timestamp=datetime.utcnow(),
                description=description,
                debit_account=debit_account,
                credit_account=credit_account,
                amount=amount,
            )
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_account_receivable(self, study_id: str, min_amount: int):
        """Record a promised payment (debit AR, credit Revenue)."""

        if study_id in self.accounts_receivable:
            raise ValueError(f"Study {study_id} already exists in accounts receivable")

        self.accounts_receivable[study_id] = StudyPayment(study_id, min_amount)

        self._post_entry(
            debit_account=self.AR,
            credit_account=self.REVENUE,
            amount=min_amount,
            description=f"Promised payment for study {study_id}",
        )

    def receive_payment(self, study_id: str, amount: int):
        """Record settlement of a study payment (debit Cash, credit AR)."""

        if study_id not in self.accounts_receivable:
            raise ValueError(f"Study {study_id} not found in accounts receivable")

        outstanding = self.accounts_receivable[study_id].min_amount
        if amount < outstanding:
            raise ValueError(
                f"Amount {amount} is less than the minimum/outstanding amount {outstanding}"
            )

        # Double entry: Cash (debit) / AR (credit)
        self._post_entry(
            debit_account=self.CASH,
            credit_account=self.AR,
            amount=amount,
            description=f"Payment received for study {study_id}",
        )

        # Update study payment record
        self.accounts_receivable[study_id].actual_amount = amount
        self.accounts_receivable[study_id].min_amount = 0

        # Mark study as settled
        self.paid_studies.append(study_id)
        # Remove from AR listing now that it's settled
        del self.accounts_receivable[study_id]

    # Generic cash movements ------------------------------------------------

    def deposit(self, credits: int, description: str = "Manual deposit"):
        """Direct cash injection (outside normal AR workflow)."""
        self._post_entry(
            debit_account=self.CASH,
            credit_account=self.EXTERNAL,
            amount=credits,
            description=description,
        )

    def withdraw(self, credits: int, description: str = "Manual withdrawal"):
        self._post_entry(
            debit_account=self.EXTERNAL,
            credit_account=self.CASH,
            amount=credits,
            description=description,
        )

    # ------------------------------------------------------------------
    # Reporting helpers
    # ------------------------------------------------------------------

    @property
    def balance(self) -> int:
        """Current cash balance."""
        return self._accounts[self.CASH]

    def get_balance(self) -> int:
        return self.balance

    def receivables_total(self) -> int:
        return self._accounts[self.AR]

    def ledger(self) -> list[LedgerEntry]:
        """Return a copy of the ledger entries."""
        return list(self._ledger)

    def reconcile(self) -> None:
        """Simple sanity check: ensure debits equal credits for each entry."""
        # Verify that for every ledger entry debited amount is matched by credited amount
        # (This should always be true individually), and overall that total of all accounts is 0.
        total = sum(self._accounts.values())
        if abs(total) > 1e-6:
            raise RuntimeError(
                f"Ledger out of balance by {total}. Investigate transactions!"
            )

class Subject:

    def __init__(self, uuid):
        self.uuid = uuid

        # Study states
        self._requested_studies: list[str] = []
        # study_id -> completion_deadline (datetime)
        self._pending_studies: dict[str, datetime] = {}
        self._completed_studies = []

        # Study results 
        self._study_results: dict[str, dict] = {}

        # Map of study_id -> StudyOffer
        self._study_offers: dict[str, StudyOffer] = {}

        self._messages = []
        self._wallet = Wallet()

    def __repr__(self):
        return f"Subject(uuid={self.uuid})"

    def __str__(self):
        return self.uuid

    def __eq__(self, other):
        return self.uuid == other.uuid
    
    # ------------------------------------------------------------------
    # Study acceptance / completion
    # ------------------------------------------------------------------

    def accept_study(self, study_id: str):
        """Move a study from requested to pending and register receivable."""

        if study_id not in self._study_offers:
            raise ValueError(f"No offer found for study {study_id}")

        offer = self._study_offers[study_id]

        # Check offer expiration
        if datetime.utcnow() > offer.expires_at:
            raise ValueError(f"Offer for study {study_id} has expired")

        # Ensure the study was indeed requested
        if study_id in self._requested_studies:
            self._requested_studies.remove(study_id)
        else:
            raise ValueError(f"Study {study_id} not found in requested studies")

        min_amount: int = offer.min_amount

        # Create an account receivable for the promised payment
        self._wallet.add_account_receivable(study_id, min_amount)

        # Track study progression
        self._pending_studies[study_id] = datetime.utcnow() + timedelta(
            seconds=offer.completion_deadline_sec
        )
        # No longer need to keep the offer mapping – the receivable is the source of truth
        del self._study_offers[study_id]

    # ------------------------------------------------------------------
    # Messaging helpers (simple internal mail between respondent and researcher)
    # ------------------------------------------------------------------

    def post_message(self, message: dict) -> None:
        """Add a message to the internal mailbox."""
        self._messages.append(message)

    def pop_all_messages(self) -> list[dict]:
        """Retrieve and clear all messages (used by researcher)."""
        msgs = list(self._messages)
        self._messages.clear()
        return msgs

class RespondentSubjectView:

    def __init__(self, subject: Subject):
        self._subject = subject

    def accept_study(self, study_id: str):
        # Subject handles creation of AR and pending status
        self._subject.accept_study(study_id)

    def reject_study(self, study_id: str, reason: str | None = None):
        """Respondent rejects a requested study, informing the researcher."""

        if study_id not in self._subject._requested_studies:
            raise ValueError(f"Study {study_id} not found in requested studies")

        # Remove the request and associated offer
        self._subject._requested_studies.remove(study_id)
        self._subject._study_offers.pop(study_id, None)

        # Post a message for the researcher
        self._subject.post_message(
            {
                "type": "rejection",
                "study_id": study_id,
                "reason": reason or "No reason provided",
                "timestamp": datetime.utcnow(),
            }
        )

    def complete_study(self, study_id: str) -> None:
        """Respondent completes a study."""
        if study_id not in self._subject._pending_studies:
            raise ValueError(f"Study {study_id} is not currently pending")
        
        deadline = self._subject._pending_studies[study_id]
        if datetime.utcnow() > deadline:
            raise ValueError(f"Study {study_id} completion deadline has passed")
        
        # Generate a mock set of results for the study (placeholder behaviour)
        results_uuid = str(uuid.uuid4())
        self._subject._study_results[study_id] = {
            "study_id": study_id,
            "results": results_uuid,
        }

        # Move study from pending to completed
        self._subject._completed_studies.append(study_id)
        self._subject._pending_studies.pop(study_id)


# ------------------------------------------------------------------------------
# Researcher interface
# ------------------------------------------------------------------------------
class ResearcherSubjectView:
    def __init__(self, subject: Subject):
        self._subject = subject

    def send_study(
        self,
        study_id: str,
        min_amount: int,
        offer_ttl_sec: int = 3600,
        completion_deadline_sec: int = 7200,
    ):
        """Invite the respondent to a study.

        Args:
            study_id: Identifier for the study.
            min_amount: Minimum payment upon completion.
            offer_ttl_sec: Seconds the offer remains valid for acceptance.
            completion_deadline_sec: Seconds allowed to complete study after acceptance.
        """

        self._subject._requested_studies.append(study_id)
        self._subject._study_offers[study_id] = StudyOffer(
            study_id,
            min_amount,
            datetime.utcnow() + timedelta(seconds=offer_ttl_sec),
            completion_deadline_sec,
        )

    def list_pending_studies(self):
        return list(self._subject._pending_studies.keys())
    
    def get_study_results(self, study_id: str):
        return self._subject._study_results[study_id]
    
    def pay_respondent(self, study_id: str, amount: int):
        """Settle the study payment to the respondent (affects their ledger)."""

        self._subject._wallet.receive_payment(study_id, amount)

    def get_balance(self):
        return self._subject._wallet.get_balance()
        
    # ---------------- Messaging ------------------

    def fetch_messages(self) -> list[dict]:
        """Retrieve and clear all new messages from the respondent."""
        return self._subject.pop_all_messages()

    # ---------------- Offer management ------------------

    def update_offer_price(self, study_id: str, new_min_amount: int):
        """Increase the minimum payment offered for an unaccepted study."""

        if study_id not in self._subject._study_offers:
            raise ValueError("Cannot update price: study not in requested offers or already accepted")

        offer = self._subject._study_offers[study_id]

        if new_min_amount <= offer.min_amount:
            raise ValueError("New minimum amount must be greater than existing offer")

        offer.min_amount = new_min_amount

        # Notify respondent of price update
        self._subject.post_message(
            {
                "type": "price_update",
                "study_id": study_id,
                "new_min_amount": new_min_amount,
                "timestamp": datetime.utcnow(),
            }
        )

def _demo_workflow() -> None:
    """Exercise the major features of Subject / Wallet / Views in one run."""

    print("================ DEMO: SURVEY PAYMENT WORKFLOW ================")

    # Instantiate core objects
    subject = Subject(str(uuid.uuid4()))
    researcher = ResearcherSubjectView(subject)
    respondent = RespondentSubjectView(subject)

    # 1. Researcher invites the respondent to two studies with promised payments
    print("\n[RESEARCHER] Sending study invitations …")
    researcher.send_study("study-1", 10)
    researcher.send_study("study-2", 5)
    researcher.send_study("study-3", 7)
    print("Requested studies:", subject._requested_studies)

    # Researcher decides to sweeten the deal for study-2
    print("[RESEARCHER] Increasing price for study-2 to 8 credits …")
    researcher.update_offer_price("study-2", 8)

    # 2. Respondent accepts the first study (creates an Account Receivable)
    print("\n[RESPONDENT] Accepting study-1 …")
    respondent.accept_study("study-1")
    print("Pending studies (after accept):", researcher.list_pending_studies())
    print("Outstanding receivables total:", subject._wallet.receivables_total())

    # 3. Respondent completes the first study → results get stored
    print("\n[RESPONDENT] Completing study-1 …")
    respondent.complete_study("study-1")
    print("Completed studies:", subject._completed_studies)
    print("Study-1 results:", researcher.get_study_results("study-1"))

    # 4. Researcher pays the promised amount for study-1
    print("\n[RESEARCHER] Paying respondent 10 credits for study-1 …")
    researcher.pay_respondent("study-1", 10)
    print("Cash balance after payment:", subject._wallet.get_balance())
    print("Outstanding receivables after payment:", subject._wallet.receivables_total())

    # 5. Respondent rejects study-3 with a reason
    print("\n[RESPONDENT] Rejecting study-3 …")
    respondent.reject_study("study-3", reason="Not interested in topic")

    # Researcher checks messages
    print("[RESEARCHER] Fetching messages …")
    for msg in researcher.fetch_messages():
        print("Message:", msg)

    # 6. Try an improper payment amount to demonstrate validation
    print("\n[RESEARCHER] Attempting to underpay study-2 (should raise)…")
    try:
        researcher.pay_respondent("study-2", 5)  # less than promised 8 credits
    except ValueError as exc:
        print("Caught expected ValueError:", exc)

    # 7. Accept and pay study-2 correctly
    print("\n[RESPONDENT] Accepting & completing study-2 …")
    respondent.accept_study("study-2")
    respondent.complete_study("study-2")
    researcher.pay_respondent("study-2", 8)
    print("Cash balance after all payments:", subject._wallet.get_balance())

    # 8. Final ledger dump & reconciliation
    print("\n=== FINAL LEDGER ENTRIES ===")
    for entry in subject._wallet.ledger():
        print(entry)

    print("\nRunning reconciliation …")
    subject._wallet.reconcile()
    print("Books reconcile perfectly. Demo complete!")

# If executed as script, run the demonstration
if __name__ == "__main__":
    _demo_workflow()