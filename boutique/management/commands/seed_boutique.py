"""Seed de données de démonstration pour le module Boutique.

Usage :
    python manage.py seed_boutique          # idempotent : complète sans écraser
    python manage.py seed_boutique --force  # purge les données boutique puis re-crée

Comptes créés (à changer en prod) :
    admin / admin123          (superuser, tous domaines)
    caissier / caissier123    (CAISSIER — succursale IBB / Boutique)
    magasinier / magasinier123 (MAGASINIER — succursale IBB / Boutique)
    responsable / responsable123 (RESPONSABLE — succursale IBB / Boutique)
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from boutique.models import (
    ArticleBoutique,
    CategorieBoutique,
    FournisseurBoutique,
    InventaireBoutique,
    MouvementStockBoutique,
    SousCategorieBoutique,
    StockBoutique,
    UniteBoutique,
    Vente,
)
from boutique.services import (
    InventaireBoutiqueService,
    StockBoutiqueService,
    VenteService,
)
from core.models import Domaine, Role, Succursale
from core.services import UserService

User = get_user_model()


class Command(BaseCommand):
    help = 'Crée des données de démonstration (module Boutique) pour les tests.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Purge d\'abord les données boutique existantes, puis re-crée.',
        )

    def handle(self, *args, **options):
        if options['force']:
            self._nettoyer()

        self.stdout.write('1) Fondations core (init_core)...')
        call_command('init_core')

        self.domaine = Domaine.objects.get(code='BOUTIQUE')
        self.succ, _ = Succursale.objects.get_or_create(
            code='IBB',
            defaults={'nom': 'IBB — Administration centrale'},
        )

        self._creer_superuser()
        self.responsable = self._creer_utilisateur('responsable', 'responsable123', 'RESPONSABLE')
        self.caissier = self._creer_utilisateur('caissier', 'caissier123', 'CAISSIER')
        self._creer_utilisateur('magasinier', 'magasinier123', 'MAGASINIER')

        self._creer_referentiels()
        self._creer_articles()
        self._creer_stock()
        self._creer_ventes()
        self._creer_inventaire()

        self.stdout.write(self.style.SUCCESS(
            f'\nSeed terminé : {ArticleBoutique.objects.count()} article(s), '
            f'{StockBoutique.objects.count()} ligne(s) de stock, '
            f'{MouvementStockBoutique.objects.count()} mouvement(s), '
            f'{Vente.objects.count()} vente(s), '
            f'{InventaireBoutique.objects.count()} inventaire(s).'
        ))

    # --- Nettoyage ---------------------------------------------------------

    def _nettoyer(self):
        self.stdout.write(self.style.WARNING('Purge des données boutique...'))
        Vente.objects.all().delete()
        InventaireBoutique.objects.all().delete()
        MouvementStockBoutique.objects.all().delete()
        ArticleBoutique.objects.all().delete()  # cascade sur StockBoutique
        SousCategorieBoutique.objects.all().delete()
        CategorieBoutique.objects.all().delete()
        UniteBoutique.objects.all().delete()
        FournisseurBoutique.objects.all().delete()

    # --- Utilisateurs ------------------------------------------------------

    def _creer_superuser(self):
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser('admin', email='admin@example.com', password='admin123')
            self.stdout.write('  superuser admin / admin123 créé.')
        else:
            self.stdout.write('  superuser admin déjà présent.')

    def _creer_utilisateur(self, username, password, role_code):
        user = User.objects.filter(username=username).first()
        if user:
            self.stdout.write(f'  utilisateur {username} déjà présent.')
            return user
        role = Role.objects.get(code=role_code)
        user = UserService.creer(
            username=username,
            password=password,
            roles=[role],
            fonction={'RESPONSABLE': 'Responsable boutique',
                      'CAISSIER': 'Caissier',
                      'MAGASINIER': 'Magasinier'}[role_code],
        )
        UserService.affecter_succursale(
            user, self.succ, self.domaine, principale=True, role=role)
        self.stdout.write(f'  utilisateur {username} / {password} créé (rôle {role_code}).')
        return user

    # --- Référentiels ------------------------------------------------------

    def _creer_referentiels(self):
        self.cat_vet, _ = CategorieBoutique.objects.get_or_create(
            code='VET', defaults={'nom': 'Vêtements', 'description': 'Habillement'})
        self.cat_acc, _ = CategorieBoutique.objects.get_or_create(
            code='ACC', defaults={'nom': 'Accessoires', 'description': 'Accessoires'})

        self.sous_cats = {}
        for code, nom, cat in [
            ('TSH', 'T-shirts', self.cat_vet),
            ('JEA', 'Jeans', self.cat_vet),
            ('CHE', 'Chemises', self.cat_vet),
            ('PAN', 'Pantalons', self.cat_vet),
            ('CAS', 'Casquettes', self.cat_acc),
        ]:
            self.sous_cats[code], _ = SousCategorieBoutique.objects.get_or_create(
                categorie=cat, code=code, defaults={'nom': nom})

        self.unite_pce, _ = UniteBoutique.objects.get_or_create(
            code='PCE', defaults={'nom': 'Pièce'})

        self.fournisseur, _ = FournisseurBoutique.objects.get_or_create(
            nom='SOTEX DRC',
            defaults={'contact': 'M. Kabila', 'telephone': '+243 810 000 000',
                      'adresse': 'Kinshasa, Gombe'},
        )

    # --- Articles ----------------------------------------------------------

    def _creer_articles(self):
        # code, désignation, sous-cat, genre, taille, couleur, marque,
        # prix_achat, prix_vente, prix_min, prix_max, rayon, étagère
        donnees = [
            ('TSHIRT-N-M', 'T-shirt IBBS noir', 'TSH', 'HOMME', 'M', 'Noir', 'IBBS',
             12000, 20000, 17000, 25000, 'Homme', 'A1'),
            ('TSHIRT-N-L', 'T-shirt IBBS noir', 'TSH', 'HOMME', 'L', 'Noir', 'IBBS',
             12000, 20000, 17000, 25000, 'Homme', 'A1'),
            ('TSHIRT-B-M', 'T-shirt IBBS bleu', 'TSH', 'HOMME', 'M', 'Bleu', 'IBBS',
             12000, 20000, 17000, 25000, 'Homme', 'A2'),
            ('TSHIRT-B-L', 'T-shirt IBBS bleu', 'TSH', 'HOMME', 'L', 'Bleu', 'IBBS',
             12000, 20000, 17000, 25000, 'Homme', 'A2'),
            ('TSHIRT-R-M', 'T-shirt IBBS rouge', 'TSH', 'HOMME', 'M', 'Rouge', 'IBBS',
             12000, 20000, 17000, 25000, 'Homme', 'A3'),
            ('JEAN-B-32', 'Jean bleu taille 32', 'JEA', 'HOMME', '32', 'Bleu', 'IBBS',
             25000, 35000, 30000, 45000, 'Homme', 'B1'),
            ('CHEMISE-W-M', 'Chemise blanche manches longues', 'CHE', 'HOMME', 'M', 'Blanche', 'IBBS',
             20000, 30000, 26000, 40000, 'Homme', 'B2'),
            ('PANT-N-S', 'Pantalon noir', 'PAN', 'HOMME', 'S', 'Noir', 'IBBS',
             18000, 28000, 24000, 35000, 'Homme', 'B3'),
            ('CASQ-N-U', 'Casquette IBBS noire', 'CAS', 'MIXTE', 'U', 'Noir', 'IBBS',
             5000, 10000, 8000, 15000, 'Accessoires', 'C1'),
        ]
        for code, designation, sous, genre, taille, couleur, marque, \
                pa, pv, pmin, pmax, rayon, etagere in donnees:
            ArticleBoutique.objects.get_or_create(
                code=code,
                succursale=self.succ,
                domaine=self.domaine,
                defaults=dict(
                    designation=designation,
                    categorie=self.cat_vet if sous != 'CAS' else self.cat_acc,
                    sous_categorie=self.sous_cats[sous],
                    unite=self.unite_pce,
                    genre=genre,
                    taille=taille,
                    couleur=couleur,
                    marque=marque,
                    rayon=rayon,
                    etagere=etagere,
                    prix_achat=pa,
                    prix_unitaire=pv,
                    prix_minimum=pmin,
                    prix_maximum=pmax,
                ),
            )
        self.stdout.write(f'  {ArticleBoutique.objects.count()} article(s) prêts.')

    # --- Stock -------------------------------------------------------------

    def _entrer(self, code, quantite, seuil=0):
        article = ArticleBoutique.objects.get(code=code, succursale=self.succ, domaine=self.domaine)
        stock = StockBoutique.obtenir(article, self.succ, self.domaine)
        if stock.quantite != 0:
            return  # déjà approvisionné (seed idempotent)
        if seuil:
            stock.seuil_alerte = seuil
            stock.save(update_fields=['seuil_alerte'])
        StockBoutiqueService.entrer(
            article=article, succursale=self.succ, domaine=self.domaine,
            quantite=quantite, utilisateur=self.responsable, motif='Entrée initiale (seed)',
        )

    def _creer_stock(self):
        self._entrer('TSHIRT-N-M', 25, seuil=10)
        self._entrer('TSHIRT-N-L', 18, seuil=10)
        self._entrer('TSHIRT-B-M', 8, seuil=10)    # → alerte STOCK_FAIBLE
        self._entrer('TSHIRT-B-L', 30, seuil=10)
        self._entrer('JEAN-B-32', 12, seuil=5)
        self._entrer('CHEMISE-W-M', 20, seuil=5)
        self._entrer('PANT-N-S', 5, seuil=10)       # → alerte STOCK_FAIBLE
        self._entrer('CASQ-N-U', 15, seuil=3)
        # Rupture volontaire : entrée 5 puis sortie 5 → stock 0 → alerte RUPTURE
        stock_r = StockBoutique.objects.filter(
            article__code='TSHIRT-R-M', succursale=self.succ).first()
        if stock_r is None or stock_r.quantite == 0:
            StockBoutiqueService.entrer(
                article=ArticleBoutique.objects.get(code='TSHIRT-R-M', succursale=self.succ),
                succursale=self.succ, domaine=self.domaine,
                quantite=5, utilisateur=self.responsable, motif='Entrée initiale (seed)',
            )
            StockBoutiqueService.sortir(
                article=ArticleBoutique.objects.get(code='TSHIRT-R-M', succursale=self.succ),
                succursale=self.succ, domaine=self.domaine,
                quantite=5, utilisateur=self.responsable, motif='Casse démonstration',
            )
        self.stdout.write(f'  {MouvementStockBoutique.objects.count()} mouvement(s) de stock.')

    # --- Ventes ------------------------------------------------------------

    def _creer_ventes(self):
        if Vente.objects.exists():
            self.stdout.write('  ventes déjà présentes.')
            return
        # Vente validée (caissier)
        v1 = VenteService.creer(
            succursale=self.succ, domaine=self.domaine, utilisateur=self.caissier)
        VenteService.ajouter_ligne(
            v1, ArticleBoutique.objects.get(code='TSHIRT-N-M', succursale=self.succ),
            2, 20000)
        VenteService.ajouter_ligne(
            v1, ArticleBoutique.objects.get(code='JEAN-B-32', succursale=self.succ),
            1, 35000)
        VenteService.valider(v1, par=self.responsable)
        self.stdout.write(f'  vente validée : {v1.numero} (total {v1.total}).')

        # Vente brouillon (caissier)
        v2 = VenteService.creer(
            succursale=self.succ, domaine=self.domaine, utilisateur=self.caissier)
        VenteService.ajouter_ligne(
            v2, ArticleBoutique.objects.get(code='TSHIRT-B-L', succursale=self.succ),
            1, 20000)
        self.stdout.write(f'  vente brouillon : {v2.numero}.')

        # Vente validée avec remise (responsable)
        v3 = VenteService.creer(
            succursale=self.succ, domaine=self.domaine, utilisateur=self.responsable, remise=5000)
        VenteService.ajouter_ligne(
            v3, ArticleBoutique.objects.get(code='CHEMISE-W-M', succursale=self.succ),
            3, 30000)
        VenteService.valider(v3, par=self.responsable)
        self.stdout.write(f'  vente avec remise : {v3.numero} (total {v3.total}).')

    # --- Inventaire --------------------------------------------------------

    def _creer_inventaire(self):
        if InventaireBoutique.objects.exists():
            self.stdout.write('  inventaire déjà présent.')
            return
        inventaire = InventaireBoutiqueService.creer(
            date_inventaire=timezone.localdate(),
            succursale=self.succ,
            domaine=self.domaine,
            utilisateur=self.responsable,
            commentaire='Inventaire initial (démo).',
            portee=InventaireBoutique.Portee.COMPLET,
        )
        self.stdout.write(f'  inventaire brouillon : {inventaire.numero}.')
