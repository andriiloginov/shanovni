from django.core.management.base import BaseCommand
from deputy_parser.improved_parser import improved_parse_deputy_page
from officials.models import Official
from django.utils.text import slugify
import logging
import re

class Command(BaseCommand):
    help = 'Parse deputy data from a given URL using the improved parser and update Official model'

    def add_arguments(self, parser):
        parser.add_argument('url', type=str, help='URL of the deputy page to parse')

    def generate_unique_slug(self, name, exclude_id=None):
        """Generate a unique slug for the given name"""
        base_slug = slugify(name)
        print(f"[DEBUG] Original name: '{name}'")
        print(f"[DEBUG] Generated base_slug: '{base_slug}'")
        
        # Fallback if slugify fails with Cyrillic
        if not base_slug:
            # Try transliteration or use a fallback
            import re
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
            for char in name:
                transliterated += cyrillic_to_latin.get(char, char)
            
            base_slug = slugify(transliterated)
            print(f"[DEBUG] Transliterated: '{transliterated}'")
            print(f"[DEBUG] Final base_slug after transliteration: '{base_slug}'")
            
            # Last resort fallback
            if not base_slug:
                base_slug = f"official-{hash(name) % 10000}"
                print(f"[DEBUG] Using hash fallback: '{base_slug}'")
        
        # Query to check existing slugs
        existing_query = Official.objects.filter(slug__startswith=base_slug)
        if exclude_id:
            existing_query = existing_query.exclude(id=exclude_id)
        
        existing_slugs = set(existing_query.values_list('slug', flat=True))
        
        # Check if base slug is unique
        if base_slug not in existing_slugs:
            return base_slug
        
        # If not unique, append numbers until we find a unique one
        counter = 1
        while f"{base_slug}-{counter}" in existing_slugs:
            counter += 1
        
        return f"{base_slug}-{counter}"

    def handle(self, *args, **options):
        url = options['url']
        self.stdout.write(f"[INFO] Starting improved parsing for {url}")
        
        deputy_data = improved_parse_deputy_page(url)
        
        if deputy_data:
            if not deputy_data.get('name'):
                logging.error(f"Не знайдено ім'я для {url}. Не зберігаю запис.")
                self.stdout.write(self.style.ERROR(f"Не знайдено ім'я для {url}. Не зберігаю запис."))
                return
                
            try:
                # Check if official already exists by name
                existing_official = Official.objects.filter(name=deputy_data['name']).first()
                exclude_id = existing_official.id if existing_official else None
                
                # Generate unique slug if needed
                if not deputy_data.get('slug'):
                    unique_slug = self.generate_unique_slug(deputy_data['name'], exclude_id=exclude_id)
                    deputy_data['slug'] = unique_slug
                else:
                    # Ensure the slug is unique
                    existing_slug = Official.objects.filter(slug=deputy_data['slug']).exclude(id=exclude_id).exists()
                    if existing_slug:
                        unique_slug = self.generate_unique_slug(deputy_data['name'], exclude_id=exclude_id)
                        deputy_data['slug'] = unique_slug
                
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
                    self.stdout.write(self.style.SUCCESS(f"Створено новий запис для {deputy_data.get('name')} з slug: {deputy_data.get('slug')}"))
                else:
                    self.stdout.write(self.style.SUCCESS(f"Оновлено дані для {deputy_data.get('name')} з slug: {deputy_data.get('slug')}"))
                    
            except Exception as e:
                logging.error(f"Помилка при збереженні даних для {deputy_data.get('name', 'NO NAME')}: {e}")
                self.stdout.write(self.style.ERROR(f"Помилка при збереженні даних для {deputy_data.get('name', 'NO NAME')}: {e}"))
        else:
            self.stdout.write(self.style.ERROR(f"Не вдалося спарсити дані з {url}"))