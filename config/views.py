from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect


def healthz(request):
    return JsonResponse({'status': 'ok'})


def root(request):
    return redirect(settings.FRONTEND_APP_URL, permanent=False)


def frontend_entry(request, path: str = ''):
    target = settings.FRONTEND_APP_URL.rstrip('/')
    if path:
        target = f'{target}/{path.lstrip("/")}'
    qs = request.META.get('QUERY_STRING', '')
    if qs:
        target = f'{target}?{qs}'
    return redirect(target, permanent=False)
