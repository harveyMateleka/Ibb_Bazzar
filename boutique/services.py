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
                         type_tissu=None,
                         marque='', matiere='', modele='', rayon='', etagere='',
                         emplacement='', devise='FC', prix_achat=0, prix_unitaire=0,
                         prix_minimum=0, prix_maximum=0, seuil_alerte=0,
                         par=None, **kwargs):
        """Retourne (variante, cree).

        L'identité d'une variante = article + couleur + taille + genre + type de
        tissu. `get_or_create` gère la course (TOCTOU) sur cette combinaison : en
        cas d'IntegrityError concurrent, il rattrape l'erreur et refait le `get`
        (la variante est alors réutilisée au lieu de faire planter la transaction).
        """
        defaults = {
            'categorie': categorie,
            'sous_categorie': sous_categorie,
            'unite': unite,
            'type_tissu': type_tissu,
            'marque': marque,
            'matiere': matiere,
            'modele': modele,
            'rayon': rayon,
            'etagere': etagere,
            'emplacement': emplacement,
            'devise': devise or 'FC',
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
                type_tissu=type_tissu,
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
              categorie=None, sous_categorie=None, unite=None, type_tissu=None,
              genre='', taille='',
              couleur='', marque='', modele='', rayon='', etagere='', emplacement='',
              devise='FC', prix_achat=0, prix_unitaire=0, prix_minimum=0, seuil_alerte=0):
        with transaction.atomic():
            bon = BonEntreeBoutique.objects.create(
                numero=BonEntreeBoutique.prochain_numero(),
                article=article,
                succursale=succursale,
                domaine=domaine,
                categorie=categorie,
                sous_categorie=sous_categorie,
                unite=unite,
                type_tissu=type_tissu,
                genre=genre,
                taille=taille,
                couleur=couleur,
                marque=marque,
                modele=modele,
                rayon=rayon,
                etagere=etagere,
                emplacement=emplacement,
                devise=devise or 'FC',
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
                type_tissu=bon.type_tissu,
                genre=bon.genre,
                taille=bon.taille,
                couleur=bon.couleur,
                marque=bon.marque,
                modele=bon.modele,
                rayon=bon.rayon,
                etagere=bon.etagere,
                emplacement=bon.emplacement,
                devise=bon.devise,
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
        """Règles de prix par ligne (sur le PRIX PROPOSÉ). Retourne 'ok' ou
        'pending' ; lève une ValidationError si le prix est sous le minimum ou
        au-dessus du prix normal de la variante."""
        var = ligne.variante
        prix = ligne.prix_propose if ligne.prix_propose is not None else ligne.prix_unitaire
        if var.prix_minimum and prix < var.prix_minimum:
            raise ValidationError(
                f'Cette variante ne peut pas être vendue en dessous de son prix '
                f'minimum autorisé ({var.prix_minimum}).')
        if prix > var.prix_unitaire:
            raise ValidationError(
                f'Le prix proposé de la variante {var.article.code} ({var.label}) '
                f'({prix}) est supérieur au prix de référence autorisé '
                f'({var.prix_unitaire}).')
        if prix < var.prix_unitaire:
            return 'pending'
        return 'ok'

    @staticmethod
    def _finaliser(vente, par):
        """Contrôles (prix sur chaque ligne, paiement) puis statut :
        PENDING_VALIDATION si une ligne est sous la référence (traitement du
        responsable), sinon TRAITEE (prête à être confirmée par l'opérateur).
        AUCUNE sortie de stock ici — seule la confirmation finale les déclenche."""
        lignes = list(vente.lignes.select_related('variante', 'variante__article'))
        if not lignes:
            raise ValidationError('Ajoutez au moins une ligne de produit.')
        needs_traitement = False
        for ligne in lignes:
            if VenteService._controle_prix_ligne(ligne) == 'pending':
                needs_traitement = True
        if vente.montant_recu < vente.total:
            raise ValidationError(
                f'Le montant reçu ({vente.montant_recu}) est inférieur au total '
                f'({vente.total}). Le paiement est incohérent.'
            )
        vente.statut = (
            Vente.Statut.PENDING_VALIDATION if needs_traitement else Vente.Statut.TRAITEE)
        vente.save(update_fields=['statut'])
        AuditService.auditer(
            utilisateur=par, succursale=vente.succursale, module='BOUTIQUE',
            action='vente.submit', objet_type='Vente', objet_id=vente.pk,
            nouvelle_valeur={'numero': vente.numero, 'statut': vente.statut},
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
                    prix_unitaire=var.prix_unitaire,  # prix normal (instantané)
                    prix_propose=prix or var.prix_unitaire,  # prix facturé
                )
            vente.recalculer()
            # Montant reçu non saisi : toujours égal au total de la facture.
            vente.montant_recu = vente.total
            vente.save(update_fields=['montant_recu'])
            VenteService._finaliser(vente, par or utilisateur)
        return vente

    @staticmethod
    def traiter_ligne(*, vente, ligne_pk, decision, prix_responsable=None, par=None):
        """Le responsable traite UNE ligne : VALIDEE ou REJETEE, éventuellement en
        fixant le prix retenu (contrôlé ≥ prix minimum). La décision est enregistrée
        sur la ligne."""
        with transaction.atomic():
            if vente.statut != Vente.Statut.PENDING_VALIDATION:
                raise ValidationError('Seule une vente en attente de traitement est modifiable.')
            ligne = vente.lignes.select_related('variante').get(pk=ligne_pk)
            if decision == VenteLigne.StatutLigne.REJETEE:
                ligne.statut_ligne = VenteLigne.StatutLigne.REJETEE
                ligne.prix_responsable = None
            else:
                ligne.statut_ligne = VenteLigne.StatutLigne.VALIDEE
                if prix_responsable is not None:
                    if ligne.variante.prix_minimum and prix_responsable < ligne.variante.prix_minimum:
                        raise ValidationError(
                            f'Le prix retenu ({prix_responsable}) est inférieur au prix '
                            f'minimum autorisé ({ligne.variante.prix_minimum}).')
                    ligne.prix_responsable = prix_responsable
            ligne.date_decision = timezone.now()
            ligne.decide_par = par or vente.utilisateur
            ligne.save(update_fields=[
                'statut_ligne', 'prix_responsable', 'date_decision', 'decide_par'])
            AuditService.auditer(
                utilisateur=par or vente.utilisateur, succursale=vente.succursale,
                module='BOUTIQUE', action='vente.line_process', objet_type='VenteLigne',
                objet_id=ligne.pk,
                nouvelle_valeur={
                    'vente': vente.numero, 'ligne': ligne.variante.article.code,
                    'decision': ligne.statut_ligne,
                    'prix_responsable': str(ligne.prix_responsable) if ligne.prix_responsable is not None else None,
                },
            )
        return ligne

    @staticmethod
    def traiter_vente(*, vente, par=None):
        """PENDING_VALIDATION → TRAITEE. Le responsable a terminé : toutes les
        lignes en attente (prix proposé < normal) doivent avoir une décision.
        AUCUNE sortie de stock ici."""
        with transaction.atomic():
            if vente.statut != Vente.Statut.PENDING_VALIDATION:
                raise ValidationError(
                    f'Seule une vente en attente de traitement peut être traitée '
                    f'(statut actuel : {vente.get_statut_display()}).')
            for ligne in vente.lignes.all():
                if ligne.prix_propose is not None and ligne.prix_propose < ligne.prix_unitaire \
                        and ligne.date_decision is None:
                    raise ValidationError(
                        f'La ligne {ligne.variante.article.code} ({ligne.variante.label}) '
                        'n’a pas encore été décidée par le responsable.')
            vente.statut = Vente.Statut.TRAITEE
            vente.save(update_fields=['statut'])
            AuditService.auditer(
                utilisateur=par or vente.utilisateur, succursale=vente.succursale,
                module='BOUTIQUE', action='vente.process', objet_type='Vente',
                objet_id=vente.pk,
                nouvelle_valeur={'numero': vente.numero, 'statut': 'TRAITEE'},
            )
        return vente

    @staticmethod
    def confirmer(*, vente, par=None):
        """TRAITEE → CONFIRMEE. SEUL point qui applique les sorties de stock
        (mouvements SORTIE + décrémentation) pour les lignes validées, au prix
        retenu. Idempotent : une vente déjà confirmée ne rejoue jamais le stock."""
        with transaction.atomic():
            if vente.statut == Vente.Statut.CONFIRMEE:
                return vente  # idempotent : déjà confirmée
            if vente.statut != Vente.Statut.TRAITEE:
                raise ValidationError(
                    f'Seule une vente traitée peut être confirmée (statut actuel : '
                    f'{vente.get_statut_display()}).')
            if not vente.lignes.exists():
                raise ValidationError('Cette vente n’a aucune ligne.')
            # Contrôles finaux (étape 11) puis montants au prix retenu.
            for ligne in vente.lignes.all():
                if ligne.statut_ligne != VenteLigne.StatutLigne.VALIDEE:
                    continue
                if ligne.variante.prix_minimum and ligne.prix_retenu < ligne.variante.prix_minimum:
                    raise ValidationError(
                        f'La ligne {ligne.variante.article.code} ({ligne.variante.label}) '
                        f'a un prix retenu ({ligne.prix_retenu}) inférieur au prix minimum '
                        f'({ligne.variante.prix_minimum}). Confirmation impossible.')
                ligne.total = (ligne.prix_retenu * ligne.quantite) - ligne.remise
                ligne.save(update_fields=['total'])
            vente.recalculer()
            # Montant reçu = total de la facture (auto, cohérence de paiement).
            vente.montant_recu = vente.total
            vente.save(update_fields=['montant_recu'])
            vente._appliquer_sorties()  # re-vérifie le stock ; lève sinon (rollback)
            vente.statut = Vente.Statut.CONFIRMEE
            vente.date_validation = timezone.now()
            vente.save(update_fields=['statut', 'date_validation'])
            AuditService.auditer(
                utilisateur=par or vente.utilisateur, succursale=vente.succursale,
                module='BOUTIQUE', action='vente.confirm', objet_type='Vente',
                objet_id=vente.pk,
                nouvelle_valeur={'numero': vente.numero, 'total': str(vente.total)},
            )
        return vente

    @staticmethod
    def approuver(vente, par=None):
        """Raccourci (rétrocompatibilité) : décide toutes les lignes en attente,
        traite la vente puis la confirme immédiatement (sorties de stock)."""
        with transaction.atomic():
            if vente.statut != Vente.Statut.PENDING_VALIDATION:
                raise ValidationError(
                    f'Cette vente ne peut pas être approuvée (statut actuel : '
                    f'{vente.get_statut_display()}).')
            for ligne in vente.lignes.all():
                if ligne.date_decision is None:
                    ligne.date_decision = timezone.now()
                    ligne.decide_par = par or vente.utilisateur
                    ligne.save(update_fields=['date_decision', 'decide_par'])
            VenteService.traiter_vente(vente=vente, par=par or vente.utilisateur)
            VenteService.confirmer(vente=vente, par=par or vente.utilisateur)
        return vente

    @staticmethod
    def modifier_traitement(*, vente, par=None):
        """TRAITEE → PENDING_VALIDATION : le responsable peut revenir sur le
        traitement des lignes (revalider / rejeter, corriger un prix retenu).

        Interdit dès qu'un mouvement de stock a été appliqué : une vente déjà
        confirmée (ou annulée) ne peut pas être modifiée."""
        with transaction.atomic():
            if vente.statut != Vente.Statut.TRAITEE:
                raise ValidationError(
                    f'Seule une vente traitée peut être modifiée (statut actuel : '
                    f'{vente.get_statut_display()}). Une vente confirmée a déjà '
                    'généré ses mouvements de stock et ne peut plus être modifiée.')
            vente.statut = Vente.Statut.PENDING_VALIDATION
            vente.save(update_fields=['statut'])
            AuditService.auditer(
                utilisateur=par or vente.utilisateur, succursale=vente.succursale,
                module='BOUTIQUE', action='vente.modify_process', objet_type='Vente',
                objet_id=vente.pk,
                nouvelle_valeur={'numero': vente.numero, 'statut': 'PENDING_VALIDATION'},
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
    def ajouter_ligne(vente, variante, quantite, prix_propose=None, remise=0, par=None):
        with transaction.atomic():
            ligne = VenteLigne.objects.create(
                vente=vente,
                variante=variante,
                quantite=quantite,
                prix_unitaire=variante.prix_unitaire,  # prix normal (instantané)
                prix_propose=prix_propose or variante.prix_unitaire,
                remise=remise,
            )
            vente.recalculer()
        return ligne

    @staticmethod
    def valider(vente, par=None):
        """Soumission d'un brouillon : PENDING_VALIDATION (si réduction) ou
        TRAITEE. Aucune sortie de stock à ce stade."""
        with transaction.atomic():
            if vente.statut == Vente.Statut.CONFIRMEE:
                raise ValidationError('Cette vente est déjà confirmée.')
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
