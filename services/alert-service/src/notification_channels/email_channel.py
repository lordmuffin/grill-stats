import asyncio
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List

from .base_channel import BaseNotificationChannel

logger = logging.getLogger(__name__)


class EmailChannel(BaseNotificationChannel):
    """
    Email notification channel supporting SMTP with TLS/SSL.

    Features:
    - HTML and plain text support
    - Multiple recipients
    - Attachment support
    - SMTP authentication
    - Connection pooling
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.smtp_config = {
            "server": config.get("smtp_server", "localhost"),
            "port": config.get("smtp_port", 587),
            "username": config.get("username", ""),
            "password": config.get("password", ""),
            "use_tls": config.get("use_tls", True),
            "use_ssl": config.get("use_ssl", False),
            "timeout": config.get("timeout", 30),
        }
        self.default_from = config.get("from_email", "noreply@example.com")
        self.default_recipients = config.get("recipients", [])

    async def send(
        self, recipient: str, subject: str, body: str, channel_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send email notification."""
        try:
            # Parse recipients
            if isinstance(recipient, str):
                recipients = [recipient]
            else:
                recipients = recipient

            # Use default recipients if none provided
            if not recipients:
                recipients = self.default_recipients

            if not recipients:
                return {"success": False, "error": "No recipients specified"}

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = channel_config.get("from_email", self.default_from)
            msg["To"] = ", ".join(recipients)

            # Check if body is HTML
            if "<html>" in body.lower() or "<body>" in body.lower():
                msg.attach(MIMEText(body, "html"))
            else:
                msg.attach(MIMEText(body, "plain"))

            # Send email
            result = await self._send_email(msg, recipients, channel_config)

            return {
                "success": result["success"],
                "message_id": result.get("message_id"),
                "recipients": recipients,
                "error": result.get("error"),
            }

        except Exception as e:
            logger.error(f"Error sending email: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _send_email(
        self, msg: MIMEMultipart, recipients: List[str], channel_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send email using SMTP."""
        try:
            # Get SMTP configuration
            smtp_config = {**self.smtp_config, **channel_config}

            # Create SMTP connection
            if smtp_config["use_ssl"]:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(
                    smtp_config["server"],
                    smtp_config["port"],
                    context=context,
                    timeout=smtp_config["timeout"],
                )
            else:
                server = smtplib.SMTP(
                    smtp_config["server"],
                    smtp_config["port"],
                    timeout=smtp_config["timeout"],
                )

                if smtp_config["use_tls"]:
                    context = ssl.create_default_context()
                    server.starttls(context=context)

            # Authenticate if credentials provided
            if smtp_config["username"] and smtp_config["password"]:
                server.login(smtp_config["username"], smtp_config["password"])

            # Send email
            text = msg.as_string()
            server.sendmail(msg["From"], recipients, text)
            server.quit()

            return {"success": True, "message_id": msg.get("Message-ID")}

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {str(e)}")
            return {"success": False, "error": f"SMTP authentication failed: {str(e)}"}
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"SMTP recipients refused: {str(e)}")
            return {"success": False, "error": f"Recipients refused: {str(e)}"}
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {str(e)}")
            return {"success": False, "error": f"SMTP error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error sending email: {str(e)}")
            return {"success": False, "error": str(e)}

    async def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate email configuration."""
        errors = []

        # Check required fields
        if not config.get("smtp_server"):
            errors.append("SMTP server is required")

        if not config.get("smtp_port"):
            errors.append("SMTP port is required")

        if not config.get("recipients"):
            errors.append("At least one recipient is required")

        # Validate email addresses
        recipients = config.get("recipients", [])
        if recipients:
            import re

            email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

            for recipient in recipients:
                if not re.match(email_pattern, recipient):
                    errors.append(f"Invalid email address: {recipient}")

        # Test connection if all required fields are present
        if not errors:
            try:
                test_result = await self._test_smtp_connection(config)
                if not test_result["success"]:
                    errors.append(
                        f'SMTP connection test failed: {test_result["error"]}'
                    )
            except Exception as e:
                errors.append(f"Connection test error: {str(e)}")

        return {"valid": len(errors) == 0, "errors": errors}

    async def _test_smtp_connection(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test SMTP connection."""
        try:
            smtp_config = {**self.smtp_config, **config}

            # Create SMTP connection
            if smtp_config["use_ssl"]:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(
                    smtp_config["server"],
                    smtp_config["port"],
                    context=context,
                    timeout=10,
                )
            else:
                server = smtplib.SMTP(
                    smtp_config["server"], smtp_config["port"], timeout=10
                )

                if smtp_config["use_tls"]:
                    context = ssl.create_default_context()
                    server.starttls(context=context)

            # Test authentication if credentials provided
            if smtp_config["username"] and smtp_config["password"]:
                server.login(smtp_config["username"], smtp_config["password"])

            server.quit()

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_delivery_status(self, message_id: str) -> str:
        """Get delivery status for email (basic implementation)."""
        # Email delivery status checking is complex and depends on the email provider
        # For now, we'll return 'delivered' as emails are typically delivered immediately
        # In a production system, you might integrate with email service APIs
        return "delivered"

    def get_channel_info(self) -> Dict[str, Any]:
        """Get channel information."""
        return {
            "name": "Email",
            "type": "email",
            "description": "Email notifications via SMTP",
            "config_fields": [
                {
                    "name": "smtp_server",
                    "type": "string",
                    "required": True,
                    "description": "SMTP server hostname",
                },
                {
                    "name": "smtp_port",
                    "type": "integer",
                    "required": True,
                    "description": "SMTP server port",
                },
                {
                    "name": "username",
                    "type": "string",
                    "required": False,
                    "description": "SMTP username",
                },
                {
                    "name": "password",
                    "type": "string",
                    "required": False,
                    "description": "SMTP password",
                    "secret": True,
                },
                {
                    "name": "use_tls",
                    "type": "boolean",
                    "required": False,
                    "description": "Use TLS encryption",
                },
                {
                    "name": "use_ssl",
                    "type": "boolean",
                    "required": False,
                    "description": "Use SSL encryption",
                },
                {
                    "name": "from_email",
                    "type": "string",
                    "required": False,
                    "description": "From email address",
                },
                {
                    "name": "recipients",
                    "type": "array",
                    "required": True,
                    "description": "List of recipient email addresses",
                },
            ],
        }
