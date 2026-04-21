"""
Rappi Scraper
Scraper específico para Rappi usando Playwright.
"""

import time
import logging
from typing import Optional
from dataclasses import asdict

from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

from base_scraper import BaseScraper, ProductData, ScraperConfig


logger = logging.getLogger(__name__)


class RappiScraper(BaseScraper):
    """
    Scraper para Rappi.
    Usa Playwright para manejar contenido dinámico (JavaScript).
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        super().__init__(config_path)
        self.platform_name = "Rappi"
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
        # URL base de Rappi
        self.base_url = "https://www.rappi.com.mx"
        
    def initialize_browser(self):
        """Inicializar navegador Playwright."""
        logger.info("Initializing Playwright browser for Rappi...")
        
        playwright = sync_playwright().start()
        self.playwright = playwright  # Keep reference to not get garbage collected
        
        self.browser = playwright.chromium.launch(
            headless=self.scraper_config.headless
        )
        
        self.context = self.browser.new_context(
            user_agent=self.scraper_config.user_agent,
            viewport={'width': 1280, 'height': 720},
            locale='es-MX'
        )
        
        self.page = self.context.new_page()
        
        # Set default timeout
        self.page.set_default_timeout(self.scraper_config.page_load_timeout * 1000)
        
        logger.info("Browser initialized successfully")
    
    def close_browser(self):
        """Cerrar navegador."""
        if self.browser:
            self.browser.close()
            self.playwright.stop()
            logger.info("Browser closed")
    
    def _navigate_to_address(self, zip_code: str) -> bool:
        """
        Navegar a Rappi con código postal específico.
        Returns True if successful.
        """
        try:
            # Navigate to Rappi
            self.page.goto(self.base_url, wait_until="networkidle", timeout=30000)
            
            # Wait for the location input to appear
            self.page.wait_for_selector('input[placeholder*="dirección"], input[placeholder*="CP"]', timeout=10000)
            
            # Click on the address input
            self.page.click('input[placeholder*="dirección"], input[placeholder*="CP"]')
            
            # Type the zip code
            self.page.fill('input[placeholder*="dirección"], input[placeholder*="CP"]', zip_code)
            
            # Wait for suggestions
            time.sleep(2)
            
            # Press Enter or click first suggestion
            try:
                self.page.keyboard.press('Enter')
                time.sleep(3)
            except:
                pass
            
            # Check if we successfully set location
            current_url = self.page.url
            logger.info(f"Navigated to zip code {zip_code}, URL: {current_url}")
            return True
            
        except PlaywrightTimeout:
            logger.error(f"Timeout navigating to zip code {zip_code}")
            return False
        except Exception as e:
            logger.error(f"Error navigating to zip code {zip_code}: {e}")
            return False
    
    def _search_product(self, product_name: str) -> bool:
        """
        Buscar un producto en la barra de búsqueda.
        Returns True if search results appear.
        """
        try:
            # Wait for search input
            search_selector = 'input[placeholder*="Búsqueda"], input[placeholder*="Buscar"], input[type="search"]'
            self.page.wait_for_selector(search_selector, timeout=5000)
            
            # Clear and fill search
            self.page.click(search_selector)
            self.page.fill(search_selector, product_name)
            
            # Press Enter to search
            self.page.keyboard.press('Enter')
            
            # Wait for search results to load
            time.sleep(3)
            
            return True
            
        except PlaywrightTimeout:
            logger.error(f"Timeout searching for product: {product_name}")
            return False
        except Exception as e:
            logger.error(f"Error searching for product {product_name}: {e}")
            return False
    
    def _extract_product_info(self) -> Optional[dict]:
        """
        Extraer información del primer producto en los resultados de búsqueda.
        Returns dict with product info or None if no product found.
        """
        try:
            # Wait for products to load
            time.sleep(2)
            
            # Try to find product cards - different selectors for Rappi
            product_selectors = [
                'article[data-testid="product-card"]',
                '[class*="product-card"]',
                '[class*="ProductCard"]',
                '[data-r Carpenter*="product"]',
                'div[class*="restaurant-card"]'
            ]
            
            product_info = None
            
            for selector in product_selectors:
                try:
                    self.page.wait_for_selector(selector, timeout=3000)
                    
                    # Get product name
                    name_elem = self.page.query_selector(f'{selector} [class*="name"], {selector} [class*="title"]')
                    product_name = name_elem.inner_text() if name_elem else "N/A"
                    
                    # Get price
                    price_elem = self.page.query_selector(f'{selector} [class*="price"] span, {selector} [class*="Price"]')
                    price_text = price_elem.inner_text() if price_elem else "0"
                    # Parse price (remove $ and commas)
                    try:
                        price = float(price_text.replace('$', '').replace(',', '').strip())
                    except:
                        price = 0.0
                    
                    product_info = {
                        'name': product_name,
                        'price': price
                    }
                    break
                    
                except:
                    continue
            
            return product_info
            
        except Exception as e:
            logger.error(f"Error extracting product info: {e}")
            return None
    
    def _get_delivery_info(self) -> dict:
        """
        Obtener información de delivery (fee, tiempo, etc).
        """
        info = {
            'delivery_fee': None,
            'service_fee': None,
            'estimated_time': None,
            'discounts': None
        }
        
        try:
            # Look for delivery fee
            fee_selectors = [
                '[class*="delivery-fee"]',
                '[class*="shipping"] span',
                'span[class*="fee"]'
            ]
            
            for selector in fee_selectors:
                try:
                    elem = self.page.query_selector(selector)
                    if elem:
                        fee_text = elem.inner_text()
                        # Parse fee
                        try:
                            fee = float(fee_text.replace('$', '').replace(',', '').strip())
                            info['delivery_fee'] = fee
                        except:
                            pass
                        break
                except:
                    continue
            
            # Look for delivery time
            time_selectors = [
                '[class*="time"]',
                '[class*="delivery"] span',
                'span[class*="minutes"]'
            ]
            
            for selector in time_selectors:
                try:
                    elem = self.page.query_selector(selector)
                    if elem:
                        info['estimated_time'] = elem.inner_text()
                        break
                except:
                    continue
                    
        except Exception as e:
            logger.warning(f"Could not extract delivery info: {e}")
        
        return info
    
    def search_product(self, address: dict, product: dict) -> ProductData:
        """
        Buscar un producto específico en una dirección.
        """
        # Navigate to address
        self._navigate_to_address(address['zip_code'])
        
        # Search for product
        search_success = self._search_product(product['name'])
        
        # Create base product data
        product_data = ProductData(
            platform=self.platform_name,
            address_name=address['name'],
            zip_code=address['zip_code'],
            zone_type=address.get('zone_type', 'unknown'),
            product_name=product['name'],
            product_brand=product.get('brand', 'N/A')
        )
        
        if search_success:
            # Extract product info
            product_info = self._extract_product_info()
            if product_info:
                product_data.product_price = product_info.get('price')
            
            # Get delivery info
            delivery_info = self._get_delivery_info()
            product_data.delivery_fee = delivery_info.get('delivery_fee')
            product_data.estimated_delivery_time = delivery_info.get('estimated_time')
            
            # Calculate final price if we have all components
            if product_data.product_price and product_data.delivery_fee:
                product_data.final_total_price = product_data.product_price + product_data.delivery_fee
        
        return product_data


def main():
    """Función para testing directo del scraper."""
    print("=" * 60)
    print("RAPPI SCRAPER - TEST")
    print("=" * 60)
    
    scraper = RappiScraper()
    
    # Test with one address and one product
    test_address = {
        'name': 'Polanco',
        'zip_code': '11560',
        'zone_type': 'upscale'
    }
    
    test_product = {
        'name': 'Big Mac',
        'brand': "McDonald's"
    }
    
    print(f"Testing with address: {test_address['name']}")
    print(f"Product: {test_product['name']}")
    
    try:
        scraper.initialize_browser()
        
        result = scraper.search_product(test_address, test_product)
        
        print("\nResult:")
        print(asdict(result))
        
        scraper.close_browser()
        
    except Exception as e:
        print(f"Error during test: {e}")


if __name__ == "__main__":
    main()
