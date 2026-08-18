"""Services métier Boutique — transactions + audit (module 'BOUTIQUE')."""

from django.core.exceptions import ValidationError
from django.db import transaction

from core.services import AuditService

from .models import (
    ArticleBoutique,
    InventaireBoutique,
    LigneInventaireBoutique,
    MouvementStockBoutique,
    StockBoutique,
    Vente,
    VenteLigne,
)


class StockBoutiqueService:
    """Opérations sur le stock boutique : toute variation = mouvement + stock,
    dans une même transaction avec verrouillage de la ligne de stock."""

    @staticmethod
    def _executer(*, article, succursale, domaine, type_, quantite,
                  utilisateur, reference='', motif='', action_audit):
        with transaction.atomic():
            stock = StockBoutique.obtenir(article, succursale, domaine)
            mouvement = MouvementStockBoutique(
                article=article,
                stock=stock,
                type=type_,
                quantite=quantite,
                reference=reference,
                motif=motif,
                utilisateur=utilisateur,
            )
            mouvement.valider()
            AuditService.auditer(
                utilisateur=utilisateur,
                succursale=succursale,
                module='BOUTIQUE',
                action=action_audit,
                objet_type='StockBoutique',
                objet_id=stock.pk,
                ancienne_valeur={'quantite': mouvement.stock_avant},
                nouvelle_valeur={'quantite': mouvement.stock_apres, 'article': article.code},
                motif=motif,
            )
            return mouvement

    @staticmethod
    def entrer(*, article, succursale, domaine, quantite, utilisateur, reference='', motif=''):
        if quantite <= 0:
            raise ValidationError('La quantité d’une entrée doit être positive.')
        return StockBoutiqueService._executer(
            article=article, succursale=succursale, domaine=domaine,
            type_=MouvementStockBoutique.Type.ENTREE, quantite=quantite,
            utilisateur=utilisateur, reference=reference, motif=motif,
            action_audit='stock.entree',
        )

    @staticmethod
    def sortir(*, article, succursale, domaine, quantite, utilisateur, reference='', motif=''):
        if quantite <= 0:
            raise ValidationError('La quantité d’une sortie doit être positive.')
        return StockBoutiqueService._executer(
            article=article, succursale=succursale, domaine=domaine,
            type_=MouvementStockBoutique.Type.SORTIE, quantite=quantite,
            utilisateur=utilisateur, reference=reference, motif=motif,
            action_audit='stock.sortie',
        )

    @staticmethod
    def ajuster(*, article, succursale, domaine, quantite, utilisateur, reference='', motif=''):
        if quantite == 0:
            raise ValidationError('Un ajustement ne peut pas être nul.')
        return StockBoutiqueService._executer(
            article=article, succursale=succursale, domaine=domaine,
            type_=MouvementStockBoutique.Type.AJUSTEMENT, quantite=quantite,
            utilisateur=utilisateur, reference=reference, motif=motif,
            action_audit='stock.ajustement',
        )


class VenteService:
    """Cycle de vie d'une vente (création → validation → stock boutique)."""

    @staticmethod
    def creer(*, succursale, domaine, utilisateur, client='', type_paiement='ESPECES', montant_recu=0, remise=0):
        with transaction.atomic():
            vente = Vente.objects.create(
                numero=Vente.prochain_numero(),
                client=client,
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
            vente.valider()  # lève une ValidationError si stock insuffisant / prix hors bornes
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


class InventaireBoutiqueService:
    """Cycle de vie d'un inventaire boutique (création → validation → ajustements)."""

    @staticmethod
    def creer(*, date_inventaire, succursale, domaine, utilisateur, commentaire='',
              portee='COMPLET', article=None):
        with transaction.atomic():
            inventaire = InventaireBoutique.objects.create(
                numero=InventaireBoutique.prochain_numero(),
                date_inventaire=date_inventaire,
                succursale=succursale,
                domaine=domaine,
                responsable=utilisateur,
                commentaire=commentaire,
                portee=portee,
            )
            if portee == 'UN_ARTICLE':
                articles = [article] if article else []
            else:
                articles = list(ArticleBoutique.objects.filter(
                    succursale=succursale, domaine=domaine))
            for art in articles:
                stock = StockBoutique.objects.filter(
                    article=art, succursale=succursale, domaine=domaine).first()
                quantite = stock.quantite if stock else 0
                LigneInventaireBoutique.objects.create(
                    inventaire=inventaire,
                    article=art,
                    stock_systeme=quantite,
                    stock_physique=quantite,
                )
            AuditService.auditer(
                utilisateur=utilisateur,
                succursale=succursale,
                module='BOUTIQUE',
                action='inventaire.create',
                objet_type='InventaireBoutique',
                objet_id=inventaire.pk,
                nouvelle_valeur={'numero': inventaire.numero},
            )
        return inventaire

    @staticmethod
    def valider(inventaire, par=None):
        with transaction.atomic():
            inventaire.valider()
            AuditService.auditer(
                utilisateur=par or inventaire.responsable,
                succursale=inventaire.succursale,
                module='BOUTIQUE',
                action='inventaire.validate',
                objet_type='InventaireBoutique',
                objet_id=inventaire.pk,
                nouvelle_valeur={'numero': inventaire.numero, 'statut': 'VALIDE'},
            )
        return inventaire
