# VC Portfolio Scraper

A Python tool to scrape company information from VC portfolio pages. Uses Playwright for JavaScript-heavy sites and falls back to BeautifulSoup for simpler pages.

## Features

- Handles both static and JavaScript-rendered pages
- Extracts company names and website URLs
- Supports various portfolio page layouts
- Outputs results to CSV
- Built-in retry and error handling

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd <repo-directory>
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

Run the scraper with a portfolio URL:
```bash
python vc_scraper.py https://example.vc/portfolio
```

The script will:
1. Try to extract companies using BeautifulSoup
2. If needed, fall back to Playwright for JavaScript-rendered pages
3. Save results to `portfolio_companies.csv`

## Output Format

The script generates a CSV file with two columns:
- Company Name
- Website URL

## Examples

```bash
# Scrape Index Ventures portfolio
python vc_scraper.py https://www.indexventures.com/companies/backed/all/

# Scrape a16z portfolio
python vc_scraper.py https://speedrun.a16z.com/companies
```

## Error Handling

The script includes:
- Multiple retry attempts
- Different page load strategies
- Fallback extraction methods
- Detailed error logging

## Requirements

- Python 3.8+
- Playwright
- BeautifulSoup4
- Requests
- tldextract 