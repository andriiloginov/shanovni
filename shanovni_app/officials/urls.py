from django.urls import path
from . import views

app_name = 'officials'  # Простір імен для уникнення конфліктів

urlpatterns = [
    path('', views.off_list, name='officials'),  # Список представників
    path('<slug:slug>', views.off_page, name='official'),  # Сторінка окремого представника
]