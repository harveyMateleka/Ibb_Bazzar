from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.permissions import require_permission
from core.stats import bornes_deux_mois, comparaison_mois, compter_entre, filtrer_periode
from facturation.services import encaisser_et_facturer
from .forms import AnnulationForm, CommandeForm, EncaissementForm
from .impression import imprimer_commande_aux_postes
from .models import CategorieMenu, Commande, LigneCommande, Plat, Salle, ServicePoste, Table


def _message_erreur(exc):
    if getattr(exc, 'messages', None):
        return exc.messages[0]
    return str(exc)


def _lignes_poste(service):
    return (
        LigneCommande.objects.filter(
            commande__statut__in=(Commande.Statut.VALIDEE, Commande.Statut.PAYEE),
            statut=LigneCommande.Statut.EN_ATTENTE,
            service=service,
        )
        .select_related(
            'commande',
            'commande__table',
            'commande__table__salle',
            'commande__utilisateur',
            'plat',
        )
        .order_by('commande__date_validation', 'id')
    )


@require_permission('restauration.view_restauration')
def tableau_de_bord(request):
    aujourd_hui = timezone.localdate()
    commandes_jour = Commande.objects.filter(date_ouverture__date=aujourd_hui)
    payees = commandes_jour.filter(statut=Commande.Statut.PAYEE).prefetch_related('lignes')
    ca_jour = sum((commande.total for commande in payees), Decimal('0.00'))
    salles = Salle.objects.prefetch_related(
        Prefetch(
            'tables',
            queryset=Table.objects.prefetch_related(
                Prefetch(
                    'commandes',
                    queryset=Commande.objects.filter(statut__in=Commande.STATUTS_ACTIFS),
                )
            ),
        )
    )
    tables = [table for salle in salles for table in salle.tables.all()]
    nb_occupees = sum(1 for table in tables if table.commande_ouverte())
    debut_p, debut_c, fin_c = bornes_deux_mois()
    commandes = Commande.objects.all()
    payees_mois = Commande.objects.filter(statut=Commande.Statut.PAYEE)

    def _ca(debut, fin):
        return float(sum(
            (commande.total for commande in filtrer_periode(
                payees_mois, 'date_ouverture', debut, fin
            ).prefetch_related('lignes')),
            Decimal('0.00'),
        ))

    comparaison = comparaison_mois([
        {
            'label': 'Commandes',
            'precedent': compter_entre(commandes, 'date_ouverture', debut_p, debut_c),
            'courant': compter_entre(commandes, 'date_ouverture', debut_c, fin_c),
        },
        {
            'label': 'Payées',
            'precedent': compter_entre(payees_mois, 'date_ouverture', debut_p, debut_c),
            'courant': compter_entre(payees_mois, 'date_ouverture', debut_c, fin_c),
        },
        {
            'label': 'CA',
            'precedent': _ca(debut_p, debut_c),
            'courant': _ca(debut_c, fin_c),
        },
        {
            'label': 'Annulées',
            'precedent': compter_entre(
                commandes.filter(statut=Commande.Statut.ANNULEE),
                'date_annulation', debut_p, debut_c,
            ),
            'courant': compter_entre(
                commandes.filter(statut=Commande.Statut.ANNULEE),
                'date_annulation', debut_c, fin_c,
            ),
        },
    ])
    return render(
        request,
        'restauration/tableau_de_bord.html',
        {
            'salles': salles,
            'nb_tables': len(tables),
            'nb_occupees': nb_occupees,
            'nb_ouvertes': commandes_jour.filter(statut__in=Commande.STATUTS_ACTIFS).count(),
            'nb_payees_jour': payees.count(),
            'ca_jour': ca_jour,
            'nb_cuisine': _lignes_poste(ServicePoste.CUISINE).count(),
            'nb_barbecus': _lignes_poste(ServicePoste.BARBECUS).count(),
            'nb_terrasse': _lignes_poste(ServicePoste.TERRASSE).count(),
            'commandes_actives': Commande.objects.filter(
                statut__in=Commande.STATUTS_ACTIFS
            ).select_related('table', 'table__salle', 'utilisateur').prefetch_related('lignes')[:12],
            'comparaison': comparaison,
        },
    )


@require_permission('restauration.view_restauration')
def ecran_cuisine(request):
    return render(
        request,
        'restauration/ecran_poste.html',
        {
            'poste': 'Cuisine',
            'service': ServicePoste.CUISINE,
            'lignes': _lignes_poste(ServicePoste.CUISINE),
            'plats_portions': Plat.objects.filter(
                service=ServicePoste.CUISINE, actif=True
            ).select_related('categorie'),
            'saisie_portions': True,
            'rafraichir': False,
        },
    )


@require_permission('restauration.view_restauration')
def ecran_barbecus(request):
    return render(
        request,
        'restauration/ecran_poste.html',
        {
            'poste': 'Barbecus',
            'service': ServicePoste.BARBECUS,
            'lignes': _lignes_poste(ServicePoste.BARBECUS),
            'plats_portions': Plat.objects.filter(
                service=ServicePoste.BARBECUS, actif=True
            ).select_related('categorie'),
            'saisie_portions': True,
            'rafraichir': False,
        },
    )


@require_permission('restauration.view_restauration')
def ecran_bar(request):
    return redirect('restauration:terrasse')


@require_permission('restauration.view_restauration')
def ecran_terrasse(request):
    return render(
        request,
        'restauration/ecran_poste.html',
        {
            'poste': 'Terrasse',
            'service': ServicePoste.TERRASSE,
            'lignes': _lignes_poste(ServicePoste.TERRASSE),
            'plats_portions': Plat.objects.filter(
                service=ServicePoste.TERRASSE, actif=True
            ).select_related('categorie'),
            'saisie_portions': False,
            'rafraichir': True,
        },
    )


def _redirect_poste_saisie(plat):
    if plat.service == ServicePoste.BARBECUS:
        return redirect('restauration:barbecus')
    return redirect('restauration:cuisine')


@require_permission('restauration.adjust_plat_portions')
@require_POST
def plat_ajouter_portions(request, pk):
    plat = get_object_or_404(
        Plat,
        pk=pk,
        service__in=[ServicePoste.CUISINE, ServicePoste.BARBECUS],
        actif=True,
    )
    try:
        nombre = int(request.POST.get('nombre') or 0)
    except (TypeError, ValueError):
        nombre = 0
    try:
        plat.ajouter_portions(nombre)
        messages.success(
            request,
            f'{plat.nom} : +{nombre} plat(s) préparé(s) (reste {plat.quantite}).',
        )
        _avertir_stock_plat(request, plat)
    except ValidationError as exc:
        messages.error(request, _message_erreur(exc))
    return _redirect_poste_saisie(plat)


@require_permission('restauration.adjust_plat_portions')
@require_POST
def plat_ajuster_quantite(request, pk):
    plat = get_object_or_404(
        Plat,
        pk=pk,
        service__in=[ServicePoste.CUISINE, ServicePoste.BARBECUS],
        actif=True,
    )
    try:
        quantite = int(request.POST.get('quantite') or 0)
    except (TypeError, ValueError):
        quantite = 0
    try:
        plat.ajuster_quantite(quantite)
        messages.success(request, f'{plat.nom} : reste ajusté à {plat.quantite} plat(s).')
        _avertir_stock_plat(request, plat)
    except ValidationError as exc:
        messages.error(request, _message_erreur(exc))
    return _redirect_poste_saisie(plat)


@require_permission('restauration.view_restauration')
def commande_liste(request):
    filtre = request.GET.get('paiement', 'impayee')
    commandes = Commande.objects.select_related(
        'table', 'table__salle', 'utilisateur', 'facture'
    ).prefetch_related('lignes').annotate(nb_lignes=Count('lignes'))
    if filtre == 'payee':
        commandes = commandes.filter(statut=Commande.Statut.PAYEE)
    elif filtre == 'impayee':
        commandes = commandes.filter(statut__in=Commande.STATUTS_ACTIFS)
    elif filtre == 'annulee':
        commandes = commandes.filter(statut=Commande.Statut.ANNULEE)
    nb_impayees = Commande.objects.filter(statut__in=Commande.STATUTS_ACTIFS).count()
    nb_payees = Commande.objects.filter(statut=Commande.Statut.PAYEE).count()
    nb_annulees = Commande.objects.filter(statut=Commande.Statut.ANNULEE).count()
    return render(
        request,
        'restauration/commande_liste.html',
        {
            'commandes': commandes,
            'filtre': filtre,
            'nb_impayees': nb_impayees,
            'nb_payees': nb_payees,
            'nb_annulees': nb_annulees,
        },
    )


@require_permission('restauration.create_commande')
def commande_nouveau(request):
    initial = {
        'serveur': request.user.get_full_name() or request.user.get_username(),
        'source': Commande.Source.TABLETTE,
    }
    formulaire = CommandeForm(
        request.POST if request.method == 'POST' else None,
        initial=initial,
    )
    if request.method == 'POST' and formulaire.is_valid():
        if not Plat.objects.filter(actif=True).exists():
            messages.error(
                request,
                'Créez d’abord des plats dans l’administration (tables de paramètre).',
            )
        else:
            with transaction.atomic():
                commande = formulaire.save(commit=False)
                commande.utilisateur = request.user
                commande.numero = Commande.prochain_numero()
                commande.save()
            return redirect('restauration:commande_detail', pk=commande.pk)
    return render(
        request,
        'restauration/commande_form.html',
        {'form': formulaire},
    )


@require_permission('restauration.create_commande')
def table_ouvrir(request, pk):
    table = get_object_or_404(Table.objects.select_related('salle'), pk=pk)
    ouverte = table.commande_ouverte()
    if ouverte:
        return redirect('restauration:commande_detail', pk=ouverte.pk)
    if request.method != 'POST':
        return redirect('restauration:dashboard')
    if not Plat.objects.filter(actif=True).exists():
        messages.error(
            request,
            'Créez d’abord des plats dans l’administration (tables de paramètre).',
        )
        return redirect('restauration:dashboard')
    with transaction.atomic():
        commande = Commande.objects.create(
            numero=Commande.prochain_numero(),
            table=table,
            utilisateur=request.user,
            serveur=request.user.get_full_name() or request.user.get_username(),
            source=Commande.Source.TABLETTE,
        )
    return redirect('restauration:commande_detail', pk=commande.pk)


@require_permission('restauration.view_restauration')
def commande_detail(request, pk):
    commande = get_object_or_404(
        Commande.objects.select_related(
            'table', 'table__salle', 'utilisateur', 'validee_par', 'annulee_par', 'facture'
        ).prefetch_related('lignes__plat', 'lignes__servi_par'),
        pk=pk,
    )
    categories = CategorieMenu.objects.prefetch_related(
        Prefetch('plats', queryset=Plat.objects.filter(actif=True).select_related('imprimante'))
    )
    dialog_stock = request.session.pop('dialog_stock_indisponible', None)
    deja_par_plat = {}
    for ligne in commande.lignes.all():
        deja_par_plat[ligne.plat_id] = deja_par_plat.get(ligne.plat_id, 0) + ligne.quantite
    return render(
        request,
        'restauration/commande_detail.html',
        {
            'commande': commande,
            'categories': categories,
            'deja_par_plat': deja_par_plat,
            'encaissement_form': EncaissementForm(),
            'annulation_form': AnnulationForm(),
            'dialog_stock': dialog_stock,
            'peut_annuler': (
                commande.statut == Commande.Statut.OUVERTE
                and request.user.has_perm('restauration.cancel_commande')
            ) or (
                commande.statut == Commande.Statut.VALIDEE
                and request.user.is_superuser
            ),
            'peut_modifier': commande.modifiable and request.user.has_perm('restauration.modify_commande'),
            'stock_deja_reserve': commande.stock_deja_reserve,
            'peut_valider': (
                commande.statut == Commande.Statut.OUVERTE
                and request.user.has_perm('restauration.validate_commande')
            ),
            'peut_imprimer_ajouts': (
                commande.statut in (Commande.Statut.VALIDEE, Commande.Statut.SERVIE)
                and commande.a_des_lignes_imprimees
                and commande.a_des_ajouts_a_imprimer
                and request.user.has_perm('restauration.validate_commande')
            ),
        },
    )


def _avertir_stock_plat(request, plat):
    plat.refresh_from_db(fields=['quantite', 'seuil_alerte', 'nom'])
    if plat.quantite <= 0:
        messages.warning(request, f'{plat.nom} : plus aucune portion disponible.')
    elif plat.en_alerte:
        messages.warning(request, f'{plat.nom} : il ne reste que {plat.quantite} portion(s).')


def _commande_modifiable(request, pk):
    commande = get_object_or_404(Commande, pk=pk)
    if not commande.modifiable:
        messages.error(
            request,
            'Cette commande est clôturée : plus d’ajout possible. '
            'L’encaissement se fait dans la facturation.',
        )
        return None
    return commande


def _ligne_non_imprimee(commande, plat, note=''):
    return commande.lignes.filter(
        plat=plat,
        note=note,
        imprimee=False,
    ).exclude(statut=LigneCommande.Statut.ANNULEE).first()


def _quantite_deja_commandee(commande, plat):
    total = 0
    for ligne in commande.lignes.exclude(statut=LigneCommande.Statut.ANNULEE):
        if ligne.plat_id == plat.pk:
            total += ligne.quantite
    return total


def _appliquer_ajout_stock(commande, plat, nombre, deja):
    if commande.stock_deja_reserve:
        if plat.quantite < nombre:
            raise ValidationError(
                f'{plat.nom} : il ne reste que {plat.quantite} portion(s).'
            )
        plat.reserver(nombre)
    else:
        if deja + nombre > plat.quantite:
            raise ValidationError(
                f'{plat.nom} : il ne reste que {plat.quantite} portion(s).'
            )
        plat.verifier_disponible(deja + nombre)


def _signaler_stock_insuffisant(request, plat):
    request.session['dialog_stock_indisponible'] = {
        'nom': plat.nom,
        'disponible': plat.quantite,
        'plat_id': plat.pk,
    }


@require_permission('restauration.modify_commande')
@require_POST
def commande_ajouter_plat(request, pk):
    commande = _commande_modifiable(request, pk)
    if commande is None:
        return redirect('restauration:commande_detail', pk=pk)
    plat = get_object_or_404(
        Plat.objects.select_related('imprimante'),
        pk=request.POST.get('plat'),
        actif=True,
    )
    try:
        nombre = int(request.POST.get('quantite') or 0)
    except (TypeError, ValueError):
        nombre = 0
    if nombre <= 0:
        return redirect('restauration:commande_detail', pk=commande.pk)
    if plat.quantite <= 0:
        _signaler_stock_insuffisant(request, plat)
        return redirect('restauration:commande_detail', pk=commande.pk)
    deja = _quantite_deja_commandee(commande, plat)
    ligne = _ligne_non_imprimee(commande, plat)
    try:
        with transaction.atomic():
            _appliquer_ajout_stock(commande, plat, nombre, deja)
            if ligne:
                ligne.quantite += nombre
                champs = ['quantite']
                if commande.stock_deja_reserve:
                    ligne.stock_consomme = True
                    ligne.figer_destination()
                    champs += ['stock_consomme', 'service', 'imprimante_nom', 'devise', 'designation', 'description_plat']
                ligne.save(update_fields=champs)
            else:
                ligne = LigneCommande(
                    commande=commande,
                    plat=plat,
                    quantite=nombre,
                    prix_unitaire=plat.prix,
                    devise=plat.devise,
                    stock_consomme=commande.stock_deja_reserve,
                )
                ligne.figer_destination()
                ligne.save()
    except ValidationError:
        _signaler_stock_insuffisant(request, plat)
    return redirect('restauration:commande_detail', pk=commande.pk)


@require_permission('restauration.modify_commande')
@require_POST
def commande_ligne_plus(request, pk, ligne_pk):
    commande = _commande_modifiable(request, pk)
    if commande is None:
        return redirect('restauration:commande_detail', pk=pk)
    ligne = get_object_or_404(commande.lignes.select_related('plat'), pk=ligne_pk)
    plat = ligne.plat
    deja = _quantite_deja_commandee(commande, plat)
    cible = ligne if not ligne.imprimee else _ligne_non_imprimee(commande, plat, ligne.note)
    try:
        with transaction.atomic():
            _appliquer_ajout_stock(commande, plat, 1, deja)
            if cible:
                cible.quantite += 1
                champs = ['quantite']
                if commande.stock_deja_reserve:
                    cible.stock_consomme = True
                    champs.append('stock_consomme')
                cible.save(update_fields=champs)
            else:
                ajout = LigneCommande(
                    commande=commande,
                    plat=plat,
                    quantite=1,
                    prix_unitaire=plat.prix,
                    devise=plat.devise,
                    note=ligne.note,
                    stock_consomme=commande.stock_deja_reserve,
                )
                ajout.figer_destination()
                ajout.save()
    except ValidationError:
        _signaler_stock_insuffisant(request, plat)
    return redirect('restauration:commande_detail', pk=commande.pk)


@require_permission('restauration.modify_commande')
@require_POST
def commande_ligne_moins(request, pk, ligne_pk):
    commande = _commande_modifiable(request, pk)
    if commande is None:
        return redirect('restauration:commande_detail', pk=pk)
    ligne = get_object_or_404(commande.lignes.select_related('plat'), pk=ligne_pk)
    if ligne.imprimee:
        messages.error(request, 'Ce plat a déjà été envoyé en cuisine : retirez seulement un ajout non imprimé.')
        return redirect('restauration:commande_detail', pk=commande.pk)
    if ligne.statut == LigneCommande.Statut.SERVIE:
        messages.error(request, 'Une ligne déjà servie ne peut plus être diminuée.')
        return redirect('restauration:commande_detail', pk=commande.pk)
    with transaction.atomic():
        if commande.stock_deja_reserve:
            ligne.plat.liberer(1)
        if ligne.quantite <= 1:
            ligne.delete()
        else:
            ligne.quantite -= 1
            ligne.save(update_fields=['quantite'])
    return redirect('restauration:commande_detail', pk=commande.pk)


@require_permission('restauration.modify_commande')
@require_POST
def commande_ligne_supprimer(request, pk, ligne_pk):
    commande = _commande_modifiable(request, pk)
    if commande is None:
        return redirect('restauration:commande_detail', pk=pk)
    ligne = get_object_or_404(commande.lignes.select_related('plat'), pk=ligne_pk)
    if ligne.imprimee:
        messages.error(request, 'Ce plat a déjà été envoyé en cuisine : il ne peut plus être retiré.')
        return redirect('restauration:commande_detail', pk=commande.pk)
    if ligne.statut == LigneCommande.Statut.SERVIE:
        messages.error(request, 'Une ligne déjà servie ne peut plus être retirée.')
        return redirect('restauration:commande_detail', pk=commande.pk)
    with transaction.atomic():
        if commande.stock_deja_reserve:
            ligne.plat.liberer(ligne.quantite)
        ligne.delete()
    return redirect('restauration:commande_detail', pk=commande.pk)


@require_permission('restauration.validate_commande')
@require_POST
def commande_valider(request, pk):
    commande = get_object_or_404(Commande, pk=pk)
    if commande.statut != Commande.Statut.OUVERTE:
        return redirect('restauration:commande_tickets', pk=commande.pk)
    try:
        commande.valider(request.user)
        messages.success(
            request,
            f'{commande.numero} validée. Vérifiez l’aperçu des tickets, '
            'puis envoyez-les à l’imprimante de chaque plat.',
        )
        return redirect('restauration:commande_tickets', pk=commande.pk)
    except ValidationError as exc:
        messages.error(request, _message_erreur(exc))
        return redirect('restauration:commande_detail', pk=commande.pk)


@require_permission('restauration.servir_ligne')
@require_POST
def commande_ligne_servir(request, pk, ligne_pk):
    commande = get_object_or_404(Commande, pk=pk)
    ligne = get_object_or_404(commande.lignes, pk=ligne_pk)
    try:
        ligne.marquer_servie(request.user)
        messages.success(request, f'{ligne.plat} marqué comme servi.')
    except ValidationError as exc:
        messages.error(request, _message_erreur(exc))
    suivant = request.POST.get('suivant')
    if suivant == 'cuisine':
        return redirect('restauration:cuisine')
    if suivant in ('bar', 'terrasse'):
        return redirect('restauration:terrasse')
    if suivant == 'barbecus':
        return redirect('restauration:barbecus')
    return redirect('restauration:commande_detail', pk=commande.pk)


@require_permission('restauration.encaisser_commande')
@require_POST
def commande_encaisser(request, pk):
    commande = get_object_or_404(Commande, pk=pk)
    formulaire = EncaissementForm(request.POST)
    if not formulaire.is_valid():
        messages.error(request, 'Choisissez un mode de paiement.')
        return redirect('restauration:commande_detail', pk=commande.pk)
    try:
        facture = encaisser_et_facturer(
            commande,
            request.user,
            formulaire.cleaned_data['mode_paiement'],
        )
        messages.success(
            request,
            f'{commande.numero} payée. Table libérée. Reçu {facture.numero} : '
            'vérifiez l’aperçu avant d’imprimer.',
        )
        return redirect(f"{reverse('facturation:recu', args=[facture.pk])}?auto=0")
    except ValidationError as exc:
        messages.error(request, _message_erreur(exc))
        return redirect('restauration:commande_detail', pk=commande.pk)


@require_permission('restauration.cancel_commande')
@require_POST
def commande_annuler(request, pk):
    commande = get_object_or_404(Commande, pk=pk)
    if commande.statut == Commande.Statut.VALIDEE and not request.user.is_superuser:
        messages.error(
            request,
            'Une commande déjà validée ne peut pas être annulée. '
            'Seul un superuser peut le faire.',
        )
        return redirect('restauration:commande_detail', pk=commande.pk)
    if commande.statut == Commande.Statut.PAYEE:
        messages.error(request, 'Une facture déjà payée ne peut pas être annulée.')
        return redirect('restauration:commande_detail', pk=commande.pk)
    formulaire = AnnulationForm(request.POST)
    if not formulaire.is_valid():
        messages.error(request, 'Indiquez le motif d’annulation.')
        return redirect('restauration:commande_detail', pk=commande.pk)
    try:
        commande.annuler(request.user, formulaire.cleaned_data['motif'])
        messages.success(request, f'{commande.numero} annulée. L’historique est conservé.')
    except ValidationError as exc:
        messages.error(request, _message_erreur(exc))
        return redirect('restauration:commande_detail', pk=commande.pk)
    return redirect('restauration:commandes')


@require_permission('restauration.validate_commande')
def commande_imprimer(request, pk):
    commande = get_object_or_404(
        Commande.objects.select_related('table', 'table__salle', 'utilisateur').prefetch_related(
            'lignes__plat'
        ),
        pk=pk,
    )
    return render(
        request,
        'restauration/commande_impression.html',
        {'commande': commande},
    )


@require_permission('restauration.view_restauration')
def commande_tickets(request, pk):
    commande = get_object_or_404(
        Commande.objects.select_related('table', 'table__salle', 'utilisateur').prefetch_related(
            'lignes__plat'
        ),
        pk=pk,
    )
    groupes = commande.groupes_impression()
    impressions = request.session.pop('impressions_commande', None)
    est_ajout = commande.a_des_lignes_imprimees
    return render(
        request,
        'restauration/commande_tickets.html',
        {
            'commande': commande,
            'groupes': groupes,
            'impressions': impressions,
            'est_ajout': est_ajout,
        },
    )


@require_permission('restauration.validate_commande')
@require_POST
def commande_imprimer_postes(request, pk):
    commande = get_object_or_404(
        Commande.objects.select_related('table', 'table__salle', 'utilisateur').prefetch_related(
            'lignes__plat'
        ),
        pk=pk,
    )
    if commande.statut == Commande.Statut.OUVERTE:
        messages.error(request, 'Validez d’abord la commande avant d’imprimer les tickets des postes.')
        return redirect('restauration:commande_detail', pk=commande.pk)
    service = (request.POST.get('service') or '').strip() or None
    imprimante = request.POST.get('imprimante')
    if imprimante is not None:
        imprimante = imprimante.strip()
    impressions = imprimer_commande_aux_postes(
        commande, service=service, imprimante=imprimante,
    )
    request.session['impressions_commande'] = impressions
    if impressions and all(item['ok'] for item in impressions):
        messages.success(
            request,
            'Ticket(s) envoyé(s) à l’imprimante rattachée au(x) plat(s).',
        )
    elif not impressions:
        if commande.a_des_lignes_imprimees:
            messages.warning(request, 'Aucun nouvel ajout à imprimer : tous les plats ont déjà été envoyés.')
        else:
            messages.warning(request, 'Aucun ticket à envoyer pour cette sélection.')
    else:
        messages.warning(
            request,
            'Certains tickets n’ont pas pu être envoyés. '
            'Enregistrez le nom Windows de chaque imprimante, puis réessayez.',
        )
    return redirect('restauration:commande_tickets', pk=commande.pk)


@require_permission('restauration.view_restauration')
def commande_ticket_service(request, pk, service):
    if service == 'BAR':
        service = ServicePoste.TERRASSE
    if service not in ServicePoste.values:
        return redirect('restauration:commande_detail', pk=pk)
    commande = get_object_or_404(
        Commande.objects.select_related('table', 'table__salle', 'utilisateur').prefetch_related(
            'lignes__plat'
        ),
        pk=pk,
    )
    lignes = [
        ligne for ligne in commande.lignes.all()
        if ligne.service == service
        and ligne.statut != LigneCommande.Statut.ANNULEE
        and not ligne.imprimee
    ]
    return render(
        request,
        'restauration/ticket_service.html',
        {
            'commande': commande,
            'service': service,
            'service_libelle': dict(ServicePoste.choices).get(service, service),
            'lignes': lignes,
            'est_ajout': commande.a_des_lignes_imprimees,
            'auto_print': request.GET.get('print') == '1',
        },
    )
