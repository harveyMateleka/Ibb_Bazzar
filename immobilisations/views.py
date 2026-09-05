"""Module Immobilisations — vues fonctions (FBV).

Périmètre : succursales où l'utilisateur est affecté au domaine IMMOBILISATIONS.
L'utilisateur connecté est toujours l'acteur (`par`), jamais l'affectataire.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Domaine, Succursale
from core.permissions import require_permission, succursales_autorisees
from core.stats import bornes_deux_mois, comparaison_mois, compter_entre

from .forms import (
    AffectationForm,
    CasseEvaluationForm,
    CasseForm,
    DeclassementForm,
    DeplacementForm,
    ImmobilisationForm,
    ReparationForm,
)
from .models import (
    Affectation,
    Casse,
    CategorieImmobilisation,
    Declassement,
    Deplacement,
    Immobilisation,
    Reparation,
)
from .services import (
    AffectationService,
    CasseService,
    DeclassementService,
    DeplacementService,
    ImmobilisationService,
    ReparationService,
)


def _perimetre(user):
    domaine = Domaine.objects.filter(code='IMMOBILISATIONS').first()
    succursales = succursales_autorisees(user, domaine=domaine)
    return {
        'succursales': succursales,
        'succursales_ids': list(succursales.values_list('id', flat=True)),
        'domaine': domaine,
        'domaine_id': domaine.pk if domaine else None,
    }


def _peut_voir_declasses(user):
    """Seul un superuser (ou un utilisateur disposant de la permission dédiée)
    voit les biens déclassés."""
    return user.is_superuser or user.has_perm('immobilisations.view_declassified_asset')


def _contexte_immobilisations(user):
    """Contexte du module Immobilisations : affectation de l'utilisateur au
    domaine IMMOBILISATIONS (préférer la principale), jamais sa principale
    globale qui peut appartenir à un autre domaine (ex. BOUTIQUE).
    Repli : première succursale du périmètre immobilisations."""
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


def _biens_perimetre(peri, inclure_declasses=False):
    qs = Immobilisation.objects.select_related('categorie').filter(
        succursale_id__in=peri['succursales_ids'],
        domaine_id=peri['domaine_id'],
    )
    if not inclure_declasses:
        # Un bien déclassé disparaît du système : seuls les privilégiés le voient.
        qs = qs.exclude(statut_administratif=Immobilisation.StatutAdministratif.DECLASSE)
    return qs


def _paginer(request, qs, par_page=100):
    return Paginator(qs, par_page).get_page(request.GET.get('page'))


def _timeline(peri, limite=None):
    """Journal consolidé des opérations du cycle de vie (par date décroissante)."""
    f_immo = dict(immobilisation__succursale_id__in=peri['succursales_ids'],
                  immobilisation__domaine_id=peri['domaine_id'])
    evenements = []
    for a in Affectation.objects.filter(**f_immo).select_related(
            'immobilisation', 'par', 'succursale', 'service', 'emplacement'):
        evenements.append({
            'date': a.date_affectation,
            'type': 'Affectation',
            'bien': a.immobilisation,
            'details': f'→ {a.succursale}' + (f' · {a.service}' if a.service else ''),
            'par': a.par,
        })
    for d in Deplacement.objects.filter(**f_immo).select_related(
            'immobilisation', 'par', 'ancienne_succursale', 'nouvelle_succursale',
            'ancien_service', 'nouveau_service', 'ancien_emplacement', 'nouvel_emplacement'):
        evenements.append({
            'date': d.date_deplacement,
            'type': 'Déplacement',
            'bien': d.immobilisation,
            'details': f'{d.ancienne_succursale} → {d.nouvelle_succursale}',
            'par': d.par,
        })
    for r in Reparation.objects.filter(**f_immo).select_related('immobilisation', 'par'):
        evenements.append({
            'date': r.date_reparation,
            'type': f'Réparation ({r.get_statut_display()})',
            'bien': r.immobilisation,
            'details': r.motif,
            'par': r.par,
        })
    for c in Casse.objects.filter(**f_immo).select_related('immobilisation', 'par'):
        evenements.append({
            'date': c.date_casse,
            'type': 'Casse',
            'bien': c.immobilisation,
            'details': c.motif,
            'par': c.par,
        })
    for d in Declassement.objects.filter(**f_immo).select_related('immobilisation', 'par'):
        evenements.append({
            'date': d.date_demande,
            'type': f'Déclassement ({d.get_statut_display()})',
            'bien': d.immobilisation,
            'details': d.motif,
            'par': d.par,
        })
    evenements.sort(key=lambda e: e['date'], reverse=True)
    return evenements[:limite] if limite else evenements


@require_permission('immobilisations.view_asset')
def tableau_de_bord(request):
    peri = _perimetre(request.user)
    biens = _biens_perimetre(peri, inclure_declasses=_peut_voir_declasses(request.user))
    derniers = biens[:8]
    evenements = _timeline(peri, limite=8)
    debut_p, debut_c, fin_c = bornes_deux_mois()
    ids_biens = list(biens.values_list('pk', flat=True))
    casses = Casse.objects.filter(immobilisation_id__in=ids_biens)
    reparations = Reparation.objects.filter(immobilisation_id__in=ids_biens)
    affectations = Affectation.objects.filter(immobilisation_id__in=ids_biens)
    deplacements = Deplacement.objects.filter(immobilisation_id__in=ids_biens)
    comparaison = comparaison_mois([
        {
            'label': 'Biens créés',
            'precedent': compter_entre(biens, 'date_creation', debut_p, debut_c),
            'courant': compter_entre(biens, 'date_creation', debut_c, fin_c),
        },
        {
            'label': 'Casses',
            'precedent': compter_entre(casses, 'date_casse', debut_p, debut_c),
            'courant': compter_entre(casses, 'date_casse', debut_c, fin_c),
        },
        {
            'label': 'Réparations',
            'precedent': compter_entre(reparations, 'date_reparation', debut_p, debut_c),
            'courant': compter_entre(reparations, 'date_reparation', debut_c, fin_c),
        },
        {
            'label': 'Affectations',
            'precedent': compter_entre(affectations, 'date_affectation', debut_p, debut_c),
            'courant': compter_entre(affectations, 'date_affectation', debut_c, fin_c),
        },
        {
            'label': 'Déplacements',
            'precedent': compter_entre(deplacements, 'date_deplacement', debut_p, debut_c),
            'courant': compter_entre(deplacements, 'date_deplacement', debut_c, fin_c),
        },
    ])
    return render(
        request,
        'immobilisations/tableau_de_bord.html',
        {
            'biens': biens,
            'derniers_biens': derniers,
            'evenements': evenements,
            'nb_biens': biens.count(),
            'nb_en_service': biens.filter(statut_administratif='EN_SERVICE').count(),
            'nb_en_reparation': biens.filter(statut_administratif='EN_REPARATION').count(),
            'nb_declasses': biens.filter(statut_administratif='DECLASSE').count(),
            'nb_casses': biens.filter(etat_physique='CASSE').count(),
            'comparaison': comparaison,
        },
    )


@require_permission('immobilisations.view_asset')
def biens(request):
    peri = _perimetre(request.user)
    peut_voir_declasses = _peut_voir_declasses(request.user)
    afficher = peut_voir_declasses and request.GET.get('declasses') == '1'
    biens_qs = _biens_perimetre(peri, inclure_declasses=afficher)
    q = request.GET.get('q', '')
    etat = request.GET.get('etat', '')
    if q:
        biens_qs = biens_qs.filter(
            Q(code__icontains=q)
            | Q(designation__icontains=q)
            | Q(numero_serie__icontains=q)
        )
    if etat:
        biens_qs = biens_qs.filter(etat_physique=etat)
    page_obj = _paginer(request, biens_qs.order_by('code'))
    return render(
        request,
        'immobilisations/biens.html',
        {
            'biens': page_obj.object_list,
            'page_obj': page_obj,
            'q': q,
            'etat': etat,
            'etats': Immobilisation.EtatPhysique.choices,
            'peut_voir_declasses': peut_voir_declasses,
            'afficher': afficher,
        },
    )


@require_permission('immobilisations.create_asset')
def bien_nouveau(request):
    peri = _perimetre(request.user)
    domaine = (
        Domaine.objects.filter(pk=peri['domaine_id'])
        if peri['domaine_id']
        else Domaine.objects.none()
    )
    contexte = _contexte_immobilisations(request.user)
    formulaire = ImmobilisationForm(
        request.POST if request.method == 'POST' else None,
        succursales=peri['succursales'],
        domaines=domaine,
        contexte=contexte,
    )
    if request.method == 'POST' and formulaire.is_valid():
        donnees = formulaire.cleaned_data
        succursale = donnees.get('succursale')
        domaine_v = donnees.get('domaine')
        if contexte and contexte['verrouille']:
            succursale = contexte['succursale']
            domaine_v = contexte['domaine']
        immo = ImmobilisationService.creer(
            designation=donnees['designation'],
            succursale=succursale,
            domaine=domaine_v,
            categorie=donnees.get('categorie'),
            numero_serie=donnees.get('numero_serie', ''),
            valeur_acquisition=donnees.get('valeur_acquisition', 0),
            date_acquisition=donnees.get('date_acquisition'),
            service=donnees.get('service'),
            emplacement=donnees.get('emplacement'),
            periode_entretien=donnees.get('periode_entretien'),
            duree_vie=donnees.get('duree_vie'),
            observation=donnees.get('observation', ''),
            par=request.user,
        )
        messages.success(request, f'Bien {immo.code} créé avec succès (brouillon).')
        return redirect('immobilisations:bien_detail', pk=immo.pk)
    return render(
        request,
        'immobilisations/bien_form.html',
        {'form': formulaire},
    )


@require_permission('immobilisations.update_asset')
@require_POST
def bien_soumettre(request, pk):
    """Soumet un bien brouillon pour validation."""
    bien = _bien_du_perimetre(request, pk)
    try:
        ImmobilisationService.soumettre(immobilisation=bien, par=request.user)
        messages.success(request, f'Bien {bien.code} soumis pour validation.')
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
    return redirect('immobilisations:bien_detail', pk=bien.pk)


@require_permission('immobilisations.validate_asset')
@require_POST
def bien_valider(request, pk):
    """Valide un bien en attente."""
    bien = _bien_du_perimetre(request, pk)
    try:
        ImmobilisationService.valider(immobilisation=bien, par=request.user)
        messages.success(request, f'Bien {bien.code} validé.')
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
    return redirect('immobilisations:bien_detail', pk=bien.pk)


@require_permission('immobilisations.validate_asset')
@require_POST
def bien_rejeter(request, pk):
    """Rejette un bien en attente (motif obligatoire)."""
    bien = _bien_du_perimetre(request, pk)
    motif = request.POST.get('motif', '')
    try:
        ImmobilisationService.rejeter(immobilisation=bien, par=request.user, motif=motif)
        messages.success(request, f'Bien {bien.code} rejeté.')
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
    return redirect('immobilisations:bien_detail', pk=bien.pk)


@require_permission('immobilisations.validate_asset')
def biens_a_valider(request):
    """Liste des biens en attente de validation (validation individuelle + par lots)."""
    peri = _perimetre(request.user)
    biens = _biens_perimetre(peri).filter(
        statut_validation=Immobilisation.StatutValidation.EN_ATTENTE)
    page_obj = _paginer(request, biens.order_by('code'))
    return render(
        request,
        'immobilisations/biens_a_valider.html',
        {'biens': page_obj.object_list, 'page_obj': page_obj},
    )


@require_permission('immobilisations.validate_asset')
@require_POST
def biens_valider_lot(request):
    """Valide plusieurs biens sélectionnés (seuls les éligibles sont validés)."""
    peri = _perimetre(request.user)
    ids = request.POST.getlist('biens')
    biens = _biens_perimetre(peri).filter(pk__in=ids)
    nb_valides, nb_ignores = ImmobilisationService.valider_plusieurs(
        biens=biens, par=request.user)
    message = f'{nb_valides} bien(s) validé(s).'
    if nb_ignores:
        message += f' {nb_ignores} ignoré(s) (statut inéligible).'
    messages.success(request, message)
    return redirect('immobilisations:biens_a_valider')


@require_permission('immobilisations.view_asset')
def bien_detail(request, pk):
    peri = _perimetre(request.user)
    bien = get_object_or_404(
        _biens_perimetre(
            peri, inclure_declasses=_peut_voir_declasses(request.user)
        ).select_related('categorie'),
        pk=pk,
    )
    affectations = bien.affectations.select_related(
        'succursale', 'par', 'service', 'emplacement')
    deplacements = bien.deplacements.select_related(
        'par', 'ancienne_succursale', 'nouvelle_succursale',
        'ancien_service', 'nouveau_service', 'ancien_emplacement', 'nouvel_emplacement')
    reparations = bien.reparations.select_related('par')
    casses = bien.casses.select_related('par')
    declassements = bien.declassements.select_related('par', 'valide_par')
    return render(
        request,
        'immobilisations/bien_detail.html',
        {
            'bien': bien,
            'affectation_courante': bien.affectation_courante,
            'affectations': affectations,
            'deplacements': deplacements,
            'reparations': reparations,
            'casses': casses,
            'declassements': declassements,
        },
    )


def _bien_du_perimetre(request, pk):
    peri = _perimetre(request.user)
    return get_object_or_404(
        _biens_perimetre(peri, inclure_declasses=_peut_voir_declasses(request.user)),
        pk=pk,
    )


@require_permission('immobilisations.assign_asset')
def affectation_nouvelle(request, pk):
    bien = _bien_du_perimetre(request, pk)
    peri = _perimetre(request.user)
    formulaire = AffectationForm(
        request.POST if request.method == 'POST' else None,
        succursales=peri['succursales'],
        request_user=request.user,
        initial={'succursale': bien.succursale},
    )
    if request.method == 'POST' and formulaire.is_valid():
        try:
            AffectationService.affecter(
                immobilisation=bien,
                succursale=formulaire.cleaned_data['succursale'],
                service=formulaire.cleaned_data.get('service'),
                emplacement=formulaire.cleaned_data.get('emplacement'),
                par=request.user,
            )
            messages.success(request, f'Bien {bien.code} affecté avec succès.')
        except ValidationError as exc:
            messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
        return redirect('immobilisations:bien_detail', pk=bien.pk)
    return render(
        request,
        'immobilisations/affectation_form.html',
        {'form': formulaire, 'bien': bien},
    )


@require_permission('immobilisations.move_asset')
def deplacement_nouveau(request, pk):
    bien = _bien_du_perimetre(request, pk)
    peri = _perimetre(request.user)
    formulaire = DeplacementForm(
        request.POST if request.method == 'POST' else None,
        succursales=peri['succursales'],
        request_user=request.user,
    )
    if request.method == 'POST' and formulaire.is_valid():
        try:
            DeplacementService.deplacer(
                immobilisation=bien,
                nouvelle_succursale=formulaire.cleaned_data['nouvelle_succursale'],
                nouveau_service=formulaire.cleaned_data.get('nouveau_service'),
                nouvel_emplacement=formulaire.cleaned_data.get('nouvel_emplacement'),
                motif=formulaire.cleaned_data.get('motif', ''),
                par=request.user,
            )
            messages.success(request, f'Bien {bien.code} déplacé avec succès.')
        except ValidationError as exc:
            messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
        return redirect('immobilisations:bien_detail', pk=bien.pk)
    return render(
        request,
        'immobilisations/deplacement_form.html',
        {'form': formulaire, 'bien': bien},
    )


@require_permission('immobilisations.repair_asset')
def reparation_declarer(request, pk):
    bien = _bien_du_perimetre(request, pk)
    formulaire = ReparationForm(
        request.POST if request.method == 'POST' else None,
        request_user=request.user,
    )
    if request.method == 'POST' and formulaire.is_valid():
        try:
            ReparationService.declarer(
                immobilisation=bien,
                motif=formulaire.cleaned_data['motif'],
                description=formulaire.cleaned_data.get('description', ''),
                cout=formulaire.cleaned_data.get('cout', 0),
                par=request.user,
            )
            messages.success(request, f'Réparation déclarée pour {bien.code}.')
        except ValidationError as exc:
            messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
        return redirect('immobilisations:bien_detail', pk=bien.pk)
    return render(
        request,
        'immobilisations/reparation_form.html',
        {'form': formulaire, 'bien': bien},
    )


@require_permission('immobilisations.repair_asset')
@require_POST
def reparation_terminer(request, pk, rep_pk):
    bien = _bien_du_perimetre(request, pk)
    reparation = get_object_or_404(
        bien.reparations.filter(statut=Reparation.Statut.EN_COURS), pk=rep_pk)
    try:
        ReparationService.terminer(reparation=reparation, par=request.user)
        messages.success(request, f'Réparation terminée pour {bien.code}.')
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
    return redirect('immobilisations:bien_detail', pk=bien.pk)


@require_permission('immobilisations.report_damage_asset')
def casse_declarer(request, pk):
    bien = _bien_du_perimetre(request, pk)
    formulaire = CasseForm(
        request.POST if request.method == 'POST' else None,
        request_user=request.user,
    )
    if request.method == 'POST' and formulaire.is_valid():
        try:
            CasseService.declarer(
                immobilisation=bien,
                motif=formulaire.cleaned_data['motif'],
                date_dommage=formulaire.cleaned_data.get('date_dommage'),
                description=formulaire.cleaned_data.get('description', ''),
                responsable_dommage=formulaire.cleaned_data.get('responsable_dommage', ''),
                par=request.user,
            )
            messages.success(request, f'Casse déclarée pour {bien.code}.')
        except ValidationError as exc:
            messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
        return redirect('immobilisations:bien_detail', pk=bien.pk)
    return render(
        request,
        'immobilisations/casse_form.html',
        {'form': formulaire, 'bien': bien},
    )


@require_permission('immobilisations.validate_asset')
@require_POST
def casse_evaluer(request, pk, casse_pk):
    bien = _bien_du_perimetre(request, pk)
    casse = get_object_or_404(bien.casses.filter(decision__isnull=True), pk=casse_pk)
    formulaire = CasseEvaluationForm(request.POST, instance=casse)
    if formulaire.is_valid():
        try:
            CasseService.evaluer(
                casse=casse,
                decision=formulaire.cleaned_data['decision'],
                observation=formulaire.cleaned_data.get('observation', ''),
                par=request.user,
            )
            messages.success(request, f'Casse de {bien.code} évaluée.')
        except ValidationError as exc:
            messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
    else:
        messages.error(
            request,
            'Évaluation incomplète : choisissez une décision et enregistrez à nouveau.',
        )
    return redirect('immobilisations:bien_detail', pk=bien.pk)


@require_permission('immobilisations.decommission_asset')
def declassement_demander(request, pk):
    bien = _bien_du_perimetre(request, pk)
    formulaire = DeclassementForm(
        request.POST if request.method == 'POST' else None,
        request_user=request.user,
    )
    if request.method == 'POST' and formulaire.is_valid():
        try:
            DeclassementService.demander(
                immobilisation=bien,
                motif=formulaire.cleaned_data['motif'],
                par=request.user,
            )
            messages.success(request, f'Demande de déclassement enregistrée pour {bien.code}.')
        except ValidationError as exc:
            messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
        return redirect('immobilisations:bien_detail', pk=bien.pk)
    return render(
        request,
        'immobilisations/declassement_form.html',
        {'form': formulaire, 'bien': bien},
    )


@require_permission('immobilisations.validate_asset')
@require_POST
def declassement_valider(request, pk, dec_pk):
    bien = _bien_du_perimetre(request, pk)
    declassement = get_object_or_404(
        bien.declassements.filter(statut=Declassement.Statut.DEMANDE), pk=dec_pk)
    try:
        DeclassementService.valider(declassement=declassement, par=request.user)
        messages.success(request, f'Bien {bien.code} déclassé avec succès.')
    except ValidationError as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', [str(exc)])))
    return redirect('immobilisations:bien_detail', pk=bien.pk)


@require_permission('immobilisations.view_asset')
def etats(request):
    peri = _perimetre(request.user)
    biens_qs = _biens_perimetre(peri, inclure_declasses=_peut_voir_declasses(request.user))
    etat_physique = request.GET.get('etat_physique', '')
    statut = request.GET.get('statut', '')
    if etat_physique:
        biens_qs = biens_qs.filter(etat_physique=etat_physique)
    if statut:
        biens_qs = biens_qs.filter(statut_administratif=statut)
    page_obj = _paginer(request, biens_qs.order_by('code'))
    return render(
        request,
        'immobilisations/etats.html',
        {
            'biens': page_obj.object_list,
            'page_obj': page_obj,
            'etat_physique': etat_physique,
            'statut': statut,
            'etats_physiques': Immobilisation.EtatPhysique.choices,
            'statuts': Immobilisation.StatutAdministratif.choices,
        },
    )


@require_permission('immobilisations.view_asset')
def affectations(request):
    peri = _perimetre(request.user)
    qs = Affectation.objects.select_related(
        'immobilisation', 'succursale', 'par', 'service', 'emplacement').filter(
        immobilisation__succursale_id__in=peri['succursales_ids'],
        immobilisation__domaine_id=peri['domaine_id'],
    )
    page_obj = _paginer(request, qs.order_by('-date_affectation'))
    return render(
        request,
        'immobilisations/affectations.html',
        {'affectations': page_obj.object_list, 'page_obj': page_obj},
    )


@require_permission('immobilisations.view_asset')
def deplacements(request):
    peri = _perimetre(request.user)
    qs = Deplacement.objects.select_related(
        'immobilisation', 'par', 'ancienne_succursale', 'nouvelle_succursale',
        'ancien_service', 'nouveau_service', 'ancien_emplacement', 'nouvel_emplacement').filter(
        immobilisation__succursale_id__in=peri['succursales_ids'],
        immobilisation__domaine_id=peri['domaine_id'],
    )
    page_obj = _paginer(request, qs.order_by('-date_deplacement'))
    return render(
        request,
        'immobilisations/deplacements.html',
        {'deplacements': page_obj.object_list, 'page_obj': page_obj},
    )


@require_permission('immobilisations.view_asset')
def historique(request):
    peri = _perimetre(request.user)
    evenements = _timeline(peri)
    type_ = request.GET.get('type', '')
    q = request.GET.get('q', '')
    if type_:
        evenements = [e for e in evenements if e['type'].startswith(type_)]
    if q:
        evenements = [
            e for e in evenements
            if q.lower() in (e['bien'].code.lower())
            or q.lower() in (e['bien'].designation.lower())
            or q.lower() in e['details'].lower()
        ]
    paginator = Paginator(evenements, 100)
    page = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'immobilisations/historique.html',
        {
            'evenements': page,
            'types': ['Affectation', 'Déplacement', 'Réparation', 'Casse', 'Déclassement'],
            'type': type_,
            'q': q,
        },
    )


@require_permission('immobilisations.view_asset')
def rapports(request):
    """Centre des rapports des immobilisations."""
    return render(request, 'immobilisations/rapports.html', {
        'utilisateur': request.user,
        'date_generation': timezone.localtime(),
    })


@require_permission('immobilisations.view_asset')
def rapport_immobilisations(request):
    """Rapport des biens enregistrés (filtres bornés au périmètre)."""
    peri = _perimetre(request.user)
    qs = _biens_perimetre(peri, inclure_declasses=_peut_voir_declasses(request.user))
    q = request.GET.get('q', '')
    categorie_id = request.GET.get('categorie', '')
    etat = request.GET.get('etat', '')
    statut = request.GET.get('statut', '')
    succursale_id = request.GET.get('succursale', '')
    if q:
        qs = qs.filter(
            Q(code__icontains=q)
            | Q(designation__icontains=q)
            | Q(numero_serie__icontains=q))
    if categorie_id:
        qs = qs.filter(categorie_id=categorie_id)
    if etat:
        qs = qs.filter(etat_physique=etat)
    if statut:
        qs = qs.filter(statut_administratif=statut)
    if succursale_id:
        qs = qs.filter(succursale_id=succursale_id)
    qs = qs.select_related('categorie', 'succursale').order_by('code')
    return render(
        request,
        'immobilisations/rapport_immobilisations.html',
        {
            'biens': qs,
            'q': q,
            'categorie_id': categorie_id,
            'etat': etat,
            'statut': statut,
            'succursale_id': succursale_id,
            'categories': CategorieImmobilisation.objects.filter(actif=True),
            'etats': Immobilisation.EtatPhysique.choices,
            'statuts': Immobilisation.StatutAdministratif.choices,
            'succursales': peri['succursales'],
            'nb_biens': qs.count(),
            'utilisateur': request.user,
            'date_generation': timezone.localtime(),
        },
    )


@require_permission('immobilisations.view_asset')
def rapport_affectations(request):
    """Rapport des affectations (période + statut)."""
    peri = _perimetre(request.user)
    qs = Affectation.objects.select_related(
        'immobilisation', 'succursale', 'par', 'service', 'emplacement').filter(
        immobilisation__succursale_id__in=peri['succursales_ids'],
        immobilisation__domaine_id=peri['domaine_id'],
    )
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    statut = request.GET.get('statut', '')
    if date_debut:
        qs = qs.filter(date_affectation__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_affectation__date__lte=date_fin)
    if statut == 'active':
        qs = qs.filter(actif=True)
    elif statut == 'cloturee':
        qs = qs.filter(actif=False)
    qs = qs.order_by('-date_affectation')
    return render(
        request,
        'immobilisations/rapport_affectations.html',
        {
            'affectations': qs,
            'date_debut': date_debut,
            'date_fin': date_fin,
            'statut': statut,
            'statuts': [('', 'Toutes'), ('active', 'Active'), ('cloturee', 'Clôturée')],
            'nb_affectations': qs.count(),
            'utilisateur': request.user,
            'date_generation': timezone.localtime(),
        },
    )


@require_permission('immobilisations.view_asset')
def rapport_deplacements(request):
    """Rapport des déplacements (période)."""
    peri = _perimetre(request.user)
    qs = Deplacement.objects.select_related(
        'immobilisation', 'par', 'ancienne_succursale', 'nouvelle_succursale').filter(
        immobilisation__succursale_id__in=peri['succursales_ids'],
        immobilisation__domaine_id=peri['domaine_id'],
    )
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    if date_debut:
        qs = qs.filter(date_deplacement__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_deplacement__date__lte=date_fin)
    qs = qs.order_by('-date_deplacement')
    return render(
        request,
        'immobilisations/rapport_deplacements.html',
        {
            'deplacements': qs,
            'date_debut': date_debut,
            'date_fin': date_fin,
            'nb_deplacements': qs.count(),
            'utilisateur': request.user,
            'date_generation': timezone.localtime(),
        },
    )


@require_permission('immobilisations.view_asset')
def rapport_casses(request):
    """Rapport des biens déclarés cassés (période + décision)."""
    peri = _perimetre(request.user)
    qs = Casse.objects.select_related('immobilisation', 'par').filter(
        immobilisation__succursale_id__in=peri['succursales_ids'],
        immobilisation__domaine_id=peri['domaine_id'],
    )
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    decision = request.GET.get('decision', '')
    if date_debut:
        qs = qs.filter(date_casse__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_casse__date__lte=date_fin)
    if decision:
        qs = qs.filter(decision=decision)
    qs = qs.order_by('-date_casse')
    return render(
        request,
        'immobilisations/rapport_casses.html',
        {
            'casses': qs,
            'date_debut': date_debut,
            'date_fin': date_fin,
            'decision': decision,
            'decisions': Casse.Decision.choices,
            'nb_casses': qs.count(),
            'utilisateur': request.user,
            'date_generation': timezone.localtime(),
        },
    )


@require_permission('immobilisations.view_asset')
def rapport_etats(request):
    """Rapport par état physique / statut administratif des biens."""
    peri = _perimetre(request.user)
    qs = _biens_perimetre(peri, inclure_declasses=_peut_voir_declasses(request.user))
    etat = request.GET.get('etat_physique', '')
    statut = request.GET.get('statut', '')
    if etat:
        qs = qs.filter(etat_physique=etat)
    if statut:
        qs = qs.filter(statut_administratif=statut)
    qs = qs.select_related('categorie', 'succursale').order_by('code')
    par_etat = [
        (label, qs.filter(etat_physique=choix).count())
        for choix, label in Immobilisation.EtatPhysique.choices
    ]
    return render(
        request,
        'immobilisations/rapport_etats.html',
        {
            'biens': qs,
            'etat': etat,
            'statut': statut,
            'etats': Immobilisation.EtatPhysique.choices,
            'statuts': Immobilisation.StatutAdministratif.choices,
            'par_etat': par_etat,
            'nb_biens': qs.count(),
            'utilisateur': request.user,
            'date_generation': timezone.localtime(),
        },
    )
