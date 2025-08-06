from django.shortcuts import render
from .models import Official
# Create your views here.
def off_list(request):
	officials = Official.objects.all()
	return render(request,'officials/off_list.html', { 'officials': officials})

def off_page(request, slug):
	official = Official.objects.get(slug=slug)
	return render(request,'officials/off_page.html', { 'official': official})
