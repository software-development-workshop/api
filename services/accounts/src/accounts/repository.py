import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from accounts.models import Account, VerificationToken


class AccountsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, account: Account) -> Account:
        self._session.add(account)
        self._session.commit()
        self._session.refresh(account)
        return account

    def exists_with_email(self, email: str) -> bool:
        return self._exists(Account.email, email)

    def exists_with_handle(self, handle: str) -> bool:
        return self._exists(Account.handle, handle)

    def find_by_email(self, email: str) -> Account | None:
        statement = select(Account).where(func.lower(Account.email) == email.lower())
        return self._session.execute(statement).scalar_one_or_none()

    def add_token(self, token: VerificationToken) -> VerificationToken:
        self._session.add(token)
        self._session.commit()
        self._session.refresh(token)
        return token

    def find_token(self, token_digest: str) -> VerificationToken | None:
        statement = select(VerificationToken).where(VerificationToken.token_digest == token_digest)
        return self._session.execute(statement).scalar_one_or_none()

    def invalidate_tokens_for(self, account_id: uuid.UUID) -> None:
        """Burn every live token of an account, so a resend leaves exactly one usable link."""
        statement = (
            update(VerificationToken)
            .where(VerificationToken.account_id == account_id)
            .where(VerificationToken.used_at.is_(None))
            .values(used_at=datetime.now(UTC))
        )
        self._session.execute(statement)
        self._session.commit()

    def mark_verified(self, token: VerificationToken) -> Account:
        now = datetime.now(UTC)
        token.used_at = now
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
