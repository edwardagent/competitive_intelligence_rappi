"""
DiDi Food Scraper
Scraper para DiDi Food usando Playwright.
"""

import time
import re
import logging
from typing import Optional, Dict
from dataclasses import asdict

from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

from base_scraper import BaseScraper, ProductData


logger = logging.getLogger(__name__)


class DiDiFoodScraper(BaseScraper):
    """
    Scraper para DiDi Food.
    Usa Playwright para manejar contenido dinámico (JavaScript).
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        super().__init__(config_path)
        self.platform_name = "DiDiFood"
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
        # URL base de DiDi Food México
        self.base_url = "https://www.didi-food.com/es-MX/food/"
        
    def initialize_browser(self):
        """Inicializar navegador Playwright con configuraciones stealth."""
        logger.info("Initializing Playwright browser for DiDi Food...")
        
        playwright = sync_playwright().start()
        self.playwright = playwright
        
        self.browser = playwright.chromium.launch(
            headless=self.scraper_config.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 720},
            locale='es-MX',
            timezone_id='America/Mexico_City',
            permissions=['geolocation']
        )
        
        self.page = self.context.new_page()
        
        # Evitar detección de webdriver
        self.page.add_init_script('''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        ''')
        
        self.page.set_default_timeout(self.scraper_config.page_load_timeout * 1000)
        logger.info("Browser initialized successfully")
    
    def close_browser(self):
        """Cerrar navegador."""
        if self.browser:
            self.browser.close()
            self.playwright.stop()
            logger.info("Browser closed")
    
    def _wait_for_page_stable(self, timeout: int = 5):
        """Esperar a que la página se estabilice después de una acción."""
        time.sleep(timeout)
        try:
            self.page.wait_for_load_state('networkidle', timeout=5000)
        except:
            pass
    
    def _select_address(self, zip_code: str) -> bool:
        """
        Seleccionar dirección usando código postal.
        Returns True si fue exitoso.
        """
        try:
            logger.info(f"Selecting address with zip code: {zip_code}")
            
            # Esperar a que cargue la página
            self.page.wait_for_timeout(3000)
            
            # Buscar input de dirección
            address_selectors = [
                'input[placeholder*="Ingresar dirección"]',
                'input[placeholder*="dirección"]',
                'input[aria-label*="address"]',
                'input[type="text"]'
            ]
            
            address_input = None
            for selector in address_selectors:
                try:
                    address_input = self.page.query_selector(selector)
                    if address_input and address_input.is_visible():
                        logger.info(f"Found address input with selector: {selector}")
                        break
                except:
                    continue
            
            if address_input:
                address_input.click()
                time.sleep(1)
                address_input.fill(zip_code)
                time.sleep(2)
                
                # Buscar sugerencias
                try:
                    suggestions = self.page.query_selector_all('li, ul li, div[role="option"]')
                    if suggestions and len(suggestions) > 0:
                        for sug in suggestions[:10]:
                            text = sug.inner_text()
                            if zip_code in text or 'Ciudad' in text or 'CDMX' in text:
                                sug.click()
                                logger.info(f"Clicked suggestion: {text[:50]}")
                                time.sleep(3)
                                return True
                        # Click first suggestion if no match
                        if suggestions[0]:
                            suggestions[0].click()
                            time.sleep(3)
                            return True
                except Exception as e:
                    logger.warning(f"Could not click suggestion: {e}")
                
                # Try pressing Enter
                self.page.keyboard.press('Enter')
                time.sleep(3)
                return True
            
            logger.warning("Could not find address input")
            return False
            
        except Exception as e:
            logger.error(f"Error selecting address: {e}")
            return False
    
    def search_product(self, address: dict, product: dict) -> ProductData:
        """
        Buscar un producto específico con información completa.
        """
        product_data = ProductData(
            platform=self.platform_name,
            address_name=address['name'],
            zip_code=address['zip_code'],
            zone_type=address.get('zone_type', 'unknown'),
            product_name=product['name'],
            product_brand=product.get('brand', 'N/A')
        )
        
        try:
            if self.page.url != self.base_url:
                self.page.goto(self.base_url, timeout=30000)
                self._wait_for_page_stable(5)
            
            # Seleccionar dirección primero
            if not self._select_address(address['zip_code']):
                logger.warning(f"Could not select address {address['zip_code']}")
            
            time.sleep(3)
            
            # Buscar input de búsqueda
            search_selectors = [
                'input[placeholder*="Buscar comida"]',
                'input[placeholder*="Search"]',
                'input[placeholder*="Buscar"]',
                'input[type="search"]'
            ]
            
            search_input = None
            for selector in search_selectors:
                try:
                    search_input = self.page.query_selector(selector)
                    if search_input and search_input.is_visible():
                        break
                except:
                    continue
            
            if not search_input:
                logger.warning("Could not find search input")
                return product_data
            
            search_input.click()
            time.sleep(0.5)
            search_input.fill(product['name'])
            time.sleep(1)
            
            self.page.keyboard.press('Enter')
            self._wait_for_page_stable(5)
            
            logger.info(f"Search submitted for: {product['name']}")
            
            # Extraer información
            product_info = self._extract_product_info()
            if product_info:
                product_data.product_price = product_info.get('price')
                product_data.product_name = product_info.get('name', product_data.product_name)
            
            delivery_info = self._get_delivery_info()
            product_data.delivery_fee = delivery_info.get('delivery_fee')
            product_data.estimated_delivery_time = delivery_info.get('estimated_time')
            product_data.active_discounts = delivery_info.get('discounts')
            
            if product_data.product_price:
                delivery = product_data.delivery_fee or 0
                product_data.final_total_price = round(product_data.product_price + delivery, 2)
            
        except Exception as e:
            logger.error(f"Error searching product: {e}")
        
        return product_data
    
    def _extract_product_info(self) -> Optional[dict]:
        """
        Extraer información del producto: nombre y precio.
        """
        try:
            self._wait_for_page_stable(2)
            body_text = self.page.inner_text('body')
            
            if not body_text or len(body_text) < 50:
                return None
            
            lines = body_text.split('\n')
            
            # Buscar producto
            search_terms = ['big mac', 'whopper', 'nuggets', 'combo', 'coca-cola', 'agua']
            for i, line in enumerate(lines):
                line_lower = line.lower().strip()
                
                if any(term in line_lower for term in search_terms):
                    product_name = line.strip() if 0 < len(line.strip()) < 100 else None
                    
                    # Buscar precio en líneas cercanas
                    for j in range(max(0, i-5), min(len(lines), i+10)):
                        price_line = lines[j].strip()
                        # Skip lines that are just numbers
                        if price_line.isdigit() and len(price_line) > 2:
                            continue
                        price_match = re.search(r'\$([\d,]+\.?\d*)', price_line)
                        if price_match:
                            price_str = price_match.group(1).replace(',', '')
                            try:
                                price_val = float(price_str)
                                if 50 < price_val < 500:
                                    logger.info(f"Found product: {product_name} at ${price_val}")
                                    return {'name': product_name, 'price': price_val}
                            except:
                                pass
                    break
            
            # Fallback: buscar precio en rango válido
            for line in lines:
                if line.strip().isdigit() and len(line.strip()) > 2:
                    continue
                price_match = re.search(r'\$([\d,]+\.?\d*)', line)
                if price_match:
                    price_str = price_match.group(1).replace(',', '')
                    try:
                        price_val = float(price_str)
                        if 50 < price_val < 400:
                            return {'name': 'Unknown', 'price': price_val}
                    except:
                        pass
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting product info: {e}")
            return None
    
    def _get_delivery_info(self) -> dict:
        """
        Extraer información de delivery: fee, tiempo, descuentos.
        """
        info = {
            'delivery_fee': None,
            'estimated_time': None,
            'discounts': None
        }
        
        try:
            body_text = self.page.inner_text('body')
            lines = body_text.split('\n')
            
            for line in lines:
                line_lower = line.lower()
                
                # Free delivery
                if 'envío gratis' in line_lower or 'free delivery' in line_lower:
                    if info['delivery_fee'] is None:
                        info['delivery_fee'] = 0.0
                        info['discounts'] = 'Free Delivery'
                
                # Delivery time
                time_match = re.search(r'(\d+)\s*(?:min|mins|minutes?)', line, re.IGNORECASE)
                if time_match and info['estimated_time'] is None:
                    info['estimated_time'] = f"{time_match.group(1)} min"
                
                # Discounts
                discount_match = re.search(r'(\d+)\s*%', line)
                if discount_match:
                    info['discounts'] = f"{discount_match.group(1)}% off"
            
            # Si no encontramos delivery fee, buscar "$0"
            if info['delivery_fee'] is None:
                for line in lines:
                    if re.search(r'\$?\s*0\.?00?', line):
                        if 'envío' in line.lower() or 'delivery' in line.lower():
                            info['delivery_fee'] = 0.0
                            break
            
        except Exception as e:
            logger.warning(f"Could not extract delivery info: {e}")
        
        return info


def main():
    """Función para testing directo del scraper."""
    print("=" * 60)
    print("DIDI FOOD SCRAPER - TEST")
    print("=" * 60)
    
    scraper = DiDiFoodScraper()
    
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
        for key, value in asdict(result).items():
            print(f"  {key}: {value}")
        scraper.close_browser()
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
