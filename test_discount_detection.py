"""
Test discount detection using page.evaluate - CSS strikethrough detection
More robust version with better search handling
"""
import sys
sys.path.insert(0, '/app/src/scrapers')

from rappi_scraper import RappiScraper

print("Testing DISCOUNT DETECTION via CSS styles (strikethrough)...")
print("=" * 60)

scraper = RappiScraper()

test_product = {'name': 'Big Mac', 'brand': "McDonald's"}

try:
    scraper.initialize_browser()
    
    # Navigate to Rappi
    print("Navigating to Rappi...")
    scraper.page.goto(scraper.base_url, timeout=30000)
    scraper._wait_for_page_stable(5)
    
    print(f"Page URL after load: {scraper.page.url}")
    
    # Find search input with more selectors
    search_selectors = [
        'input[placeholder*="Buscar"]',
        'input[placeholder*="buscar"]',
        'input[aria-label*="search"]',
        'input[aria-label*="Search"]',
        'input[aria-label*="productos"]',
        'input[placeholder*="¿Qué quieres?"]',
        'input[data-testid="search-input"]',
        'input[class*="search"]'
    ]
    
    search_input = None
    for selector in search_selectors:
        try:
            el = scraper.page.query_selector(selector)
            if el and el.is_visible():
                search_input = el
                print(f"Found search input with selector: {selector}")
                break
        except Exception as e:
            continue
    
    if search_input:
        print(f"Filling search with: {test_product['name']}")
        search_input.fill(test_product['name'])
        search_input.press('Enter')
        scraper._wait_for_page_stable(5)
        
        print(f"Page URL after search: {scraper.page.url}")
        
        # Get all prices with their CSS styles
        js_result = scraper.page.evaluate("""
            () => {
                const allElements = document.querySelectorAll('span, div, p, strong, b, em, i, small, mark');
                const prices = [];
                
                for (const el of allElements) {
                    const text = el.innerText || '';
                    const priceMatch = text.match(/\\$?\\s*([\\d,]+\\.?\\d*)/);
                    
                    if (priceMatch && text.length < 50 && text.length > 2) {
                        const computed = window.getComputedStyle(el);
                        
                        prices.push({
                            text: text.substring(0, 60),
                            raw_price: priceMatch[1],
                            decoration: computed.textDecoration,
                            decorationLine: computed.textDecorationLine,
                            color: computed.color,
                            fontWeight: computed.fontWeight,
                            fontSize: computed.fontSize
                        });
                    }
                }
                
                return prices.slice(0, 50);
            }
        """)
        
        print(f"\nFound {len(js_result)} price elements\n")
        
        old_prices = []
        new_prices = []
        
        for p in js_result:
            try:
                price_val = float(p['raw_price'].replace(',', ''))
                if 20 < price_val < 1000:
                    has_strikethrough = 'line-through' in p['decoration'] or 'line-through' in p['decorationLine']
                    
                    if has_strikethrough:
                        old_prices.append((p['text'], price_val, p['color']))
                        print(f"❌ OLD: '${p['text']}' -> ${price_val:.2f} | color: {p['color']} | decor: {p['decoration']}")
                    else:
                        new_prices.append((p['text'], price_val, p['color']))
                        print(f"✅ NEW: '${p['text']}' -> ${price_val:.2f} | color: {p['color']}")
            except:
                continue
        
        print("\n" + "=" * 60)
        print("DISCOUNT ANALYSIS")
        print("=" * 60)
        
        if old_prices and new_prices:
            for old_text, old_val, old_color in old_prices:
                for new_text, new_val, new_color in new_prices:
                    if old_val > new_val:
                        discount_pct = (old_val - new_val) / old_val * 100
                        print(f"\n🎯 DISCOUNT FOUND!")
                        print(f"   Old: ${old_val:.2f} (color: {old_color})")
                        print(f"   New: ${new_val:.2f} (color: {new_color})")
                        print(f"   Discount: {discount_pct:.1f}% OFF")
        elif new_prices:
            print("No strikethrough (old price) found. Product may not be on sale.")
            print(f"Current prices found: {len(new_prices)}")
        else:
            print("No prices found on page")
            
    else:
        print("Could not find any search input")
        # Let's see what's on the page
        body_text = scraper.page.inner_text('body')
        print(f"Page text (first 500 chars): {body_text[:500]}")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    scraper.close_browser()