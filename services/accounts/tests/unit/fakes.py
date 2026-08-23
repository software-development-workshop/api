import uuid
from datetime import UTC, datetime

from accounts.models import Account, VerificationToken


class FakeAccountsRepository:
    """In-memory stand-in for AccountsRepository.

    Duck-typed on purpose: an abstract base with a single real implementation is the
    interface YAGNI forbids.
    """

    def __init__(self, accounts: list[Account] | None = None) -> None:
        self.accounts = accounts or []
        self.tokens: list[VerificationToken] = []

    def add(self, account: Account) -> Account:
        # The database fills these on insert; a fake that skips them lets a caller that
        # reads account.id right after registering pass here and fail in production.
        account.id = account.id or uuid.uuid4()
        account.created_at = account.created_at or datetime.now(UTC)
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

    def save(self, account: Account) -> Account:
        return account

    def find_token(self, token_digest: str) -> VerificationToken | None:
        return next((t for t in self.tokens if t.token_digest == token_digest), None)

    def issue_token(self, token: VerificationToken) -> VerificationToken:
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
