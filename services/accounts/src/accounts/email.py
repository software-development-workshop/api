import smtplib
from email.message import EmailMessage

from accounts.config import API_PREFIX, get_settings


class SmtpMailer:
    """Sends the verification email inline, on the request that triggered it.

    The reason there is no queue or outbox behind this is written down in
    docs/adr/0003. The short version: AC.6 already requires a resend button, so the recovery
    path for a failed send exists as a requirement and does not need building twice.
    """

    def send_verification(self, to: str, token: str) -> None:
        settings = get_settings()

        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = to
        message["Subject"] = "Verificá tu cuenta de UdeSA-X"
        message.set_content(
            "Para activar tu cuenta, entrá a este link:\n\n"
            f"{settings.public_base_url}{API_PREFIX}/verifications/{token}\n\n"
            "El link vence en 24 horas. Si no fuiste vos, ignorá este mensaje."
        )

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.send_message(message)

    def send_password_reset(self, to: str, token: str) -> None:
        settings = get_settings()

        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = to
        message["Subject"] = "Restablecé tu contraseña de UdeSA-X"
        message.set_content(
            "Para elegir una contraseña nueva, entrá a este link:\n\n"
            f"{settings.public_base_url}/reset-password?token={token}\n\n"
            "El link vence en 10 minutos. Si no fuiste vos, ignorá este mensaje."
        )

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.send_message(message)
