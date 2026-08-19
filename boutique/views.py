"""Module Boutique — vues fonctions (FBV).

Architecture : Article → VarianteArticle → StockBoutique → MouvementStockBoutique.
Périmètre = succursales affectées au domaine BOUTIQUE ; succursale/domaine
auto + readonly dans les formulaires via `contexte_actif()` / `appliquer_contexte`.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Domaine, Succursale
from core.permissions import require_permission, succursales_autorisees
from core.services import AuditService

from .forms import (
    ArticleBoutiqueForm,
    InventaireForm,
    LigneInventaireFormSet,
    LigneVenteSaisieFormSet,
    StockEntreeForm,
    VenteForm,
)
from .models import (
    AlerteStockBoutique,
    ArticleBoutique,
    BonEntreeBoutique,
    CategorieBoutique,
    InventaireBoutique,
    MouvementStockBoutique,
    StockBoutique,
    VarianteArticle,
    Vente,
)
from .services import (
    BonEntreeService,
    InventaireBoutiqueService,
    StockBoutiqueService,
    VarianteService,
    VenteService,
)


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
    return ArticleBoutique.objects.filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )


def _variantes_perimetre(peri):
    return VarianteArticle.objects.select_related('article', 'categorie', 'unite').filter(
        article__succursale_id__in=peri['succursales_ids'],
        article__domaine_id=peri['domaine_id'],
    )


def _paginer(request, qs, par_page=25):
    return Paginator(qs, par_page).get_page(request.GET.get('page'))


def _filtrer_mouvements(request, peri):
    qs = MouvementStockBoutique.objects.select_related(
        'variante', 'variante__article', 'utilisateur').filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    filtres = {
        'type': request.GET.get('type', ''),
        'q': request.GET.get('q', ''),
        'date_debut': request.GET.get('date_debut', ''),
        'date_fin': request.GET.get('date_fin', ''),
    }
    if filtres['type']:
        qs = qs.filter(type=filtres['type'])
    if filtres['q']:
        qs = qs.filter(
            Q(variante__article__code__icontains=filtres['q'])
            | Q(variante__article__designation__icontains=filtres['q'])
            | Q(variante__couleur__icontains=filtres['q'])
            | Q(reference__icontains=filtres['q'])
            | Q(motif__icontains=filtres['q'])
        )
    if filtres['date_debut']:
        qs = qs.filter(date_mouvement__date__gte=filtres['date_debut'])
    if filtres['date_fin']:
        qs = qs.filter(date_mouvement__date__lte=filtres['date_fin'])
    return qs, filtres


@require_permission('boutique.view_boutique')
def tableau_de_bord(request):
    peri = _perimetre(request.user)
    articles = _articles_perimetre(peri)
    stocks = StockBoutique.objects.select_related('variante', 'variante__article').filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    alertes = AlerteStockBoutique.objects.select_related('stock__variante').filter(
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
    q = request.GET.get('q', '')
    if q:
        articles_qs = articles_qs.filter(
            Q(code__icontains=q) | Q(designation__icontains=q)
        )
    page_obj = _paginer(request, articles_qs.order_by('code'))
    return render(
        request,
        'boutique/articles.html',
        {'articles': page_obj.object_list, 'page_obj': page_obj, 'q': q},
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
        messages.success(request, f'Arrivage {article.code} enregistré. Ajoutez les produits via l’entrée en stock.')
        return redirect('boutique:article_detail', pk=article.pk)
    return render(
        request,
        'boutique/article_form.html',
        {'form': formulaire},
    )


@require_permission('boutique.view_stock')
def article_detail(request, pk):
    peri = _perimetre(request.user)
    article = get_object_or_404(_articles_perimetre(peri), pk=pk)
    variantes_qs = article.variantes.select_related('categorie', 'unite')
    stocks = StockBoutique.objects.filter(
        variante__article=article,
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    stocks_par_variante = {s.variante_id: s for s in stocks}
    variantes = [
        {'variante': v, 'stock': stocks_par_variante.get(v.pk)}
        for v in variantes_qs
    ]
    return render(
        request,
        'boutique/article_detail.html',
        {'article': article, 'variantes': variantes},
    )


@require_permission('boutique.view_stock')
def stocks(request):
    peri = _perimetre(request.user)
    stocks_qs = StockBoutique.objects.select_related(
        'variante', 'variante__article', 'variante__categorie', 'variante__unite'
    ).filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    q = request.GET.get('q', '')
    etat = request.GET.get('etat', '')
    if q:
        stocks_qs = stocks_qs.filter(
            Q(variante__article__code__icontains=q)
            | Q(variante__article__designation__icontains=q)
        )
    if etat == 'rupture':
        stocks_qs = stocks_qs.filter(quantite__lte=0)
    elif etat == 'alerte':
        stocks_qs = stocks_qs.filter(variante__seuil_alerte__gt=0, quantite__lte=F('variante__seuil_alerte'))
    elif etat == 'vigilance':
        stocks_qs = stocks_qs.filter(
            variante__seuil_alerte__gt=0,
            variante__seuil_alerte__lt=F('quantite'),
            quantite__lte=F('variante__seuil_alerte') + 10,
        )
    elif etat == 'disponible':
        stocks_qs = stocks_qs.exclude(
            variante__seuil_alerte__gt=0, quantite__lte=F('variante__seuil_alerte'))
    page_obj = _paginer(request, stocks_qs.order_by('variante__article__code'))
    return render(
        request,
        'boutique/stocks.html',
        {'stocks': page_obj.object_list, 'page_obj': page_obj, 'q': q, 'etat': etat},
    )


@require_permission('boutique.adjust_stock')
def entree(request):
    peri = _perimetre(request.user)
    formulaire = StockEntreeForm(
        request.POST if request.method == 'POST' else None,
        articles=_articles_perimetre(peri),
    )
    if request.method == 'POST' and formulaire.is_valid():
        d = formulaire.cleaned_data
        article = d['article']
        try:
            bon = BonEntreeService.creer(
                article=article,
                succursale=article.succursale,
                domaine=article.domaine,
                quantite=d['quantite'],
                cree_par=request.user,
                categorie=d.get('categorie'),
                unite=d.get('unite'),
                genre=d.get('genre', ''),
                taille=d.get('taille', ''),
                couleur=d.get('couleur', ''),
                marque=d.get('marque', ''),
                modele=d.get('modele', ''),
                rayon=d.get('rayon', ''),
                etagere=d.get('etagere', ''),
                emplacement=d.get('emplacement', ''),
                prix_achat=d.get('prix_achat', 0),
                prix_unitaire=d.get('prix_unitaire', 0),
                prix_minimum=d.get('prix_minimum', 0),
                seuil_alerte=d.get('seuil_alerte', 0),
            )
            messages.success(
                request,
                f'Entrée {bon.numero} enregistrée en brouillon. '
                'Elle sera créée après validation par le responsable.',
            )
        except ValidationError as exc:
            messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
        # Le créateur (magasinier) n'a pas la liste de validation : retour au stock.
        return redirect('boutique:stocks')
    mes_entrees = BonEntreeBoutique.objects.filter(
        cree_par=request.user,
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    ).order_by('-date_creation')[:10]
    return render(
        request,
        'boutique/entree_form.html',
        {'form': formulaire, 'mes_entrees': mes_entrees},
    )


@require_permission('boutique.validate_entree')
def entrees_validation(request):
    """Liste des entrées de stock : les brouillons à valider par le responsable."""
    peri = _perimetre(request.user)
    bons = BonEntreeBoutique.objects.select_related('article', 'cree_par', 'succursale').filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    q = request.GET.get('q', '')
    statut = request.GET.get('statut', '')
    if q:
        bons = bons.filter(Q(numero__icontains=q) | Q(article__code__icontains=q))
    if statut:
        bons = bons.filter(statut=statut)
    page_obj = _paginer(request, bons.order_by('-date_creation'))
    return render(
        request,
        'boutique/entrees_validation.html',
        {
            'bons': page_obj.object_list,
            'page_obj': page_obj,
            'q': q,
            'statut': statut,
        },
    )


@require_permission('boutique.view_stock')
def entree_validation_detail(request, pk):
    peri = _perimetre(request.user)
    bon = get_object_or_404(
        BonEntreeBoutique.objects.select_related(
            'article', 'cree_par', 'valide_par', 'succursale', 'categorie', 'unite'
        ).filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    return render(
        request,
        'boutique/entree_validation_detail.html',
        {'bon': bon},
    )


@require_permission('boutique.validate_entree')
@require_POST
def entree_valider(request, pk):
    peri = _perimetre(request.user)
    bon = get_object_or_404(
        BonEntreeBoutique.objects.filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    try:
        BonEntreeService.valider(bon=bon, par=request.user)
        messages.success(
            request,
            f'Entrée {bon.numero} validée : la variante, le stock et le mouvement ont été créés.',
        )
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
    return redirect('boutique:entrees_validation')


@require_permission('boutique.validate_entree')
@require_POST
def entree_annuler(request, pk):
    """Annulation (rejet) d'une entrée en brouillon par le responsable,
    avec un commentaire visible par le demandeur."""
    peri = _perimetre(request.user)
    bon = get_object_or_404(
        BonEntreeBoutique.objects.filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    commentaire = request.POST.get('commentaire', '')
    try:
        BonEntreeService.annuler(bon=bon, par=request.user, commentaire=commentaire)
        messages.success(request, f'Entrée {bon.numero} annulée.')
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
    return redirect('boutique:entrees_validation')


@require_permission('boutique.view_stock')
def mouvements(request):
    peri = _perimetre(request.user)
    qs, filtres = _filtrer_mouvements(request, peri)
    page = _paginer(request, qs)
    return render(
        request,
        'boutique/historique.html',
        {
            'mouvements': page,
            'types': MouvementStockBoutique.Type.choices,
            'type': filtres['type'],
            'q': filtres['q'],
            'date_debut': filtres['date_debut'],
            'date_fin': filtres['date_fin'],
        },
    )


@require_permission('boutique.view_stock')
def mouvements_report(request):
    peri = _perimetre(request.user)
    qs, filtres = _filtrer_mouvements(request, peri)
    total_entrees = qs.filter(type=MouvementStockBoutique.Type.ENTREE).aggregate(
        total=Sum('quantite'))['total'] or 0
    total_sorties = qs.filter(type=MouvementStockBoutique.Type.SORTIE).aggregate(
        total=Sum('quantite'))['total'] or 0
    return render(
        request,
        'boutique/mouvements_report.html',
        {
            'mouvements': qs.order_by('date_mouvement', 'id'),
            'types': MouvementStockBoutique.Type.choices,
            'type': filtres['type'],
            'q': filtres['q'],
            'date_debut': filtres['date_debut'],
            'date_fin': filtres['date_fin'],
            'nb_mouvements': qs.count(),
            'total_entrees': total_entrees,
            'total_sorties': total_sorties,
            'utilisateur': request.user,
            'date_generation': timezone.localtime(),
        },
    )


@require_permission('boutique.view_stock')
def alertes(request):
    peri = _perimetre(request.user)
    alertes_qs = AlerteStockBoutique.objects.select_related('stock__variante').filter(
        stock__succursale_id__in=peri['succursales_ids'],
        stock__domaine_id=peri['domaine_id'],
        statut=AlerteStockBoutique.Statut.ACTIVE,
    )
    page_obj = _paginer(request, alertes_qs.order_by('-date_creation'))
    return render(
        request,
        'boutique/alertes.html',
        {'alertes': page_obj.object_list, 'page_obj': page_obj},
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
    q = request.GET.get('q', '')
    if q:
        ventes_qs = ventes_qs.filter(
            Q(numero__icontains=q) | Q(client__icontains=q)
        )
    page_obj = _paginer(request, ventes_qs.order_by('-date_vente'))
    return render(
        request,
        'boutique/ventes.html',
        {'ventes': page_obj.object_list, 'page_obj': page_obj, 'q': q},
    )


@require_permission('boutique.create_vente')
def vente_nouvelle(request):
    """Interface UNIQUE de vente : entête + lignes + paiement, puis « Créer et soumettre »."""
    peri = _perimetre(request.user)
    contexte = request.user.contexte_actif()
    # Succursale/domaine déterminés côté backend (contexte utilisateur).
    succursale = contexte['succursale'] if contexte and contexte['succursale'] else (
        Succursale.objects.filter(pk__in=peri['succursales_ids']).first())
    domaine = contexte['domaine'] if contexte and contexte['domaine'] else peri['domaine']

    formulaire = VenteForm(
        request.POST if request.method == 'POST' else None,
        request_user=request.user,
    )
    formset = LigneVenteSaisieFormSet(
        request.POST if request.method == 'POST' else None,
        prefix='lignes',
        succursale=succursale.pk if succursale else None,
        domaine=domaine.pk if domaine else None,
    )
    if request.method == 'POST' and formulaire.is_valid() and formset.is_valid():
        remise = formulaire.cleaned_data['remise'] or 0
        if remise > 0 and not request.user.has_perm('boutique.apply_remise'):
            messages.error(request, 'Vous n’êtes pas autorisé à appliquer une remise.')
        else:
            try:
                vente = VenteService.soumettre(
                    succursale=succursale,
                    domaine=domaine,
                    utilisateur=request.user,
                    client=formulaire.cleaned_data.get('client', ''),
                    type_paiement=formulaire.cleaned_data['type_paiement'],
                    montant_recu=formulaire.cleaned_data.get('montant_recu') or 0,
                    remise=remise,
                    lignes=formset.lignes_cleaned(),
                    par=request.user,
                )
            except ValidationError as exc:
                messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
                return redirect('boutique:vente_nouvelle')
            if vente.statut == Vente.Statut.PENDING_VALIDATION:
                messages.success(request, 'Vente créée et soumise à validation.')
            else:
                messages.success(request, 'Vente créée avec succès.')
            return redirect('boutique:vente_detail', pk=vente.pk)
    return render(
        request,
        'boutique/vente_form.html',
        {'form': formulaire, 'formset': formset},
    )


@require_permission('boutique.validate_vente')
def ventes_a_valider(request):
    """Ventes en attente de validation responsable (PENDING_VALIDATION)."""
    peri = _perimetre(request.user)
    ventes_qs = (
        Vente.objects.select_related('utilisateur', 'succursale')
        .filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
            statut=Vente.Statut.PENDING_VALIDATION,
        )
        .annotate(nb_lignes=Count('lignes'))
    )
    page_obj = _paginer(request, ventes_qs.order_by('date_vente'))
    return render(
        request,
        'boutique/ventes_a_valider.html',
        {'ventes': page_obj.object_list, 'page_obj': page_obj},
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
    lignes = vente.lignes.select_related('variante', 'variante__article', 'mouvement')
    return render(
        request,
        'boutique/vente_detail.html',
        {'vente': vente, 'lignes': lignes},
    )


@require_permission('boutique.validate_vente')
@require_POST
def vente_approuver(request, pk):
    peri = _perimetre(request.user)
    vente = get_object_or_404(
        Vente.objects.filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    try:
        VenteService.approuver(vente, par=request.user)
        messages.success(request, f'Vente {vente.numero} approuvée. Le stock a été diminué.')
        return redirect(reverse('boutique:vente_imprimer', kwargs={'pk': vente.pk}) + '?auto=1')
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
    return redirect('boutique:vente_detail', pk=vente.pk)


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
    commentaire = request.POST.get('commentaire', '')
    try:
        VenteService.annuler(vente, par=request.user, commentaire=commentaire)
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
            'lignes': vente.lignes.select_related('variante', 'variante__article'),
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
    q = request.GET.get('q', '')
    if q:
        inventaires_qs = inventaires_qs.filter(Q(numero__icontains=q))
    page_obj = _paginer(request, inventaires_qs.order_by('-date_inventaire'))
    return render(
        request,
        'boutique/inventaires.html',
        {'inventaires': page_obj.object_list, 'page_obj': page_obj, 'q': q},
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
    lignes_qs = inventaire.lignes.select_related(
        'variante', 'variante__article', 'variante__categorie', 'mouvement')

    q = request.GET.get('q', '')
    categorie = request.GET.get('categorie', '')
    ecart = request.GET.get('ecart', '')
    motif = request.GET.get('motif', '')
    if q:
        lignes_qs = lignes_qs.filter(
            Q(variante__article__code__icontains=q)
            | Q(variante__article__designation__icontains=q)
        )
    if categorie:
        lignes_qs = lignes_qs.filter(variante__categorie_id=categorie)
    if ecart == 'avec':
        lignes_qs = lignes_qs.exclude(stock_systeme=F('stock_physique'))
    elif ecart == 'sans':
        lignes_qs = lignes_qs.filter(stock_systeme=F('stock_physique'))
    if motif:
        lignes_qs = lignes_qs.filter(motif__icontains=motif)

    formset = None
    page_obj = None
    if inventaire.statut == InventaireBoutique.Statut.BROUILLON:
        formset = LigneInventaireFormSet(
            request.POST if request.method == 'POST' else None,
            instance=inventaire,
        )
        if request.method == 'POST' and formset.is_valid():
            formset.save()
            messages.success(request, 'Quantités physiques enregistrées.')
            return redirect('boutique:inventaire_detail', pk=inventaire.pk)
        lignes = lignes_qs
    else:
        page_obj = _paginer(request, lignes_qs.order_by('variante__article__code'))
        lignes = page_obj.object_list

    categories = CategorieBoutique.objects.filter(
        pk__in=lignes_qs.values('variante__categorie'))
    return render(
        request,
        'boutique/inventaire_detail.html',
        {
            'inventaire': inventaire,
            'formset': formset,
            'lignes': lignes,
            'page_obj': page_obj,
            'categories': categories,
            'q': q,
            'categorie': categorie,
            'ecart': ecart,
            'motif': motif,
        },
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
        nb_ajustes = inventaire.lignes.filter(mouvement__isnull=False).count()
        messages.success(
            request,
            f'Inventaire {inventaire.numero} validé avec succès. '
            f'{nb_ajustes} variante(s) présentent un écart et ont été ajustées.',
        )
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
    return redirect('boutique:inventaire_detail', pk=inventaire.pk)
