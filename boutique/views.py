"""Module Boutique — vues fonctions (FBV).

Le module est rattaché au domaine d'activité BOUTIQUE : le périmètre d'accès
est restreint aux succursales où l'utilisateur est affecté pour ce domaine.
Le stock est réutilisé depuis `Article` (approvisionnement) ; une vente validée
produit un `MouvementStock` SORTIE (transaction atomique).
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, F, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from approvisionnement.models import Article
from core.models import Domaine
from core.permissions import require_permission, succursales_autorisees

from .forms import VenteForm, VenteLigneFormSet
from .models import Vente
from .services import VenteService


def _perimetre(user):
    """Périmètre du module Boutique : succursales affectées au domaine BOUTIQUE."""
    domaine = Domaine.objects.filter(code='BOUTIQUE').first()
    succursales = succursales_autorisees(user, domaine=domaine)
    return {
        'succursales': succursales,
        'succursales_ids': list(succursales.values_list('id', flat=True)),
        'domaine': domaine,
        'domaine_id': domaine.pk if domaine else None,
    }


def _articles_perimetre(peri):
    return Article.objects.select_related('categorie', 'unite', 'infos_boutique').filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )


@require_permission('boutique.view_boutique')
def tableau_de_bord(request):
    peri = _perimetre(request.user)
    articles = _articles_perimetre(peri)
    alertes = articles.filter(stock__lte=F('seuil_minimum') + 10)
    ventes_qs = Vente.objects.filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    dernieres = ventes_qs.select_related('utilisateur', 'succursale')[:8]
    stock_total = articles.aggregate(total=Sum('stock'))['total'] or 0
    ventes_jour = ventes_qs.filter(date_vente__date=timezone.localdate()).count()
    return render(
        request,
        'boutique/tableau_de_bord.html',
        {
            'alertes': alertes,
            'articles': articles,
            'dernieres_ventes': dernieres,
            'nb_alertes': alertes.count(),
            'nb_articles': articles.count(),
            'stock_total': stock_total,
            'nb_ventes': ventes_qs.count(),
            'ventes_jour': ventes_jour,
        },
    )


@require_permission('boutique.view_stock')
def articles(request):
    peri = _perimetre(request.user)
    articles_qs = _articles_perimetre(peri)
    return render(
        request,
        'boutique/articles.html',
        {'articles': articles_qs},
    )


@require_permission('boutique.view_vente')
def ventes(request):
    peri = _perimetre(request.user)
    ventes_qs = (
        Vente.objects.select_related('utilisateur', 'succursale')
        .filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        )
        .annotate(nb_lignes=Count('lignes'))
    )
    return render(
        request,
        'boutique/ventes.html',
        {'ventes': ventes_qs},
    )


@require_permission('boutique.create_vente')
def vente_nouvelle(request):
    peri = _perimetre(request.user)
    domaine = Domaine.objects.filter(pk=peri['domaine_id']) if peri['domaine_id'] else Domaine.objects.none()
    contexte = request.user.contexte_actif()
    formulaire = VenteForm(
        request.POST if request.method == 'POST' else None,
        succursales=peri['succursales'],
        domaines=domaine,
        contexte=contexte,
        request_user=request.user,
    )
    if request.method == 'POST' and formulaire.is_valid():
        remise = formulaire.cleaned_data['remise'] or 0
        if remise > 0 and not request.user.has_perm('boutique.apply_remise'):
            messages.error(request, 'Vous n’êtes pas autorisé à appliquer une remise.')
        else:
            succursale = formulaire.cleaned_data.get('succursale')
            domaine_v = formulaire.cleaned_data.get('domaine')
            # Succursale/domaine imposés depuis le périmètre (champs verrouillés).
            if contexte and contexte['verrouille']:
                succursale = contexte['succursale']
                domaine_v = contexte['domaine']
            vente = VenteService.creer(
                succursale=succursale,
                domaine=domaine_v,
                utilisateur=request.user,
                type_paiement=formulaire.cleaned_data['type_paiement'],
                montant_recu=formulaire.cleaned_data['montant_recu'],
                remise=remise,
            )
            messages.success(request, f'Vente {vente.numero} créée. Ajoutez les articles.')
            return redirect('boutique:vente_detail', pk=vente.pk)
    return render(
        request,
        'boutique/vente_form.html',
        {'form': formulaire},
    )


@require_permission('boutique.view_vente')
def vente_detail(request, pk):
    peri = _perimetre(request.user)
    vente = get_object_or_404(
        Vente.objects.select_related('utilisateur', 'succursale').filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    lignes = vente.lignes.select_related(
        'article', 'article__infos_boutique', 'mouvement'
    )
    formset = None
    if vente.statut == Vente.Statut.BROUILLON:
        formset = VenteLigneFormSet(
            request.POST if request.method == 'POST' else None,
            instance=vente,
            succursale=vente.succursale_id,
            domaine=vente.domaine_id,
        )
        if request.method == 'POST' and formset.is_valid():
            formset.save()
            vente.recalculer()
            messages.success(request, 'Articles enregistrés.')
            return redirect('boutique:vente_detail', pk=vente.pk)
    return render(
        request,
        'boutique/vente_detail.html',
        {'vente': vente, 'formset': formset, 'lignes': lignes},
    )


@require_permission('boutique.validate_vente')
@require_POST
def vente_valider(request, pk):
    peri = _perimetre(request.user)
    vente = get_object_or_404(
        Vente.objects.filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    ruptures = vente.analyser_stock()
    if ruptures:
        messages.error(
            request,
            'Stock insuffisant pour un ou plusieurs articles : '
            + ', '.join(f'{r["article"].code} (dispo {r["stock"]})' for r in ruptures),
        )
        return redirect('boutique:vente_detail', pk=vente.pk)
    try:
        VenteService.valider(vente, par=request.user)
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
        return redirect('boutique:vente_detail', pk=vente.pk)
    messages.success(
        request, f'Vente {vente.numero} validée. Le stock a été diminué.'
    )
    return redirect(reverse('boutique:vente_imprimer', kwargs={'pk': vente.pk}) + '?auto=1')


@require_permission('boutique.cancel_vente')
@require_POST
def vente_annuler(request, pk):
    peri = _perimetre(request.user)
    vente = get_object_or_404(
        Vente.objects.filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    try:
        VenteService.annuler(vente, par=request.user)
        messages.success(request, f'Vente {vente.numero} annulée.')
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if hasattr(exc, 'messages') else str(exc))
    return redirect('boutique:vente_detail', pk=vente.pk)


@require_permission('boutique.view_vente')
def vente_imprimer(request, pk):
    peri = _perimetre(request.user)
    vente = get_object_or_404(
        Vente.objects.select_related('utilisateur', 'succursale').filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    return render(
        request,
        'boutique/vente_impression.html',
        {
            'vente': vente,
            'lignes': vente.lignes.select_related('article', 'article__infos_boutique'),
        },
    )
