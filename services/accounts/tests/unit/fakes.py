import uuid
from datetime import UTC, datetime, timedelta

from accounts.models import Account, PasswordResetToken, VerificationToken


class FakeAccountsRepository:
    """In-memory stand-in for AccountsRepository.

    Duck-typed on purpose: an abstract base with a single real implementation is the
    interface YAGNI forbids.
    """

    def __init__(self, accounts: list[Account] | None = None) -> None:
        self.accounts = accounts or []
        self.tokens: list[VerificationToken] = []
        self.password_reset_tokens: list[PasswordResetToken] = []
        self.completed_login_attempts = 0
        self.revoked_access_tokens: dict[uuid.UUID, datetime] = {}

    def add(self, account: Account) -> Account:
        # The database fills these on insert; a fake that skips them lets a caller that
        # reads account.id right after registering pass here and fail in production.
        account.id = account.id or uuid.uuid4()
        account.created_at = account.created_at or datetime.now(UTC)
        account.failed_login_attempts = account.failed_login_attempts or 0
        account.session_version = account.session_version or 0
        self.accounts.append(account)
        return account

    def exists_with_email(self, email: str) -> bool:
        return any(a.email.lower() == email.lower() for a in self.accounts)

    def exists_with_handle(self, handle: str) -> bool:
        return any(a.handle.lower() == handle.lower() for a in self.accounts)

    def find_by_email(self, email: str) -> Account | None:
        return next((a for a in self.accounts if a.email.lower() == email.lower()), None)

    def find_for_login(self, identifier: str) -> Account | None:
        canonical = identifier.strip().lower()
        if canonical.startswith("@"):
            return next(
                (a for a in self.accounts if a.handle.lower() == canonical.removeprefix("@")),
                None,
            )
        if "@" in canonical:
            return next((a for a in self.accounts if a.email.lower() == canonical), None)
        return next((a for a in self.accounts if a.handle.lower() == canonical), None)

    def find_by_identifier(self, identifier: str) -> Account | None:
        return self.find_for_login(identifier)

    def save(self, account: Account) -> Account:
        return account

    def finish_login_attempt(self, account: Account | None) -> Account | None:
        self.completed_login_attempts += 1
        return account

    def revoke_access_token(self, jti: uuid.UUID, expires_at: datetime) -> None:
        self.revoked_access_tokens.setdefault(jti, expires_at)

    def is_access_token_revoked(self, jti: uuid.UUID) -> bool:
        return jti in self.revoked_access_tokens

    def active_session_version_for(self, account_id: uuid.UUID) -> int | None:
        account = next((account for account in self.accounts if account.id == account_id), None)
        if account is None or account.suspended_at is not None or account.deleted_at is not None:
            return None
        return account.session_version

    def find_password_reset(self, token_digest: str) -> PasswordResetToken | None:
        return next(
            (token for token in self.password_reset_tokens if token.token_digest == token_digest),
            None,
        )

    def account_for_password_reset(self, account_id: uuid.UUID) -> Account | None:
        return next((account for account in self.accounts if account.id == account_id), None)

    def issue_password_reset(
        self,
        token: PasswordResetToken,
        *,
        window: timedelta,
        limit: int,
    ) -> PasswordResetToken | None:
        issued_in_window = [
            existing
            for existing in self.password_reset_tokens
            if existing.account_id == token.account_id
            and existing.created_at >= token.created_at - window
        ]
        if len(issued_in_window) >= limit:
            return None
        for live in self.password_reset_tokens:
            if live.account_id == token.account_id and live.used_at is None:
                live.used_at = token.created_at
        token.id = token.id or uuid.uuid4()
        self.password_reset_tokens.append(token)
        return token

    def invalidate_password_reset(
        self,
        token: PasswordResetToken,
        *,
        invalidated_at: datetime,
    ) -> None:
        if token.used_at is None:
            token.used_at = invalidated_at

    def consume_password_reset(
        self,
        token: PasswordResetToken,
        password_hash: str,
        *,
        changed_at: datetime,
    ) -> Account | None:
        if token.used_at is not None:
            return None
        account = self.account_for_password_reset(token.account_id)
        if account is None:
            raise LookupError("password reset token points at a missing account")
        for live in self.password_reset_tokens:
            if live.account_id == token.account_id and live.used_at is None:
                live.used_at = changed_at
        account.password_hash = password_hash
        account.session_version += 1
        account.failed_login_attempts = 0
        account.locked_until = None
        return account

    def find_token(self, token_digest: str) -> VerificationToken | None:
        return next((t for t in self.tokens if t.token_digest == token_digest), None)

    def issue_token(self, token: VerificationToken) -> VerificationToken | None:
        account = next(account for account in self.accounts if account.id == token.account_id)
        if account.verified_at is not None:
            return None
        for live in self.tokens:
            if live.account_id == token.account_id and live.used_at is None:
                live.used_at = datetime.now(UTC)
        token.id = token.id or uuid.uuid4()
        self.tokens.append(token)
        return token

    def consume_token(self, token: VerificationToken) -> Account | None:
        if token.used_at is not None:
            return None
        now = datetime.now(UTC)
        token.used_at = now
        account = next(a for a in self.accounts if a.id == token.account_id)
        account.verified_at = now
        return account
