from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.permissions import require_permission, succursales_autorisees

from .forms import (
    BonApprovisionnementForm,
    BonSortieForm,
    BonValidationForm,
    InventaireForm,
    LigneApprovisionnementFormSet,
    LigneInventaireFormSet,
    LigneSortieFormSet,
    LigneValidationFormSet,
)
from .models import (
    Approvisionnement,
    Article,
    BonApprovisionnement,
    BonSortie,
    Inventaire,
    LigneApprovisionnement,
    Service,
)


def _perimetre(user):
    """Périmètre d'accès de l'utilisateur au module Approvisionnement.

    Approvisionnement est un MODULE transversal : son accès est contrôlé par
    permission. Le périmètre des données est l'intersection de :
    - succursales auxquelles l'utilisateur est affecté ;
    - domaines d'activité (BOUTIQUE, RESTAURANT…) auxquels il est affecté.
    Un bon/article n'est visible que si (succursale, domaine) ∈ périmètre.
    """
    succursales = succursales_autorisees(user)
    domaines = user.domaines_autorisees()
    return {
        'succursales': succursales,
        'succursales_ids': list(succursales.values_list('id', flat=True)),
        'domaines': domaines,
        'domaines_ids': list(domaines.values_list('id', flat=True)),
    }


@require_permission('approvisionnement.view_approvisionnement')
def tableau_de_bord(request):
    peri = _perimetre(request.user)
    articles = Article.objects.select_related('categorie', 'unite').filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id__in=peri['domaines_ids'],
    )
    alertes = articles.filter(stock__lte=F('seuil_minimum') + 10)
    derniers = Approvisionnement.objects.select_related(
        'utilisateur', 'fournisseur'
    ).filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            )[:8]
    return render(
        request,
        'approvisionnement/tableau_de_bord.html',
        {
            'alertes': alertes,
            'articles': articles,
            'derniers_mouvements': derniers,
            'nb_alertes': alertes.count(),
            'nb_articles': articles.count(),
            'nb_mouvements': Approvisionnement.objects.filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            ).count(),
        },
    )


@require_permission('approvisionnement.view_approvisionnement')
def entree_liste(request):
    peri = _perimetre(request.user)
    bons = (
        BonApprovisionnement.objects.select_related('fournisseur', 'utilisateur')
        .filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            )
        .annotate(nb_lignes=Count('lignes'))
    )
    return render(
        request,
        'approvisionnement/entree_liste.html',
        {'bons': bons},
    )


@require_permission('approvisionnement.create_approvisionnement')
def entree_nouveau(request):
    peri = _perimetre(request.user)
    contexte = request.user.contexte_actif()
    # Succursale/domaine utilisés pour filtrer les articles des lignes.
    succursale_id = (
        contexte['succursale'].pk
        if contexte and contexte['verrouille'] and contexte['succursale']
        else None
    )
    domaine_id = (
        contexte['domaine'].pk
        if contexte and contexte['verrouille'] and contexte['domaine']
        else None
    )
    if request.method == 'POST':
        succursale_id = request.POST.get('succursale') or succursale_id
        domaine_id = request.POST.get('domaine') or domaine_id

    formulaire = BonApprovisionnementForm(
        request.POST if request.method == 'POST' else None,
        succursales=peri['succursales'],
        domaines=peri['domaines'],
        contexte=contexte,
        initial={'date_approvisionnement': timezone.localtime().strftime('%Y-%m-%dT%H:%M')},
    )
    # Articles + quantités directement dans le formulaire de création.
    formset = LigneApprovisionnementFormSet(
        request.POST if request.method == 'POST' else None,
        queryset=LigneApprovisionnement.objects.none(),
        succursale=succursale_id,
        domaine=domaine_id,
    )
    if request.method == 'POST' and formulaire.is_valid() and formset.is_valid():
        if not Article.objects.filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            ).exists():
            messages.error(
                request,
                'Créez d’abord des articles dans l’administration (tables de paramètre).',
            )
        else:
            with transaction.atomic():
                bon = formulaire.save(commit=False)
                # Succursale/domaine imposés depuis le périmètre (champs verrouillés).
                if contexte and contexte['verrouille']:
                    bon.succursale = contexte['succursale']
                    bon.domaine = contexte['domaine']
                bon.utilisateur = request.user
                bon.numero = BonApprovisionnement.prochain_numero()
                bon.save()
                formset.instance = bon
                formset.save()
            messages.success(
                request, f'Bon {bon.numero} créé avec ses produits. En attente de validation.'
            )
            return redirect('approvisionnement:entree_detail', pk=bon.pk)
    return render(
        request,
        'approvisionnement/entree_form.html',
        {'form': formulaire, 'formset': formset},
    )


@require_permission('approvisionnement.view_approvisionnement')
def entree_detail(request, pk):
    peri = _perimetre(request.user)
    bon = get_object_or_404(
        BonApprovisionnement.objects.select_related('fournisseur', 'utilisateur')
        .filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            ),
        pk=pk,
    )
    lignes = bon.lignes.select_related('article', 'article__unite', 'mouvement')
    formset = None
    if bon.statut != BonApprovisionnement.Statut.VALIDE:
        articles_exclus = list(lignes.values_list('article_id', flat=True))
        formset = LigneApprovisionnementFormSet(
            request.POST if request.method == 'POST' else None,
            instance=bon,
            queryset=LigneApprovisionnement.objects.none(),
            articles_exclus=articles_exclus,
            succursale=bon.succursale_id,
            domaine=bon.domaine_id,
        )
        if request.method == 'POST' and formset.is_valid():
            nouvelles = formset.save()
            if nouvelles:
                messages.success(
                    request,
                    f'{len(nouvelles)} produit(s) enregistré(s). '
                    'En attente de validation par le responsable.',
                )
            else:
                messages.info(request, 'Aucun nouveau produit n’a été ajouté.')
            return redirect('approvisionnement:entree_detail', pk=bon.pk)
    return render(
        request,
        'approvisionnement/entree_detail.html',
        {
            'bon': bon,
            'formset': formset,
            'lignes': lignes,
        },
    )


@require_permission('approvisionnement.validate_approvisionnement')
def entree_validation_liste(request):
    peri = _perimetre(request.user)
    bons = (
        BonApprovisionnement.objects.filter(statut=BonApprovisionnement.Statut.BROUILLON)
        .filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            )
        .annotate(nb_lignes=Count('lignes'))
        .filter(nb_lignes__gt=0)
        .select_related('fournisseur', 'utilisateur')
        .prefetch_related('lignes__article', 'lignes__article__unite')
    )
    return render(
        request,
        'approvisionnement/entree_validation_liste.html',
        {'bons': bons},
    )


@require_permission('approvisionnement.validate_approvisionnement')
def entree_validation_detail(request, pk):
    peri = _perimetre(request.user)
    bon = get_object_or_404(
        BonApprovisionnement.objects.select_related('fournisseur', 'utilisateur')
        .filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            ),
        pk=pk,
    )
    bon_form = None
    formset = None
    if bon.statut != BonApprovisionnement.Statut.VALIDE:
        # Le fournisseur (et la référence) restent modifiables à la validation.
        bon_form = BonValidationForm(
            request.POST if request.method == 'POST' else None,
            instance=bon,
        )
        # Chaque quantité de ligne reste modifiable / supprimable.
        formset = LigneValidationFormSet(
            request.POST if request.method == 'POST' else None,
            instance=bon,
        )
        if request.method == 'POST' and bon_form.is_valid() and formset.is_valid():
            bon_form.save()
            formset.save()
            if request.POST.get('action') == 'valider':
                try:
                    bon.valider()
                except ValidationError as exc:
                    messages.error(
                        request, ' '.join(getattr(exc, 'messages', [str(exc)]))
                    )
                    return redirect('approvisionnement:entree_validation_detail', pk=bon.pk)
                messages.success(
                    request, f'Bon {bon.numero} validé. Le stock a été mis à jour.'
                )
                return redirect(
                    reverse('approvisionnement:entree_imprimer', kwargs={'pk': bon.pk})
                    + '?auto=1'
                )
            messages.success(request, 'Fournisseur, quantités et lignes mises à jour.')
            return redirect('approvisionnement:entree_validation_detail', pk=bon.pk)
    return render(
        request,
        'approvisionnement/entree_validation_detail.html',
        {
            'bon': bon,
            'bon_form': bon_form,
            'formset': formset,
            'lignes': bon.lignes.select_related('article', 'article__unite', 'mouvement'),
        },
    )


@require_permission('approvisionnement.validate_approvisionnement')
@require_POST
def entree_valider(request, pk):
    peri = _perimetre(request.user)
    bon = get_object_or_404(
        BonApprovisionnement.objects.filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            ),
        pk=pk,
    )
    try:
        bon.valider()
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
        return redirect('approvisionnement:entree_validation_detail', pk=bon.pk)
    messages.success(request, f'Bon {bon.numero} validé. Le stock a été mis à jour.')
    return redirect(reverse('approvisionnement:entree_imprimer', kwargs={'pk': bon.pk}) + '?auto=1')


@require_permission('approvisionnement.view_approvisionnement')
def entree_imprimer(request, pk):
    peri = _perimetre(request.user)
    bon = get_object_or_404(
        BonApprovisionnement.objects.select_related('fournisseur', 'utilisateur')
        .filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            ),
        pk=pk,
    )
    return render(
        request,
        'approvisionnement/entree_impression.html',
        {
            'bon': bon,
            'lignes': bon.lignes.select_related('article', 'article__unite', 'article__categorie'),
        },
    )


@require_permission('approvisionnement.view_sortie')
def sortie_liste(request):
    peri = _perimetre(request.user)
    bons = BonSortie.objects.select_related('utilisateur', 'destination').filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id__in=peri['domaines_ids'],
    )
    return render(
        request,
        'approvisionnement/sortie_liste.html',
        {'bons': bons},
    )


@require_permission('approvisionnement.create_sortie')
def sortie_nouveau(request):
    peri = _perimetre(request.user)
    contexte = request.user.contexte_actif()
    formulaire = BonSortieForm(
        request.POST if request.method == 'POST' else None,
        succursales=peri['succursales'],
        domaines=peri['domaines'],
        contexte=contexte,
        initial={'date_sortie': timezone.localtime().strftime('%Y-%m-%dT%H:%M')},
    )
    if request.method == 'POST' and formulaire.is_valid():
        if not Article.objects.filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            ).exists():
            messages.error(
                request,
                'Créez d’abord des articles dans l’administration (tables de paramètre).',
            )
        elif not Service.objects.exists():
            messages.error(
                request,
                'Créez d’abord les services dans l’administration (tables de paramètre).',
            )
        else:
            with transaction.atomic():
                bon = formulaire.save(commit=False)
                # Succursale/domaine imposés depuis le périmètre (champs verrouillés).
                if contexte and contexte['verrouille']:
                    bon.succursale = contexte['succursale']
                    bon.domaine = contexte['domaine']
                bon.utilisateur = request.user
                bon.numero = BonSortie.prochain_numero()
                bon.save()
            messages.success(request, f'Bon {bon.numero} créé. Ajoutez les lignes de produits.')
            return redirect('approvisionnement:sortie_detail', pk=bon.pk)
    return render(
        request,
        'approvisionnement/sortie_form.html',
        {'form': formulaire},
    )


@require_permission('approvisionnement.view_sortie')
def sortie_detail(request, pk):
    peri = _perimetre(request.user)
    bon = get_object_or_404(
        BonSortie.objects.select_related('utilisateur', 'destination')
        .filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            ),
        pk=pk,
    )
    formset = LigneSortieFormSet(
        request.POST if request.method == 'POST' else None,
        instance=bon,
        succursale=bon.succursale_id,
        domaine=bon.domaine_id,
    )
    ruptures = []
    seuils = []
    if bon.statut == BonSortie.Statut.VALIDE:
        formset = None
    elif request.method == 'POST' and formset.is_valid():
        formset.save()
        messages.success(request, 'Lignes de sortie enregistrées.')
        return redirect('approvisionnement:sortie_detail', pk=bon.pk)
    else:
        ruptures, seuils = bon.analyser_stock()
    return render(
        request,
        'approvisionnement/sortie_detail.html',
        {
            'bon': bon,
            'formset': formset,
            'lignes': bon.lignes.select_related('article', 'article__unite', 'mouvement'),
            'ruptures': ruptures,
            'seuils': seuils,
        },
    )


@require_permission('approvisionnement.validate_sortie')
@require_POST
def sortie_valider(request, pk):
    peri = _perimetre(request.user)
    bon = get_object_or_404(
        BonSortie.objects.select_related('utilisateur', 'destination')
        .filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            ),
        pk=pk,
    )
    ruptures, seuils = bon.analyser_stock()
    if ruptures or seuils:
        messages.error(
            request,
            'Impossible de valider : un article est à 0, dépasse le stock disponible, '
            'ou est au seuil d’alerte. Approvisionnez d’abord l’article concerné.',
        )
        formset = LigneSortieFormSet(
            instance=bon, succursale=bon.succursale_id, domaine=bon.domaine_id
        )
        return render(
            request,
            'approvisionnement/sortie_detail.html',
            {
                'bon': bon,
                'formset': formset,
                'lignes': bon.lignes.select_related('article', 'article__unite', 'mouvement'),
                'ruptures': ruptures,
                'seuils': seuils,
            },
        )
    try:
        bon.valider()
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
        return redirect('approvisionnement:sortie_detail', pk=bon.pk)
    messages.success(
        request,
        f'Bon {bon.numero} validé. Le stock a été diminué et l’historique a été enregistré.',
    )
    return redirect(reverse('approvisionnement:sortie_imprimer', kwargs={'pk': bon.pk}) + '?auto=1')


@require_permission('approvisionnement.view_sortie')
def sortie_imprimer(request, pk):
    peri = _perimetre(request.user)
    bon = get_object_or_404(
        BonSortie.objects.select_related('utilisateur', 'destination')
        .filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            ),
        pk=pk,
    )
    return render(
        request,
        'approvisionnement/sortie_impression.html',
        {
            'bon': bon,
            'lignes': bon.lignes.select_related('article', 'article__unite', 'article__categorie'),
        },
    )


@require_permission('approvisionnement.view_historique')
def historique(request):
    peri = _perimetre(request.user)
    journaux = Approvisionnement.objects.select_related(
        'utilisateur', 'fournisseur', 'bon_entree', 'bon_sortie'
    ).filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            ).prefetch_related('lignes__article')
    type_filtre = request.GET.get('type', '')
    recherche = request.GET.get('q', '').strip()
    if type_filtre in Approvisionnement.Type.values:
        journaux = journaux.filter(type_operation=type_filtre)
    if recherche:
        journaux = journaux.filter(
            Q(numero__icontains=recherche)
            | Q(reference__icontains=recherche)
            | Q(motif__icontains=recherche)
            | Q(destination__icontains=recherche)
            | Q(fournisseur__nom__icontains=recherche)
            | Q(lignes__article__code__icontains=recherche)
            | Q(lignes__article__designation__icontains=recherche)
        ).distinct()
    page = Paginator(journaux, 20).get_page(request.GET.get('page'))
    return render(
        request,
        'approvisionnement/historique.html',
        {
            'page': page,
            'type_filtre': type_filtre,
            'recherche': recherche,
            'types': Approvisionnement.Type.choices,
        },
    )


@require_permission('approvisionnement.view_historique')
def historique_detail(request, pk):
    peri = _perimetre(request.user)
    journal = get_object_or_404(
        Approvisionnement.objects.select_related(
            'utilisateur', 'fournisseur', 'bon_entree', 'bon_sortie'
        ).filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            ),
        pk=pk,
    )
    return render(
        request,
        'approvisionnement/historique_detail.html',
        {
            'journal': journal,
            'lignes': journal.lignes.select_related('article', 'article__unite'),
        },
    )


@require_permission('approvisionnement.view_inventaire')
def inventaire_liste(request):
    peri = _perimetre(request.user)
    inventaires = Inventaire.objects.select_related('responsable').filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id__in=peri['domaines_ids'],
    )
    return render(
        request,
        'approvisionnement/inventaire_liste.html',
        {'inventaires': inventaires},
    )


@require_permission('approvisionnement.create_inventaire')
def inventaire_nouveau(request):
    peri = _perimetre(request.user)
    contexte = request.user.contexte_actif()
    succursale_id = (
        contexte['succursale'].pk
        if contexte and contexte['verrouille'] and contexte['succursale']
        else None
    )
    domaine_id = (
        contexte['domaine'].pk
        if contexte and contexte['verrouille'] and contexte['domaine']
        else None
    )
    if request.method == 'POST':
        succursale_id = request.POST.get('succursale') or succursale_id
        domaine_id = request.POST.get('domaine') or domaine_id

    # Articles proposables pour la portée « Un article ».
    articles = Article.objects.select_related('unite')
    if succursale_id:
        articles = articles.filter(succursale_id=succursale_id)
    elif peri['succursales_ids']:
        articles = articles.filter(succursale_id__in=peri['succursales_ids'])
    if domaine_id:
        articles = articles.filter(domaine_id=domaine_id)
    elif peri['domaines_ids']:
        articles = articles.filter(domaine_id__in=peri['domaines_ids'])

    formulaire = InventaireForm(
        request.POST if request.method == 'POST' else None,
        succursales=peri['succursales'],
        domaines=peri['domaines'],
        contexte=contexte,
        articles=articles,
    )
    if request.method == 'POST' and formulaire.is_valid():
        if not articles.exists():
            messages.error(
                request,
                'Aucun article à inventorier dans ce périmètre (tables de paramètre).',
            )
        else:
            inventaire = formulaire.save(commit=False)
            # Succursale/domaine imposés depuis le périmètre (champs verrouillés).
            if contexte and contexte['verrouille']:
                inventaire.succursale = contexte['succursale']
                inventaire.domaine = contexte['domaine']
            inventaire.responsable = request.user
            inventaire.save()
            if formulaire.cleaned_data['portee'] == 'ARTICLE':
                article = formulaire.cleaned_data['article']
                inventaire.lignes.create(
                    article=article,
                    stock_systeme=article.stock,
                    stock_physique=article.stock,
                )
                libelle = f'Inventaire de {article.code}'
            else:
                articles_du_scope = Article.objects.filter(
                    succursale=inventaire.succursale,
                    domaine=inventaire.domaine,
                )
                for article in articles_du_scope:
                    inventaire.lignes.create(
                        article=article,
                        stock_systeme=article.stock,
                        stock_physique=article.stock,
                    )
                libelle = f'Inventaire complet ({articles_du_scope.count()} article(s))'
            messages.success(request, f'{libelle} créé. Saisissez les stocks physiques.')
            return redirect('approvisionnement:inventaire_detail', pk=inventaire.pk)
    return render(
        request,
        'approvisionnement/inventaire_form.html',
        {'form': formulaire},
    )


@require_permission('approvisionnement.view_inventaire')
def inventaire_detail(request, pk):
    peri = _perimetre(request.user)
    inventaire = get_object_or_404(
        Inventaire.objects.select_related('responsable').filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id__in=peri['domaines_ids'],
        ),
        pk=pk,
    )
    formset = LigneInventaireFormSet(
        request.POST if request.method == 'POST' else None,
        instance=inventaire,
    )
    if inventaire.statut == Inventaire.Statut.VALIDE:
        formset = None
    elif request.method == 'POST' and formset.is_valid():
        formset.save()
        messages.success(request, 'Lignes d’inventaire enregistrées.')
        return redirect('approvisionnement:inventaire_detail', pk=inventaire.pk)
    return render(
        request,
        'approvisionnement/inventaire_detail.html',
        {
            'inventaire': inventaire,
            'formset': formset,
            'lignes': inventaire.lignes.select_related('article', 'mouvement'),
        },
    )


@require_permission('approvisionnement.validate_inventaire')
@require_POST
def inventaire_valider(request, pk):
    peri = _perimetre(request.user)
    inventaire = get_object_or_404(
        Inventaire.objects.filter(
                succursale_id__in=peri['succursales_ids'],
                domaine_id__in=peri['domaines_ids'],
            ),
        pk=pk,
    )
    try:
        inventaire.valider()
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if hasattr(exc, 'messages') else str(exc))
        return redirect('approvisionnement:inventaire_detail', pk=inventaire.pk)
    messages.success(request, 'Inventaire validé. Les écarts ont été audités.')
    return redirect('approvisionnement:inventaire_detail', pk=inventaire.pk)
