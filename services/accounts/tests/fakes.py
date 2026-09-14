from accounts.errors import VerificationEmailNotSentError


class FakeMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.password_resets: list[tuple[str, str]] = []

    def send_verification(self, to: str, token: str) -> None:
        self.sent.append((to, token))

    def send_password_reset(self, to: str, token: str) -> None:
        self.password_resets.append((to, token))

    @property
    def last_token(self) -> str:
        return self.sent[-1][1]

    @property
    def last_password_reset_token(self) -> str:
        return self.password_resets[-1][1]


class FailingPasswordResetMailer(FakeMailer):
    def send_password_reset(self, to: str, token: str) -> None:
        raise ConnectionError("mail provider unavailable")


class RefusingMailer:
    """Stands in for a mail provider that refuses the send."""

    def send_verification(self, to: str, token: str) -> None:
        raise VerificationEmailNotSentError("Ask for a new one from the login screen.")
