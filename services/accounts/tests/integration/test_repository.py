import uuid
from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from accounts import tokens
from accounts.errors import EmailAlreadyRegisteredError, HandleTakenError
from accounts.models import Account, PasswordResetToken, RevokedAccessToken, VerificationToken
from accounts.passwords import hash_password
from accounts.repository import AccountsRepository

VALID_PASSWORD_HASH = hash_password("Passw0rd")
NONCANONICAL_STRONGER_HASH = PasswordHasher(
    memory_cost=32768,
    time_cost=3,
    parallelism=2,
).hash("Passw0rd")
RESET_REQUESTED_AT = datetime(2030, 1, 2, 3, 4, 5, tzinfo=UTC)


def account(email: str = "juan@udesa.edu.ar", handle: str = "juan") -> Account:
    return Account(email=email, handle=handle, password_hash=VALID_PASSWORD_HASH)


def token(account_id: uuid.UUID, digest: str = "a" * 64, hours: int = 24) -> VerificationToken:
    return VerificationToken(
        account_id=account_id,
        token_digest=digest,
        expires_at=datetime.now(UTC) + timedelta(hours=hours),
    )


def password_reset_token(
    account_id: uuid.UUID,
    digest: str,
    requested_at: datetime = RESET_REQUESTED_AT,
) -> PasswordResetToken:
    return PasswordResetToken(
        account_id=account_id,
        token_digest=digest,
        expires_at=requested_at + timedelta(minutes=10),
        created_at=requested_at,
    )


def test_persists_an_account_and_stamps_created_at(session: Session) -> None:
    stored = AccountsRepository(session).add(account())

    assert stored.id is not None
    assert stored.created_at is not None
    assert stored.verified_at is None


def test_rejects_noncanonical_stronger_password_hash_parameters(session: Session) -> None:
    stronger_account = account()
    stronger_account.password_hash = NONCANONICAL_STRONGER_HASH

    with pytest.raises(IntegrityError):
        AccountsRepository(session).add(stronger_account)


@pytest.mark.parametrize("lookup", ["juan@udesa.edu.ar", "JUAN@UdeSA.EDU.ar"])
def test_finds_an_email_whatever_the_casing(session: Session, lookup: str) -> None:
    repository = AccountsRepository(session)
    repository.add(account(email="Juan@Udesa.edu.ar"))

    assert repository.exists_with_email(lookup)


@pytest.mark.parametrize("lookup", ["juan", "JUAN"])
def test_finds_a_handle_whatever_the_casing(session: Session, lookup: str) -> None:
    repository = AccountsRepository(session)
    repository.add(account(handle="Juan"))

    assert repository.exists_with_handle(lookup)


def test_duplicate_email_is_mapped_and_the_session_is_reusable(session: Session) -> None:
    # AC.7 holds because of this index, not because of the check in the service: two
    # concurrent registrations both pass that check and one of them has to lose here.
    repository = AccountsRepository(session)
    repository.add(account(email="juan@udesa.edu.ar"))

    with pytest.raises(EmailAlreadyRegisteredError):
        repository.add(account(email="JUAN@UDESA.EDU.AR", handle="otro"))

    saved = repository.add(account(email="nuevo@udesa.edu.ar", handle="nuevo"))
    assert saved.email == "nuevo@udesa.edu.ar"


def test_duplicate_handle_is_mapped_and_the_session_is_reusable(session: Session) -> None:
    repository = AccountsRepository(session)
    repository.add(account(handle="juan"))

    with pytest.raises(HandleTakenError):
        repository.add(account(email="otro@udesa.edu.ar", handle="JUAN"))

    saved = repository.add(account(email="nuevo@udesa.edu.ar", handle="nuevo"))
    assert saved.handle == "nuevo"


def test_stores_a_token_and_finds_it_by_its_digest(session: Session) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())

    saved = repository.issue_token(token(stored.id))

    assert repository.find_token("a" * 64).id == saved.id


def test_a_digest_nobody_issued_finds_nothing(session: Session) -> None:
    assert AccountsRepository(session).find_token("b" * 64) is None


def test_finds_an_account_by_email_whatever_the_casing(session: Session) -> None:
    repository = AccountsRepository(session)
    repository.add(account(email="Juan@Udesa.edu.ar"))

    assert repository.find_by_email("JUAN@udesa.EDU.ar") is not None


@pytest.mark.parametrize(
    "identifier",
    ["juan@udesa.edu.ar", "JUAN@UdeSA.edu.AR", "@juan", "@JUAN", "juan"],
)
def test_finds_an_account_for_login_by_email_or_handle(session: Session, identifier: str) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())

    assert repository.find_for_login(identifier).id == stored.id


@pytest.mark.parametrize(
    "identifier",
    ["juan@udesa.edu.ar", "JUAN@UdeSA.edu.AR", "@juan", "@JUAN", "juan"],
)
def test_finds_an_account_for_password_reset_by_email_or_handle(
    session: Session, identifier: str
) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())

    assert repository.find_by_identifier(identifier).id == stored.id


def test_persists_suspended_and_deleted_account_state(session: Session) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())
    now = datetime.now(UTC)
    stored.suspended_at = now
    stored.deleted_at = now

    repository.save(stored)
    session.expire_all()
    reloaded = session.get(Account, stored.id)

    assert reloaded.suspended_at == now
    assert reloaded.deleted_at == now


def test_persists_login_lockout_state(session: Session) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())
    locked_until = datetime.now(UTC) + timedelta(minutes=15)
    stored.failed_login_attempts = 5
    stored.locked_until = locked_until

    repository.save(stored)
    session.expire_all()
    reloaded = session.get(Account, stored.id)

    assert reloaded.failed_login_attempts == 5
    assert reloaded.locked_until == locked_until


def test_persists_the_account_session_version(session: Session) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())
    stored.session_version = 4

    repository.save(stored)
    session.expire_all()
    reloaded = session.get(Account, stored.id)

    assert reloaded.session_version == 4


def test_persists_profile_fields_and_locks_only_active_accounts(session: Session) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())

    editable = repository.account_for_profile_update(stored.id)
    editable.bio = "Bio"
    editable.display_name = "Juan"
    editable.handle = "nuevo"
    repository.save(editable)

    session.expire_all()
    reloaded = session.get(Account, stored.id)
    assert reloaded.bio == "Bio"
    assert reloaded.display_name == "Juan"
    assert reloaded.handle == "nuevo"

    reloaded.suspended_at = datetime.now(UTC)
    repository.save(reloaded)
    assert repository.account_for_profile_update(stored.id) is None


def test_persists_profile_text_with_html_escaping_at_the_logical_limit(
    session: Session,
) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())
    stored.bio = "x" * 158 + " &"
    stored.display_name = "x" * 48 + " &lt;"

    repository.save(stored)
    session.expire_all()
    reloaded = session.get(Account, stored.id)

    assert reloaded.bio == "x" * 158 + " &"
    assert reloaded.display_name == "x" * 48 + " &lt;"


def test_duplicate_handle_on_profile_update_is_mapped_and_session_is_reusable(
    session: Session,
) -> None:
    repository = AccountsRepository(session)
    repository.add(account(handle="primero"))
    second = repository.add(account(email="otro@udesa.edu.ar", handle="segundo"))
    second.handle = "PRIMERO"

    with pytest.raises(HandleTakenError):
        repository.save(second)

    second.handle = "segundo"
    assert repository.save(second).handle == "segundo"


def test_only_exposes_the_session_version_for_an_active_account(session: Session) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())

    assert repository.active_session_version_for(stored.id) == 0

    stored.suspended_at = datetime.now(UTC)
    repository.save(stored)

    assert repository.active_session_version_for(stored.id) is None

    stored.suspended_at = None
    stored.deleted_at = datetime.now(UTC)
    repository.save(stored)

    assert repository.active_session_version_for(stored.id) is None


@pytest.mark.parametrize(
    "password_hash",
    [
        "",
        "   ",
        "\t",
        "\n",
        "\r\n",
        "\u00a0",
        "\u2003",
        "not-an-argon2-hash",
        "é",
        "$argon2id$stub",
        f"{VALID_PASSWORD_HASH}trailing",
        VALID_PASSWORD_HASH.replace("m=19456", "m=01024"),
        VALID_PASSWORD_HASH.replace("m=19456", "m=65537"),
        VALID_PASSWORD_HASH.replace("m=19456", "m=999999"),
        VALID_PASSWORD_HASH.replace("t=2", "t=5"),
        VALID_PASSWORD_HASH.replace("t=2", "t=999"),
        VALID_PASSWORD_HASH.replace("p=1", "p=5"),
        VALID_PASSWORD_HASH.replace("p=1", "p=99"),
        VALID_PASSWORD_HASH.replace("m=19456", "m=invalid"),
        VALID_PASSWORD_HASH.replace("$argon2id$", "$argon2i$"),
    ],
)
def test_rejects_an_unsupported_password_hash(session: Session, password_hash: str) -> None:
    blank_account = account()
    blank_account.password_hash = password_hash

    with pytest.raises(IntegrityError):
        AccountsRepository(session).add(blank_account)


def test_issuing_burns_every_live_token_of_the_account(session: Session) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())
    repository.issue_token(token(stored.id, digest="c" * 64))
    repository.issue_token(token(stored.id, digest="d" * 64))

    repository.issue_token(token(stored.id, digest="e" * 64))

    assert repository.find_token("c" * 64).used_at is not None
    assert repository.find_token("d" * 64).used_at is not None
    assert repository.find_token("e" * 64).used_at is None


def test_consuming_stamps_the_token_and_the_account(session: Session) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())
    saved = repository.issue_token(token(stored.id))

    verified = repository.consume_token(saved)

    assert verified.verified_at is not None
    assert repository.find_token("a" * 64).used_at is not None


def test_consuming_a_spent_token_answers_nothing(session: Session) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())
    saved = repository.issue_token(token(stored.id))
    repository.consume_token(saved)

    assert repository.consume_token(saved) is None


def test_issuing_a_password_reset_stores_only_the_digest_and_replaces_the_live_link(
    session: Session,
) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())
    raw_token = "first-reset-token"
    first_digest = tokens.digest(raw_token)
    first = repository.issue_password_reset(
        password_reset_token(stored.id, first_digest),
        window=timedelta(minutes=15),
        limit=3,
    )

    second = repository.issue_password_reset(
        password_reset_token(stored.id, "b" * 64, RESET_REQUESTED_AT + timedelta(minutes=1)),
        window=timedelta(minutes=15),
        limit=3,
    )

    assert first is not None
    assert second is not None
    assert repository.find_password_reset(first_digest).used_at is not None
    assert repository.find_password_reset("b" * 64).used_at is None
    assert raw_token not in first.token_digest


def test_password_reset_limit_allows_only_three_issues_inside_the_window(
    session: Session,
) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())

    issued = [
        repository.issue_password_reset(
            password_reset_token(stored.id, str(index) * 64),
            window=timedelta(minutes=15),
            limit=3,
        )
        for index in range(1, 5)
    ]

    rows = session.execute(
        select(PasswordResetToken).where(PasswordResetToken.account_id == stored.id)
    ).scalars()
    assert [record is not None for record in issued] == [True, True, True, False]
    assert len(list(rows)) == 3


def test_consuming_a_password_reset_updates_the_account_and_uses_every_live_link(
    session: Session,
) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())
    stored.failed_login_attempts = 5
    stored.locked_until = RESET_REQUESTED_AT + timedelta(minutes=15)
    stored.session_version = 2
    repository.save(stored)
    first = repository.issue_password_reset(
        password_reset_token(stored.id, "c" * 64),
        window=timedelta(minutes=15),
        limit=3,
    )
    second = repository.issue_password_reset(
        password_reset_token(stored.id, "d" * 64, RESET_REQUESTED_AT + timedelta(minutes=1)),
        window=timedelta(minutes=15),
        limit=3,
    )
    new_hash = hash_password("NewPassw0rd")

    changed = repository.consume_password_reset(
        second,
        new_hash,
        changed_at=RESET_REQUESTED_AT + timedelta(minutes=2),
    )

    assert first is not None
    assert changed.password_hash == new_hash
    assert changed.session_version == 3
    assert changed.failed_login_attempts == 0
    assert changed.locked_until is None
    assert repository.find_password_reset("c" * 64).used_at is not None
    assert repository.find_password_reset("d" * 64).used_at is not None


def test_revokes_an_access_token_and_keeps_the_record_once(session: Session) -> None:
    repository = AccountsRepository(session)
    jti = uuid.uuid4()
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    repository.revoke_access_token(jti, expires_at)
    repository.revoke_access_token(jti, expires_at)

    session.expire_all()
    stored = session.query(RevokedAccessToken).filter_by(jti=jti).all()
    assert len(stored) == 1
    assert repository.is_access_token_revoked(jti) is True
