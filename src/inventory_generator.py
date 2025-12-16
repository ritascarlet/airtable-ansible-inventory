import yaml
import os
from typing import List, Dict, Any
from loguru import logger


COUNTRY_MAPPING = {
    'Germany': 'DE',
    'Deutschland': 'DE',
    'Russian Federation': 'RU',
    'Russia': 'RU',
    'Россия': 'RU',
    'Finland': 'FI',
    'Suomi': 'FI',
    'United States': 'US',
    'USA': 'US',
    'United Kingdom': 'GB',
    'UK': 'GB',
    'France': 'FR',
    'Netherlands': 'NL',
    'Holland': 'NL',
    'Poland': 'PL',
    'Polska': 'PL',
    'Czech Republic': 'CZ',
    'Czechia': 'CZ',
    'Austria': 'AT',
    'Switzerland': 'CH',
    'Sweden': 'SE',
    'Norway': 'NO',
    'Denmark': 'DK',
    'Italy': 'IT',
    'Spain': 'ES',
    'Portugal': 'PT',
    'Belgium': 'BE',
    'Ireland': 'IE',
    'Luxembourg': 'LU',
    'Estonia': 'EE',
    'Latvia': 'LV',
    'Lithuania': 'LT',
    'Slovakia': 'SK',
    'Slovenia': 'SI',
    'Croatia': 'HR',
    'Hungary': 'HU',
    'Romania': 'RO',
    'Bulgaria': 'BG',
    'Greece': 'GR',
    'Cyprus': 'CY',
    'Malta': 'MT',
    'Japan': 'JP',
    'China': 'CN',
    'South Korea': 'KR',
    'Singapore': 'SG',
    'Hong Kong': 'HK',
    'Taiwan': 'TW',
    'India': 'IN',
    'Australia': 'AU',
    'New Zealand': 'NZ',
    'Canada': 'CA',
    'Brazil': 'BR',
    'Mexico': 'MX',
    'Argentina': 'AR',
    'Chile': 'CL',
    'Colombia': 'CO',
    'Peru': 'PE',
    'South Africa': 'ZA',
    'Egypt': 'EG',
    'Israel': 'IL',
    'Turkey': 'TR',
    'Ukraine': 'UA',
    'Belarus': 'BY',
    'Kazakhstan': 'KZ',
    'Uzbekistan': 'UZ',
    'Kyrgyzstan': 'KG',
    'Tajikistan': 'TJ',
    'Turkmenistan': 'TM',
    'Moldova': 'MD',
    'Georgia': 'GE',
    'Armenia': 'AM',
    'Azerbaijan': 'AZ'
}


class InventoryGenerator:
    
    def __init__(self, output_path: str = "./inventory", format_type: str = "yaml"):
        self.output_path = output_path
        self.format_type = format_type
    
    def _convert_country_to_code(self, country_name: str) -> str:
        if not country_name:
            return country_name
        
        country_name = country_name.strip()
        
        if country_name in COUNTRY_MAPPING:
            return COUNTRY_MAPPING[country_name]
        
        country_lower = country_name.lower()
        for full_name, code in COUNTRY_MAPPING.items():
            if full_name.lower() == country_lower:
                return code
        
        logger.warning(f"Неизвестная страна: {country_name}, используем оригинальное значение")
        return country_name
    
    def generate_inventory(self, servers_data: List[Dict]) -> Dict[str, Any]:
        inventory = {
            "all": {
                "children": {
                    "servers": {
                        "hosts": {}
                    }
                }
            }
        }
        
        for server in servers_data:
            fields = server.get('fields', {})
            
            hostname = fields.get('Server name', '').strip()
            if not hostname:
                logger.warning(f"Пропускаем сервер без Server name: {server.get('id')}")
                continue
            
            status_value = fields.get('Status', '').strip()
            ansible_port = 22 if status_value.lower() == 'new' else 11041

            host_config = {
                "ansible_host": fields.get('Server IP', '').strip(),
                "ansible_user": fields.get('User', '').strip(),
                "ansible_port": ansible_port,
                "server_name": hostname,
                "status": status_value
            }
            
            if fields.get('Password'):
                host_config['ansible_password'] = fields.get('Password', '').strip()
            
            if fields.get('OS Name'):
                host_config['os_name'] = fields.get('OS Name', '').strip()
            if fields.get('Host provider'):
                host_config['host_provider'] = fields.get('Host provider', '').strip()
            if fields.get('Location'):
                location = fields.get('Location', '').strip()
                host_config['location'] = self._convert_country_to_code(location)
            if fields.get('Group'):
                host_config['group'] = fields.get('Group', '').strip()
            
            host_config = {k: v for k, v in host_config.items() if v is not None}
            
            inventory["all"]["children"]["servers"]["hosts"][hostname] = host_config
            logger.debug(f"Добавлен сервер {hostname} в inventory")
        
        logger.info(f"Сгенерирован inventory для {len(inventory['all']['children']['servers']['hosts'])} серверов")
        return inventory
    
    def save_inventory(self, inventory_data: Dict[str, Any], filename: str = "inventory.yml") -> str:
        os.makedirs(self.output_path, exist_ok=True)
        
        filepath = f"{self.output_path}/{filename}"
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("---\n")
                f.write("all:\n")
                f.write("    children:\n")
                f.write("        servers:\n")
                f.write("            hosts:\n")
                
                servers = inventory_data["all"]["children"]["servers"]["hosts"]
                
                def sort_key(server_name):
                    import re
                    numbers = re.findall(r'\d+', server_name)
                    if numbers:
                        return int(numbers[0])
                    return 999999
                
                sorted_servers = sorted(servers.items(), key=lambda x: sort_key(x[0]))
                
                for i, (server_name, config) in enumerate(sorted_servers):
                    f.write(f"                {server_name}:\n")
                    
                    for key, value in config.items():
                        if isinstance(value, str) and (' ' in value or ':' in value):
                            f.write(f"                    {key}: \"{value}\"\n")
                        else:
                            f.write(f"                    {key}: {value}\n")
                    
                    if i < len(sorted_servers) - 1:
                        f.write("\n")
            
            logger.info(f"Inventory сохранен в {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении inventory: {e}")
            raise
    
    def generate_separate_group_files(self, servers_data: List[Dict]) -> Dict[str, str]:
        groups = {}
        ungrouped_servers = {}
        
        for server in servers_data:
            fields = server.get('fields', {})
            
            hostname = fields.get('Server name', '').strip()
            if not hostname:
                logger.warning(f"Пропускаем сервер без Server name: {server.get('id')}")
                continue
            
            status_value = fields.get('Status', '').strip()
            ansible_port = 22 if status_value.lower() == 'new' else 11041

            host_config = {
                "ansible_host": fields.get('Server IP', '').strip(),
                "ansible_user": fields.get('User', '').strip(),
                "ansible_port": ansible_port,
                "server_name": hostname,
                "status": status_value
            }
            
            if fields.get('Password'):
                host_config['ansible_password'] = fields.get('Password', '').strip()
            
            if fields.get('OS Name'):
                host_config['os_name'] = fields.get('OS Name', '').strip()
            if fields.get('Host provider'):
                host_config['host_provider'] = fields.get('Host provider', '').strip()
            if fields.get('Location'):
                location = fields.get('Location', '').strip()
                host_config['location'] = self._convert_country_to_code(location)
            if fields.get('Group'):
                host_config['group'] = fields.get('Group', '').strip()
            
            host_config = {k: v for k, v in host_config.items() if v is not None}
            
            group_name = fields.get('Group', '').strip()
            if group_name:
                if group_name not in groups:
                    groups[group_name] = {}
                groups[group_name][hostname] = host_config
                logger.debug(f"Добавлен сервер {hostname} в группу {group_name}")
            else:
                ungrouped_servers[hostname] = host_config
                logger.debug(f"Добавлен сервер {hostname} без группы")
        
        created_files = {}
        
        for group_name, servers in groups.items():
            filepath = self._create_group_file(group_name, servers)
            created_files[group_name] = filepath
        
        if ungrouped_servers:
            filepath = self._create_group_file("ungrouped", ungrouped_servers)
            created_files["ungrouped"] = filepath
        
        total_servers = sum(len(servers) for servers in groups.values()) + len(ungrouped_servers)
        logger.info(f"Создано {len(created_files)} файлов для {total_servers} серверов в {len(groups)} группах")
        
        return created_files
    
    def _create_group_file(self, group_name: str, servers: Dict[str, Dict]) -> str:
        os.makedirs(self.output_path, exist_ok=True)
        
        safe_group_name = group_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
        filename = f"{safe_group_name}_inventory.yml"
        filepath = os.path.join(self.output_path, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("---\n")
                
                f.write("all:\n")
                f.write("    children:\n")
                f.write("        servers:\n")
                f.write("            hosts:\n")
                
                def sort_key(server_name):
                    import re
                    numbers = re.findall(r'\d+', server_name)
                    if numbers:
                        return int(numbers[0])
                    return 999999
                
                sorted_servers = sorted(servers.items(), key=lambda x: sort_key(x[0]))
                
                for i, (server_name, config) in enumerate(sorted_servers):
                    f.write(f"                {server_name}:\n")
                    
                    for key, value in config.items():
                        if isinstance(value, str) and (' ' in value or ':' in value):
                            f.write(f"                    {key}: \"{value}\"\n")
                        else:
                            f.write(f"                    {key}: {value}\n")
                    
                    if i < len(sorted_servers) - 1:
                        f.write("\n")
            
            logger.info(f"Создан файл для группы {group_name}: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Ошибка при создании файла для группы {group_name}: {e}")
            raise
    
    def generate_vpn_inventory(self, servers_data: List[Dict]) -> str:
        vpn_groups = {'Remnawave-nodes', '3X-UI'}
        
        logger.info(f"Поиск VPN серверов в группах: {vpn_groups}")
        logger.info(f"Всего серверов для обработки: {len(servers_data)}")
        
        inventory = {
            "all": {
                "children": {
                    "servers": {
                        "hosts": {}
                    }
                }
            }
        }
        
        vpn_servers_found = 0
        all_groups_found = set()
        
        for server in servers_data:
            fields = server.get('fields', {})
            
            hostname = fields.get('Server name', '').strip()
            if not hostname:
                logger.debug("Пропускаем сервер без имени")
                continue
            
            group_name = fields.get('Group', '').strip()
            all_groups_found.add(group_name)
            
            logger.debug(f"Сервер {hostname}, группа: '{group_name}'")
            
            if group_name not in vpn_groups:
                logger.debug(f"Сервер {hostname} не в VPN группе (группа: '{group_name}')")
                continue
            
            vpn_servers_found += 1
            logger.info(f"Найден VPN сервер: {hostname} в группе '{group_name}'")
            
            status_value = fields.get('Status', '').strip()
            ansible_port = 22 if status_value.lower() == 'new' else 11041
            
            host_config = {
                "ansible_host": fields.get('Server IP', '').strip(),
                "ansible_user": fields.get('User', '').strip(),
                "ansible_port": ansible_port,
                "server_name": hostname,
                "status": status_value,
                "group": group_name
            }
            
            if fields.get('Password'):
                host_config['ansible_password'] = fields.get('Password', '').strip()
            
            if fields.get('OS Name'):
                host_config['os_name'] = fields.get('OS Name', '').strip()
            if fields.get('Host provider'):
                host_config['host_provider'] = fields.get('Host provider', '').strip()
            if fields.get('Location'):
                location = fields.get('Location', '').strip()
                host_config['location'] = self._convert_country_to_code(location)
            
            host_config = {k: v for k, v in host_config.items() if v is not None}
            
            inventory["all"]["children"]["servers"]["hosts"][hostname] = host_config
            logger.debug(f"Добавлен VPN сервер {hostname} (группа: {group_name}) в VPN inventory")
        
        logger.info(f"Всего найдено групп в данных: {sorted(all_groups_found)}")
        logger.info(f"VPN серверов найдено: {vpn_servers_found}")
        logger.info(f"Сгенерирован VPN inventory для {len(inventory['all']['children']['servers']['hosts'])} серверов")
        
        if vpn_servers_found == 0:
            logger.warning("VPN серверы не найдены! Проверьте названия групп в Airtable.")
            logger.warning(f"Ожидаемые группы: {vpn_groups}")
            logger.warning(f"Найденные группы: {sorted(all_groups_found)}")
        
        return self.save_vpn_inventory(inventory, "all-vpn-servers.yml")

    def save_vpn_inventory(self, inventory_data: Dict[str, Any], filename: str = "all-vpn-servers.yml") -> str:
        os.makedirs(self.output_path, exist_ok=True)
        
        filepath = f"{self.output_path}/{filename}"
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("---\n")
                f.write("all:\n")
                f.write("    children:\n")
                f.write("        servers:\n")
                f.write("            hosts:\n")
                
                servers = inventory_data["all"]["children"]["servers"]["hosts"]
                
                def sort_key(server_name):
                    import re
                    numbers = re.findall(r'\d+', server_name)
                    if numbers:
                        return int(numbers[0])
                    return 999999
                
                sorted_servers = sorted(servers.items(), key=lambda x: sort_key(x[0]))
                
                for i, (server_name, config) in enumerate(sorted_servers):
                    f.write(f"                {server_name}:\n")
                    
                    for key, value in config.items():
                        if isinstance(value, str) and (' ' in value or ':' in value):
                            f.write(f"                    {key}: \"{value}\"\n")
                        else:
                            f.write(f"                    {key}: {value}\n")
                    
                    if i < len(sorted_servers) - 1:
                        f.write("\n")
            
            logger.info(f"VPN inventory сохранен в {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении VPN inventory: {e}")
            raise

    def generate_from_airtable(self, servers_data: List[Dict], filename: str = "inventory.yml") -> str:
        inventory_data = self.generate_inventory(servers_data)
        return self.save_inventory(inventory_data, filename)
