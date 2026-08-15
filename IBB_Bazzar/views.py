from django.db.models import F
from django.shortcuts import render

from approvisionnement.models import Article, Fonctionnalite


def home(request):
    return render(
        request,
        'home.html',
        {
            'alertes': Article.objects.filter(
                stock__lte=F('seuil_minimum') + 10
            ).select_related('categorie')[:8],
            'fonctionnalites': Fonctionnalite.objects.select_related('module').prefetch_related('acteurs'),
        },
    )
