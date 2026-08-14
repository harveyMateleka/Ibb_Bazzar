from django.shortcuts import render

from approvisionnement.models import AlerteStock, Fonctionnalite


def home(request):
    return render(
        request,
        'home.html',
        {
            'alertes': AlerteStock.objects.filter(active=True).select_related('article')[:8],
            'fonctionnalites': Fonctionnalite.objects.select_related('module').prefetch_related('acteurs'),
        },
    )
