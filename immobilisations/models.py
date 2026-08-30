"""Module Immobilisations — domaine d'activité indépendant de l'Approvisionnement.

Chaque bien a son cycle de vie entièrement historisé :
  CategorieImmobilisation   référentiel de classement,
  Immobilisation            le bien (jamais supprimé physiquement),
  Affectation               affectation à un service / succursale / emplacement,
  Deplacement               changement de situation,
  Reparation                déclaration + terminaison de réparation,
  Casse                     déclaration + évaluation (décision),
  Declassement              demande + validation (contrôlée par permission).

L'utilisateur connecté est TOUJOURS l'acteur de l'action (champ `par`), jamais
l'objet de l'affectation : on affecte un bien à un service/succursale/emplacement.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class CategorieImmobilisation(models.Model):
    """Catégorie de biens (référentiel)."""

    nom = models.CharField('nom', max_length=100, unique=True)
    code = models.CharField('code', max_length=20, unique=True)
    description = models.TextField('description', blank=True)
    actif = models.BooleanField('actif', default=True)

    class Meta:
        verbose_name = 'catégorie d’immobilisation'
        verbose_name_plural = 'catégories d’immobilisations'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Service(models.Model):
    """Service d'affectation d'un bien (référentiel maintenu en admin)."""

    nom = models.CharField('nom', max_length=150, unique=True)
    description = models.TextField('description', blank=True)
    actif = models.BooleanField('actif', default=True)

    class Meta:
        verbose_name = 'service'
        verbose_name_plural = 'services'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Emplacement(models.Model):
    """Emplacement d'un bien (référentiel maintenu en admin)."""

    nom = models.CharField('nom', max_length=150, unique=True)
    description = models.TextField('description', blank=True)
    actif = models.BooleanField('actif', default=True)

    class Meta:
        verbose_name = 'emplacement'
        verbose_name_plural = 'emplacements'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Immobilisation(models.Model):
    """Bien durable. Ne se supprime jamais : seul le déclassement le clôture."""

    class EtatPhysique(models.TextChoices):
        NEUF = 'NEUF', 'Neuf'
        BON = 'BON', 'Bon'
        A_REPARER = 'A_REPARER', 'À réparer'
        CASSE = 'CASSE', 'Casse'

    class StatutAdministratif(models.TextChoices):
        STOCKE = 'STOCKE', 'Stocké'
        EN_SERVICE = 'EN_SERVICE', 'En service'
        EN_REPARATION = 'EN_REPARATION', 'En réparation'
        DECLASSE = 'DECLASSE', 'Déclassé'

    class StatutValidation(models.TextChoices):
        BROUILLON = 'BROUILLON', 'Brouillon'
        EN_ATTENTE = 'EN_ATTENTE', 'En attente de validation'
        VALIDE = 'VALIDE', 'Validé'
        REJETE = 'REJETE', 'Rejeté'

    code = models.CharField('code', max_length=20, unique=True, editable=False)
    designation = models.CharField('désignation', max_length=200)
    categorie = models.ForeignKey(
        CategorieImmobilisation,
        on_delete=models.PROTECT,
        related_name='immobilisations',
        verbose_name='catégorie',
        null=True,
        blank=True,
    )
    numero_serie = models.CharField('numéro de série', max_length=100, blank=True)
    valeur_acquisition = models.DecimalField(
        'valeur d’acquisition', max_digits=14, decimal_places=2, default=Decimal('0'))
    date_acquisition = models.DateField('date d’acquisition', null=True, blank=True)

    # Contexte centralisé (auto + readonly dans les formulaires).
    succursale = models.ForeignKey(
        'core.Succursale',
        on_delete=models.PROTECT,
        related_name='immobilisations',
        verbose_name='succursale',
    )
    domaine = models.ForeignKey(
        'core.Domaine',
        on_delete=models.PROTECT,
        related_name='immobilisations',
        verbose_name='domaine d’activité',
        null=True,
        blank=True,
    )

    etat_physique = models.CharField(
        'état physique', max_length=12, choices=EtatPhysique.choices,
        default=EtatPhysique.NEUF)
    statut_administratif = models.CharField(
        'statut administratif', max_length=14, choices=StatutAdministratif.choices,
        default=StatutAdministratif.STOCKE)

    # Cycle de validation : création (Brouillon) → soumission → Validation.
    statut_validation = models.CharField(
        'validation', max_length=12, choices=StatutValidation.choices,
        default=StatutValidation.BROUILLON)
    soumis_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='biens_soumis', verbose_name='soumis par')
    date_soumission = models.DateTimeField('soumis le', null=True, blank=True)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='biens_valides', verbose_name='validé par')
    date_validation = models.DateTimeField('validé le', null=True, blank=True)
    motif_rejet = models.CharField('motif de rejet', max_length=300, blank=True)

    # Entretien / durée de vie — facultatifs.
    periode_entretien = models.PositiveIntegerField(
        'période d’entretien (mois)', null=True, blank=True,
        help_text='Fréquence d’entretien en mois (facultatif).')
    duree_vie = models.PositiveIntegerField(
        'durée de vie (années)', null=True, blank=True,
        help_text='Durée prévue d’utilisation en années (facultatif).')

    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name='immobilisations',
        verbose_name='service',
        null=True,
        blank=True,
    )
    emplacement = models.ForeignKey(
        Emplacement,
        on_delete=models.PROTECT,
        related_name='immobilisations',
        verbose_name='emplacement',
        null=True,
        blank=True,
    )
    observation = models.TextField('observation', blank=True)
    date_creation = models.DateTimeField('créé le', default=timezone.now)
    date_modification = models.DateTimeField('modifié le', auto_now=True)

    class Meta:
        verbose_name = 'immobilisation'
        verbose_name_plural = 'immobilisations'
        ordering = ['code']
        permissions = [
            ('view_asset', 'Peut consulter les immobilisations'),
            ('create_asset', 'Peut créer une immobilisation'),
            ('update_asset', 'Peut modifier une immobilisation'),
            ('assign_asset', 'Peut affecter une immobilisation'),
            ('move_asset', 'Peut déplacer une immobilisation'),
            ('repair_asset', 'Peut gérer les réparations'),
            ('report_damage_asset', 'Peut déclarer une casse'),
            ('decommission_asset', 'Peut déclasser une immobilisation'),
            ('view_declassified_asset', 'Peut consulter les biens déclassés'),
            ('validate_asset', 'Peut valider une immobilisation'),
        ]

    def __str__(self):
        return f'{self.code} — {self.designation}'

    @classmethod
    def prochain_numero(cls):
        annee = timezone.localdate().year
        prefixe = f'IMM-{annee}-'
        dernier = (
            cls.objects.select_for_update()
            .filter(code__startswith=prefixe)
            .order_by('-code')
            .first()
        )
        sequence = int(dernier.code.rsplit('-', 1)[-1]) + 1 if dernier else 1
        return f'{prefixe}{sequence:04d}'

    @property
    def affectation_courante(self):
        return (
            self.affectations.filter(actif=True)
            .select_related('succursale')
            .first()
        )


class Affectation(models.Model):
    """Affectation d'un bien à un service / succursale / emplacement.

    `par` est l'utilisateur connecté qui pose l'action (acteur), pas un
    affectataire. L'ancienne affectation est clôturée (jamais supprimée)."""

    immobilisation = models.ForeignKey(
        Immobilisation,
        on_delete=models.CASCADE,
        related_name='affectations',
        verbose_name='immobilisation',
    )
    succursale = models.ForeignKey(
        'core.Succursale',
        on_delete=models.PROTECT,
        related_name='affectations_immobilisations',
        verbose_name='succursale',
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name='affectations',
        verbose_name='service',
        null=True,
        blank=True,
    )
    emplacement = models.ForeignKey(
        Emplacement,
        on_delete=models.PROTECT,
        related_name='affectations',
        verbose_name='emplacement',
        null=True,
        blank=True,
    )
    date_affectation = models.DateTimeField('date d’affectation', default=timezone.now)
    par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='affectations_immobilisations',
        verbose_name='par',
    )
    actif = models.BooleanField('active', default=True)
    date_fin = models.DateTimeField('fin', null=True, blank=True)

    class Meta:
        verbose_name = 'affectation'
        verbose_name_plural = 'affectations'
        ordering = ['-date_affectation']

    def __str__(self):
        return f'{self.immobilisation.code} → {self.succursale} ({self.service})'


class Deplacement(models.Model):
    """Déplacement d'un bien : ancienne → nouvelle situation, historisé."""

    immobilisation = models.ForeignKey(
        Immobilisation,
        on_delete=models.CASCADE,
        related_name='deplacements',
        verbose_name='immobilisation',
    )
    ancienne_succursale = models.ForeignKey(
        'core.Succursale',
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='ancienne succursale',
        null=True,
        blank=True,
    )
    nouvelle_succursale = models.ForeignKey(
        'core.Succursale',
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='nouvelle succursale',
        null=True,
        blank=True,
    )
    ancien_service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='ancien service',
        null=True,
        blank=True,
    )
    nouveau_service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='nouveau service',
        null=True,
        blank=True,
    )
    ancien_emplacement = models.ForeignKey(
        Emplacement,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='ancien emplacement',
        null=True,
        blank=True,
    )
    nouvel_emplacement = models.ForeignKey(
        Emplacement,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='nouvel emplacement',
        null=True,
        blank=True,
    )
    date_deplacement = models.DateTimeField('date de déplacement', default=timezone.now)
    motif = models.CharField('motif', max_length=200, blank=True)
    par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='deplacements_immobilisations',
        verbose_name='par',
    )

    class Meta:
        verbose_name = 'déplacement'
        verbose_name_plural = 'déplacements'
        ordering = ['-date_deplacement']

    def __str__(self):
        return f'{self.immobilisation.code} — déplacement'


class Reparation(models.Model):
    """Réparation d'un bien : déclaration puis terminaison."""

    class Statut(models.TextChoices):
        EN_COURS = 'EN_COURS', 'En cours'
        TERMINEE = 'TERMINEE', 'Terminée'

    immobilisation = models.ForeignKey(
        Immobilisation,
        on_delete=models.CASCADE,
        related_name='reparations',
        verbose_name='immobilisation',
    )
    date_reparation = models.DateTimeField('date', default=timezone.now)
    motif = models.CharField('motif', max_length=200)
    description = models.TextField('description', blank=True)
    cout = models.DecimalField('coût', max_digits=14, decimal_places=2, default=Decimal('0'))
    statut = models.CharField(
        'statut', max_length=10, choices=Statut.choices, default=Statut.EN_COURS)
    par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reparations_immobilisations',
        verbose_name='par',
    )

    class Meta:
        verbose_name = 'réparation'
        verbose_name_plural = 'réparations'
        ordering = ['-date_reparation']

    def __str__(self):
        return f'{self.immobilisation.code} — {self.get_statut_display()}'


class Casse(models.Model):
    """Déclaration de casse puis évaluation (décision)."""

    class Decision(models.TextChoices):
        REPARABLE = 'REPARABLE', 'Réparable'
        REMPLACEMENT = 'REMPLACEMENT', 'Remplacement'
        DECLASSEMENT = 'DECLASSEMENT', 'Déclassement'

    immobilisation = models.ForeignKey(
        Immobilisation,
        on_delete=models.CASCADE,
        related_name='casses',
        verbose_name='immobilisation',
    )
    date_casse = models.DateTimeField('date', default=timezone.now)
    date_dommage = models.DateField('date du dommage', null=True, blank=True,
                                    help_text='Date à laquelle le dommage est survenu (facultatif).')
    motif = models.CharField('motif', max_length=200)
    description = models.TextField('description', blank=True)
    responsable_dommage = models.CharField(
        'responsable du dommage', max_length=150, blank=True)
    decision = models.CharField(
        'décision', max_length=14, choices=Decision.choices, null=True, blank=True)
    observation = models.TextField('observation', blank=True)
    par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='casses_immobilisations',
        verbose_name='par',
    )

    class Meta:
        verbose_name = 'casse'
        verbose_name_plural = 'casses'
        ordering = ['-date_casse']

    def __str__(self):
        return f'{self.immobilisation.code} — casse'


class Declassement(models.Model):
    """Déclassement d'un bien : demande puis validation (contrôlée par permission)."""

    class Statut(models.TextChoices):
        DEMANDE = 'DEMANDE', 'Demande'
        VALIDE = 'VALIDE', 'Validé'

    immobilisation = models.ForeignKey(
        Immobilisation,
        on_delete=models.CASCADE,
        related_name='declassements',
        verbose_name='immobilisation',
    )
    date_demande = models.DateTimeField('demande le', default=timezone.now)
    motif = models.CharField('motif', max_length=200)
    statut = models.CharField(
        'statut', max_length=10, choices=Statut.choices, default=Statut.DEMANDE)
    par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='declassements_demandes',
        verbose_name='demandé par',
    )
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='declassements_valides',
        verbose_name='validé par',
    )
    date_validation = models.DateTimeField('validé le', null=True, blank=True)

    class Meta:
        verbose_name = 'déclassement'
        verbose_name_plural = 'déclassements'
        ordering = ['-date_demande']

    def __str__(self):
        return f'{self.immobilisation.code} — {self.get_statut_display()}'
