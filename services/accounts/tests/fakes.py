class FakeMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_verification(self, to: str, token: str) -> None:
        self.sent.append((to, token))

    @property
    def last_token(self) -> str:
        return self.sent[-1][1]
