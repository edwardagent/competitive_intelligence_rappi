"""
Rappi Scraper - Simplified MVP Version
Scraper específico para Rappi usando Playwright.
Versión simplificada que funciona sin address selection complejo.
"""

import re
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
    
    def __init__(self, config_path: str = "config/config.yaml", addresses_csv: str = "data/resultados_mexico_direcciones.csv", save_screenshots: bool = False):
        super().__init__(config_path, addresses_csv, save_screenshots=save_screenshots)
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
            zip_code=address.get('zip_code', ''),
            zone_type=address.get('zone_type', 'from_csv'),
            lat=address.get('lat'),
            lon=address.get('lon'),
            density=address.get('density'),
            product_name=product['name'],
            product_brand=product.get('brand', 'N/A')
        )
        
        try:
            # Navegar a Rappi
            if self.page.url != self.base_url:
                self.page.goto(self.base_url, timeout=30000)
                self._wait_for_page_stable(5)
            
            # Take screenshot of address overview (before search)
            self._take_screenshot(self.page, address, product, "_01_before_search")
            
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
            
            # Take screenshot of search results
            self._take_screenshot(self.page, address, product, "_02_search_results")
            
            logger.info(f"Search submitted for: {product['name']}")
            logger.info(f"Current URL: {self.page.url}")

            # Extraer toda la información de la página
            page_info = self._extract_all_page_info(product)
            product_data.product_price = page_info.get('product_price')
            product_data.delivery_fee = page_info.get('delivery_fee')
            product_data.service_fee = page_info.get('service_fee')
            product_data.estimated_delivery_time = page_info.get('estimated_time')
            product_data.active_discounts = page_info.get('discounts')
            product_data.availability = page_info.get('availability')
            product_data.final_total_price = page_info.get('final_total_price')

            # Intentar obtener service fee y descuentos haciendo click en producto
            if not product_data.service_fee or not product_data.active_discounts:
                detail_info = self._try_click_product_for_details(product.get('name', ''))
                if detail_info.get('service_fee') and not product_data.service_fee:
                    product_data.service_fee = detail_info.get('service_fee')
                if detail_info.get('discounts') and not product_data.active_discounts:
                    product_data.active_discounts = detail_info.get('discounts')
                if detail_info.get('taxes'):
                    # Agregar taxes al precio final
                    if product_data.final_total_price:
                        product_data.final_total_price += detail_info.get('taxes')

            if product_data.product_price:
                logger.info(f"Extracted - price: {product_data.product_price}, delivery: {product_data.delivery_fee}, time: {product_data.estimated_delivery_time}")
            
        except Exception as e:
            logger.error(f"Error searching product: {e}")
        
        return product_data
    
    def _try_click_product_for_details(self, product_name: str = '') -> dict:
        """
        Intentar hacer click en el producto específico para ver detalles de precio
        y extraer service fee, impuestos, etc.
        """
        info = {
            'service_fee': None,
            'service_fee_breakdown': None,
            'discounts': None,
            'taxes': None
        }

        try:
            # First try to click on a product link/element that matches our search
            clicked = False

            # Try clicking on links that contain the product name
            if product_name:
                product_lower = product_name.lower()
                links = self.page.query_selector_all('a')
                for link in links[:10]:
                    try:
                        text = link.inner_text().lower()
                        if product_lower in text or text.startswith('http'):
                            link.click()
                            clicked = True
                            time.sleep(3)
                            break
                    except:
                        continue

            # If no product-specific click, try generic product card selectors
            if not clicked:
                product_selectors = [
                    'a[href*="product"]',
                    '[class*="product-card"]',
                    '[class*="productItem"]',
                    '[class*="restaurant"] [class*="product"] a',
                ]

                for selector in product_selectors:
                    try:
                        elements = self.page.query_selector_all(selector)
                        for el in elements[:3]:
                            if el and el.is_visible():
                                el.click()
                                clicked = True
                                time.sleep(3)
                                break
                    except:
                        continue
                    if clicked:
                        break

            if not clicked:
                return info

            # Obtener texto de la vista de detalle
            detail_text = self.page.inner_text('body')
            lines = [l.strip() for l in detail_text.split('\n') if l.strip()]

            for line in lines:
                line_lower = line.lower()

                # Service fee patterns
                if info['service_fee'] is None:
                    if re.search(r'servicio|comisión|costo\s*comisión|charge\s*fee|platform\s*fee|svc\s*fee', line_lower):
                        fee_match = re.search(r'\$?\s*([\d,]+\.?\d*)', line)
                        if fee_match:
                            val = float(fee_match.group(1).replace(',', ''))
                            if val < 100:
                                info['service_fee'] = val

                # Taxes / impuestos
                if info['taxes'] is None:
                    if re.search(r'impuesto|tax|iva|igic', line_lower):
                        tax_match = re.search(r'\$?\s*([\d,]+\.?\d*)', line)
                        if tax_match:
                            val = float(tax_match.group(1).replace(',', ''))
                            if val < 100:
                                info['taxes'] = val

                # Descuentos en vista de detalle - require context to be discount-related
                if info['discounts'] is None:
                    if re.search(r'\d+\s*%\s*(?:off|desc|descuento|rebaixa)', line_lower):
                        disc_match = re.search(r'(\d+\s*%\s*(?:off|desc|descuento|rebaixa)?)', line_lower)
                        if disc_match:
                            info['discounts'] = disc_match.group(1).strip()
                    elif re.search(r'(?:2x1|buy\s*one|ahorra\s*\$[\d.]+|cupón?\s*\d+%)', line_lower):
                        disc_match = re.search(r'(2x1|buy\s*one|ahorra\s*\$[\d.]+|cupón?\s*\d+%)', line_lower)
                        if disc_match:
                            info['discounts'] = disc_match.group(1).strip()

            # Volver a la página de resultados
            self.page.go_back()
            time.sleep(2)

        except Exception as e:
            logger.warning(f"Could not get product details: {e}")
            try:
                self.page.go_back()
            except:
                pass

        return info

    def _extract_all_page_info(self, product: dict) -> dict:
        """
        Extraer toda la información relevante de la página de resultados.
        Usa tanto CSS (strikethrough detection) como parseo de texto.
        """
        info = {
            'product_price': None,
            'product_name': None,
            'delivery_fee': None,
            'service_fee': None,
            'estimated_time': None,
            'discounts': None,
            'availability': None,
            'final_total_price': None
        }

        try:
            self._wait_for_page_stable(2)
            body_text = self.page.inner_text('body')

            if not body_text or len(body_text) < 50:
                logger.warning("Body text is empty or too short")
                return info

            # ===== DETECCIÓN DE DESCuentos POR CSS (STRIKETHROUGH) =====
            # Usar JavaScript para obtener precios con estilos CSS
            try:
                price_styles = self.page.evaluate("""
                    () => {
                        const allElements = document.querySelectorAll('span, div, p, strong, b, em, i, small, mark');
                        const prices = [];
                        
                        for (const el of allElements) {
                            const text = el.innerText || '';
                            const priceMatch = text.match(/\$?\s*([\d,]+\.?\d*)/);
                            
                            if (priceMatch && text.length < 60 && text.length > 2) {
                                const computed = window.getComputedStyle(el);
                                const isStrikethrough = computed.textDecorationLine === 'line-through' || 
                                                       computed.textDecoration.includes('line-through');
                                
                                prices.push({
                                    text: text.substring(0, 60),
                                    raw_price: priceMatch[1],
                                    is_strikethrough: isStrikethrough,
                                    color: computed.color
                                });
                            }
                        }
                        
                        return prices;
                    }
                """)
                
                # Separar precios old (strikethrough) y new (normal)
                old_prices = []
                new_prices = []
                
                for p in price_styles:
                    try:
                        price_val = float(p['raw_price'].replace(',', ''))
                        if 20 < price_val < 1000:
                            if p['is_strikethrough']:
                                old_prices.append((p['text'], price_val))
                            else:
                                new_prices.append((p['text'], price_val))
                    except:
                        continue
                
                # Calcular descuentos: el precio NEW siempre debe ser más barato que OLD
                # discount = (old - new) / old * 100 (diferencia relativa)
                if old_prices and new_prices:
                    best_discount = 0
                    best_old = None
                    best_new = None
                    
                    for old_text, old_val in old_prices:
                        for new_text, new_val in new_prices:
                            if old_val > new_val:  # Discount scenario
                                discount_pct = (old_val - new_val) / old_val * 100
                                if discount_pct > best_discount:
                                    best_discount = discount_pct
                                    best_old = old_val
                                    best_new = new_val  # The cheapest new price
                    
                    if best_discount > 0:
                        info['discounts'] = f"{best_discount:.1f}% OFF"
                        info['product_price'] = best_new  # Use the NEW (cheaper) price
                        logger.info(f"CSS Discount detected: {best_discount:.1f}% OFF (old: ${best_old}, new: ${best_new})")
                
                # Si no encontramos descuento pero sí tenemos precios nuevos
                elif new_prices and not info['product_price']:
                    # Tomar el precio más barato de los nuevos (validación: siempre más barato)
                    cheapest_new = min(new_prices, key=lambda x: x[1])
                    info['product_price'] = cheapest_new[1]
                    logger.info(f"No discount found. Using cheapest price: ${cheapest_new[1]}")
                    
            except Exception as e:
                logger.warning(f"CSS discount detection failed: {e}")

            lines = [l.strip() for l in body_text.split('\n') if l.strip()]

            # Primero extraer el precio del producto específico si no lo tenemos
            if not info['product_price']:
                product_name_lower = product.get('name', '').lower()
                
                for i, line in enumerate(lines):
                    line_lower = line.lower()
                    
                    if product_name_lower and product_name_lower in line_lower:
                        for j in range(max(0, i-2), min(len(lines), i+3)):
                            price_line = lines[j]
                            price_match = re.search(r'\$?\s*([\d,]+\.?\d*)', price_line)
                            if price_match:
                                val = float(price_match.group(1).replace(',', ''))
                                if 50 < val < 500:
                                    info['product_price'] = val
                                    info['product_name'] = lines[i] if len(lines[i]) < 100 else None
                                    logger.info(f"Found product price: ${val} for {product.get('name')}")
                                    break
                        if info['product_price']:
                            break

            # Ahora buscar delivery fee, service fee, tiempo, disponibilidad
            for i, line in enumerate(lines):
                line_lower = line.lower()
                
                # Buscar tiempo estimado
                if info['estimated_time'] is None:
                    time_match = re.search(r'(\d+)\s*[-–]\s*(\d+)\s*(min|minutos|hrs|horas)', line_lower)
                    if time_match:
                        info['estimated_time'] = f"{time_match.group(1)}-{time_match.group(2)} min"
                    elif re.search(r'(\d+)\s*(min|minutos)', line_lower) and '$' not in line:
                        single_time = re.search(r'(\d+)\s*(min|minutos)', line_lower)
                        if single_time and info['estimated_time'] is None:
                            info['estimated_time'] = f"{single_time.group(1)} min"

                # Buscar delivery fee - solo gratis si dice "envío gratis" explícitamente
                if info['delivery_fee'] is None:
                    if re.search(r'env(ío|io)\s*gratis|sin\s*costo\s*(?:de\s*)?env|delivery\s*gratis|s\/ costo|s\/ env|envío\s*0', body_text):
                        info['delivery_fee'] = 0.0
                    elif re.search(r'envío[:\s]+\$?\s*([\d,]+)', body_text):
                        fee_match = re.search(r'envío[:\s]+\$?\s*([\d,]+)', body_text)
                        val = float(fee_match.group(1).replace(',', ''))
                        if val < 200:
                            info['delivery_fee'] = val
                    elif i > 0 and re.search(r'env|delivery|envío', line_lower):
                        fee_match = re.search(r'\$?\s*([\d,]+\.?\d*)', line)
                        if fee_match:
                            val = float(fee_match.group(1).replace(',', ''))
                            if 0 < val < 200:
                                info['delivery_fee'] = val
                    elif re.search(r'costo|de\s*envío|envío|costo\s*final', line_lower):
                        fee_match = re.search(r'\$?\s*([\d,]+\.?\d*)', line)
                        if fee_match:
                            val = float(fee_match.group(1).replace(',', ''))
                            if 0 < val < 200:
                                info['delivery_fee'] = val

                # Buscar service fee
                if info['service_fee'] is None:
                    if re.search(r'(?:comisión|servicio|service\s*fee|platform\s*fee)\s*\$?\s*([\d,]+)', body_text):
                        fee_match = re.search(r'(?:comisión|servicio|service\s*fee|platform\s*fee)\s*\$?\s*([\d,]+)', body_text)
                        val = float(fee_match.group(1).replace(',', ''))
                        if val < 100:
                            info['service_fee'] = val
                    elif re.search(r'cargo\s*(?:por\s*)?(?:servicio|comisión)\s*\$?\s*([\d,]+)', body_text):
                        fee_match = re.search(r'cargo\s*(?:por\s*)?(?:servicio|comisión)\s*\$?\s*([\d,]+)', body_text)
                        val = float(fee_match.group(1).replace(',', ''))
                        if val < 100:
                            info['service_fee'] = val

                # Buscar descuentos por texto (si no los encontramos por CSS)
                # Solo buscar si discounts sigue siendo None
                if info['discounts'] is None:
                    # "XX% de descuento" o "XX% off"
                    if re.search(r'\d+\s*%\s*de\s*(?:desc|descuento|off)', line_lower):
                        disc_match = re.search(r'(\d+\s*%\s*de\s*(?:desc|descuento|off))', line_lower)
                        if disc_match:
                            info['discounts'] = disc_match.group(1).strip()
                    elif re.search(r'\d+\s*%\s*(?:off|desc(?:uento)?)', line_lower, re.IGNORECASE):
                        disc_match = re.search(r'(\d+\s*%\s*(?:off|desc(?:uento)?))', line_lower, re.IGNORECASE)
                        if disc_match:
                            info['discounts'] = disc_match.group(1).strip()
                    elif re.search(r'(?:2x1|buy\s*one(?:\s+free)?|ahorra\s*\$[\d.]+)', line_lower):
                        disc_match = re.search(r'(2x1|buy\s*one(?:\s+free)?|ahorra\s*\$[\d.]+)', line_lower)
                        if disc_match:
                            info['discounts'] = disc_match.group(1).strip()
                    # FIX: Solo marcar "free_item" si NO tiene contexto de envío
                    # Si la línea tiene "envío" o "delivery", es envío gratis, no producto gratis
                    elif re.search(r'\bgratis\b|\bfree\b', line_lower) and len(line) < 80:
                        if not re.search(r'envío|delivery|env|send|shipping', line_lower):
                            info['discounts'] = 'free_item'

                # Buscar disponibilidad
                if info['availability'] is None:
                    if re.search(r'\bopen\b|abiert|disponible|disponibl|disponível', line_lower):
                        info['availability'] = 'open'
                    elif re.search(r'\bclosed\b|cerrad|no\s*disponible|unavailable', line_lower):
                        info['availability'] = 'closed'

            # Calcular precio final
            if info['product_price'] and info['delivery_fee'] is not None:
                info['final_total_price'] = info['product_price'] + info['delivery_fee']
                if info['service_fee']:
                    info['final_total_price'] += info['service_fee']

        except Exception as e:
            logger.error(f"Error extracting page info: {e}")

        return info

    def _get_delivery_info(self) -> dict:
        """
        Obtener información de delivery (fee, tiempo, etc).
        DEPRECADO: usar _extract_all_page_info en su lugar.
        """
        return self._extract_all_page_info()


def main():
    """Función para testing directo del scraper."""
    print("=" * 60)
    print("RAPPI SCRAPER MVP - TEST")
    print("=" * 60)
    
    scraper = RappiScraper()
    
    test_address = {
        'name': 'Calle Cicalco, Colonia Rinconada de Los Reyes, Colonia Pedregal de Santo Domingo, Ciudad de México, Coyoacán, Ciudad de México, 04369, México',
        'lat': 19.328750117034197,
        'lon': -99.16374961650183,
        'density': 35926.17,
        'zip_code': '',
        'zone_type': 'from_csv'
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
