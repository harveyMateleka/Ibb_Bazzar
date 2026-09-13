"""Services métier Immobilisations — transactions + audit (module 'ASSET').

Transitions d'état appliquées :
  Affectation   → statut EN_SERVICE (et nouvelle succursale/service/emplacement)
  Déplacement   → nouvelle succursale/service/emplacement (état inchangé)
  Réparation    → déclaration : état A_REPARER / statut EN_REPARATION
                  terminaison : état BON / statut EN_SERVICE
  Casse         → déclaration : état CASSE
                  évaluation : REPARABLE → statut EN_REPARATION
                               REMPLACEMENT → statut STOCKE
                               DECLASSEMENT → statut DECLASSE
  Déclassement  → validation : statut DECLASSE
"""

from datetime import datetime, time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.services import AuditService

from .models import (
    Affectation,
    Casse,
    Declassement,
    Deplacement,
    Immobilisation,
    Reparation,
)


def _verifier_bien_actif(immobilisation):
    """Un bien déclassé est sorti du système : seule l'admin peut le réactiver
    (modification de `statut_administratif`). Aucune opération applicative ne
    doit pouvoir le remettre en service directement."""
    if immobilisation.statut_administratif == Immobilisation.StatutAdministratif.DECLASSE:
        raise ValidationError(
            f'Le bien {immobilisation.code} est déclassé : réactivez-le via '
            'l’admin avant toute opération.'
        )


def _verifier_bien_en_reparation(immobilisation):
    """Règle métier : un bien en réparation ne peut être ni affecté ni déplacé.
    Il peut en revanche être déclaré cassé ou demandé au déclassement."""
    if immobilisation.statut_administratif == Immobilisation.StatutAdministratif.EN_REPARATION:
        raise ValidationError(
            f'Le bien {immobilisation.code} est en réparation : il ne peut pas '
            'être affecté ni déplacé tant que la réparation n’est pas terminée.'
        )


def _accorder_service_et_emplacement(service, emplacement):
    """Un emplacement appartient à un seul service."""
    if emplacement is None:
        return service
    if service is None:
        return emplacement.service
    if emplacement.service_id != service.pk:
        raise ValidationError(
            'L’emplacement doit appartenir au service sélectionné.'
        )
    return service


def _dater_affectation(valeur):
    if valeur is None:
        return timezone.now()
    if isinstance(valeur, datetime):
        return valeur if timezone.is_aware(valeur) else timezone.make_aware(valeur)
    return datetime.combine(valeur, time.min, tzinfo=timezone.get_current_timezone())


def _verifier_bien_valide(immobilisation):
    """Règle : un bien non validé ne peut être ni affecté, ni déplacé, ni réparé,
    ni déclaré cassé, ni déclassé. Seule la validation (soumettre/valider) agit."""
    if immobilisation.statut_validation != Immobilisation.StatutValidation.VALIDE:
        raise ValidationError(
            f'Le bien {immobilisation.code} n’est pas validé : il doit être '
            'validé avant toute opération.'
        )


def _affectation_source(immobilisation, *, affectation=None, service=None, emplacement=None):
    if affectation is not None:
        return affectation
    if service is None and emplacement is None:
        return None
    filtres = {'actif': True}
    if service is not None:
        filtres['service'] = service
    if emplacement is not None:
        filtres['emplacement'] = emplacement
    return (
        immobilisation.affectations.filter(**filtres)
        .order_by('date_affectation')
        .first()
    )


def _verifier_quantite_affectation(source, qte):
    if qte > source.quantite:
        raise ValidationError(
            f'Il n’y a que {source.quantite} unité(s) à cet emplacement.'
        )


class ImmobilisationService:
    @staticmethod
    def creer(*, designation, succursale, domaine, categorie=None, numero_serie='',
              valeur_acquisition=0, date_acquisition=None, quantite_achetee=1,
              service=None, emplacement=None, observation='', par,
              periode_entretien=None, duree_vie=None):
        with transaction.atomic():
            immo = Immobilisation.objects.create(
                code=Immobilisation.prochain_numero(),
                designation=designation,
                categorie=categorie,
                numero_serie=numero_serie,
                valeur_acquisition=valeur_acquisition,
                date_acquisition=date_acquisition,
                quantite_achetee=quantite_achetee,
                succursale=succursale,
                domaine=domaine,
                service=service,
                emplacement=emplacement,
                periode_entretien=periode_entretien,
                duree_vie=duree_vie,
                observation=observation,
            )
            AuditService.auditer(
                utilisateur=par,
                succursale=succursale,
                module='ASSET',
                action='asset.create',
                objet_type='Immobilisation',
                objet_id=immo.pk,
                nouvelle_valeur={
                    'code': immo.code,
                    'designation': immo.designation,
                    'valeur_acquisition': str(immo.valeur_acquisition),
                },
            )
            return immo

    @staticmethod
    def soumettre(*, immobilisation, par):
        """Brouillon → En attente de validation."""
        if immobilisation.statut_validation != Immobilisation.StatutValidation.BROUILLON:
            raise ValidationError('Seul un bien en brouillon peut être soumis pour validation.')
        with transaction.atomic():
            immobilisation.statut_validation = Immobilisation.StatutValidation.EN_ATTENTE
            immobilisation.soumis_par = par
            immobilisation.date_soumission = timezone.now()
            immobilisation.save(update_fields=[
                'statut_validation', 'soumis_par', 'date_soumission', 'date_modification'])
            AuditService.auditer(
                utilisateur=par, succursale=immobilisation.succursale, module='ASSET',
                action='asset.submit', objet_type='Immobilisation', objet_id=immobilisation.pk,
                nouvelle_valeur={'code': immobilisation.code, 'validation': 'EN_ATTENTE'},
            )
            return immobilisation

    @staticmethod
    def valider(*, immobilisation, par):
        """En attente → Validé."""
        if immobilisation.statut_validation != Immobilisation.StatutValidation.EN_ATTENTE:
            raise ValidationError('Seul un bien en attente de validation peut être validé.')
        with transaction.atomic():
            immobilisation.statut_validation = Immobilisation.StatutValidation.VALIDE
            immobilisation.valide_par = par
            immobilisation.date_validation = timezone.now()
            immobilisation.motif_rejet = ''
            immobilisation.save(update_fields=[
                'statut_validation', 'valide_par', 'date_validation',
                'motif_rejet', 'date_modification'])
            AuditService.auditer(
                utilisateur=par, succursale=immobilisation.succursale, module='ASSET',
                action='asset.validate', objet_type='Immobilisation', objet_id=immobilisation.pk,
                nouvelle_valeur={'code': immobilisation.code, 'validation': 'VALIDE'},
            )
            return immobilisation

    @staticmethod
    def rejeter(*, immobilisation, par, motif=''):
        """En attente → Rejeté (motif obligatoire)."""
        if immobilisation.statut_validation != Immobilisation.StatutValidation.EN_ATTENTE:
            raise ValidationError('Seul un bien en attente de validation peut être rejeté.')
        if not (motif or '').strip():
            raise ValidationError('Le motif de rejet est obligatoire.')
        with transaction.atomic():
            immobilisation.statut_validation = Immobilisation.StatutValidation.REJETE
            immobilisation.motif_rejet = motif
            immobilisation.save(update_fields=[
                'statut_validation', 'motif_rejet', 'date_modification'])
            AuditService.auditer(
                utilisateur=par, succursale=immobilisation.succursale, module='ASSET',
                action='asset.reject', objet_type='Immobilisation', objet_id=immobilisation.pk,
                nouvelle_valeur={'code': immobilisation.code, 'validation': 'REJETE', 'motif': motif},
            )
            return immobilisation

    @staticmethod
    def valider_plusieurs(*, biens, par):
        """Validation par lots : chaque bien dans sa propre transaction ; seuls
        les biens éligibles (EN_ATTENTE) sont validés, les autres sont ignorés."""
        nb_valides = 0
        nb_ignores = 0
        for bien in biens:
            try:
                ImmobilisationService.valider(immobilisation=bien, par=par)
                nb_valides += 1
            except ValidationError:
                nb_ignores += 1
        return nb_valides, nb_ignores


class AffectationService:
    @staticmethod
    def affecter(*, immobilisation, succursale, service=None, emplacement=None,
                 par, quantite=1, date_affectation=None, commentaire=''):
        if not par:
            raise ValidationError('L’utilisateur qui affecte est obligatoire.')
        _verifier_bien_actif(immobilisation)
        _verifier_bien_en_reparation(immobilisation)
        _verifier_bien_valide(immobilisation)
        service = _accorder_service_et_emplacement(service, emplacement)
        if quantite is None or quantite < 1:
            raise ValidationError('Le nombre à affecter doit être au moins 1.')
        restante = immobilisation.quantite_restante
        if quantite > restante:
            raise ValidationError(
                f'Il ne reste que {restante} unité(s) à affecter '
                f'(achetée(s) : {immobilisation.quantite_achetee}).'
            )
        quand = _dater_affectation(date_affectation)
        with transaction.atomic():
            affectation = Affectation.objects.create(
                immobilisation=immobilisation,
                succursale=succursale,
                service=service,
                emplacement=emplacement,
                quantite=quantite,
                date_affectation=quand,
                commentaire=commentaire or '',
                par=par,
            )
            immobilisation.succursale = succursale
            immobilisation.service = service
            immobilisation.emplacement = emplacement
            immobilisation.statut_administratif = Immobilisation.StatutAdministratif.EN_SERVICE
            immobilisation.save(update_fields=[
                'succursale', 'service', 'emplacement', 'statut_administratif',
                'date_modification',
            ])
            AuditService.auditer(
                utilisateur=par,
                succursale=succursale,
                module='ASSET',
                action='asset.assign',
                objet_type='Immobilisation',
                objet_id=immobilisation.pk,
                nouvelle_valeur={
                    'code': immobilisation.code,
                    'succursale': str(succursale),
                    'service': service.nom if service else '',
                    'emplacement': emplacement.nom if emplacement else '',
                    'quantite': quantite,
                },
            )
            return affectation


class DeplacementService:
    @staticmethod
    def deplacer(*, immobilisation=None, affectation=None, nouvelle_succursale=None,
                 nouveau_service=None, nouvel_emplacement=None, quantite=None,
                 motif='', par):
        if not par:
            raise ValidationError('L’utilisateur qui déplace est obligatoire.')
        source = affectation
        if source is None and immobilisation is not None:
            source = (
                immobilisation.affectations.filter(actif=True)
                .select_related('service', 'emplacement', 'succursale')
                .first()
            )
        if source is None:
            raise ValidationError('Ce bien n’a pas d’affectation à déplacer.')
        immobilisation = source.immobilisation
        _verifier_bien_actif(immobilisation)
        _verifier_bien_en_reparation(immobilisation)
        _verifier_bien_valide(immobilisation)
        nouveau_service = _accorder_service_et_emplacement(
            nouveau_service, nouvel_emplacement)
        if nouvel_emplacement is None:
            raise ValidationError('Le nouvel emplacement est obligatoire.')
        qte = source.quantite if quantite is None else quantite
        if qte < 1:
            raise ValidationError('La quantité à déplacer doit être au moins 1.')
        if qte > source.quantite:
            raise ValidationError(
                f'Il n’y a que {source.quantite} unité(s) à cet emplacement.'
            )
        meme_lieu = (
            source.service_id == (nouveau_service.pk if nouveau_service else None)
            and source.emplacement_id == nouvel_emplacement.pk
        )
        if meme_lieu:
            raise ValidationError('Choisissez un emplacement différent.')
        succursale = nouvelle_succursale or source.succursale
        with transaction.atomic():
            if qte == source.quantite:
                source.actif = False
                source.date_fin = timezone.now()
                source.save(update_fields=['actif', 'date_fin'])
            else:
                source.quantite -= qte
                source.save(update_fields=['quantite'])
            dest = (
                Affectation.objects.filter(
                    immobilisation=immobilisation,
                    actif=True,
                    service=nouveau_service,
                    emplacement=nouvel_emplacement,
                ).first()
            )
            if dest:
                dest.quantite += qte
                dest.save(update_fields=['quantite'])
            else:
                Affectation.objects.create(
                    immobilisation=immobilisation,
                    succursale=succursale,
                    service=nouveau_service,
                    emplacement=nouvel_emplacement,
                    quantite=qte,
                    par=par,
                )
            deplacement = Deplacement.objects.create(
                immobilisation=immobilisation,
                ancienne_succursale=source.succursale,
                nouvelle_succursale=succursale,
                ancien_service=source.service,
                nouveau_service=nouveau_service,
                ancien_emplacement=source.emplacement,
                nouvel_emplacement=nouvel_emplacement,
                quantite=qte,
                motif=motif,
                par=par,
            )
            immobilisation.succursale = succursale
            immobilisation.service = nouveau_service
            immobilisation.emplacement = nouvel_emplacement
            immobilisation.save(update_fields=[
                'succursale', 'service', 'emplacement', 'date_modification',
            ])
            AuditService.auditer(
                utilisateur=par,
                succursale=succursale,
                module='ASSET',
                action='asset.move',
                objet_type='Immobilisation',
                objet_id=immobilisation.pk,
                ancienne_valeur={'emplacement': str(source.emplacement or '')},
                nouvelle_valeur={
                    'emplacement': str(nouvel_emplacement),
                    'quantite': qte,
                },
                motif=motif,
            )
            return deplacement


class ReparationService:
    @staticmethod
    def declarer(*, immobilisation, motif, description='', cout=0, par):
        if not par:
            raise ValidationError('L’utilisateur qui déclare la réparation est obligatoire.')
        _verifier_bien_actif(immobilisation)
        _verifier_bien_valide(immobilisation)
        with transaction.atomic():
            reparation = Reparation.objects.create(
                immobilisation=immobilisation,
                motif=motif,
                description=description,
                cout=cout,
                par=par,
            )
            immobilisation.etat_physique = Immobilisation.EtatPhysique.A_REPARER
            immobilisation.statut_administratif = Immobilisation.StatutAdministratif.EN_REPARATION
            immobilisation.save(update_fields=[
                'etat_physique', 'statut_administratif', 'date_modification'])
            AuditService.auditer(
                utilisateur=par,
                succursale=immobilisation.succursale,
                module='ASSET',
                action='asset.repair',
                objet_type='Immobilisation',
                objet_id=immobilisation.pk,
                nouvelle_valeur={'statut': 'EN_REPARATION', 'motif': motif},
            )
            return reparation

    @staticmethod
    def terminer(*, reparation, par):
        if not par:
            raise ValidationError('L’utilisateur qui termine la réparation est obligatoire.')
        if reparation.statut == Reparation.Statut.TERMINEE:
            raise ValidationError('Cette réparation est déjà terminée.')
        _verifier_bien_actif(reparation.immobilisation)
        _verifier_bien_valide(reparation.immobilisation)
        with transaction.atomic():
            reparation.statut = Reparation.Statut.TERMINEE
            reparation.save(update_fields=['statut'])
            immo = reparation.immobilisation
            immo.etat_physique = Immobilisation.EtatPhysique.BON
            immo.statut_administratif = Immobilisation.StatutAdministratif.EN_SERVICE
            immo.save(update_fields=['etat_physique', 'statut_administratif', 'date_modification'])
            AuditService.auditer(
                utilisateur=par,
                succursale=immo.succursale,
                module='ASSET',
                action='asset.repair',
                objet_type='Immobilisation',
                objet_id=immo.pk,
                nouvelle_valeur={'statut': 'BON / EN_SERVICE'},
            )
            return reparation


class CasseService:
    @staticmethod
    def declarer(*, immobilisation, motif, date_dommage=None, description='',
                 responsable_dommage='', par, service=None, emplacement=None,
                 affectation=None, quantite=1):
        if not par:
            raise ValidationError('Le déclarant est obligatoire.')
        _verifier_bien_actif(immobilisation)
        _verifier_bien_valide(immobilisation)
        qte = 1 if quantite is None else quantite
        if qte < 1:
            raise ValidationError('La quantité cassée doit être au moins 1.')
        source = _affectation_source(
            immobilisation, affectation=affectation,
            service=service, emplacement=emplacement)
        if source is not None:
            _verifier_quantite_affectation(source, qte)
            service = source.service
            emplacement = source.emplacement
        with transaction.atomic():
            casse = Casse.objects.create(
                immobilisation=immobilisation,
                service=service,
                emplacement=emplacement,
                quantite=qte,
                motif=motif,
                date_dommage=date_dommage,
                description=description,
                responsable_dommage=responsable_dommage,
                par=par,
            )
            immobilisation.etat_physique = Immobilisation.EtatPhysique.CASSE
            immobilisation.save(update_fields=['etat_physique', 'date_modification'])
            AuditService.auditer(
                utilisateur=par,
                succursale=immobilisation.succursale,
                module='ASSET',
                action='asset.report_damage',
                objet_type='Immobilisation',
                objet_id=immobilisation.pk,
                nouvelle_valeur={
                    'etat': 'CASSE',
                    'cause': motif,
                    'quantite': qte,
                    'service': service.nom if service else '',
                },
            )
            return casse

    @staticmethod
    def evaluer(*, casse, decision, observation='', par):
        if not decision:
            raise ValidationError('Une décision est obligatoire pour évaluer la casse.')
        with transaction.atomic():
            casse.decision = decision
            casse.observation = observation
            casse.save(update_fields=['decision', 'observation'])
            immo = casse.immobilisation
            if decision == Casse.Decision.REPARABLE:
                immo.statut_administratif = Immobilisation.StatutAdministratif.EN_REPARATION
            elif decision == Casse.Decision.REMPLACEMENT:
                immo.statut_administratif = Immobilisation.StatutAdministratif.STOCKE
            elif decision == Casse.Decision.DECLASSEMENT:
                immo.statut_administratif = Immobilisation.StatutAdministratif.DECLASSE
            immo.save(update_fields=['statut_administratif', 'date_modification'])
            AuditService.auditer(
                utilisateur=par,
                succursale=immo.succursale,
                module='ASSET',
                action='asset.report_damage',
                objet_type='Immobilisation',
                objet_id=immo.pk,
                nouvelle_valeur={'decision': decision},
            )
            return casse


class DeclassementService:
    @staticmethod
    def demander(*, immobilisation, motif, par, service=None, emplacement=None,
                 affectation=None, quantite=1):
        if not par:
            raise ValidationError('Le demandeur est obligatoire.')
        _verifier_bien_actif(immobilisation)
        _verifier_bien_valide(immobilisation)
        qte = 1 if quantite is None else quantite
        if qte < 1:
            raise ValidationError('La quantité à déclasser doit être au moins 1.')
        source = _affectation_source(
            immobilisation, affectation=affectation,
            service=service, emplacement=emplacement)
        if source is not None:
            _verifier_quantite_affectation(source, qte)
            service = source.service
            emplacement = source.emplacement
        with transaction.atomic():
            declassement = Declassement.objects.create(
                immobilisation=immobilisation,
                service=service,
                emplacement=emplacement,
                quantite=qte,
                motif=motif,
                par=par,
            )
            AuditService.auditer(
                utilisateur=par,
                succursale=immobilisation.succursale,
                module='ASSET',
                action='asset.decommission',
                objet_type='Immobilisation',
                objet_id=immobilisation.pk,
                nouvelle_valeur={
                    'declassement': 'DEMANDE',
                    'motif': motif,
                    'quantite': qte,
                    'service': service.nom if service else '',
                },
            )
            return declassement

    @staticmethod
    def valider(*, declassement, par):
        if not par:
            raise ValidationError('Le validateur est obligatoire.')
        if declassement.statut == Declassement.Statut.VALIDE:
            raise ValidationError('Ce déclassement est déjà validé.')
        with transaction.atomic():
            declassement.statut = Declassement.Statut.VALIDE
            declassement.valide_par = par
            declassement.date_validation = timezone.now()
            declassement.save(update_fields=['statut', 'valide_par', 'date_validation'])
            immo = declassement.immobilisation
            # Sans lieu choisi (ancien flux) : le bien entier est déclassé.
            # Avec une affectation : le statut ne change que si tout le lot est déclassé.
            if (
                (declassement.service_id is None and declassement.emplacement_id is None)
                or immo.quantite_declassee >= immo.quantite_achetee
            ):
                immo.statut_administratif = Immobilisation.StatutAdministratif.DECLASSE
                immo.save(update_fields=['statut_administratif', 'date_modification'])
            AuditService.auditer(
                utilisateur=par,
                succursale=immo.succursale,
                module='ASSET',
                action='asset.decommission',
                objet_type='Immobilisation',
                objet_id=immo.pk,
                nouvelle_valeur={'declassement': 'VALIDE'},
            )
            return declassement
