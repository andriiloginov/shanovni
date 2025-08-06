import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from django.utils.text import slugify
from django.core.files.base import ContentFile
import logging
import time
import ssl
import os
from urllib3.util.ssl_ import create_urllib3_context
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import urllib3
import certifi
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

# Відключення попереджень про SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Встановлення змінних середовища для SSL
os.environ['SSL_CERT_FILE'] = certifi.where()

logging.basicConfig(filename='parser_errors.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')


class SSLAdapter(HTTPAdapter):
    """Custom HTTPAdapter that disables SSL verification"""
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)


# Опціонально: вкажіть проксі, якщо потрібно
PROXIES = {
    # 'http': 'http://your_proxy:port',
    # 'https': 'https://your_proxy:port',
}

def generate_unique_slug(name, existing_slugs=None):
    """Generate a unique slug for the given name"""
    base_slug = slugify(name)
    if not base_slug:
        return None
        
    # If no existing slugs provided, we'll let Django handle it later
    if existing_slugs is None:
        return base_slug
    
    # Check if base slug is unique
    if base_slug not in existing_slugs:
        return base_slug
    
    # If not unique, append numbers until we find a unique one
    counter = 1
    while f"{base_slug}-{counter}" in existing_slugs:
        counter += 1
    
    return f"{base_slug}-{counter}"

def fetch_page_with_selenium(url):
    options = Options()
    # options.headless = True  # Run in non-headless mode for manual CAPTCHA solving
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

    print("[INFO] Opening browser for page fetch. If you see a CAPTCHA or Cloudflare page, solve it in the browser.")
    driver = None
    html = ''
    try:
        driver = uc.Chrome(options=options)
        driver.get(url)
        input("[ACTION REQUIRED] Solve any CAPTCHA/Cloudflare in the browser, then press Enter here to continue...")
        try:
            # Wait for a div with class 'field-content' (guaranteed to appear for name)
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.field-content"))
            )
            html = driver.page_source or ''
        except Exception as e:
            print("[ERROR] Browser window was closed or content not loaded before page could be fetched. Please keep the window open until prompted and wait for the profile to load.")
            logging.error(f"Browser window closed or content not loaded: {e}")
            html = ''
    finally:
        if driver:
            driver.quit()
    return html

