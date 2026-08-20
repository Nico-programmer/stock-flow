from django.apps import AppConfig


class CompaniesConfig(AppConfig):
    name = 'apps.companies'

    def ready(self):
        import companies.signals  # noqa
