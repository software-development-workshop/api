from accounts.errors import EmailAlreadyRegisteredError, HandleTakenError
from accounts.models import Account
from accounts.passwords import hash_password
from accounts.repository import AccountsRepository


def register(repository: AccountsRepository, email: str, handle: str, password: str) -> Account:
    """Create an unverified account.

    The uniqueness checks here are for the error message, not for correctness: the unique
    indexes decide. Two simultaneous registrations of the same email both pass this check
    and one of them loses at commit.
    """
    if repository.exists_with_email(email):
        raise EmailAlreadyRegisteredError("That email is already registered.")
    if repository.exists_with_handle(handle):
        raise HandleTakenError("That handle is already taken.")

    return repository.add(
        Account(email=email, handle=handle, password_hash=hash_password(password))
    )
