"""Module Boutique — vues fonctions (FBV).

Le module est rattaché au domaine d'activité BOUTIQUE : le périmètre d'accès
est restreint aux succursales où l'utilisateur est affecté pour ce domaine.

La Boutique est indépendante de l'Approvisionnement : son stock, ses
mouvements, ses alertes et ses inventaires lui sont propres.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Domaine
from core.permissions import require_permission, succursales_autorisees
from core.services import AuditService

from .forms import (
    ArticleBoutiqueForm,
    EncaissementForm,
    InventaireForm,
    LigneInventaireFormSet,
    StockEntreeForm,
    VenteForm,
    VenteLigneFormSet,
)
from .models import (
    AlerteStockBoutique,
    ArticleBoutique,
    InventaireBoutique,
    MouvementStockBoutique,
    StockBoutique,
    Vente,
)
from .services import InventaireBoutiqueService, StockBoutiqueService, VenteService


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
    return ArticleBoutique.objects.select_related(
        'categorie', 'sous_categorie', 'unite'
    ).filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )


@require_permission('boutique.view_boutique')
def tableau_de_bord(request):
    peri = _perimetre(request.user)
    articles = _articles_perimetre(peri)
    stocks = StockBoutique.objects.select_related('article').filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    alertes = AlerteStockBoutique.objects.select_related('stock__article').filter(
        stock__succursale_id__in=peri['succursales_ids'],
        stock__domaine_id=peri['domaine_id'],
        statut=AlerteStockBoutique.Statut.ACTIVE,
    )
    ventes_qs = Vente.objects.filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    dernieres = ventes_qs.select_related('utilisateur', 'succursale')[:8]
    stock_total = stocks.aggregate(total=Sum('quantite'))['total'] or 0
    ventes_jour = ventes_qs.filter(date_vente__date=timezone.localdate()).count()
    return render(
        request,
        'boutique/tableau_de_bord.html',
        {
            'alertes': alertes,
            'articles': articles,
            'stocks': stocks,
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
    stocks = StockBoutique.objects.filter(
        article_id__in=articles_qs.values('id'),
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    stocks_par_article = {s.article_id: s for s in stocks}
    liste = [
        {'article': a, 'stock': stocks_par_article.get(a.pk)}
        for a in articles_qs
    ]
    return render(
        request,
        'boutique/articles.html',
        {'articles': liste},
    )


@require_permission('boutique.adjust_stock')
def article_nouveau(request):
    peri = _perimetre(request.user)
    domaine = (
        Domaine.objects.filter(pk=peri['domaine_id'])
        if peri['domaine_id']
        else Domaine.objects.none()
    )
    contexte = request.user.contexte_actif()
    formulaire = ArticleBoutiqueForm(
        request.POST if request.method == 'POST' else None,
        succursales=peri['succursales'],
        domaines=domaine,
        contexte=contexte,
    )
    if request.method == 'POST' and formulaire.is_valid():
        article = formulaire.save(commit=False)
        if contexte and contexte['verrouille']:
            article.succursale = contexte['succursale']
            article.domaine = contexte['domaine']
        article.save()
        AuditService.auditer(
            utilisateur=request.user,
            succursale=article.succursale,
            module='BOUTIQUE',
            action='article.create',
            objet_type='ArticleBoutique',
            objet_id=article.pk,
            nouvelle_valeur={'code': article.code, 'designation': article.designation},
        )
        messages.success(request, f'Article {article.code} créé. Pensez à faire une entrée en stock.')
        return redirect('boutique:articles')
    return render(
        request,
        'boutique/article_form.html',
        {'form': formulaire},
    )


@require_permission('boutique.view_stock')
def article_detail(request, pk):
    peri = _perimetre(request.user)
    article = get_object_or_404(
        ArticleBoutique.objects.select_related('categorie', 'sous_categorie', 'unite').filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    stock = StockBoutique.objects.filter(
        article=article,
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    ).first()
    return render(
        request,
        'boutique/article_detail.html',
        {'article': article, 'stock': stock},
    )


@require_permission('boutique.view_stock')
def stocks(request):
    peri = _perimetre(request.user)
    stocks_qs = StockBoutique.objects.select_related(
        'article', 'article__categorie', 'article__unite'
    ).filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    return render(
        request,
        'boutique/stocks.html',
        {'stocks': stocks_qs},
    )


@require_permission('boutique.adjust_stock')
def entree(request):
    peri = _perimetre(request.user)
    articles = _articles_perimetre(peri)
    formulaire = StockEntreeForm(
        request.POST if request.method == 'POST' else None,
        articles=articles,
    )
    if request.method == 'POST' and formulaire.is_valid():
        article = formulaire.cleaned_data['article']
        quantite = formulaire.cleaned_data['quantite']
        seuil = formulaire.cleaned_data.get('seuil_alerte')
        try:
            if seuil is not None:
                stock = StockBoutique.obtenir(article, article.succursale, article.domaine)
                stock.seuil_alerte = seuil
                stock.save(update_fields=['seuil_alerte'])
            StockBoutiqueService.entrer(
                article=article,
                succursale=article.succursale,
                domaine=article.domaine,
                quantite=quantite,
                utilisateur=request.user,
                reference=formulaire.cleaned_data.get('reference', ''),
                motif=formulaire.cleaned_data.get('motif', ''),
            )
            messages.success(request, f'Entrée de {quantite} pour {article.code} enregistrée.')
        except ValidationError as exc:
            messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
        return redirect('boutique:entree')
    return render(
        request,
        'boutique/entree_form.html',
        {'form': formulaire},
    )


@require_permission('boutique.view_stock')
def mouvements(request):
    peri = _perimetre(request.user)
    qs = MouvementStockBoutique.objects.select_related('article', 'utilisateur').filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    type_ = request.GET.get('type', '')
    q = request.GET.get('q', '')
    if type_:
        qs = qs.filter(type=type_)
    if q:
        qs = qs.filter(
            Q(article__code__icontains=q)
            | Q(article__designation__icontains=q)
            | Q(reference__icontains=q)
            | Q(motif__icontains=q)
        )
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'boutique/historique.html',
        {
            'mouvements': page,
            'types': MouvementStockBoutique.Type.choices,
            'type': type_,
            'q': q,
        },
    )


@require_permission('boutique.view_stock')
def alertes(request):
    peri = _perimetre(request.user)
    alertes_qs = AlerteStockBoutique.objects.select_related('stock__article').filter(
        stock__succursale_id__in=peri['succursales_ids'],
        stock__domaine_id=peri['domaine_id'],
        statut=AlerteStockBoutique.Statut.ACTIVE,
    )
    return render(
        request,
        'boutique/alertes.html',
        {'alertes': alertes_qs},
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
                client=formulaire.cleaned_data.get('client', ''),
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
    lignes = vente.lignes.select_related('article', 'mouvement')
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
        {
            'vente': vente,
            'formset': formset,
            'lignes': lignes,
            'encaissement_form': EncaissementForm(instance=vente),
        },
    )


@require_permission('boutique.create_vente')
@require_POST
def vente_encaissement(request, pk):
    peri = _perimetre(request.user)
    vente = get_object_or_404(
        Vente.objects.filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    if vente.statut != Vente.Statut.BROUILLON:
        messages.error(request, 'Le montant reçu ne peut être modifié que sur une vente en brouillon.')
        return redirect('boutique:vente_detail', pk=vente.pk)
    formulaire = EncaissementForm(request.POST, instance=vente)
    if formulaire.is_valid():
        formulaire.save()
        messages.success(request, 'Montant reçu enregistré.')
    else:
        messages.error(request, 'Montant reçu invalide.')
    return redirect('boutique:vente_detail', pk=vente.pk)


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
            'lignes': vente.lignes.select_related('article'),
        },
    )


@require_permission('boutique.view_stock')
def inventaires(request):
    peri = _perimetre(request.user)
    inventaires_qs = (
        InventaireBoutique.objects.select_related('succursale')
        .filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        )
        .annotate(nb_lignes=Count('lignes'))
    )
    return render(
        request,
        'boutique/inventaires.html',
        {'inventaires': inventaires_qs},
    )


@require_permission('boutique.adjust_stock')
def inventaire_nouveau(request):
    peri = _perimetre(request.user)
    domaine = (
        Domaine.objects.filter(pk=peri['domaine_id'])
        if peri['domaine_id']
        else Domaine.objects.none()
    )
    contexte = request.user.contexte_actif()
    articles = _articles_perimetre(peri)
    formulaire = InventaireForm(
        request.POST if request.method == 'POST' else None,
        succursales=peri['succursales'],
        domaines=domaine,
        contexte=contexte,
        articles=articles,
    )
    if request.method == 'POST' and formulaire.is_valid():
        succursale = formulaire.cleaned_data.get('succursale')
        domaine_v = formulaire.cleaned_data.get('domaine')
        if contexte and contexte['verrouille']:
            succursale = contexte['succursale']
            domaine_v = contexte['domaine']
        inventaire = InventaireBoutiqueService.creer(
            date_inventaire=formulaire.cleaned_data['date_inventaire'],
            succursale=succursale,
            domaine=domaine_v,
            utilisateur=request.user,
            commentaire=formulaire.cleaned_data.get('commentaire', ''),
            portee=formulaire.cleaned_data['portee'],
            article=formulaire.cleaned_data.get('article'),
        )
        messages.success(request, f'Inventaire {inventaire.numero} créé.')
        return redirect('boutique:inventaire_detail', pk=inventaire.pk)
    return render(
        request,
        'boutique/inventaire_form.html',
        {'form': formulaire},
    )


@require_permission('boutique.view_stock')
def inventaire_detail(request, pk):
    peri = _perimetre(request.user)
    inventaire = get_object_or_404(
        InventaireBoutique.objects.select_related('succursale', 'responsable').filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    lignes = inventaire.lignes.select_related('article', 'mouvement')
    formset = None
    if inventaire.statut == InventaireBoutique.Statut.BROUILLON:
        formset = LigneInventaireFormSet(
            request.POST if request.method == 'POST' else None,
            instance=inventaire,
        )
        if request.method == 'POST' and formset.is_valid():
            formset.save()
            messages.success(request, 'Quantités physiques enregistrées.')
            return redirect('boutique:inventaire_detail', pk=inventaire.pk)
    return render(
        request,
        'boutique/inventaire_detail.html',
        {'inventaire': inventaire, 'formset': formset, 'lignes': lignes},
    )


@require_permission('boutique.adjust_stock')
@require_POST
def inventaire_valider(request, pk):
    peri = _perimetre(request.user)
    inventaire = get_object_or_404(
        InventaireBoutique.objects.filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    try:
        InventaireBoutiqueService.valider(inventaire, par=request.user)
        messages.success(request, f'Inventaire {inventaire.numero} validé. Ajustements appliqués.')
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
    return redirect('boutique:inventaire_detail', pk=inventaire.pk)
