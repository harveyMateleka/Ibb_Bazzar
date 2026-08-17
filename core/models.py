"""Modèles centraux : utilisateur, rôles, succursales, domaines, audit.

L'utilisateur (AUTH_USER_MODEL = 'core.User') est le point de contrôle central
de l'application. Tous les modules (Approvisionnement, Boutique, Immobilisations)
partagent ce même modèle.
"""

from django.contrib.auth.models import AbstractUser
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
        return f'{self.nom} ({self.code})'


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


class User(AbstractUser):
    """Utilisateur central étendu (profil, rôle, succursales, désactivation)."""

    telephone = models.CharField('téléphone', max_length=30, blank=True)
    fonction = models.CharField(
        'fonction / service',
        max_length=150,
        blank=True,
        help_text='Ex. : Magasinier, Caissière, Chef de cuisine…',
    )
    cree_par = models.ForeignKey(
        'self',
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
    succursales = models.ManyToManyField(
        Succursale,
        through='UserSuccursale',
        related_name='utilisateurs',
        blank=True,
        verbose_name='succursales autorisées',
    )

    class Meta:
        verbose_name = 'utilisateur'
        verbose_name_plural = 'utilisateurs'
        ordering = ['username']
        permissions = [
            ('view_utilisateur', 'Peut consulter les utilisateurs'),
            ('create_utilisateur', 'Peut créer un utilisateur'),
            ('update_utilisateur', 'Peut modifier un utilisateur'),
            ('activate_utilisateur', 'Peut activer un utilisateur'),
            ('deactivate_utilisateur', 'Peut désactiver un utilisateur'),
        ]

    def __str__(self):
        return self.get_full_name() or self.username

    def has_perm(self, perm, obj=None):
        """Vérifie la permission en tenant compte des rôles dynamiques.

        Django ne connaît pas nativement notre M2M `roles` : on ajoute la
        vérification des permissions portées par les rôles de l'utilisateur.
        """
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        # Permissions directes + groupes Django natifs.
        if super().has_perm(perm, obj):
            return True
        # Permissions issues des rôles dynamiques.
        app_label, _, codename = perm.partition('.')
        return self.roles.filter(
            permissions__content_type__app_label=app_label,
            permissions__codename=codename,
        ).exists()

    def deactiver(self, par=None):
        """Désactive sans supprimer : l'historique est conservé."""
        self.is_active = False
        self.date_desactivation = timezone.now()
        self.save(update_fields=['is_active', 'date_desactivation'])
        from .services import AuditService
        AuditService.auditer(
            utilisateur=par or self,
            module='CORE',
            action='user.deactivate',
            objet_type='User',
            objet_id=self.pk,
            nouvelle_valeur={'actif': False},
            motif='Désactivation du compte',
        )

    def activer(self, par=None):
        """Réactive un compte désactivé."""
        self.is_active = True
        self.date_desactivation = None
        self.save(update_fields=['is_active', 'date_desactivation'])
        from .services import AuditService
        AuditService.auditer(
            utilisateur=par or self,
            module='CORE',
            action='user.activate',
            objet_type='User',
            objet_id=self.pk,
            nouvelle_valeur={'actif': True},
            motif='Activation du compte',
        )

    def succursales_autorisees(self, domaine=None):
        """Succursales accessibles, filtrées par domaine si demandé.

        Un superutilisateur accède à toutes les succursales actives.
        Sinon, on ne considère QUE les affectations (UserSuccursale) de
        l'utilisateur lui-même : succursale + domaine.
        """
        if self.is_superuser:
            qs = Succursale.objects.filter(actif=True)
            if domaine is not None:
                qs = qs.filter(affectations__domaine=domaine)
            return qs.distinct()
        qs = UserSuccursale.objects.filter(
            utilisateur=self,
            succursale__actif=True,
        )
        if domaine is not None:
            qs = qs.filter(domaine=domaine)
        return Succursale.objects.filter(pk__in=qs.values('succursale_id'))

    def domaines_autorisees(self):
        """Domaines d'activité accessibles, selon les affectations de l'utilisateur."""
        if self.is_superuser:
            return Domaine.objects.all()
        return Domaine.objects.filter(
            affectations__utilisateur=self
        ).distinct()

    def contexte_actif(self):
        """Contexte par défaut (succursale, domaine) pour les bons.

        Toujours basé sur l'affectation principale (ou la première si aucune
        n'est marquée principale) de l'utilisateur.
        - Superutilisateur : auto-rempli mais non verrouillé (il peut tout voir).
        - Autres utilisateurs : auto-rempli et VERROUILLÉ (readonly) pour éviter
          les incohérences.
        """
        aff = (
            self.affectations_succursales.select_related('succursale', 'domaine')
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
        User,
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
        User,
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
