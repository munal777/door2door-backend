from django.apps import AppConfig


class RidersConfig(AppConfig):
    name = 'riders'

    def ready(self):
        import riders.signals
