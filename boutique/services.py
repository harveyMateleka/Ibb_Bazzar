"""Services métier Boutique — transactions + audit."""

from django.db import transaction

from core.services import AuditService

from .models import Vente, VenteLigne


class VenteService:
    """Cycle de vie d'une vente (création → validation → stock)."""

    @staticmethod
    def creer(*, succursale, domaine, utilisateur, type_paiement='ESPECES', montant_recu=0, remise=0):
        with transaction.atomic():
            vente = Vente.objects.create(
                numero=Vente.prochain_numero(),
                succursale=succursale,
                domaine=domaine,
                utilisateur=utilisateur,
                type_paiement=type_paiement,
                montant_recu=montant_recu,
                remise=remise,
            )
            AuditService.auditer(
                utilisateur=utilisateur,
                succursale=succursale,
                module='BOUTIQUE',
                action='vente.create',
                objet_type='Vente',
                objet_id=vente.pk,
                nouvelle_valeur={'numero': vente.numero, 'domaine': domaine.code if domaine else None},
            )
        return vente

    @staticmethod
    def ajouter_ligne(vente, article, quantite, prix_unitaire, remise=0, par=None):
        with transaction.atomic():
            ligne = VenteLigne.objects.create(
                vente=vente,
                article=article,
                quantite=quantite,
                prix_unitaire=prix_unitaire,
                remise=remise,
            )
            vente.recalculer()
        return ligne

    @staticmethod
    def valider(vente, par=None):
        with transaction.atomic():
            vente.valider()  # lève une ValidationError si le stock est insuffisant
            AuditService.auditer(
                utilisateur=par or vente.utilisateur,
                succursale=vente.succursale,
                module='BOUTIQUE',
                action='vente.validate',
                objet_type='Vente',
                objet_id=vente.pk,
                nouvelle_valeur={'numero': vente.numero, 'total': str(vente.total)},
            )
        return vente

    @staticmethod
    def annuler(vente, par=None):
        with transaction.atomic():
            vente.annuler()
            AuditService.auditer(
                utilisateur=par or vente.utilisateur,
                succursale=vente.succursale,
                module='BOUTIQUE',
                action='vente.cancel',
                objet_type='Vente',
                objet_id=vente.pk,
                nouvelle_valeur={'numero': vente.numero, 'statut': 'ANNULEE'},
            )
        return vente
