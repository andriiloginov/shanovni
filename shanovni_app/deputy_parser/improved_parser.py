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

# Import the original fetch_page_with_selenium function
from deputy_parser.parser import fetch_page_with_selenium

def improved_parse_deputy_page(url):
    """
    Improved version of the deputy page parser with better error handling and more flexible data extraction
    """
    try:
        print(f"DEBUG: improved_parse_deputy_page called for {url}")
        html = fetch_page_with_selenium(url)
        if not html:
            print(f"[ERROR] No HTML fetched for {url}. Skipping parse.")
            logging.error(f"No HTML fetched for {url}. Skipping parse.")
            return None
        
        print(f"DEBUG: HTML length for {url}: {len(html)}")
        logging.info(f"DEBUG: HTML fetched for {url}, length={len(html)}")
        
        soup = BeautifulSoup(html, 'html.parser')
        data = {}
        
        # Initialize with default values
        data['institution_name'] = 'КМДА'
        data['status'] = 'active'
        data['is_verified'] = False
        data['role'] = 'Член'  # Default role if not found
        data['social_media'] = {}

        # 1. ПІБ (name) - Multiple approaches to find the name
        # First approach: Look for specific HTML structure
        profile_field_contents = soup.select('div.info-deputat div.field-content')
        print("[DEBUG] All field-content in profile block:")
        for idx, div in enumerate(profile_field_contents):
            print(f"[{idx}] {div.get_text(strip=True)}")
        
        # Try multiple approaches to extract the name
        name_found = False
        
        # Approach 1: Try to find name in profile_field_contents
        if len(profile_field_contents) >= 3 and not name_found:
            name_parts = []
            for i in range(1, min(4, len(profile_field_contents))):
                part = profile_field_contents[i].get_text(strip=True)
                if part and not re.match(r'\d{2}\.\d{2}\.\d{4}', part):  # Skip date formats
                    name_parts.append(part)
            
            full_name = ' '.join(name_parts)
            if full_name:
                data['name'] = full_name
                name_found = True
                print(f"[DEBUG] Name found using approach 1: {full_name}")
        
        # Approach 2: Look for h1 or h2 tags that might contain the name
        if not name_found:
            h_tags = soup.find_all(['h1', 'h2'])
            for tag in h_tags:
                text = tag.get_text(strip=True)
                if text and len(text.split()) >= 2 and len(text.split()) <= 4:  # Names usually have 2-4 words
                    data['name'] = text
                    name_found = True
                    print(f"[DEBUG] Name found using approach 2: {text}")
                    break
        
        # Approach 3: Look for title tags
        if not name_found:
            title = soup.find('title')
            if title:
                title_text = title.get_text(strip=True)
                # Extract name from title (usually in format "Name | Website")
                if ' | ' in title_text:
                    potential_name = title_text.split(' | ')[0].strip()
                    if potential_name and len(potential_name.split()) >= 2:
                        data['name'] = potential_name
                        name_found = True
                        print(f"[DEBUG] Name found using approach 3: {potential_name}")
        
        if not name_found:
            print("[ERROR] Could not find name using any approach")
            logging.error(f"Name not found for {url} using any approach")
            data['name'] = None
        
        # 2. Електронна пошта (email) - Multiple approaches
        email_found = False
        
        # Approach 1: Look for div with text "Електронна пошта:"
        email_elements = soup.find_all(lambda tag: tag.name == 'div' and re.search(r'Електронна пошта:', tag.text))
        if email_elements:
            email = email_elements[0].find_next().text.strip()
            if email and '@' in email:
                data['email'] = email
                email_found = True
                print(f"[DEBUG] Email found using approach 1: {email}")
        
        # Approach 2: Look for any element containing an email pattern
        if not email_found:
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            email_matches = re.findall(email_pattern, html)
            if email_matches:
                data['email'] = email_matches[0]
                email_found = True
                print(f"[DEBUG] Email found using approach 2: {email_matches[0]}")
        
        # 3. Біографія (bio) - Multiple approaches
        bio_found = False
        
        # Approach 1: Look for div with text "Біографія"
        bio_section = soup.find('div', string='Біографія')
        if bio_section:
            bio_text = []
            current_element = bio_section.find_next()
            while current_element and current_element.name != 'div' and 'Рішення/Проекти рішень' not in current_element.text:
                if current_element.text.strip():
                    bio_text.append(current_element.text.strip())
                current_element = current_element.find_next()
            
            if bio_text:
                data['bio'] = ' '.join(bio_text)
                bio_found = True
                print(f"[DEBUG] Bio found using approach 1, length: {len(data['bio'])}")
        
        # Approach 2: Look for any div with class containing "bio"
        if not bio_found:
            bio_divs = soup.find_all('div', class_=lambda c: c and 'bio' in c.lower())
            if bio_divs:
                data['bio'] = bio_divs[0].get_text(strip=True)
                bio_found = True
                print(f"[DEBUG] Bio found using approach 2, length: {len(data['bio'])}")
        
        # Approach 3: If still no bio, use any large text block as a fallback
        if not bio_found:
            # Look for any paragraph with substantial text
            paragraphs = soup.find_all('p')
            long_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 100]
            
            if long_paragraphs:
                data['bio'] = ' '.join(long_paragraphs)
                bio_found = True
                print(f"[DEBUG] Bio found using approach 3, length: {len(data['bio'])}")
            else:
                # Last resort: use any div with substantial text
                content_divs = [div.get_text(strip=True) for div in soup.find_all('div') 
                               if len(div.get_text(strip=True)) > 200]
                if content_divs:
                    data['bio'] = content_divs[0]
                    bio_found = True
                    print(f"[DEBUG] Bio found using approach 4, length: {len(data['bio'])}")
        
        # 4. Дата народження (birth_date) - Multiple approaches
        birth_date_found = False
        
        # Approach 1: Look for div with text "Дата народження:"
        birth_date_elements = soup.find_all(lambda tag: tag.name == 'div' and re.search(r'Дата народження:', tag.text))
        if birth_date_elements:
            date_str = birth_date_elements[0].find_next().text.strip()
            try:
                data['birth_date'] = datetime.strptime(date_str, '%d.%m.%Y').date()
                birth_date_found = True
                print(f"[DEBUG] Birth date found using approach 1: {data['birth_date']}")
            except ValueError:
                pass
        
        # Approach 2: Look for date pattern in profile_field_contents
        if not birth_date_found and profile_field_contents:
            for div in profile_field_contents:
                text = div.get_text(strip=True)
                if re.match(r'\d{2}\.\d{2}\.\d{4}', text):
                    try:
                        data['birth_date'] = datetime.strptime(text, '%d.%m.%Y').date()
                        birth_date_found = True
                        print(f"[DEBUG] Birth date found using approach 2: {data['birth_date']}")
                        break
                    except ValueError:
                        pass
        
        # Approach 3: Look for date pattern in any text
        if not birth_date_found:
            date_patterns = re.findall(r'\d{2}\.\d{2}\.\d{4}', html)
            for date_str in date_patterns:
                try:
                    data['birth_date'] = datetime.strptime(date_str, '%d.%m.%Y').date()
                    birth_date_found = True
                    print(f"[DEBUG] Birth date found using approach 3: {data['birth_date']}")
                    break
                except ValueError:
                    pass
        
        # 5. Фракція (party) - Multiple approaches
        party_found = False
        
        # Approach 1: Look for div with text "Фракція:"
        faction_elements = soup.find_all(lambda tag: tag.name == 'div' and re.search(r'Фракція:', tag.text))
        if faction_elements:
            data['party'] = faction_elements[0].find_next().text.strip()
            party_found = True
            print(f"[DEBUG] Party found using approach 1: {data['party']}")
        
        # Approach 2: Look for party keywords in profile_field_contents
        if not party_found and profile_field_contents:
            for div in profile_field_contents:
                text = div.get_text(strip=True).lower()
                if 'фракція' in text or 'партія' in text:
                    data['party'] = div.get_text(strip=True)
                    party_found = True
                    print(f"[DEBUG] Party found using approach 2: {data['party']}")
                    break
        
        # 6. Посада в комісії (role) - Multiple approaches
        role_found = False
        
        # Approach 1: Look for div with text "Посади:"
        position_elements = soup.find_all(lambda tag: tag.name == 'div' and re.search(r'Посади:', tag.text))
        if position_elements:
            secretary = position_elements[0].find_next('div', string='Секретар')
            if secretary:
                data['role'] = 'Секретар'
                role_found = True
                print(f"[DEBUG] Role found using approach 1: {data['role']}")
            else:
                # Look for other roles
                for role in ['Голова', 'Заступник голови', 'Член']:
                    role_element = position_elements[0].find_next('div', string=role)
                    if role_element:
                        data['role'] = role
                        role_found = True
                        print(f"[DEBUG] Role found using approach 1: {data['role']}")
                        break
        
        # Approach 2: Look for role keywords in profile_field_contents
        if not role_found and profile_field_contents:
            for div in profile_field_contents:
                text = div.get_text(strip=True)
                if text in ['Секретар', 'Голова', 'Заступник голови', 'Член']:
                    data['role'] = text
                    role_found = True
                    print(f"[DEBUG] Role found using approach 2: {data['role']}")
                    break
        
        # 7. Назва комісії (department) - Multiple approaches
        department_found = False
        
        # Approach 1: Look for commission in position_elements
        if position_elements:
            commission = position_elements[0].find_next('div').text.strip()
            if 'Секретар' in commission or 'Голова' in commission or 'Заступник голови' in commission or 'Член' in commission:
                commission = position_elements[0].find_next('div').find_next('div').text.strip()
            
            if commission and 'комісія' in commission.lower():
                data['department'] = commission
                department_found = True
                print(f"[DEBUG] Department found using approach 1: {data['department']}")
        
        # Approach 2: Look for commission keywords in profile_field_contents
        if not department_found and profile_field_contents:
            for div in profile_field_contents:
                text = div.get_text(strip=True)
                if 'комісія' in text.lower():
                    data['department'] = text
                    department_found = True
                    print(f"[DEBUG] Department found using approach 2: {data['department']}")
                    break
        
        # 8. Контактний телефон (contact_phone)
        phone_elements = soup.find_all(lambda tag: tag.name == 'div' and re.search(r'Телефон:', tag.text))
        if phone_elements:
            data['contact_phone'] = phone_elements[0].find_next().text.strip()
            print(f"[DEBUG] Phone found: {data['contact_phone']}")
        
        # 9. Соціальні мережі (social_media)
        website_elements = soup.find_all(lambda tag: tag.name == 'div' and re.search(r'сайт:', tag.text, re.IGNORECASE))
        if website_elements:
            data['social_media'] = {'website': website_elements[0].find_next().text.strip()}
            print(f"[DEBUG] Website found: {data['social_media']}")
        
        # 10. Партійна приналежність (affiliation)
        if data.get('bio') and 'Не є членом політичних партій' in data['bio']:
            data['affiliation'] = 'Без партійної приналежності'
        else:
            data['affiliation'] = data.get('party', '')
        
        # 11. Слаг (slug) - Ensure it's always generated
        if data.get('name'):
            # Try Django's slugify first
            slug = slugify(data['name'])
            
            # If that fails (e.g., with Cyrillic characters), use a custom approach
            if not slug:
                # Simple transliteration mapping for Ukrainian
                cyrillic_to_latin = {
                    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e', 'є': 'ie', 'ж': 'zh',
                    'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
                    'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
                    'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ь': '', 'ю': 'iu', 'я': 'ia',
                    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'H', 'Ґ': 'G', 'Д': 'D', 'Е': 'E', 'Є': 'Ie', 'Ж': 'Zh',
                    'З': 'Z', 'И': 'Y', 'І': 'I', 'Ї': 'I', 'Й': 'I', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N',
                    'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts',
                    'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch', 'Ь': '', 'Ю': 'Iu', 'Я': 'Ia'
                }
                
                transliterated = ''
                for char in data['name'].lower():
                    transliterated += cyrillic_to_latin.get(char, char)
                
                # Replace spaces with hyphens and remove non-alphanumeric characters
                slug = re.sub(r'[^a-z0-9-]', '', transliterated.replace(' ', '-'))
                
                # If still no slug, use a hash
                if not slug:
                    slug = f"official-{hash(data['name']) % 10000}"
            
            data['slug'] = slug
            print(f"[DEBUG] Generated slug: {data['slug']}")
        else:
            # Generate a random slug if no name is available
            data['slug'] = f"official-{int(time.time())}"
            print(f"[DEBUG] Generated random slug: {data['slug']}")
        
        # 12. Фото (photo)
        img = soup.find('img', class_=re.compile(r'photo|image|deputy'))
        if img and img.get('src'):
            img_url = img['src'] if img['src'].startswith('http') else f"https://kmr.gov.ua{img['src']}"
            try:
                img_response = requests.get(img_url, headers={'User-Agent': 'Mozilla/5.0'}, verify=certifi.where())
                if img_response.ok and data.get('slug'):
                    data['photo'] = ContentFile(img_response.content, name=f"{data['slug']}.jpg")
                    print(f"[DEBUG] Photo downloaded from: {img_url}")
            except Exception as img_exc:
                logging.error(f"Image download failed for {img_url}: {img_exc}")
                print(f"[ERROR] Image download failed: {img_exc}")
        
        # Debug logging for missing critical fields
        missing_fields = []
        for field in ['name', 'email', 'bio']:
            if not data.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            logging.error(f"Після парсингу {url} відсутні поля: {', '.join(missing_fields)}")
            print(f"[WARNING] Missing fields after parsing: {', '.join(missing_fields)}")
        else:
            logging.info(f"Successfully parsed {url} ({data.get('name', 'NO NAME')})")
            print(f"[SUCCESS] Successfully parsed {url} ({data.get('name', 'NO NAME')})")
        
        return data
    
    except Exception as e:
        print(f"EXCEPTION in improved_parse_deputy_page for {url}: {e}")
        logging.error(f"Помилка при парсингу {url}: {e}")
        return None