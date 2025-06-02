#!/usr/bin/env python3
"""
vc_scraper.py
-------------
Scrapes VC portfolio pages.
Falls back to Playwright when pagination or JS hides links.

Example:
    python vc_scraper.py https://www.av.vc/portfolio
"""

# ── ensure Chromium is present ───────────────────────────────────────
import subprocess, pathlib, glob, sys, os

# Check if we're in a deployment environment (like Streamlit Cloud)
IS_DEPLOYMENT = any(key in os.environ for key in [
    'STREAMLIT_SHARING_MODE', 'STREAMLIT_SERVER_PORT', 'GITHUB_ACTIONS', 
    'HEROKU', 'VERCEL', 'RAILWAY', 'RENDER'
])

print("ℹ️  Using local Playwright browsers")
CACHE = pathlib.Path.home() / ".cache/ms-playwright"
need_browser = not glob.glob(str(CACHE / "chromium-*/*/chrome-linux/headless_shell"))

if need_browser and not IS_DEPLOYMENT:
    try:
        print("▶ First launch: downloading Playwright Chromium …")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"],
            check=True,
        )
        print("✔ Chromium installed")
    except (subprocess.CalledProcessError, PermissionError) as e:
        print(f"⚠️  Could not install Playwright automatically: {e}")
        print("   Please run: pip install playwright && playwright install chromium")
elif need_browser and IS_DEPLOYMENT:
    print("ℹ️  Running in deployment environment - Playwright should be pre-installed")
# ─────────────────────────────────────────────────────────────────────

# ── config ───────────────────────────────────────────────────────────
HEADLESS  = True          # flip to False locally to watch the browser
USER_AGENT = "Mozilla/5.0 (vc-scraper 0.7)"
TIMEOUT    = (5, 15)      # connect, read
BLOCKLIST_DOMAINS = {
    "linkedin", "twitter", "facebook", "instagram",
    "medium", "github", "youtube", "notion", "airtable",
    "calendar", "crunchbase", "google", "apple", "figma",
}

# ── stdlib / third-party ─────────────────────────────────────────────
import csv, html, re
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urljoin

import requests
import tldextract
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ── helpers ──────────────────────────────────────────────────────────
def normalize(url: str) -> str:
    if not url:
        return ""
    return "https:" + url[2:] if url.startswith("//") else url

def fetch(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text

# ── Playwright pass ─────────────────────────────────────────────────
def extract_with_playwright(page_url: str) -> List[Tuple[str, str]]:
    """Extract company names and their real URLs from portfolio cards using Playwright."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
        rows, seen = [], set()
        
        # Normalize the URL
        if not page_url.startswith('http'):
            page_url = 'https://' + page_url
            
        original_domain = tldextract.extract(page_url).domain.lower()
        print(f"ℹ️  Starting Playwright extraction from {page_url}")
        
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=HEADLESS)
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={'width': 1280, 'height': 800}
            )
            
            # Add stealth script to avoid detection
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                window.chrome = {
                    runtime: {}
                };
            """)
            
            page = context.new_page()
            
            # Add headers to avoid blocking
            page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0"
            })
            
            try:
                print(f"ℹ️  Loading portfolio page...")
                
                # Try multiple times with increasing delays
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # Try different wait strategies
                        wait_strategies = ['domcontentloaded', 'networkidle', 'load']
                        for strategy in wait_strategies:
                            try:
                                page.goto(page_url, timeout=60000, wait_until=strategy)
                                page.wait_for_load_state(strategy, timeout=30000)
                                break
                            except Exception as e:
                                print(f"⚠️  Wait strategy {strategy} failed: {e}")
                                continue
                        
                        # Add random delay between 2-5 seconds
                        page.wait_for_timeout(3000)
                        
                        # Check if page loaded successfully
                        if page.content():
                            break
                            
                    except Exception as e:
                        if attempt < max_retries - 1:
                            delay = (attempt + 1) * 5
                            print(f"⚠️  Attempt {attempt + 1} failed, waiting {delay}s before retry: {e}")
                            page.wait_for_timeout(delay * 1000)
                        else:
                            raise

                # For sites that require multiple scrolls
                print("ℹ️  Scrolling to load all content...")
                prev_height = 0
                scroll_attempts = 0
                max_scroll_attempts = 5
                
                while scroll_attempts < max_scroll_attempts:
                    # Scroll by viewport height
                    page.evaluate("window.scrollBy(0, window.innerHeight)")
                    page.wait_for_timeout(1000)  # Wait for content to load
                    
                    # Check if we've reached the bottom
                    curr_height = page.evaluate("document.body.scrollHeight")
                    if curr_height == prev_height:
                        scroll_attempts += 1
                    else:
                        scroll_attempts = 0  # Reset counter if height changed
                    prev_height = curr_height
                
                # Wait for any lazy-loaded content
                page.wait_for_timeout(2000)
                
                print("ℹ️  Analyzing page structure...")
                
                # Try multiple selectors for company elements
                selectors = [
                    '[class*="company-card"]',
                    '[class*="CompanyCard"]',
                    '[class*="portfolio-item"]',
                    '[class*="company-logo"]',
                    '[data-testid*="company"]',
                    '[data-testid*="portfolio"]',
                    '[id*="company"]',
                    '[id*="portfolio"]',
                    '.company-card',
                    '[class*="company"]',
                    '[class*="portfolio-item"]',
                    '.grid-item',
                    '.portfolio-card',
                    'a[href*="/company/"]',
                    'a[href*="/portfolio/"]',
                    'a[href*="?company="]',
                    'div[role="listitem"]'
                ]
                
                # Special handling for Index Ventures and similar sites
                if 'indexventures.com' in page_url or any(x in page_url.lower() for x in ['portfolio', 'companies']):
                    # Try to find company cards or links
                    company_links = []
                    for selector in selectors:
                        try:
                            elements = page.query_selector_all(selector)
                            if elements:
                                print(f"Found {len(elements)} elements with selector: {selector}")
                                for element in elements:
                                    try:
                                        # Get the link URL
                                        href = None
                                        if element.get_attribute('href'):
                                            href = element.get_attribute('href')
                                        else:
                                            # Try to find a link inside the element
                                            link = element.query_selector('a')
                                            if link:
                                                href = link.get_attribute('href')
                                        
                                        if href:
                                            # Make relative URLs absolute
                                            if href.startswith('/'):
                                                href = urljoin(page_url, href)
                                            elif href.startswith('//'):
                                                href = 'https:' + href
                                                
                                            # Skip obvious non-company URLs
                                            if any(x in href.lower() for x in [
                                                '/blog/', '/news/', '/about/', '/contact/', 
                                                '/team/', '/careers/', '#', 'javascript:'
                                            ]):
                                                continue
                                                
                                            # Get the company name
                                            name = element.inner_text().strip()
                                            if name:
                                                name = re.sub(r'\s+', ' ', name)
                                                name = re.sub(r'^(View|Visit|Go to|Link to|About)\s+', '', name, flags=re.IGNORECASE)
                                                name = re.sub(r'\s+(Website|Page|Profile)$', '', name, flags=re.IGNORECASE)
                                                
                                                if name and len(name) <= 80 and name.lower() not in seen:
                                                    company_links.append({
                                                        'name': name,
                                                        'href': href
                                                    })
                                                    seen.add(name.lower())
                                                    
                                    except Exception as e:
                                        print(f"⚠️  Error processing element: {e}")
                                        continue
                                        
                        except Exception as e:
                            print(f"⚠️  Selector {selector} failed: {e}")
                            continue
                            
                    if company_links:
                        print(f"\nℹ️  Found {len(company_links)} company links to process")
                        
                        # Create a new page for visiting company details
                        detail_page = context.new_page()
                        detail_page.set_default_timeout(30000)
                        
                        for idx, company in enumerate(company_links):
                            try:
                                print(f"[{idx+1}/{len(company_links)}] Processing {company['name']}")
                                
                                # Navigate to company detail page
                                try:
                                    detail_page.goto(company['href'], wait_until='domcontentloaded')
                                    detail_page.wait_for_load_state('networkidle', timeout=10000)
                                except Exception as e:
                                    print(f"⚠️  Could not load detail page: {e}")
                                    continue
                                
                                # Try to find the website link
                                website = None
                                website_selectors = [
                                    'a[href*="://"][target="_blank"]',
                                    'a[href*="www."]',
                                    'a[href*="http"]',
                                    '[class*="website"] a',
                                    '[class*="link"] a',
                                    'a[class*="website"]',
                                    'a[class*="link"]'
                                ]
                                
                                for selector in website_selectors:
                                    try:
                                        links = detail_page.query_selector_all(selector)
                                        for link in links:
                                            href = link.get_attribute('href')
                                            if href and not any(x in href.lower() for x in [
                                                'linkedin.com', 'twitter.com', 'facebook.com',
                                                'instagram.com', 'youtube.com', 'medium.com',
                                                'github.com', 'crunchbase.com', original_domain
                                            ]):
                                                website = href
                                                break
                                        if website:
                                            break
                                    except:
                                        continue
                                
                                if website:
                                    print(f"✓ Found website: {website}")
                                    rows.append((company['name'], website))
                                else:
                                    print("⚠️  No website found")
                                    
                                # Add a small delay between requests
                                detail_page.wait_for_timeout(1000)
                                
                            except Exception as e:
                                print(f"⚠️  Error processing company: {e}")
                                continue
                                
                        detail_page.close()
                        
                    else:
                        print("⚠️  No company links found with specialized extraction")
                        
                else:
                    # Regular extraction for other sites
                    companies = []
                    for selector in selectors:
                        try:
                            elements = page.query_selector_all(selector)
                            if elements:
                                print(f"Found {len(elements)} elements with selector: {selector}")
                                companies.extend(elements)
                        except Exception as e:
                            print(f"⚠️  Selector {selector} failed: {e}")
                            continue
                    
                    if companies:
                        print(f"\nℹ️  Found {len(companies)} potential companies")
                        
                        for idx, company in enumerate(companies):
                            try:
                                # Try to get company info without clicking
                                try:
                                    # Get company name from text content
                                    name = company.inner_text().strip()
                                    name = re.sub(r'\s+', ' ', name)
                                    
                                    # Look for website link
                                    website = None
                                    
                                    # Try to find a website link in the card
                                    for link in company.query_selector_all('a'):
                                        href = link.get_attribute('href')
                                        if href:
                                            # Skip internal/navigation links
                                            if any(x in href.lower() for x in [
                                                '/blog/', '/news/', '/about/', '/contact/', 
                                                '/team/', '/careers/', '#', 'javascript:',
                                                '/privacy', '/terms', '/disclosures'
                                            ]):
                                                continue
                                                
                                            # If it's a relative path, make it absolute
                                            if href.startswith('/'):
                                                href = urljoin(page_url, href)
                                            
                                            # If it's an external link, it might be the company website
                                            link_domain = tldextract.extract(href).domain.lower()
                                            if link_domain and link_domain != original_domain:
                                                website = href
                                                break
                                    
                                    if website:
                                        # Clean up the name
                                        name = re.sub(r'^(View|Visit|Go to|Link to|About)\s+', '', name, flags=re.IGNORECASE)
                                        name = re.sub(r'\s+(Website|Page|Profile)$', '', name, flags=re.IGNORECASE)
                                        
                                        # If name is still not good, try to get it from the website
                                        if not name or len(name) < 2:
                                            ext = tldextract.extract(website)
                                            if ext.domain:
                                                name = ext.domain.replace('-', ' ').replace('.', ' ').title()
                                        
                                        if name and len(name) <= 80 and name.lower() not in seen:
                                            print(f"[{idx+1}/{len(companies)}] {name}: {website}")
                                            rows.append((name, website))
                                            seen.add(name.lower())
                                    
                                except Exception as e:
                                    print(f"⚠️  Could not extract info from company {idx+1}: {e}")
                                    continue
                                    
                            except Exception as e:
                                print(f"⚠️  Error processing company element: {e}")
                                continue
                
            except PlaywrightTimeoutError as e:
                print(f"⚠️  Playwright timeout: {e}")
            except Exception as e:
                print(f"⚠️  Playwright navigation error: {e}")
            finally:
                context.close()
                browser.close()
                
        if rows:
            print(f"ℹ️  Playwright found {len(rows)} companies")
        else:
            print("ℹ️  Playwright found no companies")
        return rows
        
    except Exception as e:
        print(f"⚠️  Playwright extraction failed: {e}")
        return []

# ── master extractor ────────────────────────────────────────────────
def extract_companies(url: str) -> List[Tuple[str, str]]:
    """Extract companies from a VC portfolio page."""
    # Normalize the URL
    if not url.startswith('http'):
        url = 'https://' + url
    
    vc_dom = tldextract.extract(url).domain.lower()
    rows, seen = [], set()
    seen_urls = set()  # Track seen URLs to prevent duplicates

    # Try WordPress JSON API first (common for many VC sites)
    wp_api_endpoints = [
        url.rstrip("/").split("/portfolio")[0] + "/wp-json/wp/v2/portfolio",
        url.rstrip("/") + "/wp-json/wp/v2/portfolio",
        url.rstrip("/") + "/api/portfolio",
        url.rstrip("/") + "/api/companies"
    ]
    
    for wp_api in wp_api_endpoints:
        try:
            if requests.head(wp_api, timeout=10).status_code == 200:
                print("ℹ️  Using WordPress/API endpoint")
                api_data = requests.get(wp_api, timeout=TIMEOUT).json()
                for item in api_data:
                    if isinstance(item, dict):
                        name = ""
                        website = ""
                        
                        # Try different field names for company name
                        for name_field in ["title", "name", "company_name", "company"]:
                            if name_field in item:
                                if isinstance(item[name_field], dict) and "rendered" in item[name_field]:
                                    name = item[name_field]["rendered"].strip()
                                elif isinstance(item[name_field], str):
                                    name = item[name_field].strip()
                                break
                        
                        # Try different field names for website
                        for url_field in ["website", "company_website", "url", "link", "acf"]:
                            if url_field in item:
                                if url_field == "acf" and isinstance(item[url_field], dict):
                                    website = item[url_field].get("company_website", "")
                                elif isinstance(item[url_field], str):
                                    website = item[url_field]
                                break
                        
                        if name and len(name) > 1:
                            final_url = website or f"https://www.google.com/search?q={name.replace(' ', '+')}+company"
                            if final_url not in seen_urls:
                                rows.append((name, final_url))
                                seen_urls.add(final_url)
                
                if rows:
                    return rows
        except Exception as e:
            continue

    # Try basic HTML scraping first and store results as fallback
    html_rows = []
    anchor_rows = []  # capture exact links from anchor tags when available
    html_quality_companies = 0
    
    try:
        # Fetch the page content
        print(f"ℹ️  Fetching {url}")
        html_content = fetch(url)
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 1️⃣  First, capture anchor tags that wrap portfolio cards (very precise for sites like Bling Capital)
        for a in soup.find_all("a", href=True):
            if a.find(class_="portfolio-card"):
                href_raw = a["href"].strip()
                if href_raw == "//":
                    continue  # skip invalid
                href = urljoin(url, normalize(html.unescape(href_raw)))
                dom = tldextract.extract(href).domain.lower()
                if not dom or dom == vc_dom or dom in BLOCKLIST_DOMAINS:
                    continue
                # Portfolio cards usually have an <h4> with the company name
                h4 = a.find("h4")
                name = h4.get_text(strip=True) if h4 else a.get_text(" ", strip=True)
                name = re.sub(r"\s+", " ", name)
                if name and len(name) <= 80 and href not in seen_urls:
                    anchor_rows.append((name, href))
                    seen_urls.add(href)
                    seen.add(name.lower())

        # 2️⃣  Generic pass: Look for any external links that might be company websites (fallback)
        for a in soup.find_all("a", href=True):
            href = urljoin(url, normalize(html.unescape(a["href"])))
            dom = tldextract.extract(href).domain.lower()
            if not dom or dom == vc_dom or dom in BLOCKLIST_DOMAINS:
                continue
            name = re.sub(r"\s+", " ", a.get_text(" ", strip=True)) or dom.capitalize()
            if href in seen_urls or len(name) > 100:
                continue
            seen_urls.add(href)
            html_rows.append((name, href))

        # Prefer anchor_rows if we found a decent amount (exact links)
        if len(anchor_rows) >= 5:
            print(f"ℹ️  Anchor-based extraction found {len(anchor_rows)} companies with exact URLs")
            html_rows = anchor_rows + [row for row in html_rows if row[0] not in {r[0] for r in anchor_rows}]
        else:
            print(f"ℹ️  Anchor-based extraction found only {len(anchor_rows)} companies; using generic links too")
        
        print(f"ℹ️  Basic HTML extraction found {len(html_rows)} potential companies")
        
        # Analyze quality of HTML extraction results
        if len(html_rows) > 10:  # If we found a reasonable number
            # Count how many look like real company names (not navigation/UI)
            for name, company_url in html_rows:
                name_lower = name.lower()
                # Skip obvious navigation/UI elements
                if any(nav_word in name_lower for nav_word in [
                    "home", "about", "team", "contact", "blog", "news", "portfolio", 
                    "companies", "investment", "fund", "menu", "navigation"
                ]):
                    continue
                # Skip very long descriptions
                if len(name) > 50 or len(name.split()) > 5:
                    continue
                # Skip if it looks like a sentence or description
                if any(word in name_lower for word in ["the", "and", "for", "with", "our", "we", "is", "are"]):
                    continue
                
                html_quality_companies += 1
            
            print(f"ℹ️  Quality company names found: {html_quality_companies}")
            
            # Special handling for sites that claim to have many more companies
            # Look for indicators that there's more content (like pagination or "1000+" mentions)
            soup_text = soup.get_text().lower()
            has_large_portfolio_indicators = any(indicator in soup_text for indicator in [
                "1000", "1,000", "1400", "1,400", "500+", "1000+", "1,000+", 
                "over 1000", "over 1,000", "thousand", "hundreds of companies",
                "view all", "show all", "load more", "see all portfolio"
            ])
            
            has_pagination = soup.select_one("a[class*='next'], button[class*='next'], .pagination")
            
            # If we found quality companies BUT there are indicators of much more content,
            # use Playwright to get the full dataset, but compare results
            if html_quality_companies >= 15 and (has_large_portfolio_indicators or has_pagination):
                print("ℹ️  Detected potential for more content - testing Playwright extraction")
                playwright_results = extract_with_playwright(url)  # Pass the original portfolio URL
                
                # Compare results and use the better one
                if playwright_results and len(playwright_results) > len(html_rows) * 1.2:  # Playwright found 20% more
                    print(f"ℹ️  Playwright found more companies ({len(playwright_results)} vs {len(html_rows)}) - using Playwright results")
                    return playwright_results
                elif playwright_results and len(playwright_results) > 50:  # Playwright found a significant number
                    print(f"ℹ️  Playwright found substantial companies ({len(playwright_results)}) - using Playwright results")
                    return playwright_results
                else:
                    print(f"ℹ️  Playwright didn't improve results - using HTML extraction ({len(html_rows)} companies)")
                    return html_rows
            
            # If we found a good number of quality company names, use HTML results
            elif html_quality_companies >= 15:  
                print("ℹ️  Using HTML extraction results (good quality detected)")
                return html_rows
            
    except Exception as e:
        print(f"ℹ️  Basic HTML extraction failed: {e}")

    # Fall back to Playwright extraction, but use HTML results if Playwright fails
    print("ℹ️  Using Playwright extraction")
    playwright_results = extract_with_playwright(url)  # Pass the original portfolio URL
    
    # If Playwright failed but we have HTML results, use those as fallback
    if not playwright_results and html_rows:
        print(f"ℹ️  Playwright extraction failed, falling back to HTML results ({len(html_rows)} companies)")
        return html_rows
    elif playwright_results:
        return playwright_results
    else:
        # Both failed, return empty list
        print("⚠️  Both Playwright and HTML extraction failed")
        return []

# ── CLI wrapper ─────────────────────────────────────────────────────
def main() -> None:
    import sys
    if len(sys.argv) != 2:
        sys.exit("Usage: python vc_scraper.py <portfolio-URL>")

    target = sys.argv[1] if sys.argv[1].startswith("http") else "https://" + sys.argv[1]
    data = extract_companies(target)

    out = Path("portfolio_companies.csv")
    with out.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([("Company", "URL"), *data])

    print(f"✅  {len(data)} companies saved to {out}")

if __name__ == "__main__":
    main()

# test

