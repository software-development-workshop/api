from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from accounts.errors import EmailAlreadyRegisteredError, HandleTakenError
from accounts.models import Account

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

    def _exists(self, column: object, value: str) -> bool:
        statement = select(Account.id).where(func.lower(column) == value.lower()).limit(1)
        return self._session.execute(statement).first() is not None
