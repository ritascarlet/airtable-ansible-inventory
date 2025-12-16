import requests
from typing import List, Dict, Optional
from loguru import logger


class AirtableClient:
    
    def __init__(self, api_key: str, base_id: str, table_name: str):
        self.api_key = api_key
        self.base_id = base_id
        self.table_name = table_name
        self.base_url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
        
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def get_all_records(self) -> List[Dict]:
        try:
            records = []
            url = self.base_url
            
            while url:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                
                data = response.json()
                records.extend(data.get('records', []))
                url = data.get('offset') and f"{self.base_url}?offset={data['offset']}"
                
            logger.info(f"Получено {len(records)} записей из таблицы {self.table_name}")
            return records
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении данных из Airtable: {e}")
            raise
    
    def get_all_records_from_tables(self, table_names: List[str]) -> Dict[str, List[Dict]]:
        all_records = {}
        
        for table_name in table_names:
            try:
                temp_client = AirtableClient(self.api_key, self.base_id, table_name)
                records = temp_client.get_all_records()
                all_records[table_name] = records
                logger.info(f"Таблица {table_name}: {len(records)} записей")
                
            except Exception as e:
                logger.error(f"Ошибка получения данных из таблицы {table_name}: {e}")
                all_records[table_name] = []
        
        return all_records
    
    def test_connection(self) -> bool:
        try:
            response = requests.get(self.base_url, headers=self.headers, params={"maxRecords": 1})
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Ошибка тестирования соединения: {e}")
            return False