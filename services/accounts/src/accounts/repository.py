from sqlalchemy import func, select
from sqlalchemy.orm import Session

from accounts.models import Account


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

    def _exists(self, column: object, value: str) -> bool:
        statement = select(Account.id).where(func.lower(column) == value.lower()).limit(1)
        return self._session.execute(statement).first() is not None
