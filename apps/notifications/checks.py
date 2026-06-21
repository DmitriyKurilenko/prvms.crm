from django.conf import settings
from django.core.checks import Warning, register


@register('settings')
def email_backend_configuration_check(app_configs, **kwargs):
    """Warn when the console backend is active despite a real SMTP host configured."""
    errors = []
    is_console = settings.EMAIL_BACKEND.endswith('console.EmailBackend')
    has_real_smtp_host = settings.EMAIL_HOST and settings.EMAIL_HOST not in ('localhost', '127.0.0.1')
    if is_console and has_real_smtp_host:
        errors.append(
            Warning(
                'EMAIL_BACKEND is console, but EMAIL_HOST points to a real SMTP server. '
                'Outgoing mail will be printed to logs instead of being delivered.',
                hint='Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend '
                     'or unset SMTP_HOST to suppress this warning.',
                id='notifications.W001',
            )
        )
    return errors
