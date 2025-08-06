import cloudscraper
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from deputy_parser.parser import parse_deputy_page
from officials.models import Official
import re
import time
import logging
import requests
import ssl
import os
from urllib3.util.ssl_ import create_urllib3_context
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import urllib3

# Відключення попереджень про SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SSLAdapter(HTTPAdapter):
    """Custom HTTPAdapter that disables SSL verification"""
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)


class Command(BaseCommand):
    help = 'Parse all deputies from the alphabetical index and update Official model'

    def handle(self, *args, **options):
        index_url = 'https://kmr.gov.ua/uk/deputies'
        try:
            # Створення власної сесії з відключенням перевірки SSL сертифікатів
            session = requests.Session()
            session.verify = False  # Відключення перевірки сертифікатів
            
            # Використання кастомного SSL адаптера
            ssl_adapter = SSLAdapter(pool_connections=1, pool_maxsize=1, max_retries=3)
            session.mount('https://', ssl_adapter)
            session.mount('http://', requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=3))
            
            # Використовуємо звичайну сесію замість cloudscraper для уникнення SSL проблем
            scraper = session
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,uk;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            }
            response = scraper.get(index_url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Витягнення всіх посилань на профілі
            deputy_links = soup.find_all('a', href=re.compile(r'/uk/users/'))
            deputy_urls = [f"https://kmr.gov.ua{link['href']}" for link in deputy_links]

            for url in deputy_urls:
                deputy_data = parse_deputy_page(url)
                if deputy_data:
                    try:
                        # Перевірка унікальності email
                        if deputy_data.get('email') and Official.objects.filter(email=deputy_data['email']).exclude(name=deputy_data['name']).exists():
                            deputy_data['email'] = None  # Скидаємо email, якщо він зайнятий

                        obj, created = Official.objects.update_or_create(
                            name=deputy_data['name'],
                            defaults={
                                'institution_name': deputy_data.get('institution_name', 'КМДА'),
                                'email': deputy_data.get('email'),
                                'bio': deputy_data.get('bio'),
                                'birth_date': deputy_data.get('birth_date'),
                                'party': deputy_data.get('party'),
                                'role': deputy_data.get('role'),
                                'department': deputy_data.get('department'),
                                'contact_phone': deputy_data.get('contact_phone'),
                                'social_media': deputy_data.get('social_media', {}),
                                'photo': deputy_data.get('photo'),
                                'affiliation': deputy_data.get('affiliation'),
                                'is_verified': deputy_data.get('is_verified', False),
                                'slug': deputy_data.get('slug'),
                            }
                        )
                        if created:
                            self.stdout.write(self.style.SUCCESS(f"Створено новий запис для {deputy_data['name']}"))
                        else:
                            self.stdout.write(self.style.SUCCESS(f"Оновлено дані для {deputy_data['name']}"))
                    except Exception as e:
                        logging.error(f"Помилка при збереженні даних для {deputy_data['name']}: {e}")
                        self.stdout.write(self.style.ERROR(f"Помилка при збереженні даних для {deputy_data['name']}: {e}"))
                else:
                    self.stdout.write(self.style.ERROR(f"Не вдалося спарсити дані з {url}"))
                time.sleep(5)  # Збільшена затримка
        except Exception as e:
            logging.error(f"Помилка при парсингу сторінки {index_url}: {e}")
            self.stdout.write(self.style.ERROR(f"Помилка при парсингу сторінки {index_url}: {e}"))