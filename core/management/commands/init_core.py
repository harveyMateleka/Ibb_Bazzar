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

APPROVISIONNEMENT = 'approvisionnement'
CORE = 'core'
BOUTIQUE = 'boutique'
IMMOBILISATIONS = 'immobilisations'
RESTAURATION = 'restauration'
FACTURATION = 'facturation'

IMMO_TOUTES = [
    'view_asset', 'create_asset', 'update_asset', 'assign_asset',
    'move_asset', 'repair_asset', 'report_damage_asset', 'decommission_asset',
    'view_declassified_asset', 'validate_asset',
]
# Entrée, affectation, casse, demande de déclassement — aucune validation.
IMMO_OPERATIONNEL = [
    'view_asset', 'create_asset', 'update_asset', 'assign_asset',
    'move_asset', 'repair_asset', 'report_damage_asset', 'decommission_asset',
]
# Validation de toute la chaîne logistique (entrée, casse, déclassement).
IMMO_VALIDATION = [
    'view_asset', 'validate_asset', 'view_declassified_asset',
]

RESTO_OPERATEUR = [
    'view_restauration', 'create_commande', 'modify_commande',
    'validate_commande', 'cancel_commande', 'adjust_plat_portions',
]
RESTO_CAISSE = ['view_restauration', 'encaisser_commande']
RESTO_SERVICE = ['view_restauration', 'servir_ligne']
RESTO_CUISINE = ['view_restauration', 'servir_ligne', 'adjust_plat_portions']

APPRO_SAISIE = [
    'view_approvisionnement', 'create_approvisionnement',
    'view_sortie', 'create_sortie',
    'view_inventaire', 'create_inventaire',
    'view_rapport_approvisionnement',
]
APPRO_VALIDATION = [
    'view_approvisionnement', 'validate_approvisionnement',
    'view_sortie', 'validate_sortie',
    'view_inventaire', 'validate_inventaire',
    'view_rapport_approvisionnement',
]

# Anciens codes conservés pour les seeds / comptes déjà affectés.
PERMISSIONS_ROLES = {
    'OPERATEUR_COMMANDE': [
        (RESTAURATION, RESTO_OPERATEUR),
    ],
    'OPERATEUR': [
        (RESTAURATION, RESTO_OPERATEUR),
    ],
    'MAGASINIER': [
        (APPROVISIONNEMENT, APPRO_SAISIE),
        (BOUTIQUE, ['view_boutique', 'view_stock', 'adjust_stock']),
    ],
    'COMPTABLE': [
        (APPROVISIONNEMENT, APPRO_VALIDATION),
        (BOUTIQUE, ['view_boutique', 'view_stock', 'validate_entree']),
        (FACTURATION, ['view_facture']),
        (CORE, ['view_audit']),
    ],
    'CAISSIER': [
        (RESTAURATION, RESTO_CAISSE),
        (FACTURATION, ['view_facture']),
        (BOUTIQUE, ['view_boutique', 'view_stock', 'view_vente']),
    ],
    'SERVEUR': [
        (RESTAURATION, RESTO_SERVICE),
    ],
    'CUISINIER': [
        (RESTAURATION, RESTO_CUISINE),
    ],
    'CHARGE_LOGISTIQUE': [
        (IMMOBILISATIONS, IMMO_OPERATIONNEL),
    ],
    'RESPONSABLE_LOGISTIQUE': [
        (IMMOBILISATIONS, IMMO_VALIDATION),
        (CORE, ['view_audit']),
    ],
    'VENDEUR': [
        (BOUTIQUE, [
            'view_boutique', 'view_stock', 'view_vente', 'create_vente',
            'adjust_stock',
        ]),
    ],
    'RESPONSABLE_VENDEUR': [
        (BOUTIQUE, ['view_boutique', 'view_vente', 'validate_vente']),
    ],
    'DIRECTION': [
        (APPROVISIONNEMENT, APPRO_SAISIE + [
            'validate_approvisionnement', 'validate_sortie', 'validate_inventaire',
        ]),
        (BOUTIQUE, [
            'view_boutique', 'view_stock', 'view_vente', 'create_vente',
            'validate_vente', 'apply_remise', 'adjust_stock', 'validate_entree',
        ]),
        (IMMOBILISATIONS, IMMO_TOUTES),
        (RESTAURATION, RESTO_OPERATEUR + ['encaisser_commande', 'servir_ligne']),
        (FACTURATION, ['view_facture']),
        (CORE, ['view_audit', 'view_utilisateur', 'view_succursale']),
    ],
    'RESPONSABLE': [
        (BOUTIQUE, [
            'view_boutique', 'view_stock', 'view_vente', 'create_vente',
            'validate_vente', 'apply_remise', 'adjust_stock', 'validate_entree',
        ]),
        (APPROVISIONNEMENT, APPRO_VALIDATION),
        (RESTAURATION, RESTO_OPERATEUR + ['encaisser_commande']),
        (CORE, ['view_audit']),
    ],
}

ROLES = {
    'ADMIN': ('Administrateur', 'Accès total. Seul le superuser peut supprimer.'),
    'OPERATEUR_COMMANDE': (
        'Opérateur de la commande',
        'Enregistre, modifie, valide et imprime une commande. '
        'Ne peut pas annuler une commande déjà validée. '
        'Peut ajouter des portions cuisine / barbecus.',
    ),
    'OPERATEUR': (
        'Opérateur',
        'Alias historique de l’opérateur de la commande.',
    ),
    'MAGASINIER': (
        'Magasinier',
        'Enregistre les entrées et sorties de stock et produit les rapports. '
        'Ne valide pas les bons.',
    ),
    'COMPTABLE': (
        'Comptable',
        'Valide les entrées et sorties. Ne peut pas les annuler une fois enregistrées.',
    ),
    'CAISSIER': (
        'Caissière',
        'Visualise les commandes et enregistre le paiement. '
        'Ne peut pas annuler une facture déjà payée.',
    ),
    'SERVEUR': (
        'Serveur',
        'Consulte les commandes et marque les plats servis.',
    ),
    'CUISINIER': (
        'Cuisinier',
        'Prépare les plats, ajoute les portions cuisine / barbecus, marque le service.',
    ),
    'CHARGE_LOGISTIQUE': (
        'Chargé de logistique',
        'Enregistre l’entrée d’un bien, l’affecte, signale une casse ou un déclassement. '
        'Ne valide rien et ne peut rien supprimer.',
    ),
    'RESPONSABLE_LOGISTIQUE': (
        'Responsable du logistique',
        'Valide les entrées, les casses et les déclassements de la logistique.',
    ),
    'VENDEUR': (
        'Vendeur',
        'Enregistre les arrivages, les ventes et les rapports. Ne valide rien.',
    ),
    'RESPONSABLE_VENDEUR': (
        'Responsable de vendeur',
        'Valide uniquement les lignes vendues sous le prix de vente normal.',
    ),
    'DIRECTION': (
        'Direction / Propriétaire',
        'Supervision et validation supérieure.',
    ),
    'RESPONSABLE': (
        'Responsable',
        'Rôle historique de validation (boutique / stock).',
    ),
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

        for code, (nom, desc) in ROLES.items():
            role, cree = Role.objects.get_or_create(
                code=code,
                defaults={'nom': nom, 'description': desc, 'est_systeme': True},
            )
            if not cree:
                role.nom = nom
                role.description = desc
                role.est_systeme = True
                role.save(update_fields=['nom', 'description', 'est_systeme'])
            self.stdout.write(self.style.SUCCESS(f'Rôle {"créé" if cree else "mis à jour"} : {nom}'))

        admin_role = Role.objects.get(code='ADMIN')
        admin_role.permissions.set(Permission.objects.all())
        self.stdout.write(self.style.SUCCESS('Rôle ADMIN = toutes les permissions.'))

        for code, groupes in PERMISSIONS_ROLES.items():
            role = Role.objects.get(code=code)
            permissions = []
            for app_label, codenames in groupes:
                permissions += list(_chercher_permissions(app_label, codenames))
            role.permissions.set(permissions)
            self.stdout.write(
                self.style.SUCCESS(f'Permissions {code} : {len(permissions)} synchronisée(s).')
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
                User.objects.create_superuser(
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
            utilisateur = User.objects.get(username=options['superuser'])
            from core.models import UserSuccursale

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
