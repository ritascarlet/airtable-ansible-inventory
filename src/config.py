import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    
    AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
    AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
    AIRTABLE_TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME', 'Table%201')
    
    AIRTABLE_TABLES = os.getenv('AIRTABLE_TABLES', '').split(',') if os.getenv('AIRTABLE_TABLES') else [AIRTABLE_TABLE_NAME]
    AIRTABLE_TABLES = [table.strip() for table in AIRTABLE_TABLES if table.strip()]
    
    POLLING_INTERVAL = int(os.getenv('POLLING_INTERVAL', 2))
    POLLING_ENABLED = os.getenv('POLLING_ENABLED', 'true').lower() == 'true'
    
    ALERT_TACTS_TIMEOUT = int(os.getenv('ALERT_TACTS_TIMEOUT', 5))
    
    ANSIBLE_INVENTORY_PATH = os.getenv('ANSIBLE_INVENTORY_PATH', '/etc/ansible-airtable')
    ANSIBLE_INVENTORY_FORMAT = os.getenv('ANSIBLE_INVENTORY_FORMAT', 'yaml')
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'airtable_monitor.log')
    
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    TELEGRAM_TOPIC_ID = os.getenv('TELEGRAM_TOPIC_ID')
    TELEGRAM_ENABLED = os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true'
    
    def validate(self):
        if not self.AIRTABLE_API_KEY:
            raise ValueError("AIRTABLE_API_KEY is required")
        if not self.AIRTABLE_BASE_ID:
            raise ValueError("AIRTABLE_BASE_ID is required")
        
        if self.TELEGRAM_ENABLED:
            if not self.TELEGRAM_BOT_TOKEN:
                raise ValueError("TELEGRAM_BOT_TOKEN is required when TELEGRAM_ENABLED=true")
            if not self.TELEGRAM_CHAT_ID:
                raise ValueError("TELEGRAM_CHAT_ID is required when TELEGRAM_ENABLED=true")