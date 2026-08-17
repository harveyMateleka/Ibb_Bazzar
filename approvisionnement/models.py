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
    nombre_portions = models.PositiveIntegerField(
        'nombre de portions',
        default=0,
        help_text=(
            'Mettre une valeur supérieure à 0 pour les vivres frais '
            '(poisson, poulet, etc.). Un champ portions sera alors demandé à la sortie.'
        ),
    )

    class Meta:
        verbose_name = 'catégorie'
        verbose_name_plural = 'catégories'
        ordering = ['nom']

    def __str__(self):
        return self.nom

    @property
    def exige_portions(self):
        return self.nombre_portions > 0


class Unite(models.Model):
    code = models.CharField('code', max_length=10, unique=True)
    libelle = models.CharField('libellé', max_length=50)

    class Meta:
        verbose_name = 'unité'
        verbose_name_plural = 'unités'
        ordering = ['code']

    def __str__(self):
        return self.libelle or self.code


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


class Service(models.Model):
    nom = models.CharField('nom', max_length=150, unique=True)

    class Meta:
        verbose_name = 'service'
        verbose_name_plural = 'services'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class BonApprovisionnement(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = 'BROUILLON', 'Brouillon'
        VALIDE = 'VALIDE', 'Validé'

    numero = models.CharField('numéro', max_length=20, unique=True, editable=False)
    date_approvisionnement = models.DateTimeField('date', default=timezone.now)
    fournisseur = models.ForeignKey(
        Fournisseur,
        on_delete=models.PROTECT,
        related_name='bons_approvisionnement',
        verbose_name='fournisseur',
    )
    reference = models.CharField('référence', max_length=100, blank=True)
    commentaire = models.TextField('commentaire', blank=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='bons_approvisionnement',
        verbose_name='utilisateur',
    )
    statut = models.CharField(
        'statut',
        max_length=12,
        choices=Statut.choices,
        default=Statut.BROUILLON,
    )
    date_validation = models.DateTimeField('date de validation', null=True, blank=True)

    class Meta:
        verbose_name = 'bon d’approvisionnement'
        verbose_name_plural = 'bons d’approvisionnement'
        ordering = ['-date_approvisionnement']

    def __str__(self):
        return self.numero

    @classmethod
    def prochain_numero(cls):
        annee = timezone.localdate().year
        prefixe = f'APP-{annee}-'
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
            raise ValidationError('Ce bon d’approvisionnement est déjà validé.')
        lignes = [ligne for ligne in self.lignes.select_related('article') if ligne.quantite > 0]
        if not lignes:
            raise ValidationError('Ajoutez au moins une ligne de produit avant de valider.')
        with transaction.atomic():
            for ligne in lignes:
                mouvement = MouvementStock(
                    article=ligne.article,
                    type_mouvement=MouvementStock.Type.ENTREE,
                    quantite=ligne.quantite,
                    fournisseur=self.fournisseur,
                    reference=self.reference or self.numero,
                    date_mouvement=self.date_approvisionnement,
                    utilisateur=self.utilisateur,
                    bon=self,
                )
                mouvement.valider()
                ligne.mouvement = mouvement
                ligne.save(update_fields=['mouvement'])
            self.statut = self.Statut.VALIDE
            self.date_validation = timezone.now()
            self.save(update_fields=['statut', 'date_validation'])
            Approvisionnement.enregistrer_entree(self)


class BonSortie(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = 'BROUILLON', 'Brouillon'
        VALIDE = 'VALIDE', 'Validé'

    numero = models.CharField('numéro', max_length=20, unique=True, editable=False)
    date_sortie = models.DateTimeField('date', default=timezone.now)
    motif = models.CharField('motif', max_length=200)
    destination = models.ForeignKey(
        'Service',
        on_delete=models.PROTECT,
        related_name='bons_sortie',
        verbose_name='service',
        null=True,
        blank=True,
    )
    autorisation_depassement = models.BooleanField(
        'autorisation de dépassement',
        default=False,
        help_text='Autorise une sortie au-delà du stock disponible.',
    )
    commentaire = models.TextField('commentaire', blank=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='bons_sortie',
        verbose_name='utilisateur',
    )
    statut = models.CharField(
        'statut',
        max_length=12,
        choices=Statut.choices,
        default=Statut.BROUILLON,
    )
    date_validation = models.DateTimeField('date de validation', null=True, blank=True)

    class Meta:
        verbose_name = 'bon de sortie'
        verbose_name_plural = 'bons de sortie'
        ordering = ['-date_sortie']

    def __str__(self):
        return self.numero

    @classmethod
    def prochain_numero(cls):
        annee = timezone.localdate().year
        prefixe = f'SOR-{annee}-'
        dernier = (
            cls.objects.select_for_update()
            .filter(numero__startswith=prefixe)
            .order_by('-numero')
            .first()
        )
        sequence = int(dernier.numero.rsplit('-', 1)[-1]) + 1 if dernier else 1
        return f'{prefixe}{sequence:04d}'

    @property
    def nom_destination(self):
        return self.destination.nom if self.destination_id else ''

    def depassements_stock(self):
        ruptures, _seuils = self.analyser_stock()
        return ruptures

    def analyser_stock(self):
        restants = {}
        ruptures = []
        seuils = []
        for ligne in self.lignes.select_related('article', 'article__unite'):
            if ligne.quantite <= 0:
                continue
            article = ligne.article
            stock = restants.get(article.pk, article.stock)
            if stock <= 0:
                ruptures.append(
                    {
                        'article': article,
                        'quantite': ligne.quantite,
                        'stock': stock,
                        'motif': 'Stock à 0 : la sortie de cet article est refusée.',
                    }
                )
            elif ligne.quantite > stock:
                ruptures.append(
                    {
                        'article': article,
                        'quantite': ligne.quantite,
                        'stock': stock,
                        'motif': 'Quantité supérieure au stock disponible : sortie refusée.',
                    }
                )
            elif stock <= article.seuil_minimum:
                seuils.append(
                    {
                        'article': article,
                        'quantite': ligne.quantite,
                        'stock': stock,
                        'seuil': article.seuil_minimum,
                    }
                )
            restants[article.pk] = stock - ligne.quantite
        return ruptures, seuils

    def valider(self, autorisation_depassement=False):
        if self.statut == self.Statut.VALIDE:
            raise ValidationError('Ce bon de sortie est déjà validé.')
        lignes = [
            ligne
            for ligne in self.lignes.select_related('article', 'article__categorie')
            if ligne.quantite > 0
        ]
        if not lignes:
            raise ValidationError('Ajoutez au moins une ligne de produit avant de valider.')
        if autorisation_depassement:
            self.autorisation_depassement = True
        with transaction.atomic():
            for ligne in lignes:
                if ligne.article.exige_portions and ligne.nombre_portions <= 0:
                    raise ValidationError(
                        f'Indiquez le nombre de portions pour {ligne.article}.'
                    )
                mouvement = MouvementStock(
                    article=ligne.article,
                    type_mouvement=MouvementStock.Type.SORTIE,
                    quantite=ligne.quantite,
                    motif=self.motif,
                    destination=self.nom_destination,
                    date_mouvement=self.date_sortie,
                    utilisateur=self.utilisateur,
                    autorisation_depassement=self.autorisation_depassement,
                    nombre_portions=ligne.nombre_portions,
                    bon_sortie=self,
                )
                mouvement.valider()
                ligne.mouvement = mouvement
                ligne.save(update_fields=['mouvement'])
            self.statut = self.Statut.VALIDE
            self.date_validation = timezone.now()
            champs = ['statut', 'date_validation']
            if autorisation_depassement:
                champs.append('autorisation_depassement')
            self.save(update_fields=champs)
            Approvisionnement.enregistrer_sortie(self)


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
    def en_rupture(self):
        return self.stock <= 0

    @property
    def en_alerte(self):
        return self.stock <= self.seuil_minimum

    @property
    def en_vigilance(self):
        return self.seuil_minimum + 1 <= self.stock <= self.seuil_minimum + 10

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

    @property
    def exige_portions(self):
        return self.categorie.exige_portions


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
    nombre_portions = models.PositiveIntegerField(
        'nombre de portions',
        default=0,
        help_text='Renseigné à la sortie pour les vivres frais (poisson, poulet, etc.).',
    )
    bon = models.ForeignKey(
        'BonApprovisionnement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mouvements',
        verbose_name='bon d’approvisionnement',
    )
    bon_sortie = models.ForeignKey(
        'BonSortie',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mouvements',
        verbose_name='bon de sortie',
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
        if (
            self.type_mouvement == self.Type.SORTIE
            and self.article_id
            and self.article.exige_portions
            and self.nombre_portions <= 0
        ):
            raise ValidationError({
                'nombre_portions': 'Indiquez le nombre de portions pour cette catégorie de vivres frais.',
            })
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
                and (article.stock <= 0 or self.quantite > article.stock)
            ):
                raise ValidationError(
                    f'{article} : stock à 0 ou insuffisant. La sortie est refusée.'
                )
            if (
                self.type_mouvement == self.Type.SORTIE
                and article.stock <= article.seuil_minimum
                and not self.autorisation_depassement
            ):
                raise ValidationError(
                    f'{article} : le stock a atteint le seuil ({article.seuil_minimum}). '
                    'Une autorisation du propriétaire est requise.'
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
        return f'Alerte {self.article.code} (stock {self.stock} / seuil {self.seuil})'

    @property
    def en_rupture(self):
        return self.stock <= 0

    @property
    def en_vigilance(self):
        return self.seuil + 1 <= self.stock <= self.seuil + 10

    @property
    def classe_stock(self):
        if self.stock <= self.seuil:
            return 'row-alert'
        return 'row-vigilance'

    @property
    def niveau_stock(self):
        if self.stock <= 0:
            return 'Rupture'
        if self.stock <= self.seuil:
            return 'Seuil atteint'
        return 'Vigilance'

    @classmethod
    def synchroniser(cls, article):
        if article.a_signaler:
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
        constraints = [
            models.UniqueConstraint(
                fields=['date_inventaire'],
                name='inventaire_unique_par_jour',
            ),
        ]

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


class LigneApprovisionnement(models.Model):
    bon = models.ForeignKey(
        BonApprovisionnement,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='bon d’approvisionnement',
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.PROTECT,
        related_name='lignes_approvisionnement',
        verbose_name='article',
    )
    quantite = models.PositiveIntegerField('quantité')
    mouvement = models.OneToOneField(
        MouvementStock,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ligne_approvisionnement',
        verbose_name='mouvement d’entrée',
    )

    class Meta:
        verbose_name = 'ligne d’approvisionnement'
        verbose_name_plural = 'lignes d’approvisionnement'

    def __str__(self):
        return f'{self.bon.numero} — {self.article.code} × {self.quantite}'


class LigneSortie(models.Model):
    bon = models.ForeignKey(
        BonSortie,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='bon de sortie',
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.PROTECT,
        related_name='lignes_sortie',
        verbose_name='article',
    )
    quantite = models.PositiveIntegerField('quantité')
    nombre_portions = models.PositiveIntegerField('nombre de portions', default=0)
    mouvement = models.OneToOneField(
        MouvementStock,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ligne_sortie',
        verbose_name='mouvement de sortie',
    )

    class Meta:
        verbose_name = 'ligne de sortie'
        verbose_name_plural = 'lignes de sortie'

    def __str__(self):
        return f'{self.bon.numero} — {self.article.code} × {self.quantite}'


class Approvisionnement(models.Model):
    """Journal unique pour retracer les entrées et les sorties."""

    class Type(models.TextChoices):
        ENTREE = 'ENTREE', 'Entrée'
        SORTIE = 'SORTIE', 'Sortie'

    numero = models.CharField('numéro', max_length=20, unique=True)
    type_operation = models.CharField(
        'type',
        max_length=12,
        choices=Type.choices,
    )
    date_operation = models.DateTimeField('date')
    fournisseur = models.ForeignKey(
        Fournisseur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historiques_approvisionnement',
        verbose_name='fournisseur',
    )
    motif = models.CharField('motif', max_length=200, blank=True)
    destination = models.CharField('destination', max_length=200, blank=True)
    reference = models.CharField('référence', max_length=100, blank=True)
    commentaire = models.TextField('commentaire', blank=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='historiques_approvisionnement',
        verbose_name='utilisateur',
    )
    bon_entree = models.OneToOneField(
        BonApprovisionnement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal',
        verbose_name='bon d’entrée',
    )
    bon_sortie = models.OneToOneField(
        BonSortie,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal',
        verbose_name='bon de sortie',
    )
    date_enregistrement = models.DateTimeField('enregistré le', default=timezone.now)

    class Meta:
        verbose_name = 'approvisionnement'
        verbose_name_plural = 'approvisionnements'
        ordering = ['-date_operation', '-id']

    def __str__(self):
        return f'{self.numero} ({self.get_type_operation_display()})'

    @classmethod
    def enregistrer_entree(cls, bon):
        journal = cls.objects.create(
            numero=bon.numero,
            type_operation=cls.Type.ENTREE,
            date_operation=bon.date_approvisionnement,
            fournisseur=bon.fournisseur,
            reference=bon.reference,
            commentaire=bon.commentaire,
            utilisateur=bon.utilisateur,
            bon_entree=bon,
        )
        for ligne in bon.lignes.select_related('article', 'mouvement'):
            if not ligne.mouvement_id:
                continue
            ApprovisionnementLigne.objects.create(
                approvisionnement=journal,
                article=ligne.article,
                quantite=ligne.quantite,
                stock_avant=ligne.mouvement.stock_avant,
                stock_apres=ligne.mouvement.stock_apres,
                mouvement=ligne.mouvement,
            )
        return journal

    @classmethod
    def enregistrer_sortie(cls, bon):
        journal = cls.objects.create(
            numero=bon.numero,
            type_operation=cls.Type.SORTIE,
            date_operation=bon.date_sortie,
            motif=bon.motif,
            destination=bon.nom_destination,
            commentaire=bon.commentaire,
            utilisateur=bon.utilisateur,
            bon_sortie=bon,
        )
        for ligne in bon.lignes.select_related('article', 'mouvement'):
            if not ligne.mouvement_id:
                continue
            ApprovisionnementLigne.objects.create(
                approvisionnement=journal,
                article=ligne.article,
                quantite=ligne.quantite,
                nombre_portions=ligne.nombre_portions,
                stock_avant=ligne.mouvement.stock_avant,
                stock_apres=ligne.mouvement.stock_apres,
                mouvement=ligne.mouvement,
            )
        return journal


class ApprovisionnementLigne(models.Model):
    approvisionnement = models.ForeignKey(
        Approvisionnement,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='approvisionnement',
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.PROTECT,
        related_name='lignes_journal_approvisionnement',
        verbose_name='article',
    )
    quantite = models.IntegerField('quantité')
    nombre_portions = models.PositiveIntegerField('nombre de portions', default=0)
    stock_avant = models.IntegerField('stock avant', null=True, blank=True)
    stock_apres = models.IntegerField('stock après', null=True, blank=True)
    mouvement = models.OneToOneField(
        MouvementStock,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ligne_journal',
        verbose_name='mouvement',
    )

    class Meta:
        verbose_name = 'ligne d’historique d’approvisionnement'
        verbose_name_plural = 'lignes d’historique d’approvisionnement'

    def __str__(self):
        return f'{self.approvisionnement.numero} — {self.article.code}'
