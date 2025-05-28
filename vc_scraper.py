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
        original_domain = tldextract.extract(page_url).domain.lower()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=HEADLESS)
            page = browser.new_page(user_agent=USER_AGENT)
            try:
                print(f"ℹ️  Loading {page_url} with Playwright...")
                response = page.goto(page_url, timeout=60000, wait_until='networkidle')
                
                # Check if we got redirected to a different domain
                final_url = page.url
                final_domain = tldextract.extract(final_url).domain.lower()
                if final_domain != original_domain:
                    print(f"⚠️  Got redirected to different domain: {final_url}")
                    print("ℹ️  Skipping Playwright extraction")
                    return []
                
                # Wait longer and scroll to handle dynamic loading
                page.wait_for_load_state("networkidle", timeout=30000)
                
                # Scroll to bottom to trigger lazy loading
                print("ℹ️  Scrolling to load all content...")
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)  # Wait for any lazy loading
                
                # Try multiple common portfolio card selectors
                portfolio_selectors = [
                    'a:has(.portfolio-card)',  # Bling Capital style
                    '.portfolio-company a',     # Common pattern
                    '.portfolio-item a',        # Common pattern
                    '.company-card a',          # Common pattern
                    'a:has([class*="portfolio"])',  # Any element with portfolio in class
                    'a:has([class*="company"])',    # Any element with company in class
                    '[class*="portfolio"] a',       # Links inside portfolio elements
                    '[class*="company"] a',         # Links inside company elements
                    '.grid a',                      # Common grid layout
                ]
                
                all_links = []
                for selector in portfolio_selectors:
                    try:
                        links = page.query_selector_all(selector)
                        if links:
                            print(f"Found {len(links)} links with selector: {selector}")
                            all_links.extend(links)
                    except Exception:
                        continue
                
                # Remove duplicates while preserving order
                seen_elements = set()
                unique_links = []
                for link in all_links:
                    try:
                        href = link.get_attribute('href')
                        if href and href not in seen_elements:
                            seen_elements.add(href)
                            unique_links.append(link)
                    except:
                        continue
                
                print(f"\nℹ️  Found {len(unique_links)} unique company links")
                
                for idx, link in enumerate(unique_links):
                    try:
                        # Get the href and normalize it
                        href = link.get_attribute('href')
                        if not href:
                            continue
                            
                        # Normalize protocol-relative URLs
                        if href.startswith('//'):
                            href = 'https:' + href
                        elif href.startswith('/'):
                            # Handle relative URLs
                            href = urljoin(page_url, href)
                            
                        # Skip obvious non-company URLs
                        if any(x in href.lower() for x in ['/blog/', '/news/', '/about/', '/contact/', '/team/', '/careers/']):
                            continue
                            
                        # Try multiple selectors for company name
                        name = None
                        for name_selector in ['h4', 'h3', 'h2', '.company-name', '[class*="name"]']:
                            try:
                                name_elem = link.query_selector(name_selector)
                                if name_elem:
                                    name = name_elem.inner_text().strip()
                                    break
                            except:
                                continue
                                
                        # If no text name found, try getting it from the URL
                        if not name:
                            ext = tldextract.extract(href)
                            if ext.domain and ext.domain != original_domain:
                                # Convert domain to title case and remove common TLDs
                                name = ext.domain.replace('-', ' ').replace('.', ' ').title()
                            
                        # Clean up name
                        if name:
                            name = re.sub(r'\s+', ' ', name)
                            
                        if not name or name.lower() in seen or len(name) > 80:
                            continue
                            
                        # Check if it's an external link
                        dom = tldextract.extract(href).domain.lower()
                        if dom == original_domain or dom in BLOCKLIST_DOMAINS:
                            continue
                            
                        print(f"[{idx+1}/{len(unique_links)}] {name}: {href}")
                        rows.append((name, href))
                        seen.add(name.lower())
                        
                    except Exception as e:
                        print(f"⚠️  Error processing link: {e}")
                        continue
                        
            except PlaywrightTimeoutError as e:
                print(f"⚠️  Playwright timeout: {e}")
            except Exception as e:
                print(f"⚠️  Playwright navigation error: {e}")
            finally:
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
    vc_dom = tldextract.extract(url).domain.lower()
    rows, seen = [], set()

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
                            rows.append((name, final_url))
                
                if rows:
                    return rows
        except Exception as e:
            continue

    # Try basic HTML scraping first and store results as fallback
    html_rows = []
    anchor_rows = []  # capture exact links from anchor tags when available
    html_quality_companies = 0
    
    try:
        soup = BeautifulSoup(fetch(url), "html.parser")
        
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
                if name and len(name) <= 80 and href not in seen:
                    anchor_rows.append((name, href))
                    seen.add(name)

        # 2️⃣  Generic pass: Look for any external links that might be company websites (fallback)
        for a in soup.find_all("a", href=True):
            href = urljoin(url, normalize(html.unescape(a["href"])))
            dom = tldextract.extract(href).domain.lower()
            if not dom or dom == vc_dom or dom in BLOCKLIST_DOMAINS:
                continue
            name = re.sub(r"\s+", " ", a.get_text(" ", strip=True)) or dom.capitalize()
            if href in seen or len(name) > 100:
                continue
            seen.add(href)
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
            for name, url in html_rows:
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
                playwright_results = extract_with_playwright(url)
                
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
    playwright_results = extract_with_playwright(url)
    
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

