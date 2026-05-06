"""
App configuration for core app.
"""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Attendance Bridge Core'
    
    def ready(self):
        """
        Import signals when the app is ready.
        """
        import core.signals  # noqa

         # Load template tags
        try:
            from django.template.defaultfilters import register
            import core.templatetags.timezone_filters  # noqa
        except ImportError:
            pass
