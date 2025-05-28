# VC Portfolio Scraper

A generalized web scraper that can extract portfolio companies from any VC firm's website. Works with simple HTML sites, complex JavaScript sites, and everything in between.

## Features

- **🧠 Smart Strategy Selection**: Automatically chooses the best extraction method
- **📄 Multi-Strategy Fallback**: API detection → HTML scraping → Playwright extraction
- **🔄 Pagination Handling**: Automatically follows pagination to get complete portfolios
- **✨ Quality Analysis**: Filters out navigation/UI elements to focus on actual companies
- **🚀 Deployment Ready**: Works on Streamlit Cloud and other deployment platforms

## Setup

1. Clone and setup:
```bash
git clone <your-repo>
cd Scraper
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Run the scraper:
```bash
python vc_scraper.py https://www.primary.vc/portfolio
```

## Usage

### Command Line
```bash
python vc_scraper.py <portfolio-URL>
```

### Streamlit Web App
```bash
streamlit run app.py
```

## How It Works

The scraper uses a multi-strategy approach:

1. **API Detection**: First tries WordPress JSON APIs and other common API endpoints
2. **HTML Scraping**: Extracts external links from HTML that might be company websites
3. **Quality Analysis**: Analyzes extracted results to determine if they look like real companies
4. **Playwright Fallback**: For complex JavaScript sites, uses browser automation to:
   - Click through portfolio detail pages to find company websites
   - Extract company names from text lists (like Alumni Ventures)
   - Handle pagination automatically
   - Scroll and wait for dynamic content to load

## Supported Sites

The scraper intelligently adapts to various VC portfolio structures:
- ✅ Simple HTML portfolio pages (like Primary VC, Pear VC)
- ✅ Complex JavaScript sites (like A16Z with dynamic loading)
- ✅ Text-based company lists (like Alumni Ventures)
- ✅ Paginated portfolios (automatic pagination handling)
- ✅ API-driven sites (WordPress, JSON endpoints)

## Example Results

- **Primary VC**: 88 companies extracted
- **Pear VC**: 196 companies extracted  
- **Oceans Ventures**: 41 companies extracted
- **Alumni Ventures**: 1,405 companies extracted (across 21 pages)

## Output

The scraper generates a `portfolio_companies.csv` file with:
- Company Name
- Company Website (or Google search URL if website not found)

## Troubleshooting

If you get `ModuleNotFoundError: No module named 'requests'`:
```bash
# Make sure you're in the virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

If Playwright browsers aren't installing automatically:
```bash
playwright install chromium
``` 