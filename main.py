import sys
import argparse
from loguru import logger

from src.monitor import AirtableMonitor

def main():
    parser = argparse.ArgumentParser(
        description="Airtable to Ansible Inventory Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--once", 
        action="store_true", 
        help="Выполнить одну проверку и остановиться"
    )
    parser.add_argument(
        "--test", 
        action="store_true", 
        help="Тестировать соединение с Airtable"
    )
    parser.add_argument(
        "--config-check", 
        action="store_true", 
        help="Проверить конфигурацию и показать настройки"
    )
    
    args = parser.parse_args()
    
    try:
        monitor = AirtableMonitor()
        
        if args.config_check:
            logger.info("Configuration loaded successfully")
            logger.info(f"Tables for monitoring: {monitor.config.AIRTABLE_TABLES}")
            logger.info(f"Inventory path: {monitor.config.ANSIBLE_INVENTORY_PATH}")
            logger.info(f"Check interval: {monitor.config.POLLING_INTERVAL} seconds")
            logger.info(f"Monitoring enabled: {monitor.config.POLLING_ENABLED}")
            return
        
        if args.test:
            logger.info("Testing Airtable connection...")
            success = monitor.test_connection()
            if success:
                logger.info("Airtable connection successful")
                
                for table_name in monitor.config.AIRTABLE_TABLES:
                    try:
                        records = monitor.airtable.get_all_records_from_tables([table_name])
                        record_count = len(records.get(table_name, []))
                        logger.info(f"Table {table_name}: {record_count} records")
                    except Exception as e:
                        logger.warning(f"Error getting data from table {table_name}: {e}")
            else:
                logger.error("Airtable connection error")
            return
        
        if args.once:
            logger.info("Running single check...")
            monitor.run_single_check(1)
        else:
            logger.info("Starting continuous monitoring...")
            logger.info("Press Ctrl+C to stop")
            monitor.start_monitoring()
            
    except KeyboardInterrupt:
        logger.info("Stop signal received")
    except Exception as e:
        logger.error(f"Critical error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()