"""
Take screenshots of products at random locations for visual inspection.
"""
import random
import time
import logging
from pathlib import Path
from dataclasses import asdict

from playwright.sync_api import sync_playwright, Page

from rappi_scraper import RappiScraper

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def setup_screenshot_dir(base: str = "data/screenshots") -> Path:
    """Create and return screenshots directory."""
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def take_page_screenshot(page: Page, path: Path, label: str = ""):
    """Take a full-page screenshot."""
    try:
        page.screenshot(path=str(path), full_page=True)
        logger.info(f"  Screenshot saved: {path.name} ({label})")
    except Exception as e:
        logger.error(f"  Failed to screenshot {path}: {e}")


def is_product_detail_page(page) -> bool:
    """Check if current page is a product detail page (not a catalog/listing)."""
    try:
        body_text = page.inner_text('body').lower()
        # Product detail pages typically have: price with $, "añadir" (add to cart), product name in heading
        has_price = '$' in page.inner_text('body')
        has_add_to_cart = any(kw in body_text for kw in ['añadir al carrito', 'agregar al carrito', 'añadir', 'add to cart', 'comprar'])
        has_product_heading = any(kw in body_text for kw in ['detalle del producto', 'producto', 'menú', 'Descripción', 'información nutricional'])
        # Catalog/listing pages often have words like "catálogo", "tienda", "restaurante"
        is_catalog = any(kw in body_text for kw in ['catálogo', 'catalog', 'tiendas', 'ver todas', 'stores'])

        if is_catalog:
            return False
        if has_price and (has_add_to_cart or has_product_heading):
            return True
        return False
    except:
        return False


def run_screenshot_test(n_locations: int = 3, output_dir: str = "data/screenshots"):
    """
    Run screenshot test across random locations and all products.
    """
    scraper = RappiScraper()
    addresses = scraper.get_addresses()
    products = scraper.get_reference_products()

    all_products = products.get('fast_food', []) + products.get('retail', [])

    if len(addresses) < n_locations:
        logger.error(f"Not enough addresses: {len(addresses)} < {n_locations}")
        return

    # Sample n random locations
    sampled_addresses = random.sample(addresses, n_locations)
    logger.info(f"Sampled {n_locations} locations out of {len(addresses)}")

    screenshots_dir = setup_screenshot_dir(output_dir)
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    scraper.initialize_browser()

    try:
        for addr_idx, address in enumerate(sampled_addresses):
            addr_name_safe = address['name'].replace('/', '_').replace(',', '').replace(' ', '_')[:50]
            addr_dir = screenshots_dir / f"addr{addr_idx+1}_{addr_name_safe}"
            addr_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"\n=== Address {addr_idx+1}/{n_locations}: {address['name']} ===")
            logger.info(f"  lat={address['lat']}, lon={address['lon']}, density={address['density']}")

            # Navigate to Rappi first
            scraper.page.goto(scraper.base_url, timeout=30000)
            scraper._wait_for_page_stable(3)

            # Take address overview screenshot
            addr_screenshot = addr_dir / f"00_address_overview.png"
            take_page_screenshot(scraper.page, addr_screenshot, "address_overview")

            for prod_idx, product in enumerate(all_products):
                prod_name_safe = product['name'].replace('/', '_').replace(' ', '_')[:30]

                logger.info(f"  Product {prod_idx+1}/{len(all_products)}: {product['name']}")

                # Navigate and search
                scraper.page.goto(scraper.base_url, timeout=30000)
                scraper._wait_for_page_stable(5)

                inputs = scraper.page.query_selector_all('input')
                if inputs:
                    inputs[0].click()
                    inputs[0].fill(product['name'])
                    time.sleep(0.5)
                    scraper.page.keyboard.press('Enter')
                    scraper._wait_for_page_stable(5)  # Increased for full JS render

                # Search results screenshot
                results_screenshot = addr_dir / f"{prod_idx+1:02d}_{prod_name_safe}_search_results.png"
                take_page_screenshot(scraper.page, results_screenshot, f"{product['name']} search results")

                # Try clicking into product detail
                try:
                    product_selectors = [
                        'a[href*="product"]',
                        '[class*="product-card"]',
                        '[class*="productItem"]',
                    ]
                    clicked = False
                    for selector in product_selectors:
                        elements = scraper.page.query_selector_all(selector)
                        for el in elements[:3]:
                            if el and el.is_visible():
                                el.click()
                                clicked = True
                                time.sleep(3)  # Wait for detail page to load
                                break
                        if clicked:
                            break

                    if clicked and is_product_detail_page(scraper.page):
                        detail_screenshot = addr_dir / f"{prod_idx+1:02d}_{prod_name_safe}_product_detail.png"
                        take_page_screenshot(scraper.page, detail_screenshot, f"{product['name']} detail")
                        scraper.page.go_back()
                        scraper._wait_for_page_stable(1)
                    elif clicked:
                        logger.info(f"    Clicked but page is not a product detail (catalog/listing)")
                        scraper.page.go_back()
                        scraper._wait_for_page_stable(1)
                    else:
                        logger.info(f"    No clickable product element found")
                except Exception as e:
                    logger.warning(f"    Could not click product: {e}")
                    try:
                        scraper.page.go_back()
                    except:
                        pass

                time.sleep(scraper.scraper_config.delay_between_requests)

    finally:
        scraper.close_browser()

    logger.info(f"\n=== All screenshots saved to: {screenshots_dir} ===")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Take product screenshots at random locations")
    parser.add_argument('--locations', '-n', type=int, default=3, help='Number of random locations to sample')
    parser.add_argument('--output', '-o', type=str, default='data/screenshots', help='Output directory')
    args = parser.parse_args()

    run_screenshot_test(n_locations=args.locations, output_dir=args.output)