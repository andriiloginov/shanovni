# from django.http import HttpResponse
from django.shortcuts import render

def homepage(request):
	# return HttpResponse("Hello World!")
    return render(request,'home.html')

def about(request):
	# return HttpResponse("About Page!")
    return render(request,'about.html')