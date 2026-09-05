"""Module Boutique — vues fonctions (FBV).

Architecture : Article → VarianteArticle → StockBoutique → MouvementStockBoutique.
Périmètre = succursales affectées au domaine BOUTIQUE ; succursale/domaine
auto + readonly dans les formulaires via `contexte_actif()` / `appliquer_contexte`.
"""

import calendar
import json
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Domaine, Succursale, User
from core.permissions import require_permission, succursales_autorisees
from core.services import AuditService
from core.stats import bornes_deux_mois, comparaison_mois, compter_entre, filtrer_periode

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
    EmplacementBoutique,
    InventaireBoutique,
    MouvementStockBoutique,
    StockBoutique,
    TypeTissuArticle,
    VarianteArticle,
    Vente,
    VenteLigne,
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


def _payload_variantes_entree(articles_qs):
    """Données JSON pour préremplir le formulaire d'entrée depuis une variante."""
    variantes = (
        VarianteArticle.objects.filter(article__in=articles_qs)
        .select_related('article', 'categorie', 'unite', 'type_tissu')
        .prefetch_related('stocks')
    )
    emplacements = {
        (e.nom, e.etagere.nom): e.pk
        for e in EmplacementBoutique.objects.filter(actif=True).select_related('etagere')
    }
    payload = {}
    for variante in variantes:
        stocks = {str(s.succursale_id): s.quantite for s in variante.stocks.all()}
        payload[str(variante.pk)] = {
            'article': variante.article_id,
            'code': variante.code_variante,
            'designation': variante.article.designation,
            'genre': variante.genre,
            'taille': variante.taille,
            'couleur': variante.couleur,
            'marque': variante.marque,
            'modele': variante.modele,
            'categorie': variante.categorie_id or '',
            'unite': variante.unite_id or '',
            'type_tissu': variante.type_tissu_id or '',
            'tissu': variante.type_tissu.nom if variante.type_tissu_id else '',
            'rayon': variante.rayon,
            'emplacement': emplacements.get((variante.emplacement, variante.etagere), ''),
            'devise': variante.devise,
            'prix_achat': str(variante.prix_achat),
            'prix_unitaire': str(variante.prix_unitaire),
            'prix_minimum': str(variante.prix_minimum),
            'seuil_alerte': variante.seuil_alerte,
            'stocks': stocks,
        }
    return payload


def _snapshot_variante(variante):
    """Recopie les caractéristiques d'une variante existante sur le bon."""
    return {
        'categorie': variante.categorie,
        'sous_categorie': variante.sous_categorie,
        'unite': variante.unite,
        'type_tissu': variante.type_tissu,
        'genre': variante.genre,
        'taille': variante.taille,
        'couleur': variante.couleur,
        'marque': variante.marque,
        'modele': variante.modele,
        'rayon': variante.rayon,
        'etagere': variante.etagere,
        'emplacement': variante.emplacement,
        'devise': variante.devise,
        'prix_achat': variante.prix_achat,
        'prix_unitaire': variante.prix_unitaire,
        'prix_minimum': variante.prix_minimum,
        'seuil_alerte': variante.seuil_alerte,
    }


def _articles_entree(peri):
    """Articles proposés à l'entrée : tout le domaine Boutique.

    La succursale se choisit sur le bon d'entrée, plus sur l'article parent.
    """
    qs = ArticleBoutique.objects.all().order_by('code')
    if peri.get('domaine_id'):
        qs = qs.filter(Q(domaine_id=peri['domaine_id']) | Q(domaine_id__isnull=True))
    return qs


def _variantes_perimetre(peri):
    return VarianteArticle.objects.select_related(
        'article', 'categorie', 'unite', 'type_tissu').filter(
        article__succursale_id__in=peri['succursales_ids'],
        article__domaine_id=peri['domaine_id'],
    )


def _contexte_boutique(user):
    """Contexte du module Boutique : affectation de l'utilisateur au domaine
    BOUTIQUE (préférer la principale), jamais sa principale globale qui peut
    appartenir à un autre domaine (ex. IMMOBILISATIONS) — sinon les formulaires
    de vente/entrée/inventaire ne trouvent aucune variante ni article.
    Repli : première succursale du périmètre boutique."""
    peri = _perimetre(user)
    aff = (
        user.affectations_succursales
        .filter(domaine_id=peri['domaine_id'])
        .select_related('succursale', 'domaine')
        .order_by('-principale', 'date_affectation')
        .first()
    )
    if aff:
        return {
            'succursale': aff.succursale,
            'domaine': aff.domaine,
            'verrouille': not user.is_superuser,
        }
    return {
        'succursale': Succursale.objects.filter(pk__in=peri['succursales_ids']).first(),
        'domaine': peri['domaine'],
        'verrouille': not user.is_superuser,
    }


def _succursale_article(contexte, peri):
    """Succursale à poser sur un nouvel article (plus saisie à l'arrivage)."""
    return (
        (contexte or {}).get('succursale')
        or peri['succursales'].first()
        or Succursale.objects.filter(actif=True).first()
    )


def _paginer(request, qs, par_page=100):
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
    stocks = StockBoutique.objects.select_related(
        'variante', 'variante__article', 'variante__type_tissu').filter(
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
    debut_p, debut_c, fin_c = bornes_deux_mois()
    ventes_ok = ventes_qs.exclude(statut=Vente.Statut.ANNULEE)
    mouvements = MouvementStockBoutique.objects.filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    comparaison = comparaison_mois([
        {
            'label': 'Ventes',
            'precedent': compter_entre(ventes_ok, 'date_vente', debut_p, debut_c),
            'courant': compter_entre(ventes_ok, 'date_vente', debut_c, fin_c),
        },
        {
            'label': 'CA',
            'precedent': float(
                filtrer_periode(ventes_ok, 'date_vente', debut_p, debut_c)
                .aggregate(total=Sum('total'))['total'] or 0
            ),
            'courant': float(
                filtrer_periode(ventes_ok, 'date_vente', debut_c, fin_c)
                .aggregate(total=Sum('total'))['total'] or 0
            ),
        },
        {
            'label': 'Entrées',
            'precedent': compter_entre(
                mouvements.filter(type=MouvementStockBoutique.Type.ENTREE),
                'date_mouvement', debut_p, debut_c,
            ),
            'courant': compter_entre(
                mouvements.filter(type=MouvementStockBoutique.Type.ENTREE),
                'date_mouvement', debut_c, fin_c,
            ),
        },
        {
            'label': 'Sorties',
            'precedent': compter_entre(
                mouvements.filter(type=MouvementStockBoutique.Type.SORTIE),
                'date_mouvement', debut_p, debut_c,
            ),
            'courant': compter_entre(
                mouvements.filter(type=MouvementStockBoutique.Type.SORTIE),
                'date_mouvement', debut_c, fin_c,
            ),
        },
        {
            'label': 'Casses',
            'precedent': compter_entre(
                mouvements.filter(type=MouvementStockBoutique.Type.CASSE),
                'date_mouvement', debut_p, debut_c,
            ),
            'courant': compter_entre(
                mouvements.filter(type=MouvementStockBoutique.Type.CASSE),
                'date_mouvement', debut_c, fin_c,
            ),
        },
        {
            'label': 'Pertes',
            'precedent': compter_entre(
                mouvements.filter(type=MouvementStockBoutique.Type.PERTE),
                'date_mouvement', debut_p, debut_c,
            ),
            'courant': compter_entre(
                mouvements.filter(type=MouvementStockBoutique.Type.PERTE),
                'date_mouvement', debut_c, fin_c,
            ),
        },
    ])
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
            'comparaison': comparaison,
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
    articles_page = page_obj.object_list
    # Variantes par article (texte) pour la colonne « Variantes ».
    variantes_qs = VarianteArticle.objects.select_related('type_tissu').filter(
        article_id__in=articles_page.values('id')).order_by('code_variante')
    variantes_par_article = {}
    for v in variantes_qs:
        variantes_par_article.setdefault(v.article_id, []).append(v.label)
    articles = [
        {'article': a, 'variantes': variantes_par_article.get(a.pk, [])}
        for a in articles_page
    ]
    return render(
        request,
        'boutique/articles.html',
        {'articles': articles, 'page_obj': page_obj, 'q': q},
    )


@require_permission('boutique.adjust_stock')
def article_nouveau(request):
    peri = _perimetre(request.user)
    domaine = (
        Domaine.objects.filter(pk=peri['domaine_id'])
        if peri['domaine_id']
        else Domaine.objects.none()
    )
    contexte = _contexte_boutique(request.user)
    formulaire = ArticleBoutiqueForm(
        request.POST if request.method == 'POST' else None,
        succursales=peri['succursales'],
        domaines=domaine,
        contexte=contexte,
    )
    if request.method == 'POST' and formulaire.is_valid():
        article = formulaire.save(commit=False)
        article.succursale = _succursale_article(contexte, peri)
        if not article.succursale_id:
            formulaire.add_error(
                None,
                'Aucune succursale n’est disponible. Créez-en une avant d’enregistrer un article.',
            )
        else:
            if contexte and contexte.get('verrouille') and contexte.get('domaine'):
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
            messages.success(
                request,
                f'Arrivage {article.code} enregistré. Ajoutez les produits via l’entrée en stock.',
            )
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
    contexte = _contexte_boutique(request.user)
    formulaire = StockEntreeForm(
        request.POST if request.method == 'POST' else None,
        articles=_articles_entree(peri),
        succursales=peri['succursales'],
    )
    if not request.POST and contexte and contexte.get('succursale'):
        formulaire.fields['succursale'].initial = contexte['succursale']
    if request.method == 'POST' and formulaire.is_valid():
        d = formulaire.cleaned_data
        article = d['article']
        succursale = d['succursale']
        variante = d.get('variante')
        if variante:
            snap = _snapshot_variante(variante)
        else:
            snap = {
                'categorie': d.get('categorie'),
                'unite': d.get('unite'),
                'type_tissu': d.get('type_tissu'),
                'genre': d.get('genre', ''),
                'taille': d.get('taille', ''),
                'couleur': d.get('couleur', ''),
                'marque': d.get('marque', ''),
                'modele': d.get('modele', ''),
                'rayon': d.get('rayon', ''),
                'etagere': d['emplacement'].etagere.nom if d.get('emplacement') else '',
                'emplacement': d['emplacement'].nom if d.get('emplacement') else '',
                'devise': d.get('devise', 'FC'),
                'prix_achat': d.get('prix_achat', 0),
                'prix_unitaire': d.get('prix_unitaire', 0),
                'prix_minimum': d.get('prix_minimum', 0),
                'seuil_alerte': d.get('seuil_alerte', 0),
            }
        try:
            bon = BonEntreeService.creer(
                article=article,
                variante=variante,
                succursale=succursale,
                domaine=article.domaine or peri['domaine'],
                quantite=d['quantite'],
                cree_par=request.user,
                **snap,
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
    ).select_related('article', 'variante', 'variante__article', 'variante__type_tissu', 'type_tissu').order_by('-date_creation')[:10]
    return render(
        request,
        'boutique/entree_form.html',
        {
            'form': formulaire,
            'mes_entrees': mes_entrees,
            'variantes_json': _payload_variantes_entree(_articles_entree(peri)),
        },
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
            'article', 'variante', 'cree_par', 'valide_par', 'succursale',
            'categorie', 'unite', 'type_tissu',
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


@require_permission('boutique.cancel_entree')
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
    # L'historique des mouvements garde la recherche/filtres Django (serveur) ET
    # DataTable (pagination/recherche client) sur la page serveur de 100.
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


@require_permission('boutique.view_boutique')
def rapports(request):
    """Centre des rapports de la boutique."""
    return render(request, 'boutique/rapports.html', {
        'utilisateur': request.user,
        'date_generation': timezone.localtime(),
    })


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


@require_permission('boutique.view_vente')
def ventes_report(request):
    """Rapport des ventes : général, journalier (mode=jour), périodique
    (mode=periode) ou mensuel (mode=mois). Filtres succursale/statut/paiement/
    utilisateur toujours bornés au périmètre de l'utilisateur (backend)."""
    peri = _perimetre(request.user)
    qs = Vente.objects.select_related('utilisateur', 'succursale').filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    ).exclude(statut=Vente.Statut.ANNULEE)

    mode = request.GET.get('mode', '')
    jour = request.GET.get('jour', '')
    mois = request.GET.get('mois', '')
    annee = request.GET.get('annee', '')
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')

    if mode == 'jour' and jour:
        date_debut = date_fin = jour
    elif mode == 'mois' and mois and annee:
        m = int(mois)
        a = int(annee)
        date_debut = f'{a}-{m:02d}-01'
        date_fin = f'{a}-{m:02d}-{calendar.monthrange(a, m)[1]:02d}'
    elif not date_debut and not date_fin and request.GET.get('toutes') != '1':
        aujourdhui = timezone.localdate().isoformat()
        date_debut = date_fin = aujourdhui

    if date_debut:
        qs = qs.filter(date_vente__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_vente__date__lte=date_fin)

    succursale_id = request.GET.get('succursale', '')
    statut = request.GET.get('statut', '')
    paiement = request.GET.get('paiement', '')
    utilisateur_id = request.GET.get('utilisateur', '')
    if succursale_id:
        qs = qs.filter(succursale_id=succursale_id)
    if statut:
        qs = qs.filter(statut=statut)
    if paiement:
        qs = qs.filter(type_paiement=paiement)
    if utilisateur_id:
        qs = qs.filter(utilisateur_id=utilisateur_id)

    qs = qs.order_by('date_vente', 'id')
    nb_ventes = qs.count()
    aggs = qs.aggregate(t=Sum('total'), remises=Sum('remise'), recu=Sum('montant_recu'))
    total_montant = aggs['t'] or 0
    total_remises = aggs['remises'] or 0
    total_recu = aggs['recu'] or 0
    utilisateurs = User.objects.filter(
        pk__in=Vente.objects.filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ).values('utilisateur_id'),
    ).order_by('username')
    return render(
        request,
        'boutique/ventes_report.html',
        {
            'ventes': qs,
            'mode': mode,
            'jour': jour,
            'mois': mois,
            'annee': annee,
            'date_debut': date_debut,
            'date_fin': date_fin,
            'succursale_id': succursale_id,
            'succursales': peri['succursales'],
            'statut': statut,
            'paiement': paiement,
            'utilisateur_id': utilisateur_id,
            'statuts': Vente.Statut.choices,
            'paiements': Vente.Paiement.choices,
            'utilisateurs': utilisateurs,
            'mois_list': range(1, 13),
            'nb_ventes': nb_ventes,
            'total_montant': total_montant,
            'total_remises': total_remises,
            'total_recu': total_recu,
            'monnaie': max(total_recu - total_montant, 0),
            'utilisateur': request.user,
            'date_generation': timezone.localtime(),
        },
    )


@require_permission('boutique.view_stock')
def rapport_articles(request):
    """Rapport des articles enregistrés (filtres bornés au périmètre)."""
    peri = _perimetre(request.user)
    qs = _articles_perimetre(peri)
    q = request.GET.get('q', '')
    succursale_id = request.GET.get('succursale', '')
    if q:
        qs = qs.filter(Q(code__icontains=q) | Q(designation__icontains=q))
    if succursale_id:
        qs = qs.filter(succursale_id=succursale_id)
    qs = qs.annotate(nb_var=Count('variantes')).order_by('code')
    return render(
        request,
        'boutique/rapport_articles.html',
        {
            'articles': qs,
            'q': q,
            'succursale_id': succursale_id,
            'succursales': peri['succursales'],
            'nb_articles': qs.count(),
            'utilisateur': request.user,
            'date_generation': timezone.localtime(),
        },
    )


@require_permission('boutique.view_stock')
def rapport_variantes(request):
    """Rapport des variantes (avec quantité disponible par variante)."""
    peri = _perimetre(request.user)
    qs = _variantes_perimetre(peri)
    q = request.GET.get('q', '')
    categorie_id = request.GET.get('categorie', '')
    tissu_id = request.GET.get('tissu', '')
    genre = request.GET.get('genre', '')
    statut = request.GET.get('statut', '')
    if q:
        qs = qs.filter(
            Q(article__code__icontains=q)
            | Q(article__designation__icontains=q)
            | Q(code_variante__icontains=q)
            | Q(couleur__icontains=q)
            | Q(taille__icontains=q)
        )
    if categorie_id:
        qs = qs.filter(categorie_id=categorie_id)
    if tissu_id:
        qs = qs.filter(type_tissu_id=tissu_id)
    if genre:
        qs = qs.filter(genre=genre)
    if statut:
        qs = qs.filter(statut=statut)
    qs = qs.order_by('article__code', 'code_variante')
    stocks = {
        s.variante_id: s.quantite
        for s in StockBoutique.objects.filter(
            variante_id__in=qs.values('id'),
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        )
    }
    for v in qs:
        v.stock_qte = stocks.get(v.pk, 0)
    return render(
        request,
        'boutique/rapport_variantes.html',
        {
            'variantes': qs,
            'q': q,
            'categorie_id': categorie_id,
            'tissu_id': tissu_id,
            'genre': genre,
            'statut': statut,
            'categories': CategorieBoutique.objects.filter(actif=True),
            'tissus': TypeTissuArticle.objects.filter(actif=True),
            'genres': VarianteArticle.Genre.choices,
            'statuts': VarianteArticle.Statut.choices,
            'nb_variantes': qs.count(),
            'utilisateur': request.user,
            'date_generation': timezone.localtime(),
        },
    )


@require_permission('boutique.view_stock')
def rapport_variantes_crees(request):
    """Variantes nouvellement créées sur une période."""
    peri = _perimetre(request.user)
    qs = _variantes_perimetre(peri)
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    if date_debut:
        qs = qs.filter(date_creation__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_creation__date__lte=date_fin)
    qs = qs.order_by('date_creation')
    return render(
        request,
        'boutique/rapport_variantes_crees.html',
        {
            'variantes': qs,
            'date_debut': date_debut,
            'date_fin': date_fin,
            'nb_variantes': qs.count(),
            'utilisateur': request.user,
            'date_generation': timezone.localtime(),
        },
    )


@require_permission('boutique.view_stock')
def rapport_stock(request):
    """État du stock : quantités, seuils, niveaux, filtre par niveau."""
    peri = _perimetre(request.user)
    qs = StockBoutique.objects.select_related(
        'variante', 'variante__article', 'variante__type_tissu').filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    niveau = request.GET.get('niveau', '')
    if niveau == 'rupture':
        qs = qs.filter(quantite__lte=0)
    elif niveau == 'alerte':
        qs = qs.filter(seuil_alerte__gt=0, quantite__gt=0, quantite__lte=F('seuil_alerte'))
    elif niveau == 'vigilance':
        qs = qs.filter(
            seuil_alerte__gt=0,
            quantite__gt=F('seuil_alerte'),
            quantite__lte=F('seuil_alerte') + 10,
        )
    elif niveau == 'disponible':
        qs = (qs.exclude(quantite__lte=0)
              .exclude(seuil_alerte__gt=0, quantite__lte=F('seuil_alerte'))
              .exclude(seuil_alerte__gt=0,
                       quantite__gt=F('seuil_alerte'),
                       quantite__lte=F('seuil_alerte') + 10))
    qs = qs.order_by('variante__article__code', 'variante__code_variante')
    total_qte = qs.aggregate(t=Sum('quantite'))['t'] or 0
    return render(
        request,
        'boutique/rapport_stock.html',
        {
            'stocks': qs,
            'niveau': niveau,
            'niveaux': [('', 'Tous'), ('rupture', 'Rupture'), ('alerte', 'Seuil atteint'),
                        ('vigilance', 'Vigilance'), ('disponible', 'Disponible')],
            'nb_lignes': qs.count(),
            'total_qte': total_qte,
            'utilisateur': request.user,
            'date_generation': timezone.localtime(),
        },
    )


@require_permission('boutique.view_stock')
def rapport_inventaires(request):
    """Inventaires réalisés : nb de variantes et écarts constatés."""
    peri = _perimetre(request.user)
    qs = InventaireBoutique.objects.select_related('succursale', 'responsable').filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    statut = request.GET.get('statut', '')
    if date_debut:
        qs = qs.filter(date_inventaire__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_inventaire__lte=date_fin)
    if statut:
        qs = qs.filter(statut=statut)
    qs = qs.annotate(
        nb_lignes=Count('lignes'),
        ecart_net=Sum(F('lignes__stock_physique') - F('lignes__stock_systeme')),
    ).order_by('-date_inventaire')
    return render(
        request,
        'boutique/rapport_inventaires.html',
        {
            'inventaires': qs,
            'date_debut': date_debut,
            'date_fin': date_fin,
            'statut': statut,
            'statuts': InventaireBoutique.Statut.choices,
            'nb_inventaires': qs.count(),
            'utilisateur': request.user,
            'date_generation': timezone.localtime(),
        },
    )


@require_permission('boutique.create_vente')
def vente_nouvelle(request):
    """Interface UNIQUE de vente : entête + lignes + paiement, puis « Créer et soumettre »."""
    peri = _perimetre(request.user)
    contexte = _contexte_boutique(request.user)
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

    # Panneau droit : variantes disponibles dans le contexte, avec leur stock.
    variantes_qs = _variantes_perimetre(peri)
    if succursale:
        variantes_qs = variantes_qs.filter(article__succursale_id=succursale.pk)
    if domaine:
        variantes_qs = variantes_qs.filter(article__domaine_id=domaine.pk)
    stocks = {
        s.variante_id: s.quantite
        for s in StockBoutique.objects.filter(
            variante_id__in=variantes_qs.values('id'),
            succursale_id=succursale.pk if succursale else None,
            domaine_id=domaine.pk if domaine else None,
        )
    }
    for v in variantes_qs:
        v.stock_qte = stocks.get(v.pk, 0)
    variantes_json = {
        v.pk: {
            'label': str(v),
            'normal': str(v.prix_unitaire),
            'min': str(v.prix_minimum),
            'max': str(v.prix_maximum),
            'stock': stocks.get(v.pk, 0),
        }
        for v in variantes_qs
    }
    if request.method == 'POST' and formulaire.is_valid() and formset.is_valid():
        remise = formulaire.cleaned_data['remise'] or 0
        if not succursale or not domaine:
            messages.error(
                request,
                'Aucune succursale boutique n’est disponible pour votre compte. '
                'Faites-vous affecter au domaine Boutique avant de vendre.',
            )
        elif remise > 0 and not request.user.has_perm('boutique.apply_remise'):
            messages.error(request, 'Vous n’êtes pas autorisé à appliquer une remise.')
        else:
            try:
                vente = VenteService.soumettre(
                    succursale=succursale,
                    domaine=domaine,
                    utilisateur=request.user,
                    client=formulaire.cleaned_data.get('client', ''),
                    type_paiement=formulaire.cleaned_data['type_paiement'],
                    # Le montant reçu n'est plus saisi : posé = total côté service.
                    remise=remise,
                    lignes=formset.lignes_cleaned(),
                    par=request.user,
                )
            except ValidationError as exc:
                # Étape 9 : en cas d'erreur, on ré-affiche le formulaire avec le
                # panier conservé (variantes, quantités, prix proposés) au lieu
                # de rediriger vers un formulaire vide.
                messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
            else:
                if vente.statut == Vente.Statut.PENDING_VALIDATION:
                    messages.success(request, 'Vente créée et soumise à validation.')
                else:
                    messages.success(request, 'Vente créée avec succès.')
                return redirect('boutique:vente_detail', pk=vente.pk)
    return render(
        request,
        'boutique/vente_form.html',
        {
            'form': formulaire,
            'formset': formset,
            'variantes': variantes_qs,
            'variantes_json': json.dumps(variantes_json),
        },
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
def vente_decider_ligne(request, pk, ligne_pk):
    """Le responsable décide d'UNE ligne : valider / rejeter + éventuel prix retenu."""
    peri = _perimetre(request.user)
    vente = get_object_or_404(
        Vente.objects.filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    decision = request.POST.get('decision', VenteLigne.StatutLigne.VALIDEE)
    prix_responsable = request.POST.get('prix_responsable') or None
    try:
        if prix_responsable is not None:
            prix_responsable = Decimal(prix_responsable)
        VenteService.traiter_ligne(
            vente=vente, ligne_pk=ligne_pk, decision=decision,
            prix_responsable=prix_responsable, par=request.user)
        messages.success(request, 'Ligne traitée.')
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
    return redirect('boutique:vente_detail', pk=vente.pk)


@require_permission('boutique.validate_vente')
@require_POST
def vente_traiter(request, pk):
    """Le responsable termine : PENDING_VALIDATION → TRAITEE (aucune sortie de stock)."""
    peri = _perimetre(request.user)
    vente = get_object_or_404(
        Vente.objects.filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    try:
        VenteService.traiter_vente(vente=vente, par=request.user)
        messages.success(request, f'Vente {vente.numero} traitée (en attente de confirmation).')
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
    return redirect('boutique:vente_detail', pk=vente.pk)


@require_permission('boutique.validate_vente')
@require_POST
def vente_modifier_traitement(request, pk):
    """Le responsable revient sur le traitement : TRAITEE → PENDING_VALIDATION
    pour revalider/rejeter des lignes. Aucune sortie de stock à ce stade."""
    peri = _perimetre(request.user)
    vente = get_object_or_404(
        Vente.objects.filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    try:
        VenteService.modifier_traitement(vente=vente, par=request.user)
        messages.success(request, f'Vente {vente.numero} renvoyée en traitement : vous pouvez modifier les décisions de ligne.')
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
    return redirect('boutique:vente_detail', pk=vente.pk)


@require_permission('boutique.create_vente')
@require_POST
def vente_confirmer(request, pk):
    """L'opérateur confirme la vente : TRAITEE → CONFIRMEE (sorties de stock)."""
    peri = _perimetre(request.user)
    vente = get_object_or_404(
        Vente.objects.filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    try:
        VenteService.confirmer(vente=vente, par=request.user)
        messages.success(request, f'Vente {vente.numero} confirmée. Le stock a été diminué.')
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
    """Ticket thermique 80 mm d'une vente. Seule une vente VALIDÉE peut être
    imprimée (le statut est contrôlé côté backend, pas seulement en frontend)."""
    peri = _perimetre(request.user)
    vente = get_object_or_404(
        Vente.objects.select_related('utilisateur', 'succursale').filter(
            succursale_id__in=peri['succursales_ids'],
            domaine_id=peri['domaine_id'],
        ),
        pk=pk,
    )
    if vente.statut not in (Vente.Statut.VALIDEE, Vente.Statut.CONFIRMEE):
        messages.error(
            request,
            f'La vente {vente.numero} n’est pas confirmée : '
            'seules les ventes confirmées peuvent être imprimées.')
        return redirect('boutique:vente_detail', pk=vente.pk)
    return render(
        request,
        'boutique/vente_impression.html',
        {
            'vente': vente,
            # Seules les lignes VALIDÉES figurent au ticket : une ligne rejetée
            # par le responsable n'est ni vendue ni facturée.
            'lignes': vente.lignes.filter(
                statut_ligne=VenteLigne.StatutLigne.VALIDEE,
            ).select_related('variante', 'variante__article'),
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
    contexte = _contexte_boutique(request.user)
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
