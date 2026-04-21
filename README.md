# tender_scrapper

This repository contains a Maharashtra tender scraping and reporting workflow:

- `main.py` scrapes active tenders from the MahaTenders portal and saves them to `mahatenders_output.csv`.
- `report_generator.py` reads that CSV, creates charts, and generates `Tender_Report.pdf`.

## Prerequisites

- Python 3.10+
- Google Chrome installed
- ChromeDriver available on PATH (matching your Chrome version)

## Install dependencies

```bash
pip install selenium pandas matplotlib reportlab
```

## Usage

### 1) Scrape tenders

```bash
python main.py
```

When Chrome opens:
1. Solve CAPTCHA
2. Click **SEARCH**
3. Return to terminal and press **ENTER**

Output: `mahatenders_output.csv`

### 2) Generate report

```bash
python report_generator.py
```

Outputs:
- `Tender_Report.pdf`
- `district.png`
- `value.png`
- `category.png`
- `timeline.png`
- `size.png`
