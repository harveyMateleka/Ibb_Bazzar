from django.db.models import F
from django.shortcuts import render

from approvisionnement.models import Fonctionnalite, Produit
from core.permissions import MESSAGE_ACCES_REFUSE


def home(request):
    return render(
        request,
        'home.html',
        {
            'alertes': Produit.objects.filter(
                stock__lte=F('seuil_minimum') + 10
            ).select_related('categorie')[:8],
            'fonctionnalites': Fonctionnalite.objects.select_related('module').prefetch_related('acteurs'),
        },
    )


def erreur_acces(request, exception=None):
    message = str(exception).strip() if exception else ''
    if not message or message in {'403', 'Forbidden', '403 Forbidden'}:
        message = MESSAGE_ACCES_REFUSE
    return render(
        request,
        '403.html',
        {'message': message},
        status=403,
    )


def page_introuvable(request, exception=None):
    return render(
        request,
        '404.html',
        {
            'message': (
                'Cette page n’existe pas ou n’est plus disponible. '
                'Prière de contacter votre administrateur si le problème continue.'
            ),
        },
        status=404,
    )
