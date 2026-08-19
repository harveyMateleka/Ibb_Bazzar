"""Services métier Boutique — Article → Variante → Stock → Mouvement.

Toute opération de stock porte sur une `VarianteArticle` ; le stock et le
mouvement sont créés/mis à jour dans une même transaction avec verrouillage.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.services import AuditService

from .models import (
    ArticleBoutique,
    BonEntreeBoutique,
    InventaireBoutique,
    LigneInventaireBoutique,
    MouvementStockBoutique,
    StockBoutique,
    VarianteArticle,
    Vente,
    VenteLigne,
)


class VarianteService:
    """Création (avec anti-doublon) d'une variante d'article."""

    @staticmethod
    def creer_ou_trouver(*, article, couleur='', taille='', genre='',
                         categorie=None, sous_categorie=None, unite=None,
                         marque='', matiere='', modele='', rayon='', etagere='',
                         emplacement='', prix_achat=0, prix_unitaire=0,
                         prix_minimum=0, prix_maximum=0, seuil_alerte=0,
                         par=None, **kwargs):
        """Retourne (variante, cree).

        `get_or_create` gère la course (TOCTOU) sur l'unicité
        article/couleur/taille/genre : en cas d'IntegrityError concurrent, il
        rattrape l'erreur et refait le `get` (la variante est alors réutilisée
        au lieu de faire planter la transaction).
        """
        defaults = {
            'categorie': categorie,
            'sous_categorie': sous_categorie,
            'unite': unite,
            'marque': marque,
            'matiere': matiere,
            'modele': modele,
            'rayon': rayon,
            'etagere': etagere,
            'emplacement': emplacement,
            # Champs numériques jamais nuls (NULL interdit en base).
            'prix_achat': prix_achat or 0,
            'prix_unitaire': prix_unitaire or 0,
            'prix_minimum': prix_minimum or 0,
            'prix_maximum': prix_maximum or 0,
            'seuil_alerte': seuil_alerte or 0,
        }
        with transaction.atomic():
            variante, cree = VarianteArticle.objects.get_or_create(
                article=article,
                couleur=couleur,
                taille=taille,
                genre=genre,
                defaults=defaults,
            )
            if cree:
                AuditService.auditer(
                    utilisateur=par,
                    succursale=article.succursale,
                    module='BOUTIQUE',
                    action='variante.create',
                    objet_type='VarianteArticle',
                    objet_id=variante.pk,
                    nouvelle_valeur={
                        'article': article.code,
                        'code_variante': variante.code_variante,
                        'couleur': couleur, 'taille': taille, 'genre': genre,
                    },
                )
        return variante, cree

    @staticmethod
    def creer_strict(*, article, couleur='', taille='', genre='',
                     categorie=None, sous_categorie=None, unite=None,
                     marque='', matiere='', modele='', rayon='', etagere='',
                     emplacement='', prix_achat=0, prix_unitaire=0,
                     prix_minimum=0, prix_maximum=0, seuil_alerte=0,
                     par=None):
        """Crée une variante si elle n'existe PAS ; sinon lève une ValidationError.

        Utilisé par l'entrée en stock (pas de réutilisation silencieuse).
        `get_or_create` gère la course concurrente (IntegrityError → re-get) ;
        si la variante existe, on la refuse avec un message clair.
        """
        defaults = {
            'categorie': categorie,
            'sous_categorie': sous_categorie,
            'unite': unite,
            'marque': marque,
            'matiere': matiere,
            'modele': modele,
            'rayon': rayon,
            'etagere': etagere,
            'emplacement': emplacement,
            'prix_achat': prix_achat or 0,
            'prix_unitaire': prix_unitaire or 0,
            'prix_minimum': prix_minimum or 0,
            'prix_maximum': prix_maximum or 0,
            'seuil_alerte': seuil_alerte or 0,
        }
        with transaction.atomic():
            variante, cree = VarianteArticle.objects.get_or_create(
                article=article,
                couleur=couleur,
                taille=taille,
                genre=genre,
                defaults=defaults,
            )
            if not cree:
                raise ValidationError(
                    f'La variante {couleur}/{taille}/{genre} existe déjà pour '
                    f'{article.code}. Elle ne peut pas être soumise pour validation.'
                )
            AuditService.auditer(
                utilisateur=par,
                succursale=article.succursale,
                module='BOUTIQUE',
                action='variante.create',
                objet_type='VarianteArticle',
                objet_id=variante.pk,
                nouvelle_valeur={
                    'article': article.code,
                    'code_variante': variante.code_variante,
                    'couleur': couleur, 'taille': taille, 'genre': genre,
                },
            )
        return variante


class BonEntreeService:
    """Entrée en stock en deux temps : enregistrement (brouillon) puis validation.
    La variante, le stock et le mouvement ne sont créés qu'à la validation."""

    @staticmethod
    def creer(*, article, succursale, domaine, quantite, cree_par,
              categorie=None, sous_categorie=None, unite=None, genre='', taille='',
              couleur='', marque='', modele='', rayon='', etagere='', emplacement='',
              prix_achat=0, prix_unitaire=0, prix_minimum=0, seuil_alerte=0):
        # Refus immédiat : la variante existe déjà → pas de brouillon soumis.
        if VarianteArticle.objects.filter(
            article=article, couleur=couleur, taille=taille, genre=genre,
        ).exists():
            raise ValidationError(
                f'La variante {couleur}/{taille}/{genre} existe déjà pour '
                f'{article.code}. Elle ne peut pas être soumise pour validation.'
            )
        with transaction.atomic():
            bon = BonEntreeBoutique.objects.create(
                numero=BonEntreeBoutique.prochain_numero(),
                article=article,
                succursale=succursale,
                domaine=domaine,
                categorie=categorie,
                sous_categorie=sous_categorie,
                unite=unite,
                genre=genre,
                taille=taille,
                couleur=couleur,
                marque=marque,
                modele=modele,
                rayon=rayon,
                etagere=etagere,
                emplacement=emplacement,
                prix_achat=prix_achat or 0,
                prix_unitaire=prix_unitaire or 0,
                prix_minimum=prix_minimum or 0,
                seuil_alerte=seuil_alerte or 0,
                quantite=quantite,
                cree_par=cree_par,
            )
            AuditService.auditer(
                utilisateur=cree_par,
                succursale=succursale,
                module='BOUTIQUE',
                action='stock.entree.create',
                objet_type='BonEntreeBoutique',
                objet_id=bon.pk,
                nouvelle_valeur={'numero': bon.numero, 'article': article.code, 'quantite': quantite},
            )
            return bon

    @staticmethod
    def valider(*, bon, par):
        if bon.statut == BonEntreeBoutique.Statut.VALIDE:
            raise ValidationError('Cette entrée est déjà validée.')
        if not par:
            raise ValidationError('Le validateur est obligatoire.')
        with transaction.atomic():
            # Refus si la variante existe déjà (lève une ValidationError).
            variante = VarianteService.creer_strict(
                article=bon.article,
                categorie=bon.categorie,
                sous_categorie=bon.sous_categorie,
                unite=bon.unite,
                genre=bon.genre,
                taille=bon.taille,
                couleur=bon.couleur,
                marque=bon.marque,
                modele=bon.modele,
                rayon=bon.rayon,
                etagere=bon.etagere,
                emplacement=bon.emplacement,
                prix_achat=bon.prix_achat,
                prix_unitaire=bon.prix_unitaire,
                prix_minimum=bon.prix_minimum,
                seuil_alerte=bon.seuil_alerte,
                par=par,
            )
            StockBoutiqueService.entrer(
                variante=variante,
                quantite=bon.quantite,
                utilisateur=par,
                motif=f'Validation {bon.numero}',
            )
            bon.statut = BonEntreeBoutique.Statut.VALIDE
            bon.valide_par = par
            bon.date_validation = timezone.now()
            bon.save(update_fields=['statut', 'valide_par', 'date_validation'])
            AuditService.auditer(
                utilisateur=par,
                succursale=bon.succursale,
                module='BOUTIQUE',
                action='stock.entree.validate',
                objet_type='BonEntreeBoutique',
                objet_id=bon.pk,
                nouvelle_valeur={'numero': bon.numero, 'variante': variante.code_variante},
            )
            return bon


class StockBoutiqueService:
    """Opérations sur le stock d'une variante : mouvement + stock, atomiques."""

    @staticmethod
    def _contexte(variante):
        return variante.article.succursale, variante.article.domaine

    @staticmethod
    def _executer(*, variante, type_, quantite, utilisateur, reference='', motif='', action_audit):
        succursale, domaine = StockBoutiqueService._contexte(variante)
        with transaction.atomic():
            stock = StockBoutique.obtenir(variante, succursale, domaine)
            mouvement = MouvementStockBoutique(
                variante=variante,
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
                nouvelle_valeur={'quantite': mouvement.stock_apres, 'variante': variante.code_variante},
                motif=motif,
            )
            return mouvement

    @staticmethod
    def entrer(*, variante, quantite, utilisateur, reference='', motif=''):
        if quantite <= 0:
            raise ValidationError('La quantité d’une entrée doit être positive.')
        return StockBoutiqueService._executer(
            variante=variante, type_=MouvementStockBoutique.Type.ENTREE,
            quantite=quantite, utilisateur=utilisateur,
            reference=reference, motif=motif, action_audit='stock.entree')

    @staticmethod
    def sortir(*, variante, quantite, utilisateur, reference='', motif=''):
        if quantite <= 0:
            raise ValidationError('La quantité d’une sortie doit être positive.')
        return StockBoutiqueService._executer(
            variante=variante, type_=MouvementStockBoutique.Type.SORTIE,
            quantite=quantite, utilisateur=utilisateur,
            reference=reference, motif=motif, action_audit='stock.sortie')

    @staticmethod
    def ajuster(*, variante, quantite, utilisateur, reference='', motif=''):
        if quantite == 0:
            raise ValidationError('Un ajustement ne peut pas être nul.')
        return StockBoutiqueService._executer(
            variante=variante, type_=MouvementStockBoutique.Type.AJUSTEMENT,
            quantite=quantite, utilisateur=utilisateur,
            reference=reference, motif=motif, action_audit='stock.ajustement')


class VenteService:
    """Cycle de vie d'une vente (création → validation → stock des variantes)."""

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
    def ajouter_ligne(vente, variante, quantite, prix_unitaire, remise=0, par=None):
        with transaction.atomic():
            ligne = VenteLigne.objects.create(
                vente=vente,
                variante=variante,
                quantite=quantite,
                prix_unitaire=prix_unitaire,
                remise=remise,
            )
            vente.recalculer()
        return ligne

    @staticmethod
    def valider(vente, par=None):
        with transaction.atomic():
            vente.valider()
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
    """Cycle de vie d'un inventaire boutique (lignes par variante)."""

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
                variantes = list(VarianteArticle.objects.filter(article=article))
            else:
                variantes = list(VarianteArticle.objects.filter(
                    article__succursale=succursale,
                    article__domaine=domaine,
                ))
            for variante in variantes:
                stock = StockBoutique.objects.filter(
                    variante=variante, succursale=succursale, domaine=domaine).first()
                quantite = stock.quantite if stock else 0
                LigneInventaireBoutique.objects.create(
                    inventaire=inventaire,
                    variante=variante,
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
