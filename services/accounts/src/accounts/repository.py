from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from accounts.errors import EmailAlreadyRegisteredError, HandleTakenError
from accounts.models import Account, VerificationToken

_EMAIL_UNIQUE_INDEX = "ix_accounts_email_lower"
_HANDLE_UNIQUE_INDEX = "ix_accounts_handle_lower"


class AccountsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, account: Account) -> Account:
        self._session.add(account)
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if constraint_name == _EMAIL_UNIQUE_INDEX:
                raise EmailAlreadyRegisteredError("That email is already registered.") from error
            if constraint_name == _HANDLE_UNIQUE_INDEX:
                raise HandleTakenError("That handle is already taken.") from error
            raise
        self._session.refresh(account)
        return account

    def exists_with_email(self, email: str) -> bool:
        return self._exists(Account.email, email)

    def exists_with_handle(self, handle: str) -> bool:
        return self._exists(Account.handle, handle)

    def find_by_email(self, email: str) -> Account | None:
        statement = select(Account).where(func.lower(Account.email) == email.lower())
        return self._session.execute(statement).scalar_one_or_none()

    def find_for_login(self, identifier: str) -> Account | None:
        canonical = identifier.strip().lower()
        if canonical.startswith("@"):
            column = Account.handle
            canonical = canonical.removeprefix("@")
            identifier_kind = "handle"
        elif "@" in canonical:
            column = Account.email
            identifier_kind = "email"
        else:
            column = Account.handle
            identifier_kind = "handle"
        # A missing row cannot carry a FOR UPDATE lock. The transaction-scoped advisory
        # lock gives known and unknown identifiers the same serialization boundary without
        # retaining a global lock or storing attempted identifiers.
        lock_material = f"{identifier_kind}:{canonical}".encode()
        lock_key = int.from_bytes(sha256(lock_material).digest()[:8], byteorder="big", signed=True)
        self._session.execute(select(func.pg_advisory_xact_lock(lock_key)))
        statement = select(Account).where(func.lower(column) == canonical).with_for_update()
        return self._session.execute(statement).scalar_one_or_none()

    def save(self, account: Account) -> Account:
        self._session.commit()
        self._session.refresh(account)
        return account

    def finish_login_attempt(self, account: Account | None) -> Account | None:
        self._session.commit()
        return account

    def find_token(self, token_digest: str) -> VerificationToken | None:
        statement = select(VerificationToken).where(VerificationToken.token_digest == token_digest)
        return self._session.execute(statement).scalar_one_or_none()

    def issue_token(self, token: VerificationToken) -> VerificationToken:
        """Replace every live token of an account with this one, in a single transaction.

        The account row is locked first. Without it two concurrent resends each invalidate
        the tokens they can see and then insert their own, and the account ends up with two
        usable links instead of one.
        """
        self._session.execute(
            select(Account.id).where(Account.id == token.account_id).with_for_update()
        )
        self._session.execute(
            update(VerificationToken)
            .where(VerificationToken.account_id == token.account_id)
            .where(VerificationToken.used_at.is_(None))
            .values(used_at=datetime.now(UTC))
        )
        self._session.add(token)
        self._session.commit()
        self._session.refresh(token)
        return token

    def consume_token(self, token: VerificationToken) -> Account | None:
        """Spend a token and verify its account, or answer None when it was already spent.

        Single use is this conditional update, never the read that precedes it: two requests
        carrying the same live link both pass that read, and only one of them matches a row
        here. Verifying the account in the same transaction keeps the two facts from ever
        disagreeing.
        """
        now = datetime.now(UTC)
        spent = self._session.execute(
            update(VerificationToken)
            .where(VerificationToken.id == token.id)
            .where(VerificationToken.used_at.is_(None))
            .values(used_at=now)
        )
        if spent.rowcount == 0:
            self._session.rollback()
            return None

        account = self._session.get(Account, token.account_id)
        if account is None:  # pragma: no cover - the foreign key makes this unreachable
            raise LookupError("verification token points at a missing account")
        account.verified_at = now
        self._session.commit()
        self._session.refresh(account)
        return account

    def _exists(self, column: object, value: str) -> bool:
        statement = select(Account.id).where(func.lower(column) == value.lower()).limit(1)
        return self._session.execute(statement).first() is not None
