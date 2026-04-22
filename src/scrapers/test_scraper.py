"""
Test scraper with random sample - one product, one address.
"""
import random
import logging
from pathlib import Path

from rappi_scraper import RappiScraper

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    scraper = RappiScraper()

    addresses = scraper.get_addresses()
    products = scraper.get_reference_products()

    all_products = products.get('fast_food', []) + products.get('retail', [])

    if not addresses or not all_products:
        logger.error("No addresses or products found")
        return

    random_address = random.choice(addresses)
    random_product = random.choice(all_products)

    logger.info(f"Testing with random address: {random_address['name']}")
    logger.info(f"Random product: {random_product['name']} ({random_product['brand']})")
    logger.info(f"  lat={random_address['lat']}, lon={random_address['lon']}, density={random_address['density']}")

    scraper.initialize_browser()

    try:
        result = scraper.search_product(random_address, random_product)

        from dataclasses import asdict
        logger.info("\n=== RESULT ===")
        for key, value in asdict(result).items():
            if value is not None and value != '':
                logger.info(f"  {key}: {value}")

    except Exception as e:
        logger.error(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        scraper.close_browser()

if __name__ == "__main__":
    main()