import requests
from typing import List, Dict, Optional
from loguru import logger


class TelegramNotifier:
    
    def __init__(self, bot_token: str, chat_id: str, topic_id: Optional[int] = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.topic_id = topic_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        try:
            url = f"{self.base_url}/sendMessage"
            
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            
            if self.topic_id is not None:
                payload["message_thread_id"] = self.topic_id
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("Telegram message sent successfully")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def send_change_alert(self, changes: List[Dict]) -> bool:
        if not changes:
            return True
        
        message = self._format_changes_message(changes)
        return self.send_message(message)
    
    def _format_changes_message(self, changes: List[Dict]) -> str:
        message_parts = ["<b>🔔 Airtable Changes Detected</b>\n"]
        
        for change in changes:
            change_type = change.get('type', 'unknown')
            server_name = change.get('server_name', 'Unknown')
            
            if change_type == 'added':
                message_parts.append(f"<b>➕ Added:</b> {server_name}")
            elif change_type == 'removed':
                message_parts.append(f"<b>➖ Removed:</b> {server_name}")
            elif change_type == 'modified':
                message_parts.append(f"<b>✏️ Modified:</b> {server_name}")
                fields_changed = change.get('fields_changed', [])
                if fields_changed:
                    changes_text = ", ".join(fields_changed)
                    message_parts.append(f"   <i>Changed fields: {changes_text}</i>")
            
            details = change.get('details', {})
            if details:
                details_text = []
                for key, value in details.items():
                    if value:
                        details_text.append(f"{key}: {value}")
                if details_text:
                    message_parts.append(f"   <i>{', '.join(details_text)}</i>")
            
            message_parts.append("")
        
        return "\n".join(message_parts)
    
    def test_connection(self) -> bool:
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            bot_info = response.json()
            logger.info(f"Telegram bot connection successful: {bot_info.get('result', {}).get('first_name', 'Unknown')}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram bot connection test failed: {e}")
            return False
