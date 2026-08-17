"""Module Boutique — articles d'habillement, ventes.

Le stock reste centralisé autour d'`Article` (approvisionnement) et de
`MouvementStock` : le domaine BOUTIQUE et la succursale définissent le périmètre
du stock. `ArticleBoutique` n'ajoute QUE les informations spécifiques
(taille, couleur, prix, SKU) sans dupliquer le stock.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from approvisionnement.models import Article, MouvementStock


class ArticleBoutique(models.Model):
    """Complément boutique d'un Article (variante, prix, SKU).

    Chaque variante stockable (ex. T-shirt / Noir / M) est un `Article` dédié
    (code propre, succursale + domaine BOUTIQUE), lié ici à ses infos boutique.
    """

    class Statut(models.TextChoices):
        ACTIF = 'ACTIF', 'Actif'
        INACTIF = 'INACTIF', 'Inactif'

    article = models.OneToOneField(
        Article,
        on_delete=models.PROTECT,
        related_name='infos_boutique',
        verbose_name='article',
    )
    type_produit = models.CharField('type de produit', max_length=50, blank=True)
    taille = models.CharField('taille', max_length=20, blank=True)
    couleur = models.CharField('couleur', max_length=30, blank=True)
    reference = models.CharField('référence / SKU', max_length=50, blank=True)
    prix_achat = models.DecimalField('prix d’achat', max_digits=12, decimal_places=2, default=Decimal('0'))
    prix_vente = models.DecimalField('prix de vente', max_digits=12, decimal_places=2, default=Decimal('0'))
    prix_limite = models.DecimalField(
        'prix limite',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text='Prix plancher : aucune vente en dessous de ce prix.',
    )
    statut = models.CharField(
        'statut',
        max_length=10,
        choices=Statut.choices,
        default=Statut.ACTIF,
    )
    en_vente = models.BooleanField('en vente', default=True)

    class Meta:
        verbose_name = 'article boutique'
        verbose_name_plural = 'articles boutique'
        permissions = [
            ('view_stock', 'Peut consulter le stock boutique'),
            ('adjust_stock', 'Peut ajuster le stock boutique'),
        ]

    def __str__(self):
        variantes = ' / '.join(
            p for p in (self.taille, self.couleur) if p
        )
        return f'{self.article.code} — {self.article.designation}' + (
            f' ({variantes})' if variantes else ''
        )


class Vente(models.Model):
    """Vente boutique : validation atomique → MouvementStock SORTIE."""

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
        """Lignes dont la quantité dépasse le stock disponible (validation refusée)."""
        ruptures = []
        for ligne in self.lignes.select_related('article'):
            if ligne.article.stock <= 0 or ligne.quantite > ligne.article.stock:
                ruptures.append(
                    {
                        'article': ligne.article,
                        'quantite': ligne.quantite,
                        'stock': ligne.article.stock,
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
                # Règle prix_limite : on ne peut pas vendre sous le prix plancher.
                infos = getattr(ligne.article, 'infos_boutique', None)
                if infos and infos.prix_limite and ligne.prix_unitaire < infos.prix_limite:
                    raise ValidationError(
                        f'{ligne.article.code} : prix {ligne.prix_unitaire} inférieur '
                        f'à la limite {infos.prix_limite}. Vente refusée.'
                    )
                mouvement = MouvementStock(
                    article=ligne.article,
                    type_mouvement=MouvementStock.Type.SORTIE,
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
    vente = models.ForeignKey(
        Vente,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='vente',
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.PROTECT,
        related_name='lignes_vente',
        verbose_name='article',
    )
    quantite = models.PositiveIntegerField('quantité')
    prix_unitaire = models.DecimalField('prix unitaire', max_digits=12, decimal_places=2, default=Decimal('0'))
    remise = models.DecimalField('remise', max_digits=12, decimal_places=2, default=Decimal('0'))
    total = models.DecimalField('total', max_digits=12, decimal_places=2, default=Decimal('0'))
    mouvement = models.OneToOneField(
        MouvementStock,
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
