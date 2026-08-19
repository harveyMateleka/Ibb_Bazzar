"""Module Boutique — architecture Article → Variante → Stock → Mouvement.

Niveaux de responsabilité :
  ArticleBoutique     article générique / parent (identification seule),
  VarianteArticle     version concrète du produit (caractéristiques + prix + seuil),
  StockBoutique       quantité courante d'une variante (par contexte),
  MouvementStockBoutique journal de chaque variation d'une variante,
  AlerteStockBoutique signalé au niveau du stock de la variante,
  Vente / VenteLigne  opération commerciale référençant des variantes,
  InventaireBoutique  comparaison théorique / physique au niveau de la variante.

Le stock global d'un Article n'est qu'une agrégation des stocks de ses variantes.
Aucune vente boutique ne touche le stock du module Approvisionnement.
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
    """Article générique / parent : uniquement les informations d'identification.

    Toute caractéristique de produit, prix ou stock vit au niveau des
    `VarianteArticle` / `StockBoutique`.
    """

    class Devise(models.TextChoices):
        FC = 'FC', 'Franc congolais (FC)'
        USD = 'USD', 'Dollar américain (USD)'
        EUR = 'EUR', 'Euro (EUR)'

    code = models.CharField('code', max_length=50)
    designation = models.CharField('désignation', max_length=200)
    devise = models.CharField(
        'devise', max_length=3, choices=Devise.choices, default=Devise.FC)
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
    date_creation = models.DateTimeField('créé le', default=timezone.now)
    date_modification = models.DateTimeField('modifié le', auto_now=True)

    class Meta:
        verbose_name = 'article boutique'
        verbose_name_plural = 'articles boutique'
        ordering = ['code']
        unique_together = [('code', 'succursale', 'domaine')]

    def __str__(self):
        return f'{self.code} — {self.designation}'

    @property
    def stock_total(self):
        """Stock total = agrégation des stocks de toutes les variantes."""
        return sum(
            s.quantite
            for s in StockBoutique.objects.filter(variante__article=self)
        )

    @property
    def nb_variantes(self):
        return self.variantes.count()


class VarianteArticle(models.Model):
    """Version concrète et identifiable d'un article (ex. Noir / M / Homme)."""

    class Statut(models.TextChoices):
        ACTIF = 'ACTIF', 'Actif'
        INACTIF = 'INACTIF', 'Inactif'

    class Genre(models.TextChoices):
        HOMME = 'HOMME', 'Homme'
        FEMME = 'FEMME', 'Femme'
        MIXTE = 'MIXTE', 'Mixte'
        ENFANT = 'ENFANT', 'Enfant'

    class Taille(models.TextChoices):
        XS = 'XS', 'XS'
        S = 'S', 'S'
        M = 'M', 'M'
        L = 'L', 'L'
        XL = 'XL', 'XL'
        XXL = 'XXL', 'XXL'
        T32 = '32', '32'
        T34 = '34', '34'
        T36 = '36', '36'
        T38 = '38', '38'
        T40 = '40', '40'
        T42 = '42', '42'
        U = 'U', 'U'

    class Couleur(models.TextChoices):
        NOIR = 'Noir', 'Noir'
        BLANC = 'Blanc', 'Blanc'
        BLEU = 'Bleu', 'Bleu'
        ROUGE = 'Rouge', 'Rouge'
        VERT = 'Vert', 'Vert'
        JAUNE = 'Jaune', 'Jaune'
        GRIS = 'Gris', 'Gris'
        MARRON = 'Marron', 'Marron'
        ORANGE = 'Orange', 'Orange'
        ROSE = 'Rose', 'Rose'
        VIOLET = 'Violet', 'Violet'
        BEIGE = 'Beige', 'Beige'
        MULTI = 'Multi', 'Multi'

    article = models.ForeignKey(
        ArticleBoutique,
        on_delete=models.CASCADE,
        related_name='variantes',
        verbose_name='article',
    )
    code_variante = models.CharField('code variante', max_length=50, blank=True,
                                     editable=False)

    # Classification (référentiels)
    categorie = models.ForeignKey(
        CategorieBoutique,
        on_delete=models.PROTECT,
        related_name='variantes',
        verbose_name='catégorie',
        null=True,
        blank=True,
    )
    sous_categorie = models.ForeignKey(
        SousCategorieBoutique,
        on_delete=models.PROTECT,
        related_name='variantes',
        verbose_name='sous-catégorie',
        null=True,
        blank=True,
    )
    unite = models.ForeignKey(
        UniteBoutique,
        on_delete=models.PROTECT,
        related_name='variantes',
        verbose_name='unité',
        null=True,
        blank=True,
    )

    # Caractéristiques (valeurs contrôlées pour la cohérence)
    genre = models.CharField('genre', max_length=10, choices=Genre.choices, blank=True)
    taille = models.CharField('taille', max_length=20, choices=Taille.choices, blank=True)
    couleur = models.CharField('couleur', max_length=30, choices=Couleur.choices, blank=True)
    marque = models.CharField('marque', max_length=50, blank=True)
    matiere = models.CharField('matière', max_length=50, blank=True)
    modele = models.CharField('modèle', max_length=50, blank=True)
    rayon = models.CharField('rayon', max_length=50, blank=True)
    etagere = models.CharField('étagère', max_length=50, blank=True)
    emplacement = models.CharField('emplacement', max_length=50, blank=True)

    # Tarifs — règle : prix_minimum ≤ prix_unitaire ≤ prix_maximum
    prix_achat = models.DecimalField('prix d’achat', max_digits=12, decimal_places=2, default=Decimal('0'))
    prix_unitaire = models.DecimalField('prix de vente', max_digits=12, decimal_places=2, default=Decimal('0'))
    prix_minimum = models.DecimalField(
        'prix minimum', max_digits=12, decimal_places=2, default=Decimal('0'),
        help_text='Prix plancher : aucune vente en dessous de ce prix.')
    prix_maximum = models.DecimalField(
        'prix maximum', max_digits=12, decimal_places=2, default=Decimal('0'),
        help_text='Prix plafond : aucune vente au-dessus de ce prix.')

    seuil_alerte = models.PositiveIntegerField('seuil d’alerte', default=0)

    statut = models.CharField(
        'statut', max_length=10, choices=Statut.choices, default=Statut.ACTIF)
    en_vente = models.BooleanField('en vente', default=True)
    date_creation = models.DateTimeField('créée le', default=timezone.now)
    date_modification = models.DateTimeField('modifiée le', auto_now=True)

    class Meta:
        verbose_name = 'variante d’article'
        verbose_name_plural = 'variantes d’articles'
        ordering = ['code_variante']
        # Identité métier d'une variante : pas de doublon pour un même article.
        unique_together = [('article', 'couleur', 'taille', 'genre')]

    def __str__(self):
        return f'{self.article.code} — {self.label}'

    @property
    def label(self):
        parties = [p for p in (self.couleur, self.taille, self.get_genre_display()) if p]
        return ' / '.join(parties) if parties else self.code_variante

    @property
    def prix_vente(self):
        """Alias de lecture (rétrocompatibilité) → prix_unitaire."""
        return self.prix_unitaire

    @property
    def prix_limite(self):
        """Alias de lecture (rétrocompatibilité) → prix_minimum."""
        return self.prix_minimum

    @classmethod
    def prochain_code(cls, article):
        """Code variante séquentiel : ARTICLE-V<n> (sans réutiliser un n supprimé)."""
        prefixe = f'{article.code}-V'
        dernier = (
            cls.objects.filter(article=article, code_variante__startswith=prefixe)
            .order_by('-code_variante')
            .first()
        )
        if dernier:
            suffixe = dernier.code_variante.rsplit('-V', 1)[-1]
            try:
                return f'{prefixe}{int(suffixe) + 1}'
            except ValueError:
                pass
        return f'{prefixe}1'

    def save(self, *args, **kwargs):
        if not self.code_variante and self.article_id:
            self.code_variante = self.prochain_code(self.article)
        super().save(*args, **kwargs)


class BonEntreeBoutique(models.Model):
    """Entrée en stock en deux temps : enregistrée en brouillon, puis validée
    par le responsable. La variante, le stock et le mouvement ne sont créés
    qu'à la VALIDATION."""

    class Statut(models.TextChoices):
        BROUILLON = 'BROUILLON', 'Brouillon'
        VALIDE = 'VALIDE', 'Validé'
        ANNULEE = 'ANNULEE', 'Annulé'

    numero = models.CharField('numéro', max_length=20, unique=True, editable=False)
    article = models.ForeignKey(
        ArticleBoutique,
        on_delete=models.PROTECT,
        related_name='bons_entree',
        verbose_name='article',
    )
    succursale = models.ForeignKey(
        'core.Succursale',
        on_delete=models.PROTECT,
        related_name='bons_entree_boutique',
        verbose_name='succursale',
    )
    domaine = models.ForeignKey(
        'core.Domaine',
        on_delete=models.PROTECT,
        related_name='bons_entree_boutique',
        verbose_name='domaine d’activité',
        null=True,
        blank=True,
    )
    categorie = models.ForeignKey(
        CategorieBoutique, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bons_entree', verbose_name='catégorie')
    sous_categorie = models.ForeignKey(
        SousCategorieBoutique, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bons_entree', verbose_name='sous-catégorie')
    unite = models.ForeignKey(
        UniteBoutique, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bons_entree', verbose_name='unité')
    genre = models.CharField('genre', max_length=10,
                             choices=VarianteArticle.Genre.choices, blank=True)
    taille = models.CharField('taille', max_length=20,
                              choices=VarianteArticle.Taille.choices, blank=True)
    couleur = models.CharField('couleur', max_length=30,
                               choices=VarianteArticle.Couleur.choices, blank=True)
    marque = models.CharField('marque', max_length=50, blank=True)
    modele = models.CharField('modèle', max_length=50, blank=True)
    rayon = models.CharField('rayon', max_length=50, blank=True)
    etagere = models.CharField('étagère', max_length=50, blank=True)
    emplacement = models.CharField('emplacement', max_length=50, blank=True)
    prix_achat = models.DecimalField('prix d’achat', max_digits=12, decimal_places=2, default=Decimal('0'))
    prix_unitaire = models.DecimalField('prix de vente', max_digits=12, decimal_places=2, default=Decimal('0'))
    prix_minimum = models.DecimalField(
        'prix minimum', max_digits=12, decimal_places=2, default=Decimal('0'),
        help_text='Prix plancher : aucune vente en dessous de ce prix.')
    seuil_alerte = models.PositiveIntegerField('seuil d’alerte', default=0)
    quantite = models.PositiveIntegerField('quantité')
    statut = models.CharField(
        'statut', max_length=12, choices=Statut.choices, default=Statut.BROUILLON)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='bons_entree_crees', verbose_name='créé par')
    date_creation = models.DateTimeField('créé le', default=timezone.now)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bons_entree_valides', verbose_name='validé par')
    date_validation = models.DateTimeField('validé le', null=True, blank=True)
    commentaire = models.CharField(
        'commentaire', max_length=300, blank=True,
        help_text='Motif de la décision (annulation) renseigné par le responsable.')

    class Meta:
        verbose_name = 'entrée en stock'
        verbose_name_plural = 'entrées en stock'
        ordering = ['-date_creation']
        permissions = [
            ('validate_entree', 'Peut valider une entrée de stock'),
        ]

    def __str__(self):
        return f'{self.numero} — {self.article.code}'

    @classmethod
    def prochain_numero(cls):
        annee = timezone.localdate().year
        prefixe = f'ENT-{annee}-'
        dernier = (
            cls.objects.select_for_update()
            .filter(numero__startswith=prefixe)
            .order_by('-numero')
            .first()
        )
        sequence = int(dernier.numero.rsplit('-', 1)[-1]) + 1 if dernier else 1
        return f'{prefixe}{sequence:04d}'


class StockBoutique(models.Model):
    """État actuel du stock d'une variante (une ligne par variante + contexte)."""

    variante = models.ForeignKey(
        VarianteArticle,
        on_delete=models.CASCADE,
        related_name='stocks',
        verbose_name='variante',
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

    class Meta:
        verbose_name = 'stock boutique'
        verbose_name_plural = 'stocks boutique'
        ordering = ['variante__article__code']
        unique_together = [('variante', 'succursale', 'domaine')]
        permissions = [
            ('view_stock', 'Peut consulter le stock boutique'),
            ('adjust_stock', 'Peut ajuster le stock boutique'),
        ]

    def __str__(self):
        return f'{self.variante.article.code} — {self.quantite}'

    @classmethod
    def obtenir(cls, variante, succursale, domaine):
        """Ligne de stock unique de la variante (get_or_create).

        À n'utiliser que dans les chemins d'ÉCRITURE. Les lectures utilisent
        `filter().first()` (None → quantité 0).
        """
        stock, _ = cls.objects.get_or_create(
            variante=variante,
            succursale=succursale,
            domaine=domaine,
            defaults={'quantite': 0},
        )
        return stock

    # État du stock de la variante (seuil porté par la variante)
    @property
    def seuil_alerte(self):
        return self.variante.seuil_alerte

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
    """Journal de toutes les variations de stock d'une variante."""

    class Type(models.TextChoices):
        ENTREE = 'ENTREE', 'Entrée'
        SORTIE = 'SORTIE', 'Sortie'
        AJUSTEMENT = 'AJUSTEMENT', 'Ajustement'
        RETOUR = 'RETOUR', 'Retour'
        CASSE = 'CASSE', 'Casse'
        PERTE = 'PERTE', 'Perte'

    variante = models.ForeignKey(
        VarianteArticle,
        on_delete=models.PROTECT,
        related_name='mouvements_stock',
        verbose_name='variante',
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
        return f'{self.get_type_display()} {self.variante.article.code} × {self.quantite}'

    def _delta(self):
        if self.type in (self.Type.SORTIE, self.Type.RETOUR, self.Type.CASSE, self.Type.PERTE):
            return -self.quantite
        return self.quantite  # ENTREE positive ; AJUSTEMENT peut être négatif

    def valider(self):
        """Applique le mouvement au stock de la variante : verrouillage, contrôle,
        mise à jour, journalisation et synchronisation des alertes.

        Doit être appelé DANS une transaction `transaction.atomic()` extérieure."""
        if self.stock_id is None:
            raise ValidationError('Un mouvement doit être rattaché à une ligne de stock.')
        stock = StockBoutique.objects.select_for_update().get(pk=self.stock_id)
        self.succursale_id = stock.succursale_id
        self.domaine_id = stock.domaine_id
        self.variante_id = stock.variante_id
        delta = self._delta()
        if delta < 0 and (stock.quantite <= 0 or -delta > stock.quantite):
            raise ValidationError(
                f'{stock.variante.article.code} : stock à 0 ou insuffisant. '
                f'Stock disponible : {stock.quantite}.'
            )
        self.stock_avant = stock.quantite
        stock.quantite += delta
        stock.save(update_fields=['quantite'])
        self.stock_apres = stock.quantite
        self.save()
        AlerteStockBoutique.synchroniser(stock)


class AlerteStockBoutique(models.Model):
    """Alerte générée par le stock d'une variante (une ACTIVE par stock + type)."""

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
    variante = models.ForeignKey(
        VarianteArticle,
        on_delete=models.CASCADE,
        related_name='alertes_stock',
        verbose_name='variante',
    )
    type = models.CharField('type', max_length=12, choices=Type.choices)
    seuil = models.PositiveIntegerField('seuil')
    quantite_actuelle = models.IntegerField('quantité actuelle')
    statut = models.CharField(
        'statut', max_length=10, choices=Statut.choices, default=Statut.ACTIVE)
    date_creation = models.DateTimeField('créée le', default=timezone.now)
    date_resolution = models.DateTimeField('résolue le', null=True, blank=True)

    class Meta:
        verbose_name = 'alerte de stock boutique'
        verbose_name_plural = 'alertes de stock boutique'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.get_type_display()} {self.variante.article.code} (stock {self.quantite_actuelle} / seuil {self.seuil})'

    @property
    def classe_stock(self):
        return 'row-alert' if self.type == self.Type.RUPTURE else 'row-vigilance'

    @property
    def niveau_stock(self):
        return self.get_type_display()

    @classmethod
    def synchroniser(cls, stock):
        """L'alerte s'évalue sur le stock de la variante : une ACTIVE par
        (stock, type) ; résolution quand le stock remonte au-dessus du seuil."""
        seuil = stock.variante.seuil_alerte
        if stock.quantite <= 0:
            type_ = cls.Type.RUPTURE
        elif seuil and stock.quantite <= seuil:
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
                'variante': stock.variante,
                'seuil': seuil,
                'quantite_actuelle': stock.quantite,
            },
        )


class Vente(models.Model):
    """Vente boutique. Workflow : soumission unique → VALIDEE (mouvements SORTIE
    immédiats) ou PENDING_VALIDATION (validation responsable) → VALIDEE."""

    class Statut(models.TextChoices):
        BROUILLON = 'BROUILLON', 'Brouillon'
        PENDING_VALIDATION = 'PENDING_VALIDATION', 'En attente de validation'
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
        'paiement', max_length=15, choices=Paiement.choices, default=Paiement.ESPECES)
    montant_recu = models.DecimalField('montant reçu', max_digits=12, decimal_places=2, default=Decimal('0'))
    statut = models.CharField(
        'statut', max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    sous_total = models.DecimalField('sous-total', max_digits=12, decimal_places=2, default=Decimal('0'))
    remise = models.DecimalField('remise', max_digits=12, decimal_places=2, default=Decimal('0'))
    total = models.DecimalField('total', max_digits=12, decimal_places=2, default=Decimal('0'))
    date_validation = models.DateTimeField('date de validation', null=True, blank=True)
    commentaire = models.CharField(
        'commentaire', max_length=300, blank=True,
        help_text='Motif de la décision (annulation) renseigné par le responsable.')

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

    @property
    def ecart_paiement(self):
        return self.montant_recu - self.total

    def recalculer(self):
        sous_total = sum(
            (ligne.total for ligne in self.lignes.all()),
            start=Decimal('0'),
        )
        total = max(sous_total - self.remise, Decimal('0'))
        self.sous_total = sous_total
        self.total = total
        self.save(update_fields=['sous_total', 'total'])

    def analyser_stock(self):
        """Pré-validation : lignes dont la quantité dépasse le stock de la variante."""
        ruptures = []
        for ligne in self.lignes.select_related('variante', 'variante__article'):
            stock = StockBoutique.objects.filter(
                variante_id=ligne.variante_id,
                succursale_id=self.succursale_id,
                domaine_id=self.domaine_id,
            ).first()
            dispo = stock.quantite if stock else 0
            if dispo <= 0 or ligne.quantite > dispo:
                ruptures.append({
                    'variante': ligne.variante,
                    'article': ligne.variante.article,
                    'quantite': ligne.quantite,
                    'stock': dispo,
                })
        return ruptures

    def _appliquer_sorties(self):
        """Crée les mouvements SORTIE et décrémente le stock de chaque variante.

        Anti-double : une ligne déjà pourvue d'un mouvement est ignorée.
        Lève une ValidationError (message clair) si le stock est insuffisant.
        """
        for ligne in self.lignes.select_related('variante', 'variante__article'):
            if ligne.mouvement_id:
                continue
            var = ligne.variante
            stock = StockBoutique.obtenir(var, self.succursale, self.domaine)
            mouvement = MouvementStockBoutique(
                variante=var,
                stock=stock,
                type=MouvementStockBoutique.Type.SORTIE,
                quantite=ligne.quantite,
                motif=f'Vente {self.numero}',
                date_mouvement=self.date_vente,
                utilisateur=self.utilisateur,
            )
            try:
                mouvement.valider()
            except ValidationError as exc:
                message = exc.messages[0] if hasattr(exc, 'messages') else str(exc)
                raise ValidationError(
                    f'Stock insuffisant pour la variante {var.article.code} '
                    f'({var.label}). {message}'
                )
            ligne.mouvement = mouvement
            ligne.save(update_fields=['mouvement'])

    def annuler(self, commentaire=''):
        if self.statut in (self.Statut.VALIDEE, self.Statut.ANNULEE):
            raise ValidationError(
                'Cette vente ne peut pas être annulée (statut actuel : '
                f'{self.get_statut_display()}). Pour une vente validée, prévoir un retour.'
            )
        self.statut = self.Statut.ANNULEE
        self.commentaire = commentaire
        self.save(update_fields=['statut', 'commentaire'])


class VenteLigne(models.Model):
    """Ligne de vente : référence une variante et conserve le prix appliqué."""

    vente = models.ForeignKey(
        Vente, on_delete=models.CASCADE, related_name='lignes', verbose_name='vente')
    variante = models.ForeignKey(
        VarianteArticle,
        on_delete=models.PROTECT,
        related_name='lignes_vente',
        verbose_name='variante',
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
        return f'{self.vente.numero} — {self.variante.article.code} × {self.quantite}'

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
        'core.Succursale', on_delete=models.PROTECT,
        related_name='inventaires_boutique', verbose_name='succursale')
    domaine = models.ForeignKey(
        'core.Domaine', on_delete=models.PROTECT,
        related_name='inventaires_boutique', verbose_name='domaine d’activité',
        null=True, blank=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='inventaires_boutique', verbose_name='responsable')
    commentaire = models.TextField('commentaire', blank=True)
    portee = models.CharField(
        'portée', max_length=12, choices=Portee.choices, default=Portee.COMPLET)
    statut = models.CharField(
        'statut', max_length=12, choices=Statut.choices, default=Statut.BROUILLON)
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
        lignes = list(self.lignes.select_related('variante', 'variante__article'))
        if not lignes:
            raise ValidationError('Impossible de valider un inventaire sans ligne.')
        with transaction.atomic():
            for ligne in lignes:
                ligne.creer_ajustement(self.responsable)
            self.statut = self.Statut.VALIDE
            self.date_validation = timezone.now()
            self.save(update_fields=['statut', 'date_validation'])


class LigneInventaireBoutique(models.Model):
    """Ligne d'inventaire au niveau de la variante : théorique vs physique + écart."""

    inventaire = models.ForeignKey(
        InventaireBoutique, on_delete=models.CASCADE,
        related_name='lignes', verbose_name='inventaire')
    variante = models.ForeignKey(
        VarianteArticle, on_delete=models.PROTECT,
        related_name='lignes_inventaire', verbose_name='variante')
    stock_systeme = models.IntegerField('stock système')
    stock_physique = models.IntegerField('stock physique')
    motif = models.CharField('motif', max_length=200, blank=True)
    mouvement = models.OneToOneField(
        MouvementStockBoutique, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ligne_inventaire',
        verbose_name='mouvement d’ajustement')

    class Meta:
        verbose_name = 'ligne d’inventaire boutique'
        verbose_name_plural = 'lignes d’inventaire boutique'
        unique_together = [('inventaire', 'variante')]

    def __str__(self):
        return f'{self.variante.article.code} ({self.ecart:+d})'

    @property
    def ecart(self):
        return self.stock_physique - self.stock_systeme

    def creer_ajustement(self, utilisateur):
        ecart = self.ecart
        if ecart == 0:
            return None
        if not self.motif:
            raise ValidationError(
                f'Un motif est obligatoire pour ajuster {self.variante.article.code} '
                f'(écart {ecart:+d}).'
            )
        stock = StockBoutique.obtenir(
            self.variante,
            self.inventaire.succursale,
            self.inventaire.domaine,
        )
        mouvement = MouvementStockBoutique(
            variante=self.variante,
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
