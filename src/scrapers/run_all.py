"""
Run All Scrapers
Ejecuta todos los scrapers configurados y guarda los datos.
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path
import json

from rappi_scraper import RappiScraper


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_rappi_scraper(output_dir: str = "data/raw") -> bool:
    """Ejecutar el scraper de Rappi."""
    logger.info("=" * 60)
    logger.info("STARTING RAPPI SCRAPER")
    logger.info("=" * 60)
    
    try:
        scraper = RappiScraper()
        data = scraper.scrape_all()
        
        if data:
            # Save to CSV
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = Path(output_dir) / f"rappi_data_{timestamp}.csv"
            scraper.save_to_csv(str(csv_path))
            
            # Also save as JSON for flexibility
            json_path = Path(output_dir) / f"rappi_data_{timestamp}.json"
            scraper.save_to_json(str(json_path))
            
            logger.info(f"Successfully scraped {len(data)} records from Rappi")
            return True
        else:
            logger.warning("No data scraped from Rappi")
            return False
            
    except Exception as e:
        logger.error(f"Error running Rappi scraper: {e}")
        return False


def run_uber_eats_scraper(output_dir: str = "data/raw") -> bool:
    """Ejecutar el scraper de Uber Eats (placeholder)."""
    logger.info("=" * 60)
    logger.info("UBER EATS SCRAPER - NOT YET IMPLEMENTED")
    logger.info("=" * 60)
    
    # TODO: Implement Uber Eats scraper
    logger.warning("Uber Eats scraper not implemented yet")
    return False


def run_didi_food_scraper(output_dir: str = "data/raw") -> bool:
    """Ejecutar el scraper de DiDi Food (placeholder)."""
    logger.info("=" * 60)
    logger.info("DIDI FOOD SCRAPER - NOT YET IMPLEMENTED")
    logger.info("=" * 60)
    
    # TODO: Implement DiDi Food scraper
    logger.warning("DiDi Food scraper not implemented yet")
    return False


def main():
    parser = argparse.ArgumentParser(description="Run Competitive Intelligence Scrapers")
    parser.add_argument(
        '--platform',
        choices=['all', 'rappi', 'uber_eats', 'didi_food'],
        default='all',
        help='Platform to scrape'
    )
    parser.add_argument(
        '--output',
        default='data/raw',
        help='Output directory for scraped data'
    )
    
    args = parser.parse_args()
    
    # Create output directory
    Path(args.output).mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    if args.platform in ['all', 'rappi']:
        results['rappi'] = run_rappi_scraper(args.output)
    
    if args.platform in ['all', 'uber_eats']:
        results['uber_eats'] = run_uber_eats_scraper(args.output)
    
    if args.platform in ['all', 'didi_food']:
        results['didi_food'] = run_didi_food_scraper(args.output)
    
    # Summary
    logger.info("=" * 60)
    logger.info("SCRAPING COMPLETE - SUMMARY")
    logger.info("=" * 60)
    for platform, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        logger.info(f"{platform.upper()}: {status}")
    
    # Save metadata
    metadata = {
        'timestamp': datetime.now().isoformat(),
        'platforms': results,
        'output_dir': args.output
    }
    
    metadata_path = Path(args.output) / "scrape_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return all(results.values())


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
