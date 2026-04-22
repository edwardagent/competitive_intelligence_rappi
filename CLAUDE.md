# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Competitive Intelligence system for Rappi in Mexico. Scrapes product prices, delivery fees, and other metrics from Rappi (and eventually Uber Eats and DiDi Food) to generate actionable insights.

## Commands

### Docker (Primary execution method)
```bash
# Run the scraper (main use case)
docker compose -f container/docker-compose.yml up scraper

# Run analysis (note: module not yet implemented)
docker compose -f container/docker-compose.yml up analysis

# Run Streamlit dashboard (note: module not yet implemented)
docker compose -f container/docker-compose.yml up dashboard

# Run with Jupyter (interactive analysis)
docker compose --profile jupyter up jupyter
```

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
playwright install --with-deps chromium  # with system deps

# Test Rappi scraper directly
python src/scrapers/rappi_scraper.py
```

## Architecture

```
config/config.yaml          # Drives everything: addresses, products, scraping settings
         ↓
src/scrapers/run_all.py     # Entry point, orchestrates all scrapers
         ↓
src/scrapers/base_scraper.py  # Abstract BaseScraper + ProductData dataclass
src/scrapers/rappi_scraper.py  # Rappi implementation using Playwright
         ↓
data/raw/                   # CSV/JSON output from scraping
         ↓
src/analysis/               # (not yet implemented) generate_report.py, dashboard.py
         ↓
reports/                    # Generated analysis and visualizations
```

### Key Classes

- **`ProductData`** (base_scraper.py:28): Dataclass for scraped product data with fields like `product_price`, `delivery_fee`, `estimated_delivery_time`, `final_total_price`
- **`BaseScraper`** (base_scraper.py:60): Abstract base class defining the scraper interface. Subclasses implement `initialize_browser()`, `close_browser()`, and `search_product()`
- **`RappiScraper`** (rappi_scraper.py:20): Playwright-based implementation. Uses text parsing over CSS selectors due to Rappi's dynamic DOM
- **`ScraperConfig`** (base_scraper.py:51): Configuration dataclass loaded from `config/config.yaml`

### Configuration (config/config.yaml)

- `addresses`: 10 Mexico City zones to scrape (Polanco, Condesa, Centro, etc.)
- `reference_products`: fast_food (Big Mac, Whopper, etc.) and retail (Coca-Cola, water) items
- `scraping`: delay (3s), timeout (30s), headless mode, user agent
- `platforms`: toggles for rappi/uber_eats/didi_food (uber_eats and didi_food not yet implemented)

## Current State

- **Rappi scraper**: Working MVP - extracts product prices from search results
- **Uber Eats/DiDi Food scrapers**: Placeholders only (run_all.py returns False)
- **Analysis module**: Stub files exist but `generate_report.py` and `dashboard.py` are not yet implemented