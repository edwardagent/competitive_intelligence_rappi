"""
Uber Eats Scraper
Scraper para Uber Eats usando Playwright.
"""

import time
import re
import logging
from typing import Optional, Dict
from dataclasses import asdict

from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

from base_scraper import BaseScraper, ProductData


logger = logging.getLogger(__name__)


class UberEatsScraper(BaseScraper):
    """
    Scraper para Uber Eats.
    Usa Playwright para manejar contenido dinámico (JavaScript).
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        super().__init__(config_path)
        self.platform_name = "UberEats"
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
        # URL base de Uber Eats México
        self.base_url = "https://www.ubereats.com/mx"
        
    def initialize_browser(self):
        """Inicializar navegador Playwright con configuraciones stealth."""
        logger.info("Initializing Playwright browser for Uber Eats...")
        
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
            
            # Aceptar cookies primero si aparece el banner
            try:
                accept_btn = self.page.query_selector('button[aria-label="Aceptar"]')
                if accept_btn and accept_btn.is_visible():
                    accept_btn.click()
                    logger.info("Accepted cookie banner")
                    time.sleep(1)
            except Exception as e:
                logger.debug(f"No cookie banner or could not click: {e}")
            
            # Buscar input de ubicación
            location_selectors = [
                'input[placeholder*="Ingresa la dirección"]',
                'input[placeholder*="dirección de entrega"]',
                'input[aria-label*="address"]',
                'input[placeholder*="address"]'
            ]
            
            address_input = None
            for selector in location_selectors:
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
                
                # Buscar sugerencias (li elements)
                try:
                    suggestions = self.page.query_selector_all('li')
                    if suggestions and len(suggestions) > 0:
                        # Buscar sugerencia que contenga el código postal
                        for sug in suggestions[:10]:
                            text = sug.inner_text()
                            if zip_code in text or 'Ciudad de México' in text or 'CDMX' in text:
                                sug.click()
                                logger.info(f"Clicked suggestion: {text[:50]}")
                                time.sleep(3)
                                return True
                        # Si no encontramos, click en la primera
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
            
            # Buscar input de búsqueda - cambia después de seleccionar dirección
            search_selectors = [
                'input[placeholder*="Buscar en Uber"]',
                'input[placeholder*="Buscar comida"]',
                'input[placeholder*="Search"]',
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
            
            # Buscar producto - Uber Eats muestra resultados differently
            search_terms = ['big mac', 'whopper', 'nuggets', 'combo', 'coca-cola', 'agua']
            for i, line in enumerate(lines):
                line_lower = line.lower().strip()
                
                if any(term in line_lower for term in search_terms):
                    product_name = line.strip() if 0 < len(line.strip()) < 100 else None
                    
                    # Buscar precio en líneas cercanas
                    for j in range(max(0, i-5), min(len(lines), i+10)):
                        price_line = lines[j].strip()
                        # Skip lines that are just numbers (like "554 results")
                        if price_line.isdigit() and len(price_line) > 2:
                            continue
                        price_match = re.search(r'\$([\d,]+\.?\d*)', price_line)
                        if price_match:
                            price_str = price_match.group(1).replace(',', '')
                            try:
                                price_val = float(price_str)
                                # Uber Eats prices are usually $50-$400 for food
                                if 50 < price_val < 500:
                                    logger.info(f"Found product: {product_name} at ${price_val}")
                                    return {'name': product_name, 'price': price_val}
                            except:
                                pass
                    break
            
            # Fallback: buscar precio en rango válido (no resultados, no precios grandes de pedidos)
            for line in lines:
                # Skip lines that are just numbers
                if line.strip().isdigit() and len(line.strip()) > 2:
                    continue
                price_match = re.search(r'\$([\d,]+\.?\d*)', line)
                if price_match:
                    price_str = price_match.group(1).replace(',', '')
                    try:
                        price_val = float(price_str)
                        # Valid food price range
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
            # Primero buscar el botón de "Costo de envío"
            try:
                fee_buttons = self.page.query_selector_all('button')
                for btn in fee_buttons:
                    text = btn.inner_text()
                    if 'costo de envío' in text.lower() or 'delivery fee' in text.lower():
                        logger.info(f"Found fee button: {text[:50]}")
                        # Click to see the fee
                        btn.click()
                        self._wait_for_page_stable(2)
                        # Get the content after clicking
                        fee_text = self.page.inner_text('body')
                        # Look for price patterns
                        fee_match = re.search(r'\$?([\d,]+\.?\d*)\s*(?:costo|envío|fee)', fee_text, re.IGNORECASE)
                        if not fee_match:
                            # Try just finding any dollar amount near the fee context
                            fee_match = re.search(r'\$([\d,]+\.?\d*)', text)
                        if fee_match:
                            info['delivery_fee'] = float(fee_match.group(1).replace(',', ''))
                        break
            except Exception as e:
                logger.debug(f"Could not click fee button: {e}")
            
            # Ahora buscar en el texto de la página
            body_text = self.page.inner_text('body')
            lines = body_text.split('\n')
            
            for line in lines:
                line_lower = line.lower()
                
                # Free delivery
                if ('envío gratis' in line_lower or 'free delivery' in line_lower or 
                    'free' in line_lower and 'delivery' in line_lower):
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
            
            # Si no encontramos delivery fee, buscar patrones de "$0"
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
    print("UBER EATS SCRAPER - TEST")
    print("=" * 60)
    
    scraper = UberEatsScraper()
    
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
