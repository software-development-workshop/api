import resend

from accounts.config import API_PREFIX, get_settings

# The provider is called inside the request that triggers it, so this is the ceiling on how
# long that request can take. The SDK's own default is 30 seconds.
SEND_TIMEOUT_SECONDS = 10

resend.default_http_client = resend.RequestsClient(timeout=SEND_TIMEOUT_SECONDS)


class ResendMailer:
    """Sends the service's mail inline, on the request that triggered it.

    There is no queue or outbox behind this. The resend button the product already requires
    is the recovery path for a failed send, so a second one would be built for the same job.
    """

    def send_verification(self, to: str, token: str) -> None:
        self._send(
            to,
            "Verificá tu cuenta de UdeSA-X",
            "Para activar tu cuenta, entrá a este link:\n\n"
            f"{get_settings().public_base_url}{API_PREFIX}/verifications/{token}\n\n"
            "El link vence en 24 horas. Si no fuiste vos, ignorá este mensaje.",
        )

    def send_password_reset(self, to: str, token: str) -> None:
        self._send(
            to,
            "Restablecé tu contraseña de UdeSA-X",
            "Para elegir una contraseña nueva, entrá a este link:\n\n"
            f"{get_settings().public_base_url}/reset-password?token={token}\n\n"
            "El link vence en 10 minutos. Si no fuiste vos, ignorá este mensaje.",
        )

    def _send(self, to: str, subject: str, text: str) -> None:
        settings = get_settings()
        # Assigned per send rather than at import: the SDK reads RESEND_API_KEY off the
        # process environment, which never sees what pydantic-settings loads from .env.
        resend.api_key = settings.resend_api_key

        resend.Emails.send({"from": settings.mail_from, "to": to, "subject": subject, "text": text})
