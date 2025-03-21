# Django Archive Webapp Development Guide

## Commands
- **Run server**: `python manage.py runserver`
- **Run tests**: `python manage.py test`
- **Run single test**: `python manage.py test core.tests.TestClassName.test_method_name`
- **Lint code**: `flake8`
- **Docker development**: `docker-compose up`
- **Fetch datawrapper**: `python manage.py fetch_datawrapper`

## Code Style Guidelines
- **Imports**: Group by standard lib, third-party, local apps. Sort alphabetically within groups.
- **Documentation**: Docstrings for all classes and methods. Use triple quotes `"""`.
- **Error Handling**: Use `try/except` blocks with specific exceptions. Log errors properly.
- **Naming**: Use lowercase with underscores for functions/variables. CamelCase for classes.
- **Types**: While type hints aren't currently used, consider adding them for new code.
- **Line Length**: Max 100 characters.
- **Internationalization**: Wrap user-facing strings with `_()` for translation.
- **Formatting**: Follow PEP 8 standards.
- **Templates**: Use Django's template inheritance. Keep logic out of templates.