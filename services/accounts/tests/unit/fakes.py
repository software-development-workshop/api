import uuid
from datetime import UTC, datetime

from accounts.models import Account


class FakeAccountsRepository:
    """In-memory stand-in for AccountsRepository.

    Duck-typed on purpose: an abstract base with a single real implementation is the
    interface YAGNI forbids, and the service only ever needs these three calls.
    """

    def __init__(self, accounts: list[Account] | None = None) -> None:
        self.accounts = accounts or []

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
