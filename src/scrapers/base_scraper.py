"""
Base Scraper Class
Clase base para todos los scrapers de plataformas.
"""

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime
import json
import csv
from pathlib import Path

import yaml


# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ProductData:
    """Estructura para datos de un producto."""
    platform: str
    address_name: str
    zip_code: str
    zone_type: str
    product_name: str
    product_brand: str
    product_price: Optional[float] = None
    delivery_fee: Optional[float] = None
    service_fee: Optional[float] = None
    estimated_delivery_time: Optional[str] = None
    active_discounts: Optional[str] = None
    availability: Optional[str] = None
    final_total_price: Optional[float] = None
    scraped_at: str = ""
    
    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()


@dataclass
class ScraperConfig:
    """Configuración para un scraper."""
    delay_between_requests: int = 3
    page_load_timeout: int = 30
    max_retries: int = 3
    user_agent: str = ""
    headless: bool = True


class BaseScraper(ABC):
    """
    Clase base abstracta para scrapers.
    Cada plataforma (Rappi, Uber Eats, DiDi Food) debe implementar sus propios scrapers.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Inicializar el scraper con configuración."""
        self.config = self._load_config(config_path)
        self.scraper_config = ScraperConfig(
            delay_between_requests=self.config.get('scraping', {}).get('delay_between_requests', 3),
            page_load_timeout=self.config.get('scraping', {}).get('page_load_timeout', 30),
            max_retries=self.config.get('scraping', {}).get('max_retries', 3),
            user_agent=self.config.get('scraping', {}).get('user_agent', ''),
            headless=self.config.get('scraping', {}).get('headless', True)
        )
        self.platform_name = "base"
        self.data: List[ProductData] = []
        
    def _load_config(self, config_path: str) -> dict:
        """Cargar configuración desde archivo YAML."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return {}
    
    def get_addresses(self) -> List[Dict]:
        """Obtener lista de direcciones a scrapear."""
        return self.config.get('addresses', [])
    
    def get_reference_products(self) -> Dict:
        """Obtener productos de referencia."""
        return self.config.get('reference_products', {})
    
    @abstractmethod
    def initialize_browser(self):
        """Inicializar el navegador (Playwright/Selenium)."""
        pass
    
    @abstractmethod
    def close_browser(self):
        """Cerrar el navegador."""
        pass
    
    @abstractmethod
    def search_product(self, address: Dict, product: Dict) -> ProductData:
        """
        Buscar un producto específico en una dirección.
        Debe ser implementado por cada subclase.
        """
        pass
    
    def scrape_all(self) -> List[ProductData]:
        """
        Ejecutar scraping para todas las direcciones y productos.
        """
        logger.info(f"Starting scrape for {self.platform_name}")
        
        self.initialize_browser()
        
        try:
            addresses = self.get_addresses()
            products = self.get_reference_products()
            
            # Iterar sobre cada dirección
            for address in addresses:
                logger.info(f"Scraping address: {address['name']} ({address['zip_code']})")
                
                # Iterar sobre productos de fast food
                for product in products.get('fast_food', []):
                    try:
                        product_data = self.search_product(address, product)
                        self.data.append(product_data)
                        logger.info(f"  ✓ Scraped: {product['name']} at {address['name']}")
                    except Exception as e:
                        logger.error(f"  ✗ Error scraping {product['name']}: {e}")
                    
                    # Delay entre requests
                    time.sleep(self.scraper_config.delay_between_requests)
                
                # Iterar sobre productos retail
                for product in products.get('retail', []):
                    try:
                        product_data = self.search_product(address, product)
                        self.data.append(product_data)
                        logger.info(f"  ✓ Scraped: {product['name']} at {address['name']}")
                    except Exception as e:
                        logger.error(f"  ✗ Error scraping {product['name']}: {e}")
                    
                    time.sleep(self.scraper_config.delay_between_requests)
                    
        finally:
            self.close_browser()
        
        logger.info(f"Scraping complete. Total records: {len(self.data)}")
        return self.data
    
    def save_to_csv(self, output_path: str = "data/raw/scraped_data.csv"):
        """Guardar datos en CSV."""
        if not self.data:
            logger.warning("No data to save")
            return
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            if len(self.data) > 0:
                writer = csv.DictWriter(f, fieldnames=asdict(self.data[0]).keys())
                writer.writeheader()
                for item in self.data:
                    writer.writerow(asdict(item))
        
        logger.info(f"Data saved to {output_path}")
    
    def save_to_json(self, output_path: str = "data/raw/scraped_data.json"):
        """Guardar datos en JSON."""
        if not self.data:
            logger.warning("No data to save")
            return
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump([asdict(item) for item in self.data], f, indent=2, ensure_ascii=False)
        
        logger.info(f"Data saved to {output_path}")
    
    def get_data(self) -> List[ProductData]:
        """Obtener los datos recolectados."""
        return self.data
