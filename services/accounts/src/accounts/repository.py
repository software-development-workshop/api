import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from accounts.errors import EmailAlreadyRegisteredError, HandleTakenError
from accounts.models import Account, PasswordResetToken, RevokedAccessToken, VerificationToken

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
            self._raise_identity_conflict(error)
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
        elif "@" in canonical:
            column = Account.email
        else:
            column = Account.handle
        statement = (
            select(Account)
            .where(func.lower(column) == canonical)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self._session.execute(statement).scalar_one_or_none()

    def find_by_identifier(self, identifier: str) -> Account | None:
        canonical = identifier.strip().lower()
        if canonical.startswith("@"):
            column = Account.handle
            canonical = canonical.removeprefix("@")
        elif "@" in canonical:
            column = Account.email
        else:
            column = Account.handle
        statement = select(Account).where(func.lower(column) == canonical)
        return self._session.execute(statement).scalar_one_or_none()

    def save(self, account: Account) -> Account:
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            self._raise_identity_conflict(error)
            raise
        self._session.refresh(account)
        return account

    def account_for_profile_update(self, account_id: uuid.UUID) -> Account | None:
        statement = (
            select(Account)
            .where(
                Account.id == account_id,
                Account.suspended_at.is_(None),
                Account.deleted_at.is_(None),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self._session.execute(statement).scalar_one_or_none()

    @staticmethod
    def _raise_identity_conflict(error: IntegrityError) -> None:
        constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        if constraint_name == _EMAIL_UNIQUE_INDEX:
            raise EmailAlreadyRegisteredError("That email is already registered.") from error
        if constraint_name == _HANDLE_UNIQUE_INDEX:
            raise HandleTakenError("That handle is already taken.") from error

    def finish_login_attempt(self, account: Account | None) -> Account | None:
        self._session.commit()
        return account

    def account_for_deletion(self, account_id: uuid.UUID) -> Account | None:
        return self._lock_account(account_id)

    def finish_deletion_attempt(
        self, account: Account, *, deleted_at: datetime | None = None
    ) -> None:
        if deleted_at is not None:
            account.deleted_at = deleted_at
            account.session_version += 1
            account.failed_login_attempts = 0
            account.locked_until = None
            for model in (VerificationToken, PasswordResetToken):
                self._session.execute(
                    update(model)
                    .where(model.account_id == account.id, model.used_at.is_(None))
                    .values(used_at=deleted_at)
                )
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def revoke_access_token(self, jti: uuid.UUID, expires_at: datetime) -> None:
        statement = pg_insert(RevokedAccessToken).values(jti=jti, expires_at=expires_at)
        self._session.execute(
            statement.on_conflict_do_nothing(index_elements=[RevokedAccessToken.jti])
        )
        self._session.commit()

    def is_access_token_revoked(self, jti: uuid.UUID) -> bool:
        statement = select(RevokedAccessToken.jti).where(RevokedAccessToken.jti == jti)
        return self._session.execute(statement).scalar_one_or_none() is not None

    def active_session_version_for(self, account_id: uuid.UUID) -> int | None:
        statement = select(Account.session_version).where(
            Account.id == account_id,
            Account.suspended_at.is_(None),
            Account.deleted_at.is_(None),
        )
        return self._session.execute(statement).scalar_one_or_none()

    def find_password_reset(self, token_digest: str) -> PasswordResetToken | None:
        statement = select(PasswordResetToken).where(
            PasswordResetToken.token_digest == token_digest
        )
        return self._session.execute(statement).scalar_one_or_none()

    def account_for_password_reset(self, account_id: uuid.UUID) -> Account | None:
        account = self._lock_account(account_id)
        if account is not None and (
            account.deleted_at is not None or account.suspended_at is not None
        ):
            self._session.rollback()
            return None
        return account

    def issue_password_reset(
        self,
        token: PasswordResetToken,
        *,
        window: timedelta,
        limit: int,
    ) -> PasswordResetToken | None:
        account = self._lock_account(token.account_id)
        if account is None:  # pragma: no cover - the foreign key makes this unreachable
            raise LookupError("password reset token points at a missing account")

        if (
            account.verified_at is None
            or account.suspended_at is not None
            or account.deleted_at is not None
        ):
            self._session.rollback()
            return None

        issued_in_window = self._session.execute(
            select(func.count(PasswordResetToken.id))
            .where(PasswordResetToken.account_id == token.account_id)
            .where(PasswordResetToken.created_at >= token.created_at - window)
        ).scalar_one()
        if issued_in_window >= limit:
            self._session.rollback()
            return None

        self._session.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.account_id == token.account_id)
            .where(PasswordResetToken.used_at.is_(None))
            .values(used_at=token.created_at)
        )
        self._session.add(token)
        self._session.commit()
        self._session.refresh(token)
        return token

    def invalidate_password_reset(
        self,
        token: PasswordResetToken,
        *,
        invalidated_at: datetime,
    ) -> None:
        self._session.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.id == token.id)
            .where(PasswordResetToken.used_at.is_(None))
            .values(used_at=invalidated_at)
        )
        self._session.commit()

    def consume_password_reset(
        self,
        token: PasswordResetToken,
        password_hash: str,
        *,
        changed_at: datetime,
    ) -> Account | None:
        account = self._lock_account(token.account_id)
        if account is None:  # pragma: no cover - the foreign key makes this unreachable
            raise LookupError("password reset token points at a missing account")

        if account.deleted_at is not None or account.suspended_at is not None:
            self._session.rollback()
            return None

        spent = self._session.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.id == token.id)
            .where(PasswordResetToken.used_at.is_(None))
            .values(used_at=changed_at)
        )
        if spent.rowcount == 0:
            self._session.rollback()
            return None

        self._session.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.account_id == token.account_id)
            .where(PasswordResetToken.used_at.is_(None))
            .values(used_at=changed_at)
        )
        account.password_hash = password_hash
        account.session_version += 1
        account.failed_login_attempts = 0
        account.locked_until = None
        self._session.commit()
        self._session.refresh(account)
        return account

    def find_token(self, token_digest: str) -> VerificationToken | None:
        statement = select(VerificationToken).where(VerificationToken.token_digest == token_digest)
        return self._session.execute(statement).scalar_one_or_none()

    def issue_token(
        self,
        token: VerificationToken,
        *,
        window: timedelta,
        limit: int,
    ) -> VerificationToken | None:
        """Replace every live token of an account with this one, in a single transaction.

        The account row is locked first. Without it two concurrent resends each invalidate
        the tokens they can see and then insert their own, and the account ends up with two
        usable links instead of one.
        """
        account = self._lock_account(token.account_id)
        if account is None:  # pragma: no cover - the foreign key makes this unreachable
            raise LookupError("verification token points at a missing account")
        if (
            account.verified_at is not None
            or account.suspended_at is not None
            or account.deleted_at is not None
        ):
            self._session.rollback()
            return None

        issued_in_window = self._session.execute(
            select(func.count(VerificationToken.id))
            .where(VerificationToken.account_id == token.account_id)
            .where(VerificationToken.created_at >= token.created_at - window)
        ).scalar_one()
        if issued_in_window >= limit:
            self._session.rollback()
            return None

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
        account = self._lock_account(token.account_id)
        if account is None:  # pragma: no cover - the foreign key makes this unreachable
            raise LookupError("verification token points at a missing account")
        if account.verified_at is not None or account.deleted_at is not None:
            self._session.rollback()
            return None

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

        account.verified_at = now
        self._session.commit()
        self._session.refresh(account)
        return account

    def _lock_account(self, account_id: uuid.UUID) -> Account | None:
        return self._session.get(Account, account_id, with_for_update=True, populate_existing=True)

    def _exists(self, column: object, value: str) -> bool:
        statement = select(Account.id).where(func.lower(column) == value.lower()).limit(1)
        return self._session.execute(statement).first() is not None
