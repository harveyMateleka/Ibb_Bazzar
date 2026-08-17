"""Initialise les données de base de l'app core.

Usage :
    python manage.py init_core
    python manage.py init_core --superuser admin --password admin123
"""

from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Domaine, Role, Succursale
from core.services import PermissionService

# Permissions des rôles (définies dans les Meta.permissions des modèles).
APPROVISIONNEMENT = 'approvisionnement'
CORE = 'core'
BOUTIQUE = 'boutique'

PERMISSIONS_ROLES = {
    'DIRECTION': [
        (APPROVISIONNEMENT, ['view_approvisionnement', 'create_approvisionnement',
                             'validate_approvisionnement', 'view_sortie', 'create_sortie',
                             'validate_sortie', 'view_historique', 'view_inventaire',
                             'create_inventaire', 'validate_inventaire']),
        (BOUTIQUE, ['view_boutique', 'view_stock', 'create_vente', 'validate_vente',
                    'cancel_vente', 'apply_remise', 'adjust_stock']),
        (CORE, ['view_audit', 'view_utilisateur', 'view_succursale']),
    ],
    'RESPONSABLE': [
        (APPROVISIONNEMENT, ['view_approvisionnement', 'create_approvisionnement',
                             'validate_approvisionnement', 'view_sortie', 'create_sortie',
                             'validate_sortie', 'view_historique', 'view_inventaire',
                             'create_inventaire', 'validate_inventaire']),
        (BOUTIQUE, ['view_boutique', 'view_stock', 'create_vente', 'validate_vente',
                    'cancel_vente', 'apply_remise', 'adjust_stock']),
        (CORE, ['view_audit']),
    ],
    'MAGASINIER': [
        (APPROVISIONNEMENT, ['view_approvisionnement', 'create_approvisionnement',
                             'view_sortie', 'create_sortie',
                             'view_inventaire', 'view_historique']),
        (BOUTIQUE, ['view_boutique', 'view_stock']),
    ],
    'OPERATEUR': [
        (APPROVISIONNEMENT, ['view_approvisionnement', 'view_sortie',
                             'view_inventaire', 'view_historique']),
        (BOUTIQUE, ['view_boutique', 'view_stock']),
    ],
    'CAISSIER': [
        (BOUTIQUE, ['view_boutique', 'view_stock', 'view_vente', 'create_vente']),
        (APPROVISIONNEMENT, ['view_inventaire', 'view_historique']),
    ],
}


def _chercher_permissions(app_label, codenames):
    return Permission.objects.filter(
        content_type__app_label=app_label,
        codename__in=codenames,
    )


class Command(BaseCommand):
    help = 'Crée les domaines, rôles par défaut et synchronise les permissions.'

    def add_arguments(self, parser):
        parser.add_argument('--superuser', default='', help='Nom d’utilisateur du superuser à créer.')
        parser.add_argument('--password', default='', help='Mot de passe du superuser (déconseillé en prod).')
        parser.add_argument('--email', default='', help='E-mail du superuser.')

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(f'{PermissionService.nb_permissions()} permission(s) disponibles en base.')
        )

        # Nettoyage : APPROVISIONNEMENT est un module, pas un domaine d'activité.
        ancien_domaine = Domaine.objects.filter(code='APPROVISIONNEMENT').first()
        if ancien_domaine:
            ancien_domaine.affectations.all().delete()
            ancien_domaine.delete()
            self.stdout.write(
                self.style.WARNING('Ancien domaine APPROVISIONNEMENT supprimé (module transversal).')
            )

        domaines = ['BOUTIQUE', 'RESTAURANT', 'IMMOBILISATIONS', 'ADMINISTRATION']
        for code in domaines:
            Domaine.objects.get_or_create(
                code=code,
                defaults={'libelle': code.title(), 'description': ''},
            )
        self.stdout.write(self.style.SUCCESS('Domaines créés : ' + ', '.join(domaines)))

        roles = {
            'ADMIN': ('Administrateur', 'Accès total à l’application.'),
            'DIRECTION': ('Direction / Propriétaire', 'Validation supérieure, remises.'),
            'RESPONSABLE': ('Responsable', 'Validation des opérations, inventaires.'),
            'MAGASINIER': ('Magasinier', 'Entrées / sorties de stock.'),
            'OPERATEUR': ('Opérateur', 'Saisie courante.'),
            'CAISSIER': ('Caissier', 'Encaissements.'),
        }
        for code, (nom, desc) in roles.items():
            role, cree = Role.objects.get_or_create(
                code=code,
                defaults={'nom': nom, 'description': desc, 'est_systeme': True},
            )
            if cree:
                self.stdout.write(self.style.SUCCESS(f'Rôle créé : {nom}'))
        # L'administrateur reçoit toutes les permissions.
        admin_role = Role.objects.get(code='ADMIN')
        admin_role.permissions.set(Permission.objects.all())
        self.stdout.write(self.style.SUCCESS('Rôle ADMIN = toutes les permissions.'))

        # Permissions opérationnelles par rôle (Approvisionnement, core).
        for code, groupes in PERMISSIONS_ROLES.items():
            role = Role.objects.get(code=code)
            permissions = []
            for app_label, codenames in groupes:
                permissions += list(_chercher_permissions(app_label, codenames))
            role.permissions.add(*permissions)
            self.stdout.write(
                self.style.SUCCESS(f'Permissions {code} : {len(permissions)} ajoutée(s).')
            )

        succursale, _ = Succursale.objects.get_or_create(
            code='IBB',
            defaults={
                'nom': 'IBB — Administration centrale',
                'description': 'Succursale centrale par défaut.',
            },
        )
        self.stdout.write(self.style.SUCCESS(f'Succursale : {succursale}'))

        if options['superuser']:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            if User.objects.filter(username=options['superuser']).exists():
                self.stdout.write(self.style.WARNING('Superuser déjà présent, ignoré.'))
            else:
                utilisateur = User.objects.create_superuser(
                    username=options['superuser'],
                    email=options['email'] or '',
                    password=options['password'] or 'admin123',
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Superuser créé : {options["superuser"]}'
                        + ('' if options['password'] else ' (mot de passe par défaut : admin123)')
                    )
                )
            # Affectation du superuser à la succursale principale (toutes ses affectations).
            utilisateur = User.objects.get(username=options['superuser'])
            from core.models import UserSuccursale

            # La principale du superuser = BOUTIQUE (contexte par défaut des bons).
            for code_domaine in ['ADMINISTRATION', 'BOUTIQUE', 'RESTAURANT', 'IMMOBILISATIONS']:
                domaine = Domaine.objects.get(code=code_domaine)
                UserSuccursale.objects.get_or_create(
                    utilisateur=utilisateur,
                    succursale=succursale,
                    domaine=domaine,
                )
            UserSuccursale.objects.filter(utilisateur=utilisateur).update(principale=False)
            UserSuccursale.objects.filter(
                utilisateur=utilisateur, domaine__code='BOUTIQUE'
            ).update(principale=True)
            self.stdout.write(
                self.style.SUCCESS(f'{utilisateur.username} affecté à {succursale} (principale BOUTIQUE).')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Astuce : ajoutez --superuser admin --password … pour créer un compte admin.')
            )
