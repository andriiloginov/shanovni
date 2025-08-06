from django.db import models

class Official(models.Model):
    institution_name = models.CharField(max_length=255, default="КМДА")  # Назва установи, наприклад, "КМДА"
    id = models.AutoField(primary_key=True)  # Унікальний ідентифікатор представника
    name = models.CharField(max_length=255)  # Повне ім’я представника
    email = models.EmailField(unique=True, blank=True, null=True)  # Електронна пошта для контактів
    birth_date = models.DateField(blank=True, null=True)  # Дата народження
    bio = models.TextField(blank=True, null=True)  # Біографія представника
    party = models.CharField(max_length=255, blank=True, null=True)  # Політична партія
    role = models.CharField(max_length=255)  # Посада чи роль, наприклад, "Мер"
    department = models.CharField(max_length=255, blank=True, null=True)  # Департамент або комітет
    term_start = models.DateField(blank=True, null=True)  # Дата початку повноважень
    term_end = models.DateField(blank=True, null=True)  # Дата завершення повноважень
    status = models.CharField(max_length=50, choices=[
        ('active', 'Діючий'),
        ('former', 'Колишній'),
        ('temporary', 'Тимчасовий'),
    ], default='active')  # Статус представника
    contact_phone = models.CharField(max_length=20, blank=True, null=True)  # Контактний номер телефону
    social_media = models.JSONField(blank=True, null=True)  # Посилання на соціальні мережі (JSON)
    photo = models.ImageField(upload_to='officials/photos/', blank=True, null=True)  # Фото представника
    affiliation = models.CharField(max_length=255, blank=True, null=True)  # Політична чи інша приналежність
    is_verified = models.BooleanField(default=False)  # Позначка перевірки профілю
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=['name']),  # Індекс для швидкого пошуку за ім’ям
            models.Index(fields=['institution_name']),  # Індекс для фільтрації за назвою установи
        ]