import os
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

load_dotenv()

LICENCE_NUMBER    = os.getenv("DVSA_LICENCE_NUMBER")
BOOKING_REFERENCE = os.getenv("DVSA_BOOKING_REFERENCE")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID")
CHECK_INTERVAL    = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("dvsa_checker.log"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
        if r.status_code == 200:
            log.info("✅ Telegram message sent.")
        else:
            log.error(f"Telegram error: {r.status_code} {r.text}")
    except Exception as e:
        log.error(f"Failed to send Telegram message: {e}")

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def check_slots():
    log.info("🔍 Checking DVSA for available slots...")
    driver = create_driver()
    slots_found = []
    try:
        driver.get("https://driverpracticaltest.dvsa.gov.uk/login")
        wait = WebDriverWait(driver, 20)

        licence_field = wait.until(EC.presence_of_element_located((By.ID, "driving-licence-number")))
        licence_field.clear()
        licence_field.send_keys(LICENCE_NUMBER)

        ref_field = driver.find_element(By.ID, "application-reference-number")
        ref_field.clear()
        ref_field.send_keys(BOOKING_REFERENCE)

        driver.find_element(By.ID, "booking-login").click()

        try:
            earlier_btn = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "earlier")))
            earlier_btn.click()
        except TimeoutException:
            try:
                wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Change"))).click()
            except TimeoutException:
                log.warning("Could not find earlier/reschedule button.")
                driver.save_screenshot("debug_screenshot.png")
                return []

        time.sleep(3)
        slot_elements = driver.find_elements(By.CSS_SELECTOR, ".SlotPicker-slot--available, .test-slot, [data-date]")
        for el in slot_elements:
            slot_text = el.text.strip() or el.get_attribute("data-date") or el.get_attribute("aria-label")
            if slot_text:
                slots_found.append(slot_text)

    except Exception as e:
        log.error(f"Error during slot check: {e}")
        try:
            driver.save_screenshot("debug_screenshot.png")
            log.info("Screenshot saved as debug_screenshot.png")
        except:
            pass
    finally:
        driver.quit()
    return slots_found

def test_telegram():
    log.info("Testing Telegram...")
    send_telegram("🤖 <b>Test message!</b>\nIf you see this, Telegram is working perfectly ✅")

def main():
    log.info("🚗 DVSA Slot Checker started!")
    send_telegram("🚗 <b>DVSA Slot Checker started!</b>\nI'll notify you when new slots appear.")
    last_slots = set()
    while True:
        try:
            slots = check_slots()
            if slots:
                new_slots = set(slots) - last_slots
                if new_slots:
                    log.info(f"🎉 NEW SLOTS FOUND: {new_slots}")
                    msg = "🎉 <b>New DVSA test slots available!</b>\n\n" + "\n".join(f"📅 {s}" for s in sorted(new_slots)) + "\n\n👉 Book now: https://driverpracticaltest.dvsa.gov.uk/login"
                    send_telegram(msg)
                    last_slots = set(slots)
                else:
                    log.info(f"No new slots. {len(slots)} previously known.")
            else:
                log.info("No slots found this check.")
                last_slots = set()
        except Exception as e:
            log.error(f"Unexpected error: {e}")
        log.info(f"⏳ Sleeping {CHECK_INTERVAL}s until next check...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
