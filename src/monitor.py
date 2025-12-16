import time
import hashlib
import json
import sys
from datetime import datetime
from loguru import logger

from src.config import Config
from src.airtable_client import AirtableClient
from src.inventory_generator import InventoryGenerator
from src.telegram_notifier import TelegramNotifier


class AirtableMonitor:
    
    def __init__(self):
        self.config = Config()
        self.config.validate()
        
        logger.remove()
        logger.add(
            sys.stdout,
            level=self.config.LOG_LEVEL,
            format="{time:HH:mm:ss} | {level: <8} | {message}",
            colorize=False
        )
        
        self.airtable = AirtableClient(
            self.config.AIRTABLE_API_KEY,
            self.config.AIRTABLE_BASE_ID,
            self.config.AIRTABLE_TABLES[0]
        )
        
        self.inventory_gen = InventoryGenerator(
            self.config.ANSIBLE_INVENTORY_PATH,
            self.config.ANSIBLE_INVENTORY_FORMAT
        )
        
        self.telegram_notifier = None
        if self.config.TELEGRAM_ENABLED:
            topic_id = int(self.config.TELEGRAM_TOPIC_ID) if self.config.TELEGRAM_TOPIC_ID else None
            self.telegram_notifier = TelegramNotifier(
                self.config.TELEGRAM_BOT_TOKEN,
                self.config.TELEGRAM_CHAT_ID,
                topic_id
            )
        
        self.last_data_hash = None
        self.last_check_time = None
        self.last_servers_data = {}
        
        self.pending_changes = []
        self.last_change_tact = None
        self.tacts_since_last_change = 0
        self.is_editing_session = False
        
        logger.info("AirtableMonitor initialized")
    
    def _get_data_hash(self, data: list) -> str:
        sorted_data = sorted(data, key=lambda x: x.get('id', ''))
        data_str = json.dumps(sorted_data, sort_keys=True, default=str)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def _extract_server_data(self, records: list) -> dict:
        servers = {}
        for record in records:
            fields = record.get('fields', {})
            server_name = fields.get('Server name', '').strip()
            if server_name:
                servers[server_name] = {
                    'id': record.get('id'),
                    'fields': fields
                }
        return servers
    
    def _detect_changes(self, current_servers: dict, previous_servers: dict) -> list:
        changes = []
        
        current_names = set(current_servers.keys())
        previous_names = set(previous_servers.keys())
        
        added_names = current_names - previous_names
        removed_names = previous_names - current_names
        modified_names = current_names & previous_names
        
        for name in added_names:
            server_data = current_servers[name]
            changes.append({
                'type': 'added',
                'server_name': name,
                'details': {
                    'IP': server_data['fields'].get('Server IP', ''),
                    'OS': server_data['fields'].get('OS Name', ''),
                    'Location': server_data['fields'].get('Location', ''),
                    'Group': server_data['fields'].get('Group', '')
                }
            })
        
        for name in removed_names:
            server_data = previous_servers[name]
            changes.append({
                'type': 'removed',
                'server_name': name,
                'details': {
                    'IP': server_data['fields'].get('Server IP', ''),
                    'OS': server_data['fields'].get('OS Name', ''),
                    'Location': server_data['fields'].get('Location', ''),
                    'Group': server_data['fields'].get('Group', '')
                }
            })
        
        for name in modified_names:
            current_fields = current_servers[name]['fields']
            previous_fields = previous_servers[name]['fields']
            
            fields_changed = []
            for field_name in ['Server IP', 'OS Name', 'Location', 'Group', 'Status', 'User']:
                current_value = current_fields.get(field_name, '').strip()
                previous_value = previous_fields.get(field_name, '').strip()
                if current_value != previous_value:
                    fields_changed.append(field_name)
            
            if fields_changed:
                changes.append({
                    'type': 'modified',
                    'server_name': name,
                    'fields_changed': fields_changed,
                    'details': {
                        'IP': current_fields.get('Server IP', ''),
                        'OS': current_fields.get('OS Name', ''),
                        'Location': current_fields.get('Location', ''),
                        'Group': current_fields.get('Group', '')
                    }
                })
        
        return changes
    
    def _should_send_alert(self, current_tact: int) -> bool:
        if not self.pending_changes:
            return False
        
        if self.last_change_tact is None:
            return False
        
        if not self.is_editing_session:
            return False
        
        tacts_passed = current_tact - self.last_change_tact
        return tacts_passed >= self.config.ALERT_TACTS_TIMEOUT
    
    def _send_pending_alert(self) -> bool:
        if not self.pending_changes:
            return True
        
        logger.info(f"Sending alert with {len(self.pending_changes)} changes after {self.config.ALERT_TACTS_TIMEOUT} tacts")
        
        if self.telegram_notifier:
            success = self.telegram_notifier.send_change_alert(self.pending_changes)
            if success:
                logger.info("Telegram alert sent successfully")
            else:
                logger.error("Failed to send Telegram alert")
                return False
        
        self.pending_changes = []
        self.last_change_tact = None
        self.tacts_since_last_change = 0
        self.is_editing_session = False
        return True
    
    def check_for_changes(self, current_tact: int) -> bool:
        try:
            logger.info("Checking for changes in Airtable...")
            
            all_tables_data = self.airtable.get_all_records_from_tables(self.config.AIRTABLE_TABLES)
            
            all_records = []
            for table_name, records in all_tables_data.items():
                logger.info(f"Table {table_name}: {len(records)} records")
                all_records.extend(records)
            
            current_hash = self._get_data_hash(all_records)
            logger.info(f"Total hash: {current_hash}")
            
            if self.last_data_hash is None:
                logger.info("Initial data load")
                self.last_data_hash = current_hash
                self.last_check_time = datetime.now()
                self.last_servers_data = self._extract_server_data(all_records)
                return True
            
            if current_hash != self.last_data_hash:
                logger.info("CHANGES DETECTED IN AIRTABLE!")
                logger.info(f"Old hash: {self.last_data_hash}")
                logger.info(f"New hash: {current_hash}")
                
                current_servers = self._extract_server_data(all_records)
                changes = self._detect_changes(current_servers, self.last_servers_data)
                
                if changes:
                    logger.info(f"Detected {len(changes)} changes:")
                    for change in changes:
                        logger.info(f"  {change['type']}: {change['server_name']}")
                    
                    self.is_editing_session = True
                    self.last_change_tact = current_tact
                    self.tacts_since_last_change = 0
                    
                    self.pending_changes = changes
                    logger.info(f"Started editing session, waiting for {self.config.ALERT_TACTS_TIMEOUT} tacts after last change")
                
                self.last_data_hash = current_hash
                self.last_check_time = datetime.now()
                self.last_servers_data = current_servers
                return True
            else:
                logger.info("No changes detected")
                
                if self.is_editing_session:
                    self.tacts_since_last_change += 1
                    logger.info(f"Editing session active, tacts since last change: {self.tacts_since_last_change}")
                    
                    tacts_passed = current_tact - self.last_change_tact
                    logger.info(f"Tacts passed: {tacts_passed}, required: {self.config.ALERT_TACTS_TIMEOUT}")
                    
                    if self._should_send_alert(current_tact):
                        logger.info("Alert timeout reached, sending alert")
                        self.is_editing_session = False
                        self._send_pending_alert()
                
                return False
                
        except Exception as e:
            logger.error(f"Error checking for changes: {e}")
            return False
    
    def update_inventory(self) -> bool:
        try:
            logger.info("Updating Ansible inventory with separate group files...")
            
            all_tables_data = self.airtable.get_all_records_from_tables(self.config.AIRTABLE_TABLES)
            
            all_servers = []
            for table_name, records in all_tables_data.items():
                logger.info(f"Processing table {table_name}: {len(records)} records")
                all_servers.extend(records)
            
            if not all_servers:
                logger.warning("No server data in Airtable")
                return False
            
            created_files = self.inventory_gen.generate_separate_group_files(all_servers)
            
            # Генерируем дополнительный VPN инвентарь
            vpn_filepath = self.inventory_gen.generate_vpn_inventory(all_servers)
            created_files["vpn_servers"] = vpn_filepath
            
            logger.info("Created files:")
            for group_name, filepath in created_files.items():
                logger.info(f"  - {group_name}: {filepath}")
            
            logger.info("Inventory successfully updated with separate group files and VPN inventory")
            return True
            
        except Exception as e:
            logger.error(f"Error updating inventory: {e}")
            return False
    
    def run_single_check(self, current_tact: int):
        try:
            logger.info("=== Starting check ===")
            
            has_changes = self.check_for_changes(current_tact)
            
            if has_changes:
                success = self.update_inventory()
                if success:
                    logger.info("Inventory successfully updated")
                else:
                    logger.error("Error updating inventory")
            else:
                logger.info("No changes, inventory not updated")
            
            logger.info("=== Check completed ===")
            
        except Exception as e:
            logger.error(f"Error during check: {e}")
    
    def test_connection(self) -> bool:
        try:
            logger.info("Testing Airtable connection...")
            airtable_success = self.airtable.test_connection()
            
            telegram_success = True
            if self.telegram_notifier:
                logger.info("Testing Telegram connection...")
                telegram_success = self.telegram_notifier.test_connection()
            
            if airtable_success and telegram_success:
                logger.info("All connections successful")
                return True
            else:
                if not airtable_success:
                    logger.error("Airtable connection error")
                if not telegram_success:
                    logger.error("Telegram connection error")
                return False
        except Exception as e:
            logger.error(f"Connection test error: {e}")
            return False
    
    def start_monitoring(self):
        if not self.config.POLLING_ENABLED:
            logger.info("Monitoring disabled in configuration")
            return
        
        logger.info("Starting Airtable monitoring with separate group files...")
        logger.info(f"Inventory files will be saved to: {self.config.ANSIBLE_INVENTORY_PATH}")
        logger.info(f"Check interval: {self.config.POLLING_INTERVAL} seconds")
        logger.info(f"Alert timeout: {self.config.ALERT_TACTS_TIMEOUT} tacts")
        logger.info("Each server group will be in separate file")
        logger.info("Change something in Airtable and watch the reaction!")
        logger.info("=" * 60)
        
        tact_count = 0
        
        try:
            while True:
                tact_count += 1
                logger.info(f"Tact #{tact_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                self.run_single_check(tact_count)
                
                logger.info("-" * 40)
                logger.info(f"Waiting {self.config.POLLING_INTERVAL} seconds until next tact...")
                time.sleep(self.config.POLLING_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("Stop signal received...")
        except Exception as e:
            logger.error(f"Critical monitoring error: {e}")
        finally:
            logger.info("Monitoring stopped")