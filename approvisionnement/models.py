from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class Module(models.Model):
    nom = models.CharField('nom', max_length=100, unique=True)

    class Meta:
        verbose_name = 'module'
        verbose_name_plural = 'modules'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Acteur(models.Model):
    nom = models.CharField('nom', max_length=100, unique=True)

    class Meta:
        verbose_name = 'acteur'
        verbose_name_plural = 'acteurs'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Fonctionnalite(models.Model):
    code = models.CharField('code', max_length=20, unique=True)
    module = models.ForeignKey(
        Module,
        on_delete=models.PROTECT,
        related_name='fonctionnalites',
        verbose_name='module',
    )
    libelle = models.CharField('fonctionnalité', max_length=150)
    acteurs = models.ManyToManyField(
        Acteur,
        related_name='fonctionnalites',
        verbose_name='acteurs',
    )
    comportement_attendu = models.TextField('comportement attendu')
    donnees_principales = models.TextField('données principales')
    regles_gestion = models.TextField('règles de gestion')
    priorite = models.CharField('priorité', max_length=50, blank=True)

    class Meta:
        verbose_name = 'fonctionnalité'
        verbose_name_plural = 'fonctionnalités'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} — {self.libelle}'


class Categorie(models.Model):
    nom = models.CharField('nom', max_length=100, unique=True)

    class Meta:
        verbose_name = 'catégorie'
        verbose_name_plural = 'catégories'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Unite(models.Model):
    code = models.CharField('code', max_length=10, unique=True)
    libelle = models.CharField('libellé', max_length=50)

    class Meta:
        verbose_name = 'unité'
        verbose_name_plural = 'unités'
        ordering = ['code']

    def __str__(self):
        return self.code


class Fournisseur(models.Model):
    nom = models.CharField('nom', max_length=150)
    telephone = models.CharField('téléphone', max_length=30, blank=True)
    email = models.EmailField('e-mail', blank=True)
    adresse = models.TextField('adresse', blank=True)

    class Meta:
        verbose_name = 'fournisseur'
        verbose_name_plural = 'fournisseurs'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Article(models.Model):
    code = models.CharField('code', max_length=50, unique=True)
    designation = models.CharField('désignation', max_length=200)
    categorie = models.ForeignKey(
        Categorie,
        on_delete=models.PROTECT,
        related_name='articles',
        verbose_name='catégorie',
    )
    unite = models.ForeignKey(
        Unite,
        on_delete=models.PROTECT,
        related_name='articles',
        verbose_name='unité',
    )
    seuil_minimum = models.PositiveIntegerField('seuil minimum', default=0)
    stock = models.IntegerField('stock', default=0)

    class Meta:
        verbose_name = 'article'
        verbose_name_plural = 'articles'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} — {self.designation}'

    @property
    def en_alerte(self):
        return self.stock <= self.seuil_minimum


class MouvementStock(models.Model):
    class Type(models.TextChoices):
        ENTREE = 'ENTREE', 'Entrée'
        SORTIE = 'SORTIE', 'Sortie'
        AJUSTEMENT = 'AJUSTEMENT', 'Ajustement'

    article = models.ForeignKey(
        Article,
        on_delete=models.PROTECT,
        related_name='mouvements',
        verbose_name='article',
    )
    type_mouvement = models.CharField(
        'type',
        max_length=12,
        choices=Type.choices,
    )
    quantite = models.IntegerField('quantité')
    fournisseur = models.ForeignKey(
        Fournisseur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entrees',
        verbose_name='fournisseur',
    )
    reference = models.CharField('référence', max_length=100, blank=True)
    motif = models.CharField('motif', max_length=200, blank=True)
    destination = models.CharField('destination', max_length=200, blank=True)
    date_mouvement = models.DateTimeField('date', default=timezone.now)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='mouvements_stock',
        verbose_name='utilisateur',
    )
    valide = models.BooleanField('validé', default=False)
    autorisation_depassement = models.BooleanField(
        'autorisation de dépassement',
        default=False,
        help_text='Autorise une sortie au-delà du stock disponible.',
    )
    stock_avant = models.IntegerField('stock avant', null=True, blank=True)
    stock_apres = models.IntegerField('stock après', null=True, blank=True)
    date_validation = models.DateTimeField('date de validation', null=True, blank=True)

    class Meta:
        verbose_name = 'mouvement de stock'
        verbose_name_plural = 'mouvements de stock'
        ordering = ['-date_mouvement']

    def __str__(self):
        return f'{self.get_type_mouvement_display()} {self.article.code} × {self.quantite}'

    def clean(self):
        if self.type_mouvement == self.Type.ENTREE and self.quantite <= 0:
            raise ValidationError({'quantite': "La quantité d'une entrée doit être positive."})
        if self.type_mouvement == self.Type.SORTIE and self.quantite <= 0:
            raise ValidationError({'quantite': 'La quantité d’une sortie doit être positive.'})
        if self.type_mouvement == self.Type.ENTREE and not self.fournisseur_id:
            raise ValidationError({'fournisseur': 'Le fournisseur est obligatoire pour une entrée.'})
        if self.type_mouvement == self.Type.SORTIE and not self.motif:
            raise ValidationError({'motif': 'Le motif est obligatoire pour une sortie.'})
        if self.type_mouvement == self.Type.AJUSTEMENT and self.quantite == 0:
            raise ValidationError({'quantite': 'Un ajustement ne peut pas être nul.'})

    def _delta(self):
        if self.type_mouvement == self.Type.SORTIE:
            return -self.quantite
        return self.quantite

    def valider(self):
        if self.valide:
            raise ValidationError('Ce mouvement est déjà validé.')
        self.clean()
        with transaction.atomic():
            article = Article.objects.select_for_update().get(pk=self.article_id)
            delta = self._delta()
            if (
                self.type_mouvement == self.Type.SORTIE
                and self.quantite > article.stock
                and not self.autorisation_depassement
            ):
                raise ValidationError(
                    'Stock insuffisant. Une autorisation est requise pour dépasser le stock.'
                )
            self.stock_avant = article.stock
            article.stock += delta
            article.save(update_fields=['stock'])
            self.stock_apres = article.stock
            self.valide = True
            self.date_validation = timezone.now()
            self.save()
            AlerteStock.synchroniser(article)


class AlerteStock(models.Model):
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='alertes',
        verbose_name='article',
    )
    stock = models.IntegerField('stock')
    seuil = models.PositiveIntegerField('seuil')
    date_alerte = models.DateTimeField('date', default=timezone.now)
    active = models.BooleanField('active', default=True)

    class Meta:
        verbose_name = 'alerte stock'
        verbose_name_plural = 'alertes stock'
        ordering = ['-date_alerte']

    def __str__(self):
        return f'Alerte {self.article.code} (stock {self.stock} ≤ {self.seuil})'

    @classmethod
    def synchroniser(cls, article):
        if article.en_alerte:
            cls.objects.update_or_create(
                article=article,
                active=True,
                defaults={
                    'stock': article.stock,
                    'seuil': article.seuil_minimum,
                    'date_alerte': timezone.now(),
                },
            )
        else:
            cls.objects.filter(article=article, active=True).update(active=False)


class Inventaire(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = 'BROUILLON', 'Brouillon'
        VALIDE = 'VALIDE', 'Validé'

    date_inventaire = models.DateField('date', default=timezone.now)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='inventaires',
        verbose_name='responsable',
    )
    commentaire = models.TextField('commentaire', blank=True)
    statut = models.CharField(
        'statut',
        max_length=12,
        choices=Statut.choices,
        default=Statut.BROUILLON,
    )
    date_validation = models.DateTimeField('date de validation', null=True, blank=True)

    class Meta:
        verbose_name = 'inventaire'
        verbose_name_plural = 'inventaires'
        ordering = ['-date_inventaire']

    def __str__(self):
        return f'Inventaire du {self.date_inventaire}'

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


class LigneInventaire(models.Model):
    inventaire = models.ForeignKey(
        Inventaire,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='inventaire',
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.PROTECT,
        related_name='lignes_inventaire',
        verbose_name='article',
    )
    stock_systeme = models.IntegerField('stock système')
    stock_physique = models.IntegerField('stock physique')
    motif = models.CharField('motif', max_length=200, blank=True)
    mouvement = models.OneToOneField(
        MouvementStock,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ligne_inventaire',
        verbose_name='mouvement d’ajustement',
    )

    class Meta:
        verbose_name = 'ligne d’inventaire'
        verbose_name_plural = 'lignes d’inventaire'
        unique_together = [('inventaire', 'article')]

    def __str__(self):
        return f'{self.article.code} ({self.ecart:+d})'

    @property
    def ecart(self):
        return self.stock_physique - self.stock_systeme

    def creer_ajustement(self, utilisateur):
        ecart = self.ecart
        if ecart == 0:
            return None
        if not self.motif:
            raise ValidationError(
                f'Un motif est obligatoire pour ajuster {self.article.code} (écart {ecart:+d}).'
            )
        mouvement = MouvementStock(
            article=self.article,
            type_mouvement=MouvementStock.Type.AJUSTEMENT,
            quantite=ecart,
            motif=self.motif,
            utilisateur=utilisateur,
        )
        mouvement.valider()
        self.mouvement = mouvement
        self.save(update_fields=['mouvement'])
        return mouvement
