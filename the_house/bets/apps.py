from django.apps import AppConfig

class BetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bets'

    # Only import things here if absolutely needed, and do it inside ready().
    # def ready(self):
    #     import bets.signals  # example
