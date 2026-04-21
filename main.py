"""
MahaTenders — All Pages Scraper
================================
Usage:
    pip install selenium
    python mahatenders_scraper.py

Steps:
    1. Chrome opens the site automatically.
    2. Solve the CAPTCHA in the browser, then click SEARCH.
    3. Come back to the terminal and press ENTER.
    4. The scraper auto-paginates through ALL pages and saves → mahatenders_output.csv
"""

import time
import csv
import re
from pathlib import Path
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)


# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
URL        = "https://mahatenders.gov.in/nicgep/app?page=FrontEndLatestActiveTenders&service=page"
OUTPUT_CSV = "mahatenders_output.csv"
WAIT_SEC   = 20    # seconds to wait for page elements
PAGE_DELAY = 2.0   # polite delay between pages (seconds)


# ─────────────────────────────────────────────
#  BROWSER SETUP
# ─────────────────────────────────────────────
def make_driver() -> webdriver.Chrome:
    opts = webdriver.ChromeOptions()
    opts.add_argument("--start-maximized")
    # Uncomment to run without a visible window:
    # opts.add_argument("--headless=new")
    return webdriver.Chrome(options=opts)


# ─────────────────────────────────────────────
#  TEXT HELPERS
# ─────────────────────────────────────────────
def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_title_cell(raw: str) -> tuple[str, str, str]:
    """
    Title cell format:
        [Title Text ] [Etender-2025-26] [2026_BULDH_1291793_1]

    Returns (title, etender_ref, tender_id)
    """
    blocks = re.findall(r"\[([^\]]+)\]", raw)
    blocks = [b.strip() for b in blocks if b.strip()]

    tender_id, etender_ref, title_parts = "", "", []

    for b in blocks:
        if re.match(r"\d{4}_[A-Z]+_\d+_\d+", b):
            tender_id = b
        elif re.match(r"[Ee]tender-\d{4}-\d{2,}", b):
            etender_ref = b
        else:
            title_parts.append(b)

    return " ".join(title_parts), etender_ref, tender_id


# ─────────────────────────────────────────────
#  SCRAPE ONE PAGE
# ─────────────────────────────────────────────
COLUMNS = [
    "S.No",
    "Published Date",
    "Bid Closing Date",
    "Tender Opening Date",
    "Title",
    "Etender Ref",
    "Tender ID",
    "Organisation Chain",
    "Tender Value (INR)",
    "Page",
    "Scraped At",
]


def scrape_current_page(driver: webdriver.Chrome, page_num: int) -> list[dict]:
    """Extract all tender rows from the currently loaded page."""
    wait = WebDriverWait(driver, WAIT_SEC)
    scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        wait.until(EC.presence_of_element_located((By.XPATH, "//table[.//tr[td]]")))
    except TimeoutException:
        print(f"   ❌  Timed out waiting for table on page {page_num}.")
        return []

    time.sleep(1.0)  # let JS finish any re-render

    rows = driver.find_elements(By.XPATH, "//table//tr[td]")
    records = []

    for row in rows:
        try:
            cols = row.find_elements(By.TAG_NAME, "td")
        except StaleElementReferenceException:
            continue

        if len(cols) < 7:
            continue

        sno_text = clean(cols[0].text)
        if not sno_text or not re.match(r"^\d+\.?$", sno_text):
            continue

        published = clean(cols[1].text)
        closing   = clean(cols[2].text)
        opening   = clean(cols[3].text)
        raw_title = clean(cols[4].text)
        org       = clean(cols[5].text)
        value     = clean(cols[6].text) or "NA"

        title, etender_ref, tender_id = parse_title_cell(raw_title)

        records.append({
            "S.No":                sno_text.rstrip("."),
            "Published Date":      published,
            "Bid Closing Date":    closing,
            "Tender Opening Date": opening,
            "Title":               title,
            "Etender Ref":         etender_ref,
            "Tender ID":           tender_id,
            "Organisation Chain":  org,
            "Tender Value (INR)":  value,
            "Page":                page_num,
            "Scraped At":          scraped_at,
        })

    return records


# ─────────────────────────────────────────────
#  PAGINATION HELPERS
# ─────────────────────────────────────────────
def get_total_pages(driver: webdriver.Chrome) -> int:
    """
    Try to read total page count from the pagination footer.
    Returns 0 if it can't figure it out (will paginate until no Next).
    """
    # Strategy 1: "Page X of Y" text
    try:
        page_text = driver.find_element(
            By.XPATH,
            "//*[contains(text(),'Page') and contains(text(),'of')]"
        ).text
        match = re.search(r"of\s+(\d+)", page_text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    except NoSuchElementException:
        pass

    # Strategy 2: highest numbered page link in pagination bar
    try:
        page_links = driver.find_elements(By.XPATH, "//a[contains(@href,'page=') or @onclick]")
        nums = [int(clean(lnk.text)) for lnk in page_links if re.match(r"^\d+$", clean(lnk.text))]
        if nums:
            return max(nums)
    except Exception:
        pass

    print("    Could not detect total pages — will stop when Next button disappears.")
    return 0


def click_next_page(driver: webdriver.Chrome) -> bool:
    """
    Click the Next / >> button.
    Returns True if clicked, False if we're on the last page.
    """
    next_xpaths = [
        "//a[normalize-space(text())='Next']",
        "//a[normalize-space(text())='next']",
        "//a[normalize-space(text())='>>']",
        "//a[normalize-space(text())='>']",
        "//a[contains(@title,'Next')]",
        "//input[@value='Next']",
        "//input[@value='>>']",
    ]

    for xpath in next_xpaths:
        try:
            btn = driver.find_element(By.XPATH, xpath)

            # Check if the button's parent marks it as disabled
            try:
                parent_class = btn.find_element(By.XPATH, "..").get_attribute("class") or ""
                if "disabled" in parent_class.lower():
                    return False
            except Exception:
                pass

            driver.execute_script("arguments[0].scrollIntoView(true);", btn)
            time.sleep(0.3)
            btn.click()
            return True

        except (NoSuchElementException, Exception):
            continue

    return False


# ─────────────────────────────────────────────
#  SAVE
# ─────────────────────────────────────────────
def save_csv(records: list[dict], path: str) -> None:
    out = Path(path)
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(records)
    print(f"\n  Saved {len(records)} total records → {out.resolve()}")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    driver = make_driver()
    all_records: list[dict] = []

    try:
        print(f"🌐  Opening {URL}")
        driver.get(URL)

        print("\n Solve the CAPTCHA in the browser, then click SEARCH.")
        input("    Press ENTER here once the results table is visible...\n")

        # ── Detect total pages ──────────────────────────────────────────────
        total_pages = get_total_pages(driver)
        if total_pages:
            print(f"  Detected {total_pages} pages total.\n")
        else:
            print(" Page count unknown — paginating until no Next button.\n")

        # ── Paginate through every page ─────────────────────────────────────
        page_num = 1

        while True:
            label = f"page {page_num}" + (f" / {total_pages}" if total_pages else "")
            print(f"  Scraping {label} ...")

            records = scrape_current_page(driver, page_num)
            print(f"   {len(records)} rows collected  (total so far: {len(all_records) + len(records)})")
            all_records.extend(records)

            # Stop if we've hit the known last page
            if total_pages and page_num >= total_pages:
                print("     Last page reached.")
                break

            # Try to go to the next page
            clicked = click_next_page(driver)
            if not clicked:
                print("    No Next button — done.")
                break

            page_num += 1
            time.sleep(PAGE_DELAY)

        # ── Save everything ─────────────────────────────────────────────────
        if all_records:
            save_csv(all_records, OUTPUT_CSV)
        else:
            print(" No data collected. Make sure the table loaded before pressing ENTER.")

    except KeyboardInterrupt:
        print("\n  Interrupted by user.")
        if all_records:
            print(f"   Saving {len(all_records)} records collected so far...")
            save_csv(all_records, OUTPUT_CSV)

    finally:
        driver.quit()
        print("  Browser closed.")


if __name__ == "__main__":
    main()