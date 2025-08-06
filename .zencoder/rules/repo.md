---
description: Repository Information Overview
alwaysApply: true
---

# Shanovni Information

## Summary
Shanovni is a meaningful democratic tool for civic engagement. It's built with Django, TailwindCSS, DaisyUI, and uses SQLite for development (with PostgreSQL mentioned in the stack).

## Structure
- **shanovni_app/**: Main Django application directory
  - **shanovni_backend/**: Core Django project settings and configuration
  - **posts/**: Django app for managing posts functionality
  - **officials/**: Django app for managing officials data
  - **deputy_parser/**: Django app for parsing deputy information
  - **templates/**: HTML templates for the application
  - **static/**: Static files (CSS, images)
- **src/**: Frontend source files (CSS)
- **.github/**: GitHub workflows for CI/CD

## Language & Runtime
**Language**: Python, JavaScript
**Python Version**: 3.13.5
**Django Version**: 5.2.4
**Node.js Version**: 20 (used in GitHub Actions)
**Build System**: npm for frontend, Django for backend
**Package Manager**: pip (Python), npm (JavaScript)

## Dependencies
**Main Python Dependencies**:
- Django 5.2.4
- requests >= 2.31.0
- beautifulsoup4 >= 4.12.3
- cloudscraper >= 1.2.71
- certifi >= 2023.7.22

**Frontend Dependencies**:
- tailwindcss ^4.1.7
- daisyui ^5.0.38
- postcss ^8.5.3
- autoprefixer ^10.4.21

## Build & Installation
```bash
# Python setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend setup
npm install
npm run build:css

# Run Django development server
cd shanovni_app
python manage.py runserver
```

## Testing
**Framework**: Django TestCase
**Test Location**: Each app has a tests.py file
**Run Command**:
```bash
cd shanovni_app
python manage.py test
```

## Deployment
The project uses GitHub Actions for deployment to GitHub Pages. The workflow:
1. Checks out the repository
2. Sets up Node.js v20
3. Cleans npm cache and reinstalls dependencies
4. Builds CSS with `npm run build:css`
5. Uploads and deploys the content from the './public' directory to GitHub Pages