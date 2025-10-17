#!/usr/bin/env python3
"""
main.py
CLI for eCourts cause-list scraping & case lookup.

Usage examples:
  python main.py --causelist --state "Delhi" --district "New Delhi" --complex "Tis Hazari" --date 2025-10-18 --download-pdf
  python main.py --cnr "ABC1234567890" --today --download-pdf
  python main.py --case-type "Cr." --number 123 --year 2025 --tomorrow

Outputs:
  - console prints
  - JSON saved to ./outputs/<timestamp>_result.json
  - PDFs saved to ./outputs/pdfs/
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- Configuration & Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

OUTPUT_DIR = Path("outputs")
PDF_DIR = OUTPUT_DIR / "pdfs"
OUTPUT_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)

ECOURTS_CAUSELIST_URL = "https://services.ecourts.gov.in/ecourtindia_v6/?p=cause_list/"

# --- CSS Selectors (for easier maintenance) ---
# Using more general attribute selectors for robustness
STATE_SELECT = "select[id*='state'], select[name*='state']"
DISTRICT_SELECT = "select[id*='district'], select[name*='district']"
COMPLEX_SELECT = "select[id*='courtComplex'], select[name*='court_complex']"
DATE_INPUT = "input[type='date'], input[id*='date'], input[placeholder*='Date']"
SUBMIT_BUTTON = "button:has-text('Get'), button:has-text('Search'), button[title*='Search']"
CNR_INPUT = "input[placeholder*='CNR'], input[id*='cnr'], input[name*='cnr']"
RESULTS_ROW = "table.causelist tr, div.causeListRow, .cl-row, .case-row"


def parse_args():
    p = argparse.ArgumentParser(description="eCourts cause-list scraper")
    group = p.add_mutually_exclusive_group(required=False)
    group.add_argument("--today", action="store_true", help="Check listings for today")
    group.add_argument("--tomorrow", action="store_true", help="Check listings for tomorrow")
    p.add_argument("--date", type=str, help="Specific date (YYYY-MM-DD) to check / download cause list")
    p.add_argument("--cnr", type=str, help="CNR number to look up")
    p.add_argument("--case-type", type=str, help="Case type (e.g., 'Cr.')")
    p.add_argument("--number", type=int, help="Case number")
    p.add_argument("--year", type=int, help="Case year")
    p.add_argument("--state", type=str, help="State name for cause list (required for --causelist)")
    p.add_argument("--district", type=str, help="District (optional)")
    p.add_argument("--complex", type=str, help="Court complex (optional)")
    p.add_argument("--causelist", action="store_true", help="Download cause list for provided State/District/Complex and date")
    p.add_argument("--download-pdf", action="store_true", help="Download PDF(s) when found")
    p.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode (default on)")
    p.add_argument("--output", type=str, default=None, help="Output base filename (without extension)")
    return p.parse_args()

def get_date_to_check(args) -> str:
    if args.today:
        dt = datetime.now()
    elif args.tomorrow:
        dt = datetime.now() + timedelta(days=1)
    elif args.date:
        dt = datetime.fromisoformat(args.date)
    else:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d")

def save_json(data: dict, basename: Optional[str]=None):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = OUTPUT_DIR / f"{basename or 'ecourts_result'}_{ts}.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return fname

def download_attachment(page, url: str, filename: Path):
    """Download given URL using Playwright's request context."""
    try:
        logging.info(f"Downloading {url} to {filename}...")
        response = page.request.get(url, timeout=60 * 1000)
        if response.ok:
            filename.parent.mkdir(parents=True, exist_ok=True)
            filename.write_bytes(response.body())
            logging.info(f"Successfully saved {filename}")
            return filename
        else:
            logging.error(f"Failed to download ({response.status}) from {url}")
            return None
    except Exception as e:
        logging.error(f"Exception during download of {url}: {e}")
        return None

def find_case_by_cnr(page, cnr: str, date_str: str, should_download: bool):
    """Looks up a single case by its CNR number."""
    results = []
    try:
        logging.info(f"Navigating to eCourts cause list page for CNR: {cnr}")
        page.goto(ECOURTS_CAUSELIST_URL, timeout=60 * 1000)
        
        cnr_input = page.wait_for_selector(CNR_INPUT, timeout=15 * 1000)
        cnr_input.fill(cnr)
        
        submit_btn = page.query_selector(SUBMIT_BUTTON)
        if submit_btn:
            submit_btn.click()
            
        page.wait_for_load_state("networkidle", timeout=30 * 1000)

        rows = page.query_selector_all(RESULTS_ROW)
        logging.info(f"Found {len(rows)} potential result rows.")
        
        for r in rows:
            txt = r.inner_text().strip()
            if not txt or cnr not in txt:
                continue

            cells = r.query_selector_all("td")
            serial = cells[0].inner_text().strip() if len(cells) > 0 else "N/A"
            court = cells[1].inner_text().strip() if len(cells) > 1 else "N/A"
            
            pdf_link = None
            pdf_anchor = r.query_selector("a[href$='.pdf']")
            if pdf_anchor:
                pdf_link = pdf_anchor.get_attribute("href")

            result_item = {"row_text": txt, "serial": serial, "court": court, "pdf_link": pdf_link}
            
            if should_download and pdf_link:
                filename = PDF_DIR / f"{cnr}_{int(time.time())}.pdf"
                saved_path = download_attachment(page, pdf_link, filename)
                if saved_path:
                    result_item["downloaded_pdf"] = str(saved_path)
            
            results.append(result_item)
            
    except PlaywrightTimeoutError:
        logging.error("Timeout waiting for page elements. The website might be slow or selectors need updating.")
    except Exception as e:
        logging.error(f"An error occurred during case lookup: {e}", exc_info=True)
        
    return results

def download_causelist_for_complex(page, state: str, district: str, complex_name: str, date_str: str, download_pdfs: bool):
    """Downloads the entire cause list for a given court complex."""
    out = {"state": state, "district": district, "complex": complex_name, "date": date_str, "judges": []}
    try:
        logging.info(f"Fetching cause list for {complex_name}, {district}, {state} on {date_str}")
        page.goto(ECOURTS_CAUSELIST_URL, timeout=60 * 1000)
        
        # Select State
        page.wait_for_selector(STATE_SELECT).select_option(label=state)
        # IMPORTANT: Wait for the network request that populates districts to finish
        page.wait_for_load_state("networkidle", timeout=15 * 1000)
        
        # Select District
        if district:
            page.wait_for_selector(DISTRICT_SELECT).select_option(label=district)
            page.wait_for_load_state("networkidle", timeout=15 * 1000)

        # Select Court Complex
        if complex_name:
            page.wait_for_selector(COMPLEX_SELECT).select_option(label=complex_name)

        # Set Date
        page.locator(DATE_INPUT).fill(date_str)

        # Submit
        page.locator(SUBMIT_BUTTON).click()
        page.wait_for_load_state("networkidle", timeout=45 * 1000)
        
        # Scrape results
        judge_links = page.query_selector_all("a[href$='.pdf']")
        logging.info(f"Found {len(judge_links)} judge cause list PDFs.")
        
        for idx, link in enumerate(judge_links):
            href = link.get_attribute("href")
            # Try to get meaningful text, like the judge's name
            judge_text = link.inner_text().strip() or f"Judge_{idx+1}"
            
            judge_entry = {"judge_text": judge_text, "pdf_link": href}
            
            if download_pdfs and href:
                # Sanitize judge_text for use in a filename
                safe_name = "".join(c for c in judge_text if c.isalnum() or c in (' ', '.')).rstrip()
                filename = PDF_DIR / f"{date_str}_{complex_name}_{safe_name}.pdf"
                saved_path = download_attachment(page, href, filename)
                if saved_path:
                    judge_entry["downloaded_pdf"] = str(saved_path)
            out["judges"].append(judge_entry)

    except PlaywrightTimeoutError:
        logging.error(f"Timeout waiting for elements. The website might be slow or the selectors are outdated.")
    except Exception as e:
        logging.error(f"An error occurred downloading the cause list: {e}", exc_info=True)
        
    return out

def main():
    args = parse_args()
    date_str = get_date_to_check(args)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        
        metadata = {"invoked_at": datetime.now().isoformat(), "date_checked": date_str, "args": vars(args)}
        result_data = {}

        if args.cnr:
            logging.info(f"[*] Looking up case by CNR: {args.cnr}")
            cases = find_case_by_cnr(page, cnr=args.cnr, date_str=date_str, should_download=args.download_pdf)
            result_data["cases_found"] = cases
            print(json.dumps(cases, indent=2))
        
        elif args.causelist:
            if not args.state or not args.district or not args.complex:
                logging.error("[!] --causelist requires --state, --district, and --complex")
            else:
                logging.info(f"[*] Downloading cause list for {args.complex}")
                cl = download_causelist_for_complex(page,
                    state=args.state,
                    district=args.district,
                    complex_name=args.complex,
                    date_str=date_str,
                    download_pdfs=args.download_pdf)
                result_data["cause_list"] = cl
                print(json.dumps(cl, indent=2))
        
        else:
            print("[*] No specific action requested. Use --help for usage.")

        if result_data:
            metadata["result"] = result_data
            outpath = save_json(metadata, basename=args.output)
            logging.info(f"[*] Saved output to {outpath}")

        context.close()
        browser.close()

if __name__ == "__main__":
    main()