from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
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
    LigneSortieValidationFormSet,
    LigneValidationFormSet,
    RapportPeriodeForm,
)
from .models import (
    Approvisionnement,
    Article,
    BonApprovisionnement,
    BonSortie,
    Inventaire,
    LigneApprovisionnement,
    LigneSortie,
    Service,
)


@login_required
def tableau_de_bord(request):
    articles = Article.objects.select_related('categorie', 'unite')
    alertes = articles.filter(stock__lte=F('seuil_minimum') + 10)
    derniers = Approvisionnement.objects.select_related(
        'utilisateur', 'fournisseur'
    ).prefetch_related('lignes__article', 'lignes__article__unite')[:8]
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
    bons = BonSortie.objects.select_related(
        'utilisateur', 'destination'
    ).annotate(nb_lignes=Count('lignes'))
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
    lignes = bon.lignes.select_related(
        'article', 'article__unite', 'article__categorie', 'mouvement'
    )
    formset = None
    if bon.statut != BonSortie.Statut.VALIDE:
        formset = LigneSortieFormSet(
            request.POST if request.method == 'POST' else None,
            instance=bon,
            queryset=LigneSortie.objects.none(),
            articles_exclus=list(lignes.values_list('article_id', flat=True)),
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
            return redirect('approvisionnement:sortie_detail', pk=bon.pk)
    return render(
        request,
        'approvisionnement/sortie_detail.html',
        {
            'bon': bon,
            'formset': formset,
            'lignes': lignes,
            'nb_articles': Article.objects.count(),
        },
    )


@login_required
def sortie_validation_liste(request):
    bons = (
        BonSortie.objects.filter(statut=BonSortie.Statut.BROUILLON)
        .annotate(nb_lignes=Count('lignes'))
        .filter(nb_lignes__gt=0)
        .select_related('utilisateur', 'destination')
        .prefetch_related(
            'lignes__article',
            'lignes__article__unite',
            'lignes__article__categorie',
        )
    )
    return render(
        request,
        'approvisionnement/sortie_validation_liste.html',
        {'bons': bons},
    )


def _valider_sortie_et_imprimer(request, bon, autorisation=False):
    try:
        bon.valider(autorisation_depassement=autorisation)
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
        return redirect('approvisionnement:sortie_validation_detail', pk=bon.pk)
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
    return redirect(
        reverse('approvisionnement:sortie_imprimer', kwargs={'pk': bon.pk}) + '?auto=1'
    )


@login_required
def sortie_validation_detail(request, pk):
    bon = get_object_or_404(
        BonSortie.objects.select_related('utilisateur', 'destination'),
        pk=pk,
    )
    lignes = bon.lignes.select_related(
        'article', 'article__unite', 'article__categorie', 'mouvement'
    )
    formset = None
    ruptures = []
    seuils = []
    auth_form = None
    if bon.statut != BonSortie.Statut.VALIDE:
        formset = LigneSortieValidationFormSet(
            request.POST if request.method == 'POST' else None,
            instance=bon,
            queryset=lignes,
        )
        if request.method == 'POST' and formset.is_valid():
            formset.save()
            if request.POST.get('action') == 'valider':
                ruptures, seuils = bon.analyser_stock()
                if ruptures:
                    messages.error(
                        request,
                        'Impossible de valider : un article est à 0 ou la quantité dépasse le stock. '
                        'Retirez ou corrigez la ligne concernée.',
                    )
                    formset = LigneSortieValidationFormSet(
                        instance=bon,
                        queryset=bon.lignes.select_related(
                            'article', 'article__unite', 'article__categorie'
                        ),
                    )
                    auth_form = None
                elif seuils:
                    auth_form = AutorisationDepassementForm(request.POST, request=request)
                    if auth_form.is_valid():
                        return _valider_sortie_et_imprimer(
                            request, bon, autorisation=True
                        )
                    messages.error(
                        request,
                        'Le stock a atteint le seuil. Le propriétaire doit s’authentifier '
                        'pour autoriser la sortie.',
                    )
                    formset = LigneSortieValidationFormSet(
                        instance=bon,
                        queryset=bon.lignes.select_related(
                            'article', 'article__unite', 'article__categorie'
                        ),
                    )
                else:
                    return _valider_sortie_et_imprimer(request, bon)
            else:
                messages.success(request, 'Quantités et lignes mises à jour.')
                return redirect(
                    'approvisionnement:sortie_validation_detail', pk=bon.pk
                )
        else:
            ruptures, seuils = bon.analyser_stock()
            if seuils and not ruptures:
                auth_form = AutorisationDepassementForm(request=request)
    lignes = bon.lignes.select_related(
        'article', 'article__unite', 'article__categorie', 'mouvement'
    )
    return render(
        request,
        'approvisionnement/sortie_validation_detail.html',
        {
            'bon': bon,
            'formset': formset,
            'lignes': lignes,
            'ruptures': ruptures,
            'seuils': seuils,
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
    if ruptures:
        messages.error(
            request,
            'Impossible de valider : un article est à 0 ou la quantité dépasse le stock. '
            'Retirez ou corrigez la ligne concernée.',
        )
        return redirect('approvisionnement:sortie_validation_detail', pk=bon.pk)
    if seuils:
        auth_form = AutorisationDepassementForm(request.POST, request=request)
        if not auth_form.is_valid():
            messages.error(
                request,
                'Le stock a atteint le seuil. Le propriétaire doit s’authentifier pour autoriser la sortie.',
            )
            return redirect('approvisionnement:sortie_validation_detail', pk=bon.pk)
        return _valider_sortie_et_imprimer(request, bon, autorisation=True)
    return _valider_sortie_et_imprimer(request, bon)


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
    ).prefetch_related('lignes__article', 'lignes__article__unite')
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
    return render(
        request,
        'approvisionnement/historique.html',
        {
            'journaux': journaux,
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
    inventaire_existant = None
    if request.method == 'POST' and formulaire.is_valid():
        if not Article.objects.exists():
            messages.error(
                request,
                'Créez d’abord des articles dans l’administration (tables de paramètre).',
            )
        else:
            date_jour = formulaire.cleaned_data['date_inventaire']
            inventaire_existant = Inventaire.objects.filter(
                date_inventaire=date_jour
            ).first()
            if inventaire_existant and request.POST.get('confirmer_maj') != '1':
                return render(
                    request,
                    'approvisionnement/inventaire_form.html',
                    {
                        'form': formulaire,
                        'inventaire_existant': inventaire_existant,
                    },
                )
            if inventaire_existant:
                if inventaire_existant.statut == Inventaire.Statut.VALIDE:
                    messages.info(
                        request,
                        'Un inventaire validé existe déjà pour cette journée. '
                        'Il a été ouvert sans créer de second enregistrement.',
                    )
                    return redirect(
                        'approvisionnement:inventaire_detail',
                        pk=inventaire_existant.pk,
                    )
                inventaire_existant.commentaire = formulaire.cleaned_data.get(
                    'commentaire', ''
                )
                inventaire_existant.responsable = request.user
                inventaire_existant.save(
                    update_fields=['commentaire', 'responsable']
                )
                _synchroniser_lignes_inventaire(inventaire_existant)
                messages.success(
                    request,
                    'L’inventaire du jour a été mis à jour. Vous pouvez modifier les stocks physiques.',
                )
                return redirect(
                    'approvisionnement:inventaire_detail',
                    pk=inventaire_existant.pk,
                )
            inventaire = formulaire.save(commit=False)
            inventaire.responsable = request.user
            inventaire.save()
            _synchroniser_lignes_inventaire(inventaire)
            messages.success(request, 'Inventaire créé. Saisissez les stocks physiques.')
            return redirect('approvisionnement:inventaire_detail', pk=inventaire.pk)
    return render(
        request,
        'approvisionnement/inventaire_form.html',
        {
            'form': formulaire,
            'inventaire_existant': inventaire_existant,
        },
    )


def _synchroniser_lignes_inventaire(inventaire):
    connus = {ligne.article_id: ligne for ligne in inventaire.lignes.all()}
    for article in Article.objects.all():
        ligne = connus.get(article.pk)
        if ligne is None:
            inventaire.lignes.create(
                article=article,
                stock_systeme=article.stock,
                stock_physique=article.stock,
            )
        else:
            ligne.stock_systeme = article.stock
            ligne.save(update_fields=['stock_systeme'])


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
        if request.POST.get('action') == 'valider':
            try:
                inventaire.valider()
            except ValidationError as exc:
                messages.error(
                    request, ' '.join(getattr(exc, 'messages', [str(exc)]))
                )
                return redirect('approvisionnement:inventaire_detail', pk=inventaire.pk)
            messages.success(request, 'Inventaire validé. Les écarts ont été audités.')
            return redirect('approvisionnement:inventaire_detail', pk=inventaire.pk)
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


def _periode_rapport(request):
    aujourd_hui = timezone.localdate()
    debut_defaut = aujourd_hui.replace(day=1)
    if request.GET:
        formulaire = RapportPeriodeForm(request.GET)
        if not formulaire.is_valid():
            return formulaire, None, None, None
        return (
            formulaire,
            formulaire.cleaned_data['date_debut'],
            formulaire.cleaned_data['date_fin'],
            formulaire.cleaned_data['type_rapport'],
        )
    formulaire = RapportPeriodeForm(
        initial={
            'date_debut': debut_defaut,
            'date_fin': aujourd_hui,
        }
    )
    return formulaire, debut_defaut, aujourd_hui, None


def _donnees_rapport(debut, fin, type_rapport=None):
    entrees = (
        Approvisionnement.objects.filter(
            type_operation=Approvisionnement.Type.ENTREE,
            date_operation__date__gte=debut,
            date_operation__date__lte=fin,
        )
        .select_related('utilisateur', 'fournisseur')
        .prefetch_related(
            'lignes__article',
            'lignes__article__unite',
            'lignes__article__categorie',
        )
    )
    sorties = (
        Approvisionnement.objects.filter(
            type_operation=Approvisionnement.Type.SORTIE,
            date_operation__date__gte=debut,
            date_operation__date__lte=fin,
        )
        .select_related('utilisateur')
        .prefetch_related(
            'lignes__article',
            'lignes__article__unite',
            'lignes__article__categorie',
        )
    )
    inventaires = (
        Inventaire.objects.filter(
            statut=Inventaire.Statut.VALIDE,
            date_inventaire__gte=debut,
            date_inventaire__lte=fin,
        )
        .select_related('responsable')
        .prefetch_related(
            'lignes__article',
            'lignes__article__unite',
        )
    )
    qte_entrees = sum(
        ligne.quantite for journal in entrees for ligne in journal.lignes.all()
    )
    qte_sorties = sum(
        ligne.quantite for journal in sorties for ligne in journal.lignes.all()
    )
    lignes = []
    if type_rapport == RapportPeriodeForm.TYPE_ENTREE:
        for journal in entrees:
            for ligne in journal.lignes.all():
                lignes.append({'journal': journal, 'ligne': ligne})
    elif type_rapport == RapportPeriodeForm.TYPE_SORTIE:
        for journal in sorties:
            for ligne in journal.lignes.all():
                lignes.append({'journal': journal, 'ligne': ligne})
    elif type_rapport == RapportPeriodeForm.TYPE_INVENTAIRE:
        for inventaire in inventaires:
            for ligne in inventaire.lignes.all():
                lignes.append({'inventaire': inventaire, 'ligne': ligne})
    return {
        'date_debut': debut,
        'date_fin': fin,
        'type_rapport': type_rapport,
        'entrees': entrees,
        'sorties': sorties,
        'inventaires': inventaires,
        'lignes_rapport': lignes,
        'nb_entrees': entrees.count(),
        'nb_sorties': sorties.count(),
        'nb_inventaires': inventaires.count(),
        'qte_entrees': qte_entrees,
        'qte_sorties': qte_sorties,
    }


@login_required
def rapport(request):
    formulaire, debut, fin, type_rapport = _periode_rapport(request)
    contexte = {'form': formulaire}
    if debut and fin:
        contexte.update(_donnees_rapport(debut, fin, type_rapport))
    return render(request, 'approvisionnement/rapport.html', contexte)


@login_required
def rapport_imprimer(request):
    formulaire, debut, fin, type_rapport = _periode_rapport(request)
    if not debut or not fin or not type_rapport:
        messages.error(
            request,
            'Indiquez une période et un type valides pour imprimer le rapport.',
        )
        return redirect('approvisionnement:rapport')
    contexte = _donnees_rapport(debut, fin, type_rapport)
    contexte['form'] = formulaire
    return render(request, 'approvisionnement/rapport_impression.html', contexte)
