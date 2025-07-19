import asyncio
import logging
from typing import Any, Dict, List

import httpx
from twilio.base.exceptions import TwilioException
from twilio.rest import Client as TwilioClient

from .base_channel import BaseNotificationChannel

logger = logging.getLogger(__name__)


class SMSChannel(BaseNotificationChannel):
    """
    SMS notification channel supporting multiple providers.

    Supported providers:
    - Twilio
    - AWS SNS
    - Nexmo/Vonage
    - Custom webhook
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.provider = config.get("provider", "twilio")
        self.provider_config = config.get("provider_config", {})

        # Initialize provider client
        if self.provider == "twilio":
            self.client = self._init_twilio_client()
        elif self.provider == "webhook":
            self.client = httpx.AsyncClient(timeout=30.0)
        else:
            self.client = None

    def _init_twilio_client(self) -> TwilioClient:
        """Initialize Twilio client."""
        account_sid = self.provider_config.get("account_sid")
        auth_token = self.provider_config.get("auth_token")

        if not account_sid or not auth_token:
            logger.warning("Twilio credentials not provided")
            return None

        return TwilioClient(account_sid, auth_token)

    async def send(
        self, recipient: str, subject: str, body: str, channel_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send SMS notification."""
        try:
            # Parse recipients
            if isinstance(recipient, str):
                recipients = [recipient]
            else:
                recipients = recipient

            # Use default recipients if none provided
            if not recipients:
                recipients = channel_config.get("to_numbers", [])

            if not recipients:
                return {"success": False, "error": "No recipients specified"}

            # Send SMS based on provider
            if self.provider == "twilio":
                result = await self._send_twilio_sms(recipients, body, channel_config)
            elif self.provider == "webhook":
                result = await self._send_webhook_sms(recipients, body, channel_config)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported SMS provider: {self.provider}",
                }

            return result

        except Exception as e:
            logger.error(f"Error sending SMS: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _send_twilio_sms(
        self, recipients: List[str], body: str, channel_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send SMS using Twilio."""
        if not self.client:
            return {"success": False, "error": "Twilio client not initialized"}

        try:
            from_number = channel_config.get("from_number") or self.provider_config.get(
                "from_number"
            )
            if not from_number:
                return {"success": False, "error": "From number not specified"}

            # Truncate body if too long (SMS limit is 160 characters)
            if len(body) > 160:
                body = body[:157] + "..."

            results = []
            for recipient in recipients:
                try:
                    # Send SMS
                    message = self.client.messages.create(
                        body=body, from_=from_number, to=recipient
                    )

                    results.append(
                        {
                            "recipient": recipient,
                            "success": True,
                            "message_sid": message.sid,
                            "status": message.status,
                        }
                    )

                except TwilioException as e:
                    logger.error(f"Twilio error for {recipient}: {str(e)}")
                    results.append(
                        {"recipient": recipient, "success": False, "error": str(e)}
                    )

            success_count = sum(1 for r in results if r["success"])

            return {
                "success": success_count > 0,
                "total_recipients": len(recipients),
                "successful_sends": success_count,
                "failed_sends": len(recipients) - success_count,
                "results": results,
            }

        except Exception as e:
            logger.error(f"Error in Twilio SMS sending: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _send_webhook_sms(
        self, recipients: List[str], body: str, channel_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send SMS using webhook."""
        webhook_url = channel_config.get("webhook_url") or self.provider_config.get(
            "webhook_url"
        )
        if not webhook_url:
            return {"success": False, "error": "Webhook URL not specified"}

        try:
            # Prepare webhook payload
            payload = {
                "recipients": recipients,
                "message": body,
                "timestamp": str(asyncio.get_event_loop().time()),
            }

            # Add any additional webhook parameters
            webhook_params = channel_config.get("webhook_params", {})
            payload.update(webhook_params)

            # Send webhook request
            response = await self.client.post(
                webhook_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "AlertService/1.0",
                },
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "webhook_response": response.json() if response.content else {},
                    "status_code": response.status_code,
                }
            else:
                return {
                    "success": False,
                    "error": f"Webhook returned status {response.status_code}",
                    "response": response.text,
                }

        except Exception as e:
            logger.error(f"Error in webhook SMS sending: {str(e)}")
            return {"success": False, "error": str(e)}

    async def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate SMS configuration."""
        errors = []

        provider = config.get("provider", "twilio")
        provider_config = config.get("provider_config", {})

        if provider == "twilio":
            # Validate Twilio configuration
            if not provider_config.get("account_sid"):
                errors.append("Twilio Account SID is required")

            if not provider_config.get("auth_token"):
                errors.append("Twilio Auth Token is required")

            if not provider_config.get("from_number"):
                errors.append("Twilio From Number is required")

            # Test Twilio connection
            if not errors:
                try:
                    test_result = await self._test_twilio_connection(provider_config)
                    if not test_result["success"]:
                        errors.append(
                            f'Twilio connection test failed: {test_result["error"]}'
                        )
                except Exception as e:
                    errors.append(f"Twilio test error: {str(e)}")

        elif provider == "webhook":
            # Validate webhook configuration
            if not provider_config.get("webhook_url"):
                errors.append("Webhook URL is required")

            # Test webhook
            if not errors:
                try:
                    test_result = await self._test_webhook_connection(provider_config)
                    if not test_result["success"]:
                        errors.append(f'Webhook test failed: {test_result["error"]}')
                except Exception as e:
                    errors.append(f"Webhook test error: {str(e)}")

        else:
            errors.append(f"Unsupported SMS provider: {provider}")

        # Validate phone numbers
        to_numbers = config.get("to_numbers", [])
        if not to_numbers:
            errors.append("At least one recipient phone number is required")
        else:
            for number in to_numbers:
                if not self._validate_phone_number(number):
                    errors.append(f"Invalid phone number format: {number}")

        return {"valid": len(errors) == 0, "errors": errors}

    def _validate_phone_number(self, phone_number: str) -> bool:
        """Validate phone number format."""
        import re

        # Basic phone number validation (E.164 format)
        pattern = r"^\+[1-9]\d{1,14}$"
        return bool(re.match(pattern, phone_number))

    async def _test_twilio_connection(
        self, provider_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test Twilio connection."""
        try:
            client = TwilioClient(
                provider_config["account_sid"], provider_config["auth_token"]
            )

            # Test by fetching account info
            account = client.api.accounts(provider_config["account_sid"]).fetch()

            return {
                "success": True,
                "account_sid": account.sid,
                "status": account.status,
            }

        except TwilioException as e:
            return {"success": False, "error": str(e)}

    async def _test_webhook_connection(
        self, provider_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test webhook connection."""
        try:
            webhook_url = provider_config["webhook_url"]

            # Send test request
            test_payload = {"test": True, "message": "Test message from AlertService"}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    webhook_url,
                    json=test_payload,
                    headers={"Content-Type": "application/json"},
                )

                return {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "response": response.text[:200] if response.text else "",
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def check_delivery_status(
        self, notification_id: int, response_data: Dict[str, Any]
    ) -> str:
        """Check SMS delivery status."""
        if self.provider == "twilio" and self.client:
            try:
                # Get message SID from response data
                results = response_data.get("results", [])

                for result in results:
                    if result.get("success") and result.get("message_sid"):
                        message_sid = result["message_sid"]

                        # Fetch message status from Twilio
                        message = self.client.messages(message_sid).fetch()

                        if message.status in ["delivered", "received"]:
                            return "delivered"
                        elif message.status in ["failed", "undelivered"]:
                            return "failed"
                        else:
                            return "pending"

            except Exception as e:
                logger.error(f"Error checking Twilio delivery status: {str(e)}")

        return "delivered"  # Default assumption

    def get_channel_info(self) -> Dict[str, Any]:
        """Get channel information."""
        return {
            "name": "SMS",
            "type": "sms",
            "description": "SMS notifications via various providers",
            "providers": ["twilio", "webhook"],
            "config_fields": [
                {
                    "name": "provider",
                    "type": "select",
                    "required": True,
                    "description": "SMS provider",
                    "options": ["twilio", "webhook"],
                },
                {
                    "name": "provider_config",
                    "type": "object",
                    "required": True,
                    "description": "Provider-specific configuration",
                },
                {
                    "name": "to_numbers",
                    "type": "array",
                    "required": True,
                    "description": "List of recipient phone numbers (E.164 format)",
                },
            ],
            "provider_configs": {
                "twilio": [
                    {
                        "name": "account_sid",
                        "type": "string",
                        "required": True,
                        "description": "Twilio Account SID",
                    },
                    {
                        "name": "auth_token",
                        "type": "string",
                        "required": True,
                        "description": "Twilio Auth Token",
                        "secret": True,
                    },
                    {
                        "name": "from_number",
                        "type": "string",
                        "required": True,
                        "description": "Twilio phone number (E.164 format)",
                    },
                ],
                "webhook": [
                    {
                        "name": "webhook_url",
                        "type": "string",
                        "required": True,
                        "description": "Webhook URL for SMS sending",
                    },
                    {
                        "name": "webhook_params",
                        "type": "object",
                        "required": False,
                        "description": "Additional webhook parameters",
                    },
                ],
            },
        }
