"""Modèles centraux : profil, rôles, succursales, domaines, audit.

Le compte de connexion reste django.contrib.auth.User (déjà en base).
core.User est le profil étendu (téléphone, rôles, succursales).
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Role(models.Model):
    """Rôle dynamique et configurable (Administrateur, Direction, Magasinier…)."""

    nom = models.CharField('nom', max_length=100, unique=True)
    code = models.CharField('code', max_length=50, unique=True)
    description = models.TextField('description', blank=True)
    est_systeme = models.BooleanField(
        'rôle système',
        default=False,
        help_text='Un rôle système ne peut pas être supprimé.',
    )
    permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='roles',
        blank=True,
        verbose_name='permissions',
    )

    class Meta:
        verbose_name = 'rôle'
        verbose_name_plural = 'rôles'
        ordering = ['nom']
        # view_role / delete_role : générées automatiquement par Django.
        permissions = [
            ('create_role', 'Peut créer un rôle'),
            ('update_role', 'Peut modifier un rôle'),
            ('view_permission', 'Peut consulter les permissions'),
        ]

    def __str__(self):
        return self.nom


class Succursale(models.Model):
    """Établissement / site (ex. : Kinshasa Centre, Administration centrale)."""

    nom = models.CharField('nom', max_length=150)
    code = models.CharField('code', max_length=20, unique=True)
    adresse = models.TextField('adresse', blank=True)
    actif = models.BooleanField('actif', default=True)
    description = models.TextField('description', blank=True)
    date_creation = models.DateTimeField('créée le', default=timezone.now)

    class Meta:
        verbose_name = 'succursale'
        verbose_name_plural = 'succursales'
        ordering = ['nom']
        # view_succursale : générée automatiquement par Django.
        permissions = [
            ('create_succursale', 'Peut créer une succursale'),
            ('update_succursale', 'Peut modifier une succursale'),
        ]

    def __str__(self):
        return self.nom


class Domaine(models.Model):
    """Domaine d'activité : BOUTIQUE, RESTAURANT, APPROVISIONNEMENT…"""

    code = models.CharField('code', max_length=30, unique=True)
    libelle = models.CharField('libellé', max_length=100)
    description = models.TextField('description', blank=True)

    class Meta:
        verbose_name = 'domaine d’activité'
        verbose_name_plural = 'domaines d’activité'
        ordering = ['code']

    def __str__(self):
        return self.libelle


class User(models.Model):
    """Profil étendu du compte Django déjà présent dans BDDIBB_BAZAR."""

    compte = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='profil',
        verbose_name='compte',
    )
    telephone = models.CharField('téléphone', max_length=30, blank=True)
    fonction = models.CharField(
        'fonction / service',
        max_length=150,
        blank=True,
        help_text='Ex. : Magasinier, Caissière, Chef de cuisine…',
    )
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='utilisateurs_crees',
        verbose_name='créé par',
    )
    date_desactivation = models.DateTimeField(
        'date de désactivation',
        null=True,
        blank=True,
        help_text='Renseignée lors d’une désactivation (l’utilisateur n’est jamais supprimé).',
    )
    roles = models.ManyToManyField(
        Role,
        related_name='utilisateurs',
        blank=True,
        verbose_name='rôles',
    )

    class Meta:
        verbose_name = 'profil utilisateur'
        verbose_name_plural = 'profils utilisateurs'
        ordering = ['compte__username']
        permissions = [
            ('view_utilisateur', 'Peut consulter les utilisateurs'),
            ('create_utilisateur', 'Peut créer un utilisateur'),
            ('update_utilisateur', 'Peut modifier un utilisateur'),
            ('activate_utilisateur', 'Peut activer un utilisateur'),
            ('deactivate_utilisateur', 'Peut désactiver un utilisateur'),
        ]

    def __str__(self):
        return self.compte.get_full_name() or self.compte.username

    @property
    def username(self):
        return self.compte.username

    @property
    def first_name(self):
        return self.compte.first_name

    @property
    def last_name(self):
        return self.compte.last_name

    @property
    def email(self):
        return self.compte.email

    @property
    def is_active(self):
        return self.compte.is_active

    @property
    def is_superuser(self):
        return self.compte.is_superuser

    @property
    def is_staff(self):
        return self.compte.is_staff

    @is_staff.setter
    def is_staff(self, value):
        self.compte.is_staff = value

    @is_superuser.setter
    def is_superuser(self, value):
        self.compte.is_superuser = value

    @is_active.setter
    def is_active(self, value):
        self.compte.is_active = value

    def get_full_name(self):
        return self.compte.get_full_name()

    @property
    def date_joined(self):
        return self.compte.date_joined

    @property
    def last_login(self):
        return self.compte.last_login

    @property
    def affectations_succursales(self):
        return UserSuccursale.objects.filter(utilisateur=self.compte)

    def check_password(self, raw_password):
        return self.compte.check_password(raw_password)

    def get_all_permissions(self, obj=None):
        return self.compte.get_all_permissions(obj)

    def has_perm(self, perm, obj=None):
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        if self.compte.has_perm(perm, obj):
            return True
        app_label, _, codename = perm.partition('.')
        return self.roles.filter(
            permissions__content_type__app_label=app_label,
            permissions__codename=codename,
        ).exists()

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        compte_fields = ('is_staff', 'is_superuser', 'is_active')
        if update_fields:
            a_reporter = [f for f in update_fields if f in compte_fields]
            profil_fields = [f for f in update_fields if f not in compte_fields]
            if a_reporter:
                self.compte.save(update_fields=a_reporter)
            if profil_fields:
                kwargs['update_fields'] = profil_fields
                super().save(*args, **kwargs)
            return
        self.compte.save()
        super().save(*args, **kwargs)

    def deactiver(self, par=None):
        """Désactive sans supprimer : l'historique est conservé."""
        self.compte.is_active = False
        self.compte.save(update_fields=['is_active'])
        self.date_desactivation = timezone.now()
        self.save(update_fields=['date_desactivation'])
        from .services import AuditService
        AuditService.auditer(
            utilisateur=par if getattr(par, 'pk', None) else self.compte,
            module='CORE',
            action='user.deactivate',
            objet_type='User',
            objet_id=self.pk,
            nouvelle_valeur={'actif': False},
            motif='Désactivation du compte',
        )

    def activer(self, par=None):
        """Réactive un compte désactivé."""
        self.compte.is_active = True
        self.compte.save(update_fields=['is_active'])
        self.date_desactivation = None
        self.save(update_fields=['date_desactivation'])
        from .services import AuditService
        AuditService.auditer(
            utilisateur=par if getattr(par, 'pk', None) else self.compte,
            module='CORE',
            action='user.activate',
            objet_type='User',
            objet_id=self.pk,
            nouvelle_valeur={'actif': True},
            motif='Activation du compte',
        )

    def succursales_autorisees(self, domaine=None):
        if self.is_superuser:
            return Succursale.objects.filter(actif=True)
        qs = UserSuccursale.objects.filter(
            utilisateur=self.compte,
            succursale__actif=True,
        )
        if domaine is not None:
            qs = qs.filter(domaine=domaine)
        return Succursale.objects.filter(pk__in=qs.values('succursale_id'))

    def domaines_autorisees(self):
        if self.is_superuser:
            return Domaine.objects.all()
        return Domaine.objects.filter(
            affectations__utilisateur=self.compte
        ).distinct()

    def contexte_actif(self):
        aff = (
            UserSuccursale.objects.filter(utilisateur=self.compte)
            .select_related('succursale', 'domaine')
            .order_by('-principale', 'date_affectation')
            .first()
        )
        if aff is None:
            return {'succursale': None, 'domaine': None, 'verrouille': False}
        return {
            'succursale': aff.succursale,
            'domaine': aff.domaine,
            'verrouille': not self.is_superuser,
        }


class UserSuccursale(models.Model):
    """Rattachement utilisateur ↔ succursale ↔ domaine."""

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='affectations_succursales',
        verbose_name='utilisateur',
    )
    succursale = models.ForeignKey(
        Succursale,
        on_delete=models.PROTECT,
        related_name='affectations',
        verbose_name='succursale',
    )
    domaine = models.ForeignKey(
        Domaine,
        on_delete=models.PROTECT,
        related_name='affectations',
        verbose_name='domaine',
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='affectations',
        verbose_name='rôle dans ce périmètre',
        help_text='Rôle exercé par l’utilisateur dans ce périmètre (succursale + domaine).',
    )
    principale = models.BooleanField('succursale principale', default=False)
    date_affectation = models.DateTimeField('affecté le', default=timezone.now)

    class Meta:
        verbose_name = 'affectation utilisateur / succursale'
        verbose_name_plural = 'affectations utilisateurs / succursales'
        unique_together = [('utilisateur', 'succursale', 'domaine')]

    def __str__(self):
        return f'{self.utilisateur} → {self.succursale} / {self.domaine}'


class AuditLog(models.Model):
    """Audit centralisé de toutes les opérations sensibles."""

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audits',
        verbose_name='utilisateur',
    )
    succursale = models.ForeignKey(
        Succursale,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audits',
        verbose_name='succursale',
    )
    module = models.CharField('module', max_length=50)
    action = models.CharField('action', max_length=100)
    objet_type = models.CharField('type d’objet', max_length=100, blank=True)
    objet_id = models.PositiveBigIntegerField('id objet', null=True, blank=True)
    ancienne_valeur = models.JSONField('ancienne valeur', null=True, blank=True)
    nouvelle_valeur = models.JSONField('nouvelle valeur', null=True, blank=True)
    motif = models.TextField('motif', blank=True)
    adresse_ip = models.GenericIPAddressField('adresse IP', null=True, blank=True)
    date = models.DateTimeField('date', default=timezone.now)

    class Meta:
        verbose_name = 'trace d’audit'
        verbose_name_plural = 'traces d’audit'
        ordering = ['-date']
        permissions = [
            ('view_audit', 'Peut consulter les traces d’audit'),
        ]

    def __str__(self):
        return f'{self.module} / {self.action} — {self.date:%d/%m/%Y %H:%M}'
