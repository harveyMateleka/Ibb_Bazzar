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


class BonEntreeService:
    """Entrée en stock en deux temps : enregistrement (brouillon) puis validation.

    Règle : l'unicité porte sur la VARIANTE, pas sur l'entrée. Une nouvelle
    entrée sur une variante existante = RÉAPPROVISIONNEMENT (autorisé) : à la
    validation, la variante est réutilisée, son stock est augmenté et un nouveau
    mouvement est créé — jamais de deuxième variante.
    """

    @staticmethod
    def creer(*, article, succursale, domaine, quantite, cree_par,
              categorie=None, sous_categorie=None, unite=None, genre='', taille='',
              couleur='', marque='', modele='', rayon='', etagere='', emplacement='',
              prix_achat=0, prix_unitaire=0, prix_minimum=0, seuil_alerte=0):
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
        if bon.statut != BonEntreeBoutique.Statut.BROUILLON:
            raise ValidationError(
                f'Cette entrée ne peut pas être validée (statut actuel : '
                f'{bon.get_statut_display()}).')
        if not par:
            raise ValidationError('Le validateur est obligatoire.')
        with transaction.atomic():
            # Réapprovisionnement : réutilise la variante si elle existe déjà,
            # sinon la crée (jamais de deuxième variante pour la même combinaison).
            variante, _ = VarianteService.creer_ou_trouver(
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

    @staticmethod
    def annuler(*, bon, par, commentaire=''):
        """Annulation (rejet) d'une entrée en brouillon par le responsable,
        avec un commentaire obligatoire visible par le demandeur."""
        if bon.statut != BonEntreeBoutique.Statut.BROUILLON:
            raise ValidationError('Seule une entrée en brouillon peut être annulée.')
        if not (commentaire or '').strip():
            raise ValidationError('Le commentaire (raison) est obligatoire pour annuler.')
        with transaction.atomic():
            bon.statut = BonEntreeBoutique.Statut.ANNULEE
            bon.commentaire = commentaire
            bon.save(update_fields=['statut', 'commentaire'])
            AuditService.auditer(
                utilisateur=par,
                succursale=bon.succursale,
                module='BOUTIQUE',
                action='stock.entree.annuler',
                objet_type='BonEntreeBoutique',
                objet_id=bon.pk,
                nouvelle_valeur={'numero': bon.numero, 'statut': 'ANNULEE', 'commentaire': commentaire},
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
    """Cycle de vie d'une vente : soumission unique → VALIDEE (sorties immédiates)
    ou PENDING_VALIDATION (validation responsable) → VALIDEE."""

    @staticmethod
    def _controle_prix_ligne(ligne):
        """Règles de prix par ligne. Retourne 'ok' ou 'pending' ; lève une
        ValidationError si le prix est sous le minimum ou au-dessus de la référence."""
        var = ligne.variante
        if var.prix_minimum and ligne.prix_unitaire < var.prix_minimum:
            raise ValidationError(
                f'Cette variante ne peut pas être vendue en dessous de son prix '
                f'minimum autorisé ({var.prix_minimum}).')
        if ligne.prix_unitaire > var.prix_unitaire:
            raise ValidationError(
                f'Le prix de vente de la variante {var.article.code} ({var.label}) '
                f'({ligne.prix_unitaire}) est supérieur au prix de référence '
                f'autorisé ({var.prix_unitaire}).')
        if ligne.prix_unitaire < var.prix_unitaire:
            return 'pending'
        return 'ok'

    @staticmethod
    def _finaliser(vente, par):
        """Contrôles (prix sur chaque ligne, paiement) puis statut final :
        PENDING_VALIDATION si au moins une ligne est sous la référence, sinon
        VALIDEE avec application immédiate des sorties."""
        lignes = list(vente.lignes.select_related('variante', 'variante__article'))
        if not lignes:
            raise ValidationError('Ajoutez au moins une ligne de produit.')
        needs_validation = False
        for ligne in lignes:
            if VenteService._controle_prix_ligne(ligne) == 'pending':
                needs_validation = True
        if vente.montant_recu < vente.total:
            raise ValidationError(
                f'Le montant reçu ({vente.montant_recu}) est inférieur au total '
                f'({vente.total}). Le paiement est incohérent : saisissez un '
                'montant reçu supérieur ou égal au total.'
            )
        if needs_validation:
            vente.statut = Vente.Statut.PENDING_VALIDATION
            vente.save(update_fields=['statut'])
            AuditService.auditer(
                utilisateur=par, succursale=vente.succursale, module='BOUTIQUE',
                action='vente.submit', objet_type='Vente', objet_id=vente.pk,
                nouvelle_valeur={'numero': vente.numero, 'statut': 'PENDING_VALIDATION'},
            )
        else:
            vente._appliquer_sorties()  # lève si stock insuffisant → rollback
            vente.statut = Vente.Statut.VALIDEE
            vente.date_validation = timezone.now()
            vente.save(update_fields=['statut', 'date_validation'])
            AuditService.auditer(
                utilisateur=par, succursale=vente.succursale, module='BOUTIQUE',
                action='vente.validate', objet_type='Vente', objet_id=vente.pk,
                nouvelle_valeur={'numero': vente.numero, 'total': str(vente.total)},
            )
        return vente

    @staticmethod
    def soumettre(*, succursale, domaine, utilisateur, client='', type_paiement='ESPECES',
                  montant_recu=0, remise=0, lignes=(), par=None):
        """Interface unique : crée la vente + ses lignes, contrôle tout (prix,
        stocks, paiement), détermine le statut et applique les sorties si la
        vente est normale. Tout est atomique (tout ou rien)."""
        with transaction.atomic():
            vente = Vente.objects.create(
                numero=Vente.prochain_numero(),
                client=client,
                succursale=succursale,
                domaine=domaine,
                utilisateur=utilisateur,
                type_paiement=type_paiement,
                montant_recu=montant_recu or 0,
                remise=remise or 0,
            )
            AuditService.auditer(
                utilisateur=utilisateur, succursale=succursale, module='BOUTIQUE',
                action='vente.create', objet_type='Vente', objet_id=vente.pk,
                nouvelle_valeur={'numero': vente.numero, 'domaine': domaine.code if domaine else None},
            )
            for var, quantite, prix in lignes:
                VenteLigne.objects.create(
                    vente=vente, variante=var, quantite=quantite,
                    prix_unitaire=prix)
            vente.recalculer()
            VenteService._finaliser(vente, par or utilisateur)
        return vente

    @staticmethod
    def approuver(vente, par=None):
        """Approuve une vente PENDING_VALIDATION : re-vérifie le stock, crée les
        mouvements SORTIE, décrémente les stocks et passe la vente en VALIDEE."""
        with transaction.atomic():
            if vente.statut != Vente.Statut.PENDING_VALIDATION:
                raise ValidationError(
                    f'Cette vente ne peut pas être approuvée (statut actuel : '
                    f'{vente.get_statut_display()}).')
            if not vente.lignes.exists():
                raise ValidationError('Cette vente n’a aucune ligne.')
            vente._appliquer_sorties()
            vente.statut = Vente.Statut.VALIDEE
            vente.date_validation = timezone.now()
            vente.save(update_fields=['statut', 'date_validation'])
            AuditService.auditer(
                utilisateur=par or vente.utilisateur,
                succursale=vente.succursale, module='BOUTIQUE',
                action='vente.approve', objet_type='Vente', objet_id=vente.pk,
                nouvelle_valeur={'numero': vente.numero, 'statut': 'VALIDEE'},
            )
        return vente

    @staticmethod
    def creer(*, succursale, domaine, utilisateur, client='', type_paiement='ESPECES', montant_recu=0, remise=0):
        """Création d'entête (rétrocompatibilité)."""
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
        """Validation normale d'un brouillon (rétrocompatibilité seed/tests)."""
        with transaction.atomic():
            if vente.statut == Vente.Statut.VALIDEE:
                raise ValidationError('Cette vente est déjà validée.')
            VenteService._finaliser(vente, par or vente.utilisateur)
        return vente

    @staticmethod
    def annuler(vente, par=None, commentaire=''):
        if not (commentaire or '').strip():
            raise ValidationError('Le commentaire (raison) est obligatoire pour annuler.')
        with transaction.atomic():
            vente.annuler(commentaire=commentaire)
            AuditService.auditer(
                utilisateur=par or vente.utilisateur,
                succursale=vente.succursale,
                module='BOUTIQUE',
                action='vente.cancel',
                objet_type='Vente',
                objet_id=vente.pk,
                nouvelle_valeur={'numero': vente.numero, 'statut': 'ANNULEE', 'commentaire': commentaire},
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
