"""
Module for handling notifications via Telegram.
"""
import logging
from time import sleep
from typing import Optional
import requests
from .config import TelegramConfig

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Handles sending messages to a Telegram chat."""
    # pylint: disable=too-few-public-methods
    def __init__(self, config: Optional[TelegramConfig]):
        self.config = config
        self.api_url = "https://api.telegram.org/bot{token}/sendMessage"

    def send(self, message: str, parse_mode: str = "Markdown"):
        """
        Sends a message to the configured Telegram chat.
        Retries up to 3 times on failure.
        """
        if not self.config or not self.config.enabled:
            logger.debug("Telegram notification disabled or not configured.")
            return

        url = self.api_url.format(token=self.config.token)
        data = {
            "chat_id": self.config.chat_id,
            "text": message,
            "parse_mode": parse_mode
        }

        retries = 3
        for attempt in range(1, retries + 1):
            try:
                response = requests.post(url, data=data, timeout=10)
                response.raise_for_status()
                logger.info("Telegram message sent successfully.")
                return
            except requests.RequestException as e:
                logger.warning(
                    "Failed to send Telegram message (Attempt %d/%d): %s",
                    attempt, retries, e
                )
                if attempt < retries:
                    sleep(2)

        logger.error("Failed to send Telegram message after all retries.")
