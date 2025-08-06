import cloudscraper
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from deputy_parser.improved_parser import improved_parse_deputy_page
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
    help = 'Parse all deputies from the alphabetical index using the improved parser and update Official model'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, help='Limit the number of deputies to parse', default=0)
        parser.add_argument('--delay', type=int, help='Delay between requests in seconds', default=5)

    def handle(self, *args, **options):
        index_url = 'https://kmr.gov.ua/uk/deputies'
        limit = options['limit']
        delay = options['delay']
        
        self.stdout.write(f"[INFO] Starting improved parsing for all deputies from {index_url}")
        if limit > 0:
            self.stdout.write(f"[INFO] Limiting to {limit} deputies")
        self.stdout.write(f"[INFO] Using delay of {delay} seconds between requests")
        
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
            
            if limit > 0:
                deputy_urls = deputy_urls[:limit]
            
            self.stdout.write(f"[INFO] Found {len(deputy_urls)} deputy URLs to process")
            
            success_count = 0
            error_count = 0
            
            for i, url in enumerate(deputy_urls):
                self.stdout.write(f"[INFO] Processing deputy {i+1}/{len(deputy_urls)}: {url}")
                
                try:
                    deputy_data = improved_parse_deputy_page(url)
                    if deputy_data and deputy_data.get('name'):
                        try:
                            # Check if official already exists by name
                            existing_official = Official.objects.filter(name=deputy_data['name']).first()
                            exclude_id = existing_official.id if existing_official else None
                            
                            # Ensure the slug is unique
                            if existing_official and existing_official.slug != deputy_data.get('slug'):
                                # Keep the existing slug if it exists
                                deputy_data['slug'] = existing_official.slug
                            elif Official.objects.filter(slug=deputy_data.get('slug')).exclude(id=exclude_id).exists():
                                # Generate a new unique slug
                                base_slug = deputy_data.get('slug')
                                counter = 1
                                while Official.objects.filter(slug=f"{base_slug}-{counter}").exclude(id=exclude_id).exists():
                                    counter += 1
                                deputy_data['slug'] = f"{base_slug}-{counter}"
                            
                            # Перевірка унікальності email
                            if deputy_data.get('email'):
                                email_query = Official.objects.filter(email=deputy_data['email'])
                                if exclude_id:
                                    email_query = email_query.exclude(id=exclude_id)
                                if email_query.exists():
                                    self.stdout.write(self.style.WARNING(f"Email {deputy_data['email']} already exists, setting to None"))
                                    deputy_data['email'] = None  # Скидаємо email, якщо він зайнятий
                            
                            # Ensure required fields have default values
                            if not deputy_data.get('role'):
                                deputy_data['role'] = 'Член'  # Default role
                            
                            if not deputy_data.get('bio'):
                                deputy_data['bio'] = f"Депутат Київської міської ради. {deputy_data.get('department', '')}"
                                self.stdout.write(self.style.WARNING(f"No bio found, using default: {deputy_data['bio']}"))

                            # Оновлення або створення запису
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
                                self.stdout.write(self.style.SUCCESS(f"Створено новий запис для {deputy_data['name']} з slug: {deputy_data.get('slug')}"))
                            else:
                                self.stdout.write(self.style.SUCCESS(f"Оновлено дані для {deputy_data['name']} з slug: {deputy_data.get('slug')}"))
                            
                            success_count += 1
                            
                        except Exception as e:
                            error_count += 1
                            logging.error(f"Помилка при збереженні даних для {deputy_data.get('name', 'NO NAME')}: {e}")
                            self.stdout.write(self.style.ERROR(f"Помилка при збереженні даних для {deputy_data.get('name', 'NO NAME')}: {e}"))
                    else:
                        error_count += 1
                        self.stdout.write(self.style.ERROR(f"Не вдалося спарсити дані з {url}"))
                
                except Exception as e:
                    error_count += 1
                    logging.error(f"Помилка при обробці URL {url}: {e}")
                    self.stdout.write(self.style.ERROR(f"Помилка при обробці URL {url}: {e}"))
                
                # Add delay between requests
                if i < len(deputy_urls) - 1:  # Don't delay after the last request
                    self.stdout.write(f"[INFO] Waiting {delay} seconds before next request...")
                    time.sleep(delay)
            
            self.stdout.write(self.style.SUCCESS(f"Parsing completed. Success: {success_count}, Errors: {error_count}"))
            
        except Exception as e:
            logging.error(f"Помилка при парсингу сторінки {index_url}: {e}")
            self.stdout.write(self.style.ERROR(f"Помилка при парсингу сторінки {index_url}: {e}"))