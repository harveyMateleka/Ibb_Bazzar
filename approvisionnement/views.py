from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import EntreeStockForm, InventaireForm, LigneInventaireFormSet, SortieStockForm
from .models import AlerteStock, Article, Inventaire, MouvementStock


def _enregistrer_mouvement(request, formulaire, type_mouvement, message_ok):
    if formulaire.is_valid():
        mouvement = formulaire.save(commit=False)
        mouvement.type_mouvement = type_mouvement
        mouvement.utilisateur = request.user
        try:
            mouvement.save()
            mouvement.valider()
        except ValidationError as exc:
            mouvement.delete()
            if hasattr(exc, 'message_dict'):
                for champ, erreurs in exc.message_dict.items():
                    for erreur in erreurs:
                        formulaire.add_error(champ if champ != '__all__' else None, erreur)
            else:
                formulaire.add_error(None, exc)
        else:
            messages.success(request, message_ok)
            return redirect('approvisionnement:historique')
    return None


@login_required
def tableau_de_bord(request):
    alertes = AlerteStock.objects.filter(active=True).select_related('article')
    articles = Article.objects.select_related('categorie', 'unite')
    derniers = MouvementStock.objects.select_related('article', 'utilisateur')[:8]
    return render(
        request,
        'approvisionnement/tableau_de_bord.html',
        {
            'alertes': alertes,
            'articles': articles,
            'derniers_mouvements': derniers,
            'nb_alertes': alertes.count(),
            'nb_articles': articles.count(),
            'nb_mouvements': MouvementStock.objects.count(),
        },
    )


@login_required
def entree_stock(request):
    formulaire = EntreeStockForm(
        request.POST if request.method == 'POST' else None,
        initial={'date_mouvement': timezone.localtime().strftime('%Y-%m-%dT%H:%M')},
    )
    redirection = None
    if request.method == 'POST':
        redirection = _enregistrer_mouvement(
            request,
            formulaire,
            MouvementStock.Type.ENTREE,
            'Entrée de stock enregistrée et validée.',
        )
    if redirection:
        return redirection
    return render(
        request,
        'approvisionnement/entree_form.html',
        {'form': formulaire},
    )


@login_required
def sortie_stock(request):
    formulaire = SortieStockForm(
        request.POST if request.method == 'POST' else None,
        initial={'date_mouvement': timezone.localtime().strftime('%Y-%m-%dT%H:%M')},
    )
    redirection = None
    if request.method == 'POST':
        redirection = _enregistrer_mouvement(
            request,
            formulaire,
            MouvementStock.Type.SORTIE,
            'Sortie de stock enregistrée et validée.',
        )
    if redirection:
        return redirection
    return render(
        request,
        'approvisionnement/sortie_form.html',
        {'form': formulaire},
    )


@login_required
def historique(request):
    mouvements = MouvementStock.objects.select_related(
        'article', 'fournisseur', 'utilisateur'
    )
    type_filtre = request.GET.get('type', '')
    recherche = request.GET.get('q', '').strip()
    if type_filtre in MouvementStock.Type.values:
        mouvements = mouvements.filter(type_mouvement=type_filtre)
    if recherche:
        mouvements = mouvements.filter(
            Q(article__code__icontains=recherche)
            | Q(article__designation__icontains=recherche)
            | Q(reference__icontains=recherche)
            | Q(motif__icontains=recherche)
        )
    page = Paginator(mouvements, 20).get_page(request.GET.get('page'))
    return render(
        request,
        'approvisionnement/historique.html',
        {
            'page': page,
            'type_filtre': type_filtre,
            'recherche': recherche,
            'types': MouvementStock.Type.choices,
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
