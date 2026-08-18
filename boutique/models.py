"""Module Boutique — module métier totalement indépendant de l'Approvisionnement.

Chaque notion a sa responsabilité :
  ArticleBoutique   décrit le produit (pas de stock),
  StockBoutique     conserve la quantité courante (une ligne par article+contexte),
  MouvementStockBoutique trace chaque variation (journal),
  AlerteStockBoutique signale les situations de stock à surveiller,
  Vente / VenteLigne représente l'opération commerciale,
  InventaireBoutique compare le stock théorique au stock physique.

Aucune vente boutique ne modifie le stock du module Approvisionnement.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class CategorieBoutique(models.Model):
    """Catégorie d'articles boutique (référentiel)."""

    nom = models.CharField('nom', max_length=100, unique=True)
    code = models.CharField('code', max_length=20, unique=True)
    description = models.TextField('description', blank=True)
    actif = models.BooleanField('actif', default=True)

    class Meta:
        verbose_name = 'catégorie boutique'
        verbose_name_plural = 'catégories boutique'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class SousCategorieBoutique(models.Model):
    """Sous-catégorie d'articles boutique (référentiel rattaché à une catégorie)."""

    categorie = models.ForeignKey(
        CategorieBoutique,
        on_delete=models.PROTECT,
        related_name='sous_categories',
        verbose_name='catégorie',
    )
    nom = models.CharField('nom', max_length=100)
    code = models.CharField('code', max_length=20)
    actif = models.BooleanField('actif', default=True)

    class Meta:
        verbose_name = 'sous-catégorie boutique'
        verbose_name_plural = 'sous-catégories boutique'
        ordering = ['nom']
        unique_together = [('categorie', 'code')]

    def __str__(self):
        return f'{self.nom} ({self.categorie.nom})'


class UniteBoutique(models.Model):
    """Unité de gestion des articles boutique (référentiel)."""

    nom = models.CharField('nom', max_length=100)
    code = models.CharField('code', max_length=10, unique=True)

    class Meta:
        verbose_name = 'unité boutique'
        verbose_name_plural = 'unités boutique'
        ordering = ['code']

    def __str__(self):
        return self.code


class FournisseurBoutique(models.Model):
    """Fournisseur de la boutique (référentiel)."""

    nom = models.CharField('nom', max_length=150)
    contact = models.CharField('contact', max_length=100, blank=True)
    telephone = models.CharField('téléphone', max_length=30, blank=True)
    adresse = models.TextField('adresse', blank=True)
    actif = models.BooleanField('actif', default=True)

    class Meta:
        verbose_name = 'fournisseur boutique'
        verbose_name_plural = 'fournisseurs boutique'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class ArticleBoutique(models.Model):
    """Produit de la boutique. Représente l'article, PAS son stock.

    La création d'un article n'est pas une entrée en stock : le stock est créé
    et alimenté via `StockBoutique` / `MouvementStockBoutique`.
    """

    class Statut(models.TextChoices):
        ACTIF = 'ACTIF', 'Actif'
        INACTIF = 'INACTIF', 'Inactif'

    class Genre(models.TextChoices):
        HOMME = 'HOMME', 'Homme'
        FEMME = 'FEMME', 'Femme'
        MIXTE = 'MIXTE', 'Mixte'
        ENFANT = 'ENFANT', 'Enfant'

    # Identification
    code = models.CharField('code', max_length=50)
    reference = models.CharField('référence / SKU', max_length=50, blank=True)
    designation = models.CharField('désignation', max_length=200)
    description = models.TextField('description', blank=True)
    type = models.CharField('type', max_length=50, blank=True)

    # Classification (référentiels)
    categorie = models.ForeignKey(
        CategorieBoutique,
        on_delete=models.PROTECT,
        related_name='articles',
        verbose_name='catégorie',
        null=True,
        blank=True,
    )
    sous_categorie = models.ForeignKey(
        SousCategorieBoutique,
        on_delete=models.PROTECT,
        related_name='articles',
        verbose_name='sous-catégorie',
        null=True,
        blank=True,
    )
    unite = models.ForeignKey(
        UniteBoutique,
        on_delete=models.PROTECT,
        related_name='articles',
        verbose_name='unité',
        null=True,
        blank=True,
    )

    # Caractéristiques (champs simples, pas de tables dédiées)
    genre = models.CharField('genre', max_length=10, choices=Genre.choices, blank=True)
    taille = models.CharField('taille', max_length=20, blank=True)
    couleur = models.CharField('couleur', max_length=30, blank=True)
    marque = models.CharField('marque', max_length=50, blank=True)
    matiere = models.CharField('matière', max_length=50, blank=True)
    modele = models.CharField('modèle', max_length=50, blank=True)

    # Localisation physique (champs simples)
    rayon = models.CharField('rayon', max_length=50, blank=True)
    etagere = models.CharField('étagère', max_length=50, blank=True)
    emplacement = models.CharField('emplacement', max_length=50, blank=True)

    # Contexte centralisé
    succursale = models.ForeignKey(
        'core.Succursale',
        on_delete=models.PROTECT,
        related_name='articles_boutique',
        verbose_name='succursale',
    )
    domaine = models.ForeignKey(
        'core.Domaine',
        on_delete=models.PROTECT,
        related_name='articles_boutique',
        verbose_name='domaine d’activité',
        null=True,
        blank=True,
    )

    # Tarifs — règle : prix_minimum ≤ prix_unitaire ≤ prix_maximum
    prix_achat = models.DecimalField('prix d’achat', max_digits=12, decimal_places=2, default=Decimal('0'))
    prix_unitaire = models.DecimalField('prix de vente', max_digits=12, decimal_places=2, default=Decimal('0'))
    prix_minimum = models.DecimalField(
        'prix minimum',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text='Prix plancher : aucune vente en dessous de ce prix.',
    )
    prix_maximum = models.DecimalField(
        'prix maximum',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text='Prix plafond : aucune vente au-dessus de ce prix.',
    )

    statut = models.CharField(
        'statut',
        max_length=10,
        choices=Statut.choices,
        default=Statut.ACTIF,
    )
    en_vente = models.BooleanField('en vente', default=True)
    date_creation = models.DateTimeField('créé le', default=timezone.now)
    date_modification = models.DateTimeField('modifié le', auto_now=True)

    class Meta:
        verbose_name = 'article boutique'
        verbose_name_plural = 'articles boutique'
        ordering = ['code']
        unique_together = [('code', 'succursale', 'domaine')]

    def __str__(self):
        variantes = ' / '.join(p for p in (self.taille, self.couleur) if p)
        return f'{self.code} — {self.designation}' + (
            f' ({variantes})' if variantes else ''
        )

    @property
    def prix_vente(self):
        """Alias de lecture (rétrocompatibilité) → prix_unitaire."""
        return self.prix_unitaire

    @property
    def prix_limite(self):
        """Alias de lecture (rétrocompatibilité) → prix_minimum."""
        return self.prix_minimum


class StockBoutique(models.Model):
    """État actuel du stock : une ligne par (article, succursale, domaine).

    Jamais de nouvelle ligne à chaque entrée : les opérations historiques sont
    conservées dans `MouvementStockBoutique`.
    """

    article = models.ForeignKey(
        ArticleBoutique,
        on_delete=models.CASCADE,
        related_name='stocks',
        verbose_name='article',
    )
    succursale = models.ForeignKey(
        'core.Succursale',
        on_delete=models.PROTECT,
        related_name='stocks_boutique',
        verbose_name='succursale',
    )
    domaine = models.ForeignKey(
        'core.Domaine',
        on_delete=models.PROTECT,
        related_name='stocks_boutique',
        verbose_name='domaine d’activité',
        null=True,
        blank=True,
    )
    quantite = models.IntegerField('quantité', default=0)
    seuil_alerte = models.PositiveIntegerField('seuil d’alerte', default=0)

    class Meta:
        verbose_name = 'stock boutique'
        verbose_name_plural = 'stocks boutique'
        ordering = ['article__code']
        unique_together = [('article', 'succursale', 'domaine')]
        permissions = [
            ('view_stock', 'Peut consulter le stock boutique'),
            ('adjust_stock', 'Peut ajuster le stock boutique'),
        ]

    def __str__(self):
        return f'{self.article.code} — {self.quantite}'

    @classmethod
    def obtenir(cls, article, succursale, domaine):
        """Ligne de stock unique du contexte (get_or_create).

        À n'utiliser que dans les chemins d'ÉCRITURE (services, validation de
        vente, ajustement d'inventaire). Les lectures utilisent
        `StockBoutique.objects.filter(...).first()` (None → quantité 0).
        """
        stock, _ = cls.objects.get_or_create(
            article=article,
            succursale=succursale,
            domaine=domaine,
            defaults={'quantite': 0},
        )
        return stock

    # État du stock (miroir des propriétés de l'Article approvisionnement)
    @property
    def en_rupture(self):
        return self.quantite <= 0

    @property
    def en_alerte(self):
        return self.seuil_alerte > 0 and self.quantite <= self.seuil_alerte

    @property
    def en_vigilance(self):
        return self.seuil_alerte > 0 and self.seuil_alerte < self.quantite <= self.seuil_alerte + 10

    @property
    def a_signaler(self):
        return self.en_rupture or self.en_alerte or self.en_vigilance

    @property
    def classe_stock(self):
        if self.en_rupture or self.en_alerte:
            return 'row-alert'
        if self.en_vigilance:
            return 'row-vigilance'
        return ''

    @property
    def niveau_stock(self):
        if self.en_rupture:
            return 'Rupture'
        if self.en_alerte:
            return 'Seuil atteint'
        if self.en_vigilance:
            return 'Vigilance'
        return ''


class MouvementStockBoutique(models.Model):
    """Journal de toutes les variations de stock boutique."""

    class Type(models.TextChoices):
        ENTREE = 'ENTREE', 'Entrée'
        SORTIE = 'SORTIE', 'Sortie'
        AJUSTEMENT = 'AJUSTEMENT', 'Ajustement'
        RETOUR = 'RETOUR', 'Retour'
        CASSE = 'CASSE', 'Casse'
        PERTE = 'PERTE', 'Perte'

    article = models.ForeignKey(
        ArticleBoutique,
        on_delete=models.PROTECT,
        related_name='mouvements_stock',
        verbose_name='article',
    )
    stock = models.ForeignKey(
        StockBoutique,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mouvements',
        verbose_name='stock',
    )
    succursale = models.ForeignKey(
        'core.Succursale',
        on_delete=models.PROTECT,
        related_name='mouvements_stock_boutique',
        verbose_name='succursale',
        null=True,
        blank=True,
    )
    domaine = models.ForeignKey(
        'core.Domaine',
        on_delete=models.PROTECT,
        related_name='mouvements_stock_boutique',
        verbose_name='domaine d’activité',
        null=True,
        blank=True,
    )
    type = models.CharField('type', max_length=12, choices=Type.choices)
    quantite = models.IntegerField('quantité')
    stock_avant = models.IntegerField('stock avant', null=True, blank=True)
    stock_apres = models.IntegerField('stock après', null=True, blank=True)
    date_mouvement = models.DateTimeField('date', default=timezone.now)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='mouvements_stock_boutique',
        verbose_name='utilisateur',
    )
    reference = models.CharField('référence', max_length=100, blank=True)
    motif = models.CharField('motif', max_length=200, blank=True)

    class Meta:
        verbose_name = 'mouvement de stock boutique'
        verbose_name_plural = 'mouvements de stock boutique'
        ordering = ['-date_mouvement']

    def __str__(self):
        return f'{self.get_type_display()} {self.article.code} × {self.quantite}'

    def _delta(self):
        if self.type in (self.Type.SORTIE, self.Type.RETOUR, self.Type.CASSE, self.Type.PERTE):
            return -self.quantite
        return self.quantite  # ENTREE positive ; AJUSTEMENT peut être négatif

    def valider(self):
        """Applique le mouvement au stock : verrouillage, contrôle, mise à jour,
        journalisation et synchronisation des alertes.

        Doit être appelé DANS une transaction `transaction.atomic()` extérieure
        (service, `Vente.valider`, `LigneInventaireBoutique.creer_ajustement`).
        """
        if self.stock_id is None:
            raise ValidationError('Un mouvement doit être rattaché à une ligne de stock.')
        stock = StockBoutique.objects.select_for_update().get(pk=self.stock_id)
        self.succursale_id = stock.succursale_id
        self.domaine_id = stock.domaine_id
        self.article_id = stock.article_id
        delta = self._delta()
        if delta < 0 and (stock.quantite <= 0 or -delta > stock.quantite):
            raise ValidationError(
                f'{stock.article.code} : stock à 0 ou insuffisant. '
                f'Stock disponible : {stock.quantite}.'
            )
        self.stock_avant = stock.quantite
        stock.quantite += delta
        stock.save(update_fields=['quantite'])
        self.stock_apres = stock.quantite
        self.save()
        AlerteStockBoutique.synchroniser(stock)


class AlerteStockBoutique(models.Model):
    """Alerte générée par le niveau de stock (une ACTIVE par stock + type)."""

    class Type(models.TextChoices):
        STOCK_FAIBLE = 'STOCK_FAIBLE', 'Stock faible'
        RUPTURE = 'RUPTURE', 'Rupture'

    class Statut(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        RESOLUE = 'RESOLUE', 'Résolue'

    stock = models.ForeignKey(
        StockBoutique,
        on_delete=models.CASCADE,
        related_name='alertes',
        verbose_name='stock',
    )
    article = models.ForeignKey(
        ArticleBoutique,
        on_delete=models.CASCADE,
        related_name='alertes_stock',
        verbose_name='article',
    )
    type = models.CharField('type', max_length=12, choices=Type.choices)
    seuil = models.PositiveIntegerField('seuil')
    quantite_actuelle = models.IntegerField('quantité actuelle')
    statut = models.CharField(
        'statut',
        max_length=10,
        choices=Statut.choices,
        default=Statut.ACTIVE,
    )
    date_creation = models.DateTimeField('créée le', default=timezone.now)
    date_resolution = models.DateTimeField('résolue le', null=True, blank=True)

    class Meta:
        verbose_name = 'alerte de stock boutique'
        verbose_name_plural = 'alertes de stock boutique'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.get_type_display()} {self.article.code} (stock {self.quantite_actuelle} / seuil {self.seuil})'

    @property
    def classe_stock(self):
        return 'row-alert' if self.type == self.Type.RUPTURE else 'row-vigilance'

    @property
    def niveau_stock(self):
        return self.get_type_display()

    @classmethod
    def synchroniser(cls, stock):
        """Une seule alerte ACTIVE par (stock, type) ; résout quand le stock
        remonte au-dessus du seuil. `date_creation` n'est jamais écrasée."""
        if stock.quantite <= 0:
            type_ = cls.Type.RUPTURE
        elif stock.seuil_alerte and stock.quantite <= stock.seuil_alerte:
            type_ = cls.Type.STOCK_FAIBLE
        else:
            cls.objects.filter(stock=stock, statut=cls.Statut.ACTIVE).update(
                statut=cls.Statut.RESOLUE,
                date_resolution=timezone.now(),
            )
            return
        cls.objects.update_or_create(
            stock=stock,
            type=type_,
            statut=cls.Statut.ACTIVE,
            defaults={
                'article': stock.article,
                'seuil': stock.seuil_alerte,
                'quantite_actuelle': stock.quantite,
            },
        )


class Vente(models.Model):
    """Vente boutique : la validation produit un MouvementStockBoutique SORTIE."""

    class Statut(models.TextChoices):
        BROUILLON = 'BROUILLON', 'Brouillon'
        VALIDEE = 'VALIDEE', 'Validée'
        ANNULEE = 'ANNULEE', 'Annulée'

    class Paiement(models.TextChoices):
        ESPECES = 'ESPECES', 'Espèces'
        MOBILE_MONEY = 'MOBILE_MONEY', 'Mobile Money'
        CARTE = 'CARTE', 'Carte'
        AUTRE = 'AUTRE', 'Autre'

    numero = models.CharField('numéro', max_length=20, unique=True, editable=False)
    client = models.CharField('client', max_length=200, blank=True)
    succursale = models.ForeignKey(
        'core.Succursale',
        on_delete=models.PROTECT,
        related_name='ventes',
        verbose_name='succursale',
    )
    domaine = models.ForeignKey(
        'core.Domaine',
        on_delete=models.PROTECT,
        related_name='ventes',
        verbose_name='domaine d’activité',
        null=True,
        blank=True,
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ventes',
        verbose_name='utilisateur',
    )
    date_vente = models.DateTimeField('date', default=timezone.now)
    type_paiement = models.CharField(
        'paiement',
        max_length=15,
        choices=Paiement.choices,
        default=Paiement.ESPECES,
    )
    montant_recu = models.DecimalField('montant reçu', max_digits=12, decimal_places=2, default=Decimal('0'))
    statut = models.CharField(
        'statut',
        max_length=12,
        choices=Statut.choices,
        default=Statut.BROUILLON,
    )
    sous_total = models.DecimalField('sous-total', max_digits=12, decimal_places=2, default=Decimal('0'))
    remise = models.DecimalField('remise', max_digits=12, decimal_places=2, default=Decimal('0'))
    total = models.DecimalField('total', max_digits=12, decimal_places=2, default=Decimal('0'))
    date_validation = models.DateTimeField('date de validation', null=True, blank=True)

    class Meta:
        verbose_name = 'vente'
        verbose_name_plural = 'ventes'
        ordering = ['-date_vente']
        permissions = [
            ('view_boutique', 'Peut consulter la boutique'),
            ('create_vente', 'Peut créer une vente'),
            ('validate_vente', 'Peut valider une vente'),
            ('cancel_vente', 'Peut annuler une vente'),
            ('apply_remise', 'Peut appliquer une remise'),
        ]

    def __str__(self):
        return self.numero

    @classmethod
    def prochain_numero(cls):
        annee = timezone.localdate().year
        prefixe = f'VTE-{annee}-'
        dernier = (
            cls.objects.select_for_update()
            .filter(numero__startswith=prefixe)
            .order_by('-numero')
            .first()
        )
        sequence = int(dernier.numero.rsplit('-', 1)[-1]) + 1 if dernier else 1
        return f'{prefixe}{sequence:04d}'

    @property
    def monnaie(self):
        return max(self.montant_recu - self.total, Decimal('0'))

    def recalculer(self):
        """Recalcule sous-total, total et éventuellement la remise à partir des lignes."""
        sous_total = sum(
            (ligne.total for ligne in self.lignes.all()),
            start=Decimal('0'),
        )
        total = max(sous_total - self.remise, Decimal('0'))
        self.sous_total = sous_total
        self.total = total
        self.save(update_fields=['sous_total', 'total'])

    def analyser_stock(self):
        """Pré-validation : lignes dont la quantité dépasse le stock disponible.

        Lecture seule (aucune ligne de stock créée)."""
        ruptures = []
        for ligne in self.lignes.select_related('article'):
            stock = StockBoutique.objects.filter(
                article_id=ligne.article_id,
                succursale_id=self.succursale_id,
                domaine_id=self.domaine_id,
            ).first()
            dispo = stock.quantite if stock else 0
            if dispo <= 0 or ligne.quantite > dispo:
                ruptures.append(
                    {
                        'article': ligne.article,
                        'quantite': ligne.quantite,
                        'stock': dispo,
                    }
                )
        return ruptures

    def valider(self):
        if self.statut == self.Statut.VALIDEE:
            raise ValidationError('Cette vente est déjà validée.')
        lignes = list(self.lignes.select_related('article'))
        if not lignes:
            raise ValidationError('Ajoutez au moins une ligne de produit avant de valider.')
        with transaction.atomic():
            for ligne in lignes:
                art = ligne.article
                # Contrôle des prix côté backend (source de vérité).
                if art.prix_minimum and ligne.prix_unitaire < art.prix_minimum:
                    raise ValidationError(
                        f'{art.code} : le prix de vente de {ligne.prix_unitaire} FC est '
                        f'inférieur au prix minimum autorisé de {art.prix_minimum} FC.'
                    )
                if art.prix_maximum and ligne.prix_unitaire > art.prix_maximum:
                    raise ValidationError(
                        f'{art.code} : le prix de vente de {ligne.prix_unitaire} FC est '
                        f'supérieur au prix maximum autorisé de {art.prix_maximum} FC.'
                    )
                stock = StockBoutique.obtenir(art, self.succursale, self.domaine)
                mouvement = MouvementStockBoutique(
                    article=art,
                    stock=stock,
                    type=MouvementStockBoutique.Type.SORTIE,
                    quantite=ligne.quantite,
                    motif=f'Vente {self.numero}',
                    date_mouvement=self.date_vente,
                    utilisateur=self.utilisateur,
                )
                mouvement.valider()
                ligne.mouvement = mouvement
                ligne.save(update_fields=['mouvement'])
            self.statut = self.Statut.VALIDEE
            self.date_validation = timezone.now()
            self.save(update_fields=['statut', 'date_validation'])

    def annuler(self):
        if self.statut != self.Statut.BROUILLON:
            raise ValidationError(
                'Seul un brouillon peut être annulé. '
                'Pour une vente validée, prévoir un retour.'
            )
        self.statut = self.Statut.ANNULEE
        self.save(update_fields=['statut'])


class VenteLigne(models.Model):
    """Ligne de vente : conserve le prix réellement appliqué au moment de la vente."""

    vente = models.ForeignKey(
        Vente,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='vente',
    )
    article = models.ForeignKey(
        ArticleBoutique,
        on_delete=models.PROTECT,
        related_name='lignes_vente',
        verbose_name='article',
    )
    quantite = models.PositiveIntegerField('quantité')
    prix_unitaire = models.DecimalField('prix unitaire', max_digits=12, decimal_places=2, default=Decimal('0'))
    remise = models.DecimalField('remise', max_digits=12, decimal_places=2, default=Decimal('0'))
    total = models.DecimalField('total', max_digits=12, decimal_places=2, default=Decimal('0'))
    mouvement = models.OneToOneField(
        MouvementStockBoutique,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ligne_vente',
        verbose_name='mouvement de sortie',
    )

    class Meta:
        verbose_name = 'ligne de vente'
        verbose_name_plural = 'lignes de vente'

    def __str__(self):
        return f'{self.vente.numero} — {self.article.code} × {self.quantite}'

    def save(self, *args, **kwargs):
        self.total = (self.prix_unitaire * self.quantite) - self.remise
        super().save(*args, **kwargs)


class InventaireBoutique(models.Model):
    """Inventaire boutique : compare le stock théorique au stock physique."""

    class Statut(models.TextChoices):
        BROUILLON = 'BROUILLON', 'Brouillon'
        VALIDE = 'VALIDE', 'Validé'

    class Portee(models.TextChoices):
        COMPLET = 'COMPLET', 'Complet'
        UN_ARTICLE = 'UN_ARTICLE', 'Un article'

    numero = models.CharField('numéro', max_length=20, unique=True, editable=False)
    date_inventaire = models.DateField('date', default=timezone.now)
    succursale = models.ForeignKey(
        'core.Succursale',
        on_delete=models.PROTECT,
        related_name='inventaires_boutique',
        verbose_name='succursale',
    )
    domaine = models.ForeignKey(
        'core.Domaine',
        on_delete=models.PROTECT,
        related_name='inventaires_boutique',
        verbose_name='domaine d’activité',
        null=True,
        blank=True,
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='inventaires_boutique',
        verbose_name='responsable',
    )
    commentaire = models.TextField('commentaire', blank=True)
    portee = models.CharField(
        'portée',
        max_length=12,
        choices=Portee.choices,
        default=Portee.COMPLET,
    )
    statut = models.CharField(
        'statut',
        max_length=12,
        choices=Statut.choices,
        default=Statut.BROUILLON,
    )
    date_validation = models.DateTimeField('date de validation', null=True, blank=True)

    class Meta:
        verbose_name = 'inventaire boutique'
        verbose_name_plural = 'inventaires boutique'
        ordering = ['-date_inventaire']

    def __str__(self):
        return f'Inventaire {self.numero} du {self.date_inventaire}'

    @classmethod
    def prochain_numero(cls):
        annee = timezone.localdate().year
        prefixe = f'INV-{annee}-'
        dernier = (
            cls.objects.select_for_update()
            .filter(numero__startswith=prefixe)
            .order_by('-numero')
            .first()
        )
        sequence = int(dernier.numero.rsplit('-', 1)[-1]) + 1 if dernier else 1
        return f'{prefixe}{sequence:04d}'

    def valider(self):
        if self.statut == self.Statut.VALIDE:
            raise ValidationError('Cet inventaire est déjà validé.')
        lignes = list(self.lignes.select_related('article'))
        if not lignes:
            raise ValidationError('Impossible de valider un inventaire sans ligne.')
        with transaction.atomic():
            for ligne in lignes:
                ligne.creer_ajustement(self.responsable)
            self.statut = self.Statut.VALIDE
            self.date_validation = timezone.now()
            self.save(update_fields=['statut', 'date_validation'])


class LigneInventaireBoutique(models.Model):
    """Ligne d'inventaire : stock théorique vs stock physique + écart."""

    inventaire = models.ForeignKey(
        InventaireBoutique,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='inventaire',
    )
    article = models.ForeignKey(
        ArticleBoutique,
        on_delete=models.PROTECT,
        related_name='lignes_inventaire',
        verbose_name='article',
    )
    stock_systeme = models.IntegerField('stock système')
    stock_physique = models.IntegerField('stock physique')
    motif = models.CharField('motif', max_length=200, blank=True)
    mouvement = models.OneToOneField(
        MouvementStockBoutique,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ligne_inventaire',
        verbose_name='mouvement d’ajustement',
    )

    class Meta:
        verbose_name = 'ligne d’inventaire boutique'
        verbose_name_plural = 'lignes d’inventaire boutique'
        unique_together = [('inventaire', 'article')]

    def __str__(self):
        return f'{self.article.code} ({self.ecart:+d})'

    @property
    def ecart(self):
        return self.stock_physique - self.stock_systeme

    def creer_ajustement(self, utilisateur):
        """Crée un mouvement AJUSTEMENT (quantité = écart) et corrige le stock."""
        ecart = self.ecart
        if ecart == 0:
            return None
        if not self.motif:
            raise ValidationError(
                f'Un motif est obligatoire pour ajuster {self.article.code} '
                f'(écart {ecart:+d}).'
            )
        stock = StockBoutique.obtenir(
            self.article,
            self.inventaire.succursale,
            self.inventaire.domaine,
        )
        mouvement = MouvementStockBoutique(
            article=self.article,
            stock=stock,
            type=MouvementStockBoutique.Type.AJUSTEMENT,
            quantite=ecart,
            motif=self.motif,
            utilisateur=utilisateur,
        )
        mouvement.valider()
        self.mouvement = mouvement
        self.save(update_fields=['mouvement'])
        return mouvement
