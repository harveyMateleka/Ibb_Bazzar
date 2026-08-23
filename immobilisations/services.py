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


class ImmobilisationService:
    @staticmethod
    def creer(*, designation, succursale, domaine, categorie=None, numero_serie='',
              valeur_acquisition=0, date_acquisition=None, fournisseur='',
              service=None, emplacement=None, observation='', par):
        with transaction.atomic():
            immo = Immobilisation.objects.create(
                code=Immobilisation.prochain_numero(),
                designation=designation,
                categorie=categorie,
                numero_serie=numero_serie,
                valeur_acquisition=valeur_acquisition,
                date_acquisition=date_acquisition,
                fournisseur=fournisseur,
                succursale=succursale,
                domaine=domaine,
                service=service,
                emplacement=emplacement,
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


class AffectationService:
    @staticmethod
    def affecter(*, immobilisation, succursale, service=None, emplacement=None, par):
        if not par:
            raise ValidationError('L’utilisateur qui affecte est obligatoire.')
        _verifier_bien_actif(immobilisation)
        _verifier_bien_en_reparation(immobilisation)
        with transaction.atomic():
            # Clôturer l'affectation courante (jamais supprimée).
            Affectation.objects.filter(
                immobilisation=immobilisation, actif=True
            ).update(actif=False, date_fin=timezone.now())
            affectation = Affectation.objects.create(
                immobilisation=immobilisation,
                succursale=succursale,
                service=service,
                emplacement=emplacement,
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
                },
            )
            return affectation


class DeplacementService:
    @staticmethod
    def deplacer(*, immobilisation, nouvelle_succursale, nouveau_service=None,
                 nouvel_emplacement=None, motif='', par):
        if not par:
            raise ValidationError('L’utilisateur qui déplace est obligatoire.')
        _verifier_bien_actif(immobilisation)
        _verifier_bien_en_reparation(immobilisation)
        with transaction.atomic():
            deplacement = Deplacement.objects.create(
                immobilisation=immobilisation,
                ancienne_succursale=immobilisation.succursale,
                nouvelle_succursale=nouvelle_succursale,
                ancien_service=immobilisation.service,
                nouveau_service=nouveau_service,
                ancien_emplacement=immobilisation.emplacement,
                nouvel_emplacement=nouvel_emplacement,
                motif=motif,
                par=par,
            )
            immobilisation.succursale = nouvelle_succursale
            immobilisation.service = nouveau_service
            immobilisation.emplacement = nouvel_emplacement
            immobilisation.save(update_fields=[
                'succursale', 'service', 'emplacement', 'date_modification',
            ])
            AuditService.auditer(
                utilisateur=par,
                succursale=nouvelle_succursale,
                module='ASSET',
                action='asset.move',
                objet_type='Immobilisation',
                objet_id=immobilisation.pk,
                ancienne_valeur={'succursale': str(deplacement.ancienne_succursale)},
                nouvelle_valeur={
                    'succursale': str(nouvelle_succursale),
                    'service': nouveau_service.nom if nouveau_service else '',
                    'emplacement': nouvel_emplacement.nom if nouvel_emplacement else '',
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
    def declarer(*, immobilisation, motif, description='', responsable_dommage='', par):
        if not par:
            raise ValidationError('Le déclarant est obligatoire.')
        _verifier_bien_actif(immobilisation)
        with transaction.atomic():
            casse = Casse.objects.create(
                immobilisation=immobilisation,
                motif=motif,
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
                nouvelle_valeur={'etat': 'CASSE', 'motif': motif},
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
    def demander(*, immobilisation, motif, par):
        if not par:
            raise ValidationError('Le demandeur est obligatoire.')
        _verifier_bien_actif(immobilisation)
        with transaction.atomic():
            declassement = Declassement.objects.create(
                immobilisation=immobilisation,
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
                nouvelle_valeur={'declassement': 'DEMANDE', 'motif': motif},
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
