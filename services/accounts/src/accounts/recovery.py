import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from accounts import service
from accounts.db import get_engine
from accounts.repository import AccountsRepository

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="accounts-recovery")


async def request_password_reset(identifier: str, mailer: service.Mailer) -> None:
    await asyncio.get_running_loop().run_in_executor(
        _executor, _with_repository, service.request_password_reset, mailer, identifier
    )


async def resend_verification(email: str, mailer: service.Mailer) -> None:
    await asyncio.get_running_loop().run_in_executor(
        _executor, _with_repository, service.resend_verification, mailer, email
    )


def _with_repository(
    operation: Callable[[AccountsRepository, service.Mailer, str], None],
    mailer: service.Mailer,
    identifier: str,
) -> None:
    # Own the session here and keep slow sends out of the API's shared thread pool.
    with Session(get_engine()) as session:
        operation(AccountsRepository(session), mailer, identifier)
