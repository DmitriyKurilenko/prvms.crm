from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render


def healthz(request):
    return JsonResponse({'status': 'ok'})


def landing_page(request):
    canonical_url = f"{settings.PLATFORM_PROTOCOL}://{settings.PLATFORM_DOMAIN}"
    return render(request, 'landing.html', {
        'canonical_url': canonical_url,
        'frontend_app_url': settings.FRONTEND_APP_URL,
    })


def frontend_entry(request, path: str = ''):
    target = settings.FRONTEND_APP_URL.rstrip('/')
    if path:
        target = f'{target}/{path.lstrip("/")}'
    qs = request.META.get('QUERY_STRING', '')
    if qs:
        target = f'{target}?{qs}'
    return redirect(target, permanent=False)
