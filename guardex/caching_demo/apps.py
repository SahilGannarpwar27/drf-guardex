from django.apps import AppConfig


class CachingDemoConfig(AppConfig):
    name = 'caching_demo'

    def ready(self):
        from . import signals  # noqa: F401 - import registers the @receiver hooks
