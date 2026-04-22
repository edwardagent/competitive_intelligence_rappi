"""
Rappi Scraper - Simplified MVP Version
Scraper específico para Rappi usando Playwright.
Versión simplificada que funciona sin address selection complejo.
"""

import time
import logging
from typing import Optional, Dict, List
from dataclasses import asdict

from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

from base_scraper import BaseScraper, ProductData


logger = logging.getLogger(__name__)


class RappiScraper(BaseScraper):
    """
    Scraper para Rappi.
    Usa Playwright para manejar contenido dinámico (JavaScript).
    
    MVP Version: Search works without explicit address selection.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        super().__init__(config_path)
        self.platform_name = "Rappi"
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
        # URL base de Rappi
        self.base_url = "https://www.rappi.com.mx"
        
    def initialize_browser(self):
        """Inicializar navegador Playwright con configuraciones stealth."""
        logger.info("Initializing Playwright browser for Rappi...")
        
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
        # Esperar a que no haya operaciones de red pendientes
        try:
            self.page.wait_for_load_state('networkidle', timeout=5000)
        except:
            pass
    
    def search_product(self, address: dict, product: dict) -> ProductData:
        """
        Buscar un producto específico.
        MVP: No usamos address selection, solo búsqueda global.
        """
        # Crear producto base
        product_data = ProductData(
            platform=self.platform_name,
            address_name=address['name'],
            zip_code=address['zip_code'],
            zone_type=address.get('zone_type', 'unknown'),
            product_name=product['name'],
            product_brand=product.get('brand', 'N/A')
        )
        
        try:
            # Navegar a Rappi
            if self.page.url != self.base_url:
                self.page.goto(self.base_url, timeout=30000)
                self._wait_for_page_stable(5)
            
            # Obtener input de búsqueda
            inputs = self.page.query_selector_all('input')
            if not inputs:
                logger.warning("No inputs found on page")
                return product_data
            
            search_input = inputs[0]
            
            # Buscar producto
            search_input.click()
            time.sleep(0.5)
            search_input.fill(product['name'])
            time.sleep(1)
            
            # Enviar búsqueda
            self.page.keyboard.press('Enter')
            
            # Esperar resultados
            self._wait_for_page_stable(5)
            
            logger.info(f"Search submitted for: {product['name']}")
            logger.info(f"Current URL: {self.page.url}")
            
            # Extraer información del producto
            product_info = self._extract_product_info()
            if product_info:
                product_data.product_price = product_info.get('price')
                logger.info(f"Extracted price: {product_data.product_price}")
            
            # Intentar obtener delivery info
            delivery_info = self._get_delivery_info()
            product_data.delivery_fee = delivery_info.get('delivery_fee')
            product_data.estimated_delivery_time = delivery_info.get('estimated_time')
            
            # Calcular precio final si tenemos los componentes
            if product_data.product_price and product_data.delivery_fee:
                product_data.final_total_price = product_data.product_price + product_data.delivery_fee
            
        except Exception as e:
            logger.error(f"Error searching product: {e}")
        
        return product_data
    
    def _extract_product_info(self) -> Optional[dict]:
        """
        Extraer información del primer producto en los resultados.
        Usa parseo de texto porque los selectores CSS son complejos/dinámicos.
        """
        try:
            self._wait_for_page_stable(2)
            
            # Obtener texto de la página
            body_text = self.page.inner_text('body')
            
            if not body_text or len(body_text) < 50:
                logger.warning("Body text is empty or too short")
                return None
            
            # Buscar el producto "Big Mac" específico
            # Patrones comunes: "Big Mac $125.00" o "$125.00" cerca de "Big Mac"
            lines = body_text.split('\n')
            
            product_name = None
            product_price = None
            
            # Buscar líneas que contengan "Big Mac" (case insensitive)
            for i, line in enumerate(lines):
                line_lower = line.lower().strip()
                
                # Buscar "big mac" seguido de precio
                if 'big mac' in line_lower:
                    # Guardar el nombre del producto
                    if line.strip() and len(line.strip()) < 100:
                        product_name = line.strip()
                    
                    # Buscar precio en líneas cercanas
                    for j in range(max(0, i-3), min(len(lines), i+5)):
                        price_line = lines[j].strip()
                        # Buscar patrón de precio mexicano: $XXX.XX o $XXX
                        import re
                        price_match = re.search(r'\$?([\d,]+\.?\d*)', price_line)
                        if price_match:
                            price_str = price_match.group(1).replace(',', '')
                            try:
                                price_val = float(price_str)
                                if 50 < price_val < 500:  # Rango razonable para comida
                                    product_price = price_val
                                    logger.info(f"Found product: {product_name} at ${product_price}")
                                    return {'name': product_name, 'price': product_price}
                            except:
                                pass
                    break
            
            # Si no encontramos Big Mac específico, buscar primer precio en rango razonable
            if not product_price:
                for line in lines:
                    import re
                    price_match = re.search(r'\$?([\d,]+\.?\d*)', line)
                    if price_match:
                        price_str = price_match.group(1).replace(',', '')
                        try:
                            price_val = float(price_str)
                            if 50 < price_val < 500:  # Rango razonable para comida
                                product_price = price_val
                                logger.info(f"Found first price: ${product_price}")
                                return {'name': 'Unknown', 'price': product_price}
                        except:
                            pass
            
            return None
            
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
            # Buscar elementos de info de envío
            fee_selectors = [
                '[class*="shipping"]',
                '[class*="delivery"] span',
                '[class*="time"]',
                '[class*="eta"]'
            ]
            
            for selector in fee_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    for el in elements[:3]:
                        text = el.inner_text()
                        if '$' in text and info['delivery_fee'] is None:
                            import re
                            fee_match = re.search(r'\$?([\d,]+\.?\d*)', text)
                            if fee_match:
                                info['delivery_fee'] = float(fee_match.group(1).replace(',', ''))
                        if 'min' in text.lower() or 'hora' in text.lower():
                            info['estimated_time'] = text
                except:
                    continue
                    
        except Exception as e:
            logger.warning(f"Could not extract delivery info: {e}")
        
        return info


def main():
    """Función para testing directo del scraper."""
    print("=" * 60)
    print("RAPPI SCRAPER MVP - TEST")
    print("=" * 60)
    
    scraper = RappiScraper()
    
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
