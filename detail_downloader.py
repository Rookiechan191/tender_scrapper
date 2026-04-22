import time
import os
import re
import csv
from pathlib import Path
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# CONFIG
URL = "https://mahatenders.gov.in/nicgep/app?page=FrontEndLatestActiveTenders&service=page"
DOWNLOAD_DIR = "files"
OUTPUT_CSV = "details_output.csv"
TOTAL_TO_SCRAPE = 50


# DRIVER
def make_driver():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    opts = webdriver.ChromeOptions()
    opts.add_argument("--start-maximized")

    prefs = {
        "download.default_directory": str(Path(DOWNLOAD_DIR).resolve()),
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
    }
    opts.add_experimental_option("prefs", prefs)

    return webdriver.Chrome(options=opts)


# HELPERS
def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def parse_tender_id(raw):
    match = re.search(r"\[(.*?)\]", raw)
    return match.group(1) if match else "unknown_id"


def get_files():
    return set(os.listdir(DOWNLOAD_DIR))


def wait_for_new_file(old_files, timeout=60):
    start = time.time()
    while True:
        current = set(os.listdir(DOWNLOAD_DIR))
        new_files = current - old_files
        new_files = [f for f in new_files if not f.endswith(".crdownload")]

        if new_files:
            return new_files[0]

        if time.time() - start > timeout:
            return None

        time.sleep(1)


def rename_file(old_name, new_name):
    try:
        old_path = Path(DOWNLOAD_DIR) / old_name
        new_path = Path(DOWNLOAD_DIR) / new_name

        if old_path.exists():
            old_path.rename(new_path)
            print(f"Renamed → {new_name}")
    except Exception as e:
        print("Rename error:", e)


# CAPTCHA
def wait_for_captcha_to_be_solved(driver, timeout=120):
    wait = WebDriverWait(driver, timeout)
    try:
        captcha_input = driver.find_element(By.XPATH, "//input[@type='text']")
        print("Captcha detected, waiting...")
        wait.until(EC.staleness_of(captcha_input))
        print("Captcha solved")
    except:
        pass


# DOWNLOAD FILES
def download_files(driver, tender_id):
    wait = WebDriverWait(driver, 10)
    time.sleep(2)

    try:
        section = wait.until(EC.presence_of_element_located((
            By.XPATH, "//td[contains(text(),'Tenders Documents')]"
        )))

        table = section.find_element(By.XPATH, "following::table[1]")
        links = table.find_elements(By.TAG_NAME, "a")

        print(f"Found {len(links)} document links")

        for i in range(len(links)):
            try:
                section = wait.until(EC.presence_of_element_located((
                    By.XPATH, "//td[contains(text(),'Tenders Documents')]"
                )))
                table = section.find_element(By.XPATH, "following::table[1]")
                links = table.find_elements(By.TAG_NAME, "a")

                link = links[i]
                text = link.text.strip()

                if not text:
                    continue

                print(f"Clicking: {text}")

                old_files = get_files()

                driver.execute_script("arguments[0].scrollIntoView(true);", link)
                driver.execute_script("arguments[0].click();", link)

                time.sleep(2)

                if driver.find_elements(By.XPATH, "//input[@type='text']"):
                    print("Captcha triggered")
                    wait_for_captcha_to_be_solved(driver)
                    time.sleep(2)

                    section = wait.until(EC.presence_of_element_located((
                        By.XPATH, "//td[contains(text(),'Tenders Documents')]"
                    )))
                    table = section.find_element(By.XPATH, "following::table[1]")
                    links = table.find_elements(By.TAG_NAME, "a")

                    link = links[i]
                    driver.execute_script("arguments[0].click();", link)

                new_file = wait_for_new_file(old_files)

                if new_file:
                    ext = ".pdf" if "pdf" in text.lower() else ".zip"
                    safe_id = re.sub(r'[\\/*?:"<>|]', "_", tender_id)
                    rename_file(new_file, f"{safe_id}_doc_{i}{ext}")
                else:
                    print(f"No download for {text}")

            except Exception as e:
                print(f"Error doc {i}:", e)

    except Exception as e:
        print("Document section error:", e)


# PROCESS TENDER (NEW TAB)
def process_tender(driver, index):
    rows = driver.find_elements(
        By.XPATH, "//table[@id='table']//tr[@class='even' or @class='odd']"
    )

    if index >= len(rows):
        return None

    row = rows[index]
    cols = row.find_elements(By.TAG_NAME, "td")

    sno = clean(cols[0].text)
    title_cell = cols[4]

    raw_title = clean(title_cell.text)
    tender_id = parse_tender_id(raw_title)

    print(f"\nProcessing {sno} | {tender_id}")

    link = title_cell.find_element(By.TAG_NAME, "a")

    driver.execute_script("window.open(arguments[0].href, '_blank');", link)
    driver.switch_to.window(driver.window_handles[-1])

    time.sleep(3)

    download_files(driver, tender_id)

    driver.close()
    driver.switch_to.window(driver.window_handles[0])

    return {
        "S.No": sno,
        "Tender ID": tender_id,
        "Scraped At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# MAIN
def main():
    driver = make_driver()
    driver.get(URL)

    print("Solve initial CAPTCHA and click SEARCH")
    input("Press ENTER after table loads...")

    results = []
    processed = 0
    wait = WebDriverWait(driver, 10)
    page = 1

    while processed < TOTAL_TO_SCRAPE:

        print(f"\n--- PAGE {page} ---")

        rows = wait.until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//table[@id='table']//tr[@class='even' or @class='odd']")
            )
        )

        for i in range(len(rows)):

            if processed >= TOTAL_TO_SCRAPE:
                break

            try:
                rows = driver.find_elements(
                    By.XPATH, "//table[@id='table']//tr[@class='even' or @class='odd']"
                )

                res = process_tender(driver, i)

                if res:
                    results.append(res)
                    processed += 1
                    print(f"Done: {processed}/{TOTAL_TO_SCRAPE}")

            except Exception as e:
                print("Row error:", e)

            time.sleep(2)

        # 🔥 NEXT PAGE USING loadNext
        if processed < TOTAL_TO_SCRAPE:
            try:
                print("Going to next page")

                next_btn = wait.until(
                    EC.presence_of_element_located((By.ID, "loadNext"))
                )

                next_href = next_btn.get_attribute("href")

                if not next_href:
                    print("No next page")
                    break

                driver.get(next_href)

                wait.until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, "//table[@id='table']//tr[@class='even' or @class='odd']")
                    )
                )

                time.sleep(2)

                page += 1

            except Exception as e:
                print("Next failed:", e)
                break

    driver.quit()

    if results:
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

        print("Saved to CSV")


if __name__ == "__main__":
    main()