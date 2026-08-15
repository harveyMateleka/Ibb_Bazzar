from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AutorisationDepassementForm,
    BonApprovisionnementForm,
    BonSortieForm,
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


@login_required
def tableau_de_bord(request):
    articles = Article.objects.select_related('categorie', 'unite')
    alertes = articles.filter(stock__lte=F('seuil_minimum') + 10)
    derniers = Approvisionnement.objects.select_related('utilisateur', 'fournisseur')[:8]
    return render(
        request,
        'approvisionnement/tableau_de_bord.html',
        {
            'alertes': alertes,
            'articles': articles,
            'derniers_mouvements': derniers,
            'nb_alertes': alertes.count(),
            'nb_articles': articles.count(),
            'nb_mouvements': Approvisionnement.objects.count(),
        },
    )


@login_required
def entree_liste(request):
    bons = BonApprovisionnement.objects.select_related(
        'fournisseur', 'utilisateur'
    ).annotate(nb_lignes=Count('lignes'))
    return render(
        request,
        'approvisionnement/entree_liste.html',
        {'bons': bons},
    )


@login_required
def entree_nouveau(request):
    formulaire = BonApprovisionnementForm(
        request.POST if request.method == 'POST' else None,
        initial={'date_approvisionnement': timezone.localtime().strftime('%Y-%m-%dT%H:%M')},
    )
    if request.method == 'POST' and formulaire.is_valid():
        if not Article.objects.exists():
            messages.error(
                request,
                'Créez d’abord des articles dans l’administration (tables de paramètre).',
            )
        else:
            with transaction.atomic():
                bon = formulaire.save(commit=False)
                bon.utilisateur = request.user
                bon.numero = BonApprovisionnement.prochain_numero()
                bon.save()
            messages.success(request, f'Bon {bon.numero} créé. Ajoutez les lignes de produits.')
            return redirect('approvisionnement:entree_detail', pk=bon.pk)
    return render(
        request,
        'approvisionnement/entree_form.html',
        {'form': formulaire},
    )


@login_required
def entree_detail(request, pk):
    bon = get_object_or_404(
        BonApprovisionnement.objects.select_related('fournisseur', 'utilisateur'),
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


@login_required
def entree_validation_liste(request):
    bons = (
        BonApprovisionnement.objects.filter(statut=BonApprovisionnement.Statut.BROUILLON)
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


@login_required
def entree_validation_detail(request, pk):
    bon = get_object_or_404(
        BonApprovisionnement.objects.select_related('fournisseur', 'utilisateur'),
        pk=pk,
    )
    formset = None
    if bon.statut != BonApprovisionnement.Statut.VALIDE:
        formset = LigneValidationFormSet(
            request.POST if request.method == 'POST' else None,
            instance=bon,
        )
        if request.method == 'POST' and formset.is_valid():
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
            messages.success(request, 'Quantités et lignes mises à jour.')
            return redirect('approvisionnement:entree_validation_detail', pk=bon.pk)
    return render(
        request,
        'approvisionnement/entree_validation_detail.html',
        {
            'bon': bon,
            'formset': formset,
            'lignes': bon.lignes.select_related('article', 'article__unite', 'mouvement'),
        },
    )


@login_required
@require_POST
def entree_valider(request, pk):
    bon = get_object_or_404(BonApprovisionnement, pk=pk)
    try:
        bon.valider()
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
        return redirect('approvisionnement:entree_validation_detail', pk=bon.pk)
    messages.success(request, f'Bon {bon.numero} validé. Le stock a été mis à jour.')
    return redirect(reverse('approvisionnement:entree_imprimer', kwargs={'pk': bon.pk}) + '?auto=1')


@login_required
def entree_imprimer(request, pk):
    bon = get_object_or_404(
        BonApprovisionnement.objects.select_related('fournisseur', 'utilisateur'),
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


@login_required
def sortie_liste(request):
    bons = BonSortie.objects.select_related('utilisateur', 'destination')
    return render(
        request,
        'approvisionnement/sortie_liste.html',
        {'bons': bons},
    )


@login_required
def sortie_nouveau(request):
    formulaire = BonSortieForm(
        request.POST if request.method == 'POST' else None,
        initial={'date_sortie': timezone.localtime().strftime('%Y-%m-%dT%H:%M')},
    )
    if request.method == 'POST' and formulaire.is_valid():
        if not Article.objects.exists():
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


@login_required
def sortie_detail(request, pk):
    bon = get_object_or_404(
        BonSortie.objects.select_related('utilisateur', 'destination'),
        pk=pk,
    )
    formset = LigneSortieFormSet(
        request.POST if request.method == 'POST' else None,
        instance=bon,
    )
    depassements = []
    ruptures = []
    seuils = []
    auth_form = None
    if bon.statut == BonSortie.Statut.VALIDE:
        formset = None
    elif request.method == 'POST' and formset.is_valid():
        formset.save()
        messages.success(request, 'Lignes de sortie enregistrées.')
        return redirect('approvisionnement:sortie_detail', pk=bon.pk)
    else:
        ruptures, seuils = bon.analyser_stock()
        depassements = ruptures
        if seuils and not ruptures:
            auth_form = AutorisationDepassementForm(request=request)
    return render(
        request,
        'approvisionnement/sortie_detail.html',
        {
            'bon': bon,
            'formset': formset,
            'lignes': bon.lignes.select_related('article', 'article__unite', 'mouvement'),
            'ruptures': ruptures,
            'seuils': seuils,
            'depassements': depassements,
            'auth_form': auth_form,
        },
    )


@login_required
@require_POST
def sortie_valider(request, pk):
    bon = get_object_or_404(
        BonSortie.objects.select_related('utilisateur', 'destination'),
        pk=pk,
    )
    ruptures, seuils = bon.analyser_stock()
    autorisation = False
    if ruptures:
        messages.error(
            request,
            'Impossible de valider : un article est à 0 ou la quantité dépasse le stock. '
            'Retirez ou corrigez la ligne concernée.',
        )
        formset = LigneSortieFormSet(instance=bon)
        return render(
            request,
            'approvisionnement/sortie_detail.html',
            {
                'bon': bon,
                'formset': formset,
                'lignes': bon.lignes.select_related('article', 'article__unite', 'mouvement'),
                'ruptures': ruptures,
                'seuils': seuils,
                'auth_form': None,
            },
        )
    if seuils:
        auth_form = AutorisationDepassementForm(request.POST, request=request)
        if not auth_form.is_valid():
            messages.error(
                request,
                'Le stock a atteint le seuil. Le propriétaire doit s’authentifier pour autoriser la sortie.',
            )
            formset = LigneSortieFormSet(instance=bon)
            return render(
                request,
                'approvisionnement/sortie_detail.html',
                {
                    'bon': bon,
                    'formset': formset,
                    'lignes': bon.lignes.select_related('article', 'article__unite', 'mouvement'),
                    'ruptures': ruptures,
                    'seuils': seuils,
                    'auth_form': auth_form,
                },
            )
        autorisation = True
    try:
        bon.valider(autorisation_depassement=autorisation)
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
        return redirect('approvisionnement:sortie_detail', pk=bon.pk)
    if autorisation:
        messages.success(
            request,
            f'Bon {bon.numero} validé avec autorisation du propriétaire. '
            'Le stock a été diminué et l’historique a été enregistré.',
        )
    else:
        messages.success(
            request,
            f'Bon {bon.numero} validé. Le stock a été diminué et l’historique a été enregistré.',
        )
    return redirect(reverse('approvisionnement:sortie_imprimer', kwargs={'pk': bon.pk}) + '?auto=1')


@login_required
def sortie_imprimer(request, pk):
    bon = get_object_or_404(
        BonSortie.objects.select_related('utilisateur', 'destination'),
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


@login_required
def historique(request):
    journaux = Approvisionnement.objects.select_related(
        'utilisateur', 'fournisseur', 'bon_entree', 'bon_sortie'
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


@login_required
def historique_detail(request, pk):
    journal = get_object_or_404(
        Approvisionnement.objects.select_related(
            'utilisateur', 'fournisseur', 'bon_entree', 'bon_sortie'
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


@login_required
def inventaire_liste(request):
    inventaires = Inventaire.objects.select_related('responsable')
    return render(
        request,
        'approvisionnement/inventaire_liste.html',
        {'inventaires': inventaires},
    )


@login_required
def inventaire_nouveau(request):
    formulaire = InventaireForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and formulaire.is_valid():
        if not Article.objects.exists():
            messages.error(
                request,
                'Créez d’abord des articles dans l’administration (tables de paramètre).',
            )
        else:
            inventaire = formulaire.save(commit=False)
            inventaire.responsable = request.user
            inventaire.save()
            for article in Article.objects.all():
                inventaire.lignes.create(
                    article=article,
                    stock_systeme=article.stock,
                    stock_physique=article.stock,
                )
            messages.success(request, 'Inventaire créé. Saisissez les stocks physiques.')
            return redirect('approvisionnement:inventaire_detail', pk=inventaire.pk)
    return render(
        request,
        'approvisionnement/inventaire_form.html',
        {'form': formulaire},
    )


@login_required
def inventaire_detail(request, pk):
    inventaire = get_object_or_404(
        Inventaire.objects.select_related('responsable'),
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


@login_required
@require_POST
def inventaire_valider(request, pk):
    inventaire = get_object_or_404(Inventaire, pk=pk)
    try:
        inventaire.valider()
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if hasattr(exc, 'messages') else str(exc))
        return redirect('approvisionnement:inventaire_detail', pk=inventaire.pk)
    messages.success(request, 'Inventaire validé. Les écarts ont été audités.')
    return redirect('approvisionnement:inventaire_detail', pk=inventaire.pk)
