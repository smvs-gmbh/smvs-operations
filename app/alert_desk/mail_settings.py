"""Dedicated TEST-only SendGrid configuration; capture remains the default."""

import re
from email.errors import HeaderParseError
from email.headerregistry import Address
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class MailSettings(BaseSettings):
    environment: str = "development"
    alert_desk_test_enabled: bool = False
    alert_desk_mail_mode: Literal["capture", "sendgrid"] = "capture"
    alert_desk_mail_from: str = "alerts@smvs-gmbh.ch"
    alert_desk_sendgrid_api_key: SecretStr | None = None
    alert_desk_sendgrid_template_id: str = ""
    alert_desk_mail_recipients: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    def validate_delivery(self, recipient):
        allowed = {r.strip().casefold() for r in self.alert_desk_mail_recipients.split(",") if r.strip()}
        try:
            valid = Address(addr_spec=recipient).addr_spec == recipient
            sender_valid = Address(addr_spec=self.alert_desk_mail_from).addr_spec == self.alert_desk_mail_from
        except (ValueError, HeaderParseError):
            valid = sender_valid = False
        if not (
            self.environment == "test" and self.alert_desk_test_enabled
            and self.alert_desk_sendgrid_api_key and self.alert_desk_sendgrid_api_key.get_secret_value()
            and re.fullmatch(r"d-[a-f0-9]{32,64}", self.alert_desk_sendgrid_template_id)
            and valid and sender_valid and recipient.casefold() in allowed
        ):
            raise ValueError("Configure the TEST sender, template, key and approved recipient before sending.")
