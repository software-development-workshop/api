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

    def add_token(self, token: VerificationToken) -> VerificationToken:
        token.id = token.id or uuid.uuid4()
        self.tokens.append(token)
        return token

    def find_token(self, token_digest: str) -> VerificationToken | None:
        return next((t for t in self.tokens if t.token_digest == token_digest), None)

    def invalidate_tokens_for(self, account_id: uuid.UUID) -> None:
        for token in self.tokens:
            if token.account_id == account_id and token.used_at is None:
                token.used_at = datetime.now(UTC)

    def mark_verified(self, token: VerificationToken) -> Account:
        now = datetime.now(UTC)
        token.used_at = now
        account = next(a for a in self.accounts if a.id == token.account_id)
        account.verified_at = now
        return account
