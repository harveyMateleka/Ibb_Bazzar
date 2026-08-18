"""Seed de données de démonstration pour le module Immobilisations.

Usage :
    python manage.py seed_immobilisations           # idempotent
    python manage.py seed_immobilisations --force   # purge puis recrée

Compte créé : gestionnaire_assets / assets123 (RESPONSABLE — succ IBB / IMMOBILISATIONS)
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.models import Domaine, Role, Succursale
from core.services import UserService

from immobilisations.models import (
    Affectation,
    Casse,
    CategorieImmobilisation,
    Declassement,
    Deplacement,
    Immobilisation,
    Reparation,
)
from immobilisations.services import (
    AffectationService,
    CasseService,
    DeclassementService,
    DeplacementService,
    ImmobilisationService,
    ReparationService,
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Crée des données de démonstration (module Immobilisations).'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Purge d\'abord les données immobilisations, puis re-crée.')

    def handle(self, *args, **options):
        if options['force']:
            self._nettoyer()

        self.stdout.write('1) Fondations core (init_core)...')
        call_command('init_core')

        self.domaine = Domaine.objects.get(code='IMMOBILISATIONS')
        self.succ = Succursale.objects.get_or_create(
            code='IBB', defaults={'nom': 'IBB — Administration centrale'})[0]

        self.gestionnaire = self._creer_utilisateur()
        self._creer_categories()
        self._creer_biens()

        self.stdout.write(self.style.SUCCESS(
            f'\nSeed terminé : {Immobilisation.objects.count()} bien(s), '
            f'{Affectation.objects.count()} affectation(s), '
            f'{Deplacement.objects.count()} déplacement(s), '
            f'{Reparation.objects.count()} réparation(s), '
            f'{Casse.objects.count()} casse(s), '
            f'{Declassement.objects.count()} déclassement(s).'
        ))

    def _nettoyer(self):
        self.stdout.write(self.style.WARNING('Purge des données immobilisations...'))
        Immobilisation.objects.all().delete()  # cascade sur le cycle de vie
        CategorieImmobilisation.objects.all().delete()

    def _creer_utilisateur(self):
        user = User.objects.filter(username='gestionnaire_assets').first()
        if user:
            self.stdout.write('  utilisateur gestionnaire_assets déjà présent.')
            return user
        role = Role.objects.get(code='RESPONSABLE')
        user = UserService.creer(
            username='gestionnaire_assets', password='assets123', roles=[role],
            fonction='Gestionnaire des biens')
        UserService.affecter_succursale(
            user, self.succ, self.domaine, principale=True, role=role)
        self.stdout.write('  utilisateur gestionnaire_assets / assets123 créé.')
        return user

    def _creer_categories(self):
        for code, nom in [('INFO', 'Informatique'), ('MOB', 'Mobilier'), ('VEH', 'Véhicule')]:
            CategorieImmobilisation.objects.get_or_create(code=code, defaults={'nom': nom})

    def _bien(self, code, designation, categorie, numero_serie, valeur, fournisseur,
              service='', emplacement=''):
        """Crée un bien s'il n'existe pas (par code unique)."""
        bien = Immobilisation.objects.filter(code__startswith='IMM-', designation=designation).first()
        if bien:
            return bien
        return ImmobilisationService.creer(
            designation=designation,
            succursale=self.succ,
            domaine=self.domaine,
            categorie=CategorieImmobilisation.objects.get(code=categorie),
            numero_serie=numero_serie,
            valeur_acquisition=valeur,
            fournisseur=fournisseur,
            service=service,
            emplacement=emplacement,
            par=self.gestionnaire,
        )

    def _creer_biens(self):
        # Bien 1 : en service (affecté puis déplacé)
        b1 = self._bien('IMM', 'Ordinateur Dell XPS', 'INFO', 'DLX-001', 1500000, 'SOTEX')
        if not b1.affectations.exists():
            AffectationService.affecter(
                immobilisation=b1, succursale=self.succ,
                service='Comptabilité', emplacement='Bureau 12', par=self.gestionnaire)
        if not b1.deplacements.exists():
            DeplacementService.deplacer(
                immobilisation=b1, nouvelle_succursale=self.succ,
                nouveau_service='Comptabilité', nouvel_emplacement='Bureau 14',
                motif='Changement de bureau', par=self.gestionnaire)

        # Bien 2 : en réparation
        b2 = self._bien('IMM', 'Imprimante HP Laser', 'INFO', 'HP-L-204', 800000, 'SOTEX',
                        service='Direction', emplacement='Bureau 01')
        if not b2.reparations.exists():
            ReparationService.declarer(
                immobilisation=b2, motif='Rouleau usé', cout=120000, par=self.gestionnaire)

        # Bien 3 : casse évaluée réparable
        b3 = self._bien('IMM', 'Bureau en bois', 'MOB', 'MOB-014', 450000, 'MBI',
                        service='Comptabilité', emplacement='Bureau 12')
        if not b3.casses.exists():
            casse = CasseService.declarer(immobilisation=b3, motif='Pied cassé', par=self.gestionnaire)
            CasseService.evaluer(casse=casse, decision='REPARABLE', par=self.gestionnaire)

        # Bien 4 : déclassé
        b4 = self._bien('IMM', 'Véhicule Toyota Hiace', 'VEH', 'TOY-H-12', 25000000, 'TOYOTA',
                        service='Logistique', emplacement='Parking')
        if not b4.declassements.exists():
            dec = DeclassementService.demander(immobilisation=b4, motif='Hors d’usage', par=self.gestionnaire)
            DeclassementService.valider(declassement=dec, par=self.gestionnaire)

        # Bien 5 : stocké (neuf, sans affectation)
        self._bien('IMM', 'Écran Dell 24"', 'INFO', 'DL-E-88', 350000, 'SOTEX')

        self.stdout.write(f'  {Immobilisation.objects.count()} bien(s) prêts.')
