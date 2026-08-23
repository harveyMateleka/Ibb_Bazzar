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
    BonEntreeBoutique,
    CategorieBoutique,
    FournisseurBoutique,
    InventaireBoutique,
    MouvementStockBoutique,
    SousCategorieBoutique,
    StockBoutique,
    TypeTissuArticle,
    UniteBoutique,
    VarianteArticle,
    Vente,
)
from boutique.services import (
    BonEntreeService,
    InventaireBoutiqueService,
    StockBoutiqueService,
    VarianteService,
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
        self._creer_variantes()
        self._creer_stock()
        self._creer_ventes()
        self._creer_entrees_brouillon()
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
        BonEntreeBoutique.objects.all().delete()
        Vente.objects.all().delete()
        InventaireBoutique.objects.all().delete()
        MouvementStockBoutique.objects.all().delete()
        ArticleBoutique.objects.all().delete()  # cascade sur StockBoutique/Variante
        SousCategorieBoutique.objects.all().delete()
        CategorieBoutique.objects.all().delete()
        UniteBoutique.objects.all().delete()
        TypeTissuArticle.objects.all().delete()
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

        self.tissus = {}
        for code, nom in [('COT', 'Coton'), ('POL', 'Polyester'),
                          ('JEA', 'Jean'), ('LAI', 'Laine')]:
            self.tissus[code], _ = TypeTissuArticle.objects.get_or_create(
                code=code, defaults={'nom': nom})

        self.fournisseur, _ = FournisseurBoutique.objects.get_or_create(
            nom='SOTEX DRC',
            defaults={'contact': 'M. Kabila', 'telephone': '+243 810 000 000',
                      'adresse': 'Kinshasa, Gombe'},
        )

    # --- Articles & variantes ----------------------------------------------

    def _creer_articles(self):
        """Articles parents (identification seule)."""
        for code, designation, sous in [
            ('TSHIRT', 'T-shirt IBBS', 'TSH'),
            ('JEAN', 'Jean IBBS', 'JEA'),
            ('CHEMISE', 'Chemise IBBS', 'CHE'),
            ('PANT', 'Pantalon IBBS', 'PAN'),
            ('CASQ', 'Casquette IBBS', 'CAS'),
        ]:
            ArticleBoutique.objects.get_or_create(
                code=code,
                succursale=self.succ,
                domaine=self.domaine,
                defaults={'designation': designation},
            )
        self.stdout.write(f'  {ArticleBoutique.objects.count()} article(s) parent(s) prêts.')

    def _variante(self, code_article, couleur, taille, genre, sous,
                  pa, pv, pmin, pmax, seuil=0, rayon='', etagere='', tissu=None):
        """Crée (ou réutilise) une variante d'un article parent."""
        article = ArticleBoutique.objects.get(
            code=code_article, succursale=self.succ, domaine=self.domaine)
        variante, cree = VarianteService.creer_ou_trouver(
            article=article,
            categorie=self.cat_vet if sous != 'CAS' else self.cat_acc,
            sous_categorie=self.sous_cats[sous],
            unite=self.unite_pce,
            type_tissu=tissu,
            genre=genre,
            taille=taille,
            couleur=couleur,
            marque='IBBS',
            rayon=rayon,
            etagere=etagere,
            devise='FC',
            prix_achat=pa,
            prix_unitaire=pv,
            prix_minimum=pmin,
            prix_maximum=pmax,
            seuil_alerte=seuil,
            par=self.responsable,
        )
        return variante

    def _creer_variantes(self):
        # (article, couleur, taille, genre, sous-cat, pa, pv, pmin, pmax, seuil,
        #  rayon, etagere, tissu)
        donnees = [
            ('TSHIRT', 'Noir', 'M', 'HOMME', 'TSH', 12000, 20000, 17000, 25000, 10, 'Homme', 'A1', 'COT'),
            ('TSHIRT', 'Noir', 'L', 'HOMME', 'TSH', 12000, 20000, 17000, 25000, 10, 'Homme', 'A1', 'COT'),
            ('TSHIRT', 'Bleu', 'M', 'HOMME', 'TSH', 12000, 20000, 17000, 25000, 10, 'Homme', 'A2', 'COT'),
            ('TSHIRT', 'Bleu', 'L', 'HOMME', 'TSH', 12000, 20000, 17000, 25000, 10, 'Homme', 'A2', 'COT'),
            ('TSHIRT', 'Rouge', 'M', 'HOMME', 'TSH', 12000, 20000, 17000, 25000, 10, 'Homme', 'A3', 'COT'),
            ('JEAN', 'Bleu', '32', 'HOMME', 'JEA', 25000, 35000, 30000, 45000, 5, 'Homme', 'B1', 'JEA'),
            ('CHEMISE', 'Blanche', 'M', 'HOMME', 'CHE', 20000, 30000, 26000, 40000, 5, 'Homme', 'B2', 'COT'),
            ('PANT', 'Noir', 'S', 'HOMME', 'PAN', 18000, 28000, 24000, 35000, 10, 'Homme', 'B3', 'COT'),
            ('CASQ', 'Noir', 'U', 'MIXTE', 'CAS', 5000, 10000, 8000, 15000, 3, 'Accessoires', 'C1', ''),
        ]
        for code_article, couleur, taille, genre, sous, pa, pv, pmin, pmax, seuil, rayon, etagere, tissu in donnees:
            self._variante(code_article, couleur, taille, genre, sous,
                           pa, pv, pmin, pmax, seuil, rayon, etagere,
                           tissu=self.tissus[tissu] if tissu else None)
        self.stdout.write(f'  {VarianteArticle.objects.count()} variante(s) prêtes.')

    # --- Stock -------------------------------------------------------------

    def _entrer(self, variante, quantite):
        stock = StockBoutique.objects.filter(variante=variante, succursale=self.succ).first()
        if stock and stock.quantite != 0:
            return  # déjà approvisionné (seed idempotent)
        StockBoutiqueService.entrer(
            variante=variante, quantite=quantite,
            utilisateur=self.responsable, motif='Entrée initiale (seed)',
        )

    def _variante_par(self, code_article, couleur, taille, genre):
        return VarianteArticle.objects.get(
            article__code=code_article, article__succursale=self.succ,
            couleur=couleur, taille=taille, genre=genre)

    def _creer_stock(self):
        self._entrer(self._variante_par('TSHIRT', 'Noir', 'M', 'HOMME'), 25)
        self._entrer(self._variante_par('TSHIRT', 'Noir', 'L', 'HOMME'), 18)
        self._entrer(self._variante_par('TSHIRT', 'Bleu', 'M', 'HOMME'), 8)   # → STOCK_FAIBLE
        self._entrer(self._variante_par('TSHIRT', 'Bleu', 'L', 'HOMME'), 30)
        self._entrer(self._variante_par('JEAN', 'Bleu', '32', 'HOMME'), 12)
        self._entrer(self._variante_par('CHEMISE', 'Blanche', 'M', 'HOMME'), 20)
        self._entrer(self._variante_par('PANT', 'Noir', 'S', 'HOMME'), 5)    # → STOCK_FAIBLE
        self._entrer(self._variante_par('CASQ', 'Noir', 'U', 'MIXTE'), 15)
        # Rupture volontaire : entrée 5 puis sortie 5 → stock 0 → alerte RUPTURE
        v_rouge = self._variante_par('TSHIRT', 'Rouge', 'M', 'HOMME')
        stock_r = StockBoutique.objects.filter(variante=v_rouge, succursale=self.succ).first()
        if stock_r is None or stock_r.quantite == 0:
            StockBoutiqueService.entrer(
                variante=v_rouge, quantite=5,
                utilisateur=self.responsable, motif='Entrée initiale (seed)')
            StockBoutiqueService.sortir(
                variante=v_rouge, quantite=5,
                utilisateur=self.responsable, motif='Casse démonstration')
        self.stdout.write(f'  {MouvementStockBoutique.objects.count()} mouvement(s) de stock.')

    # --- Ventes ------------------------------------------------------------

    def _creer_ventes(self):
        if Vente.objects.exists():
            self.stdout.write('  ventes déjà présentes.')
            return
        # Vente validée (caissier)
        v1 = VenteService.creer(
            succursale=self.succ, domaine=self.domaine, utilisateur=self.caissier,
            client='Jean Kalala', type_paiement='MOBILE_MONEY', montant_recu=75000)
        VenteService.ajouter_ligne(
            v1, self._variante_par('TSHIRT', 'Noir', 'M', 'HOMME'), 2, 20000)
        VenteService.ajouter_ligne(
            v1, self._variante_par('JEAN', 'Bleu', '32', 'HOMME'), 1, 35000)
        VenteService.valider(v1, par=self.responsable)
        self.stdout.write(f'  vente validée : {v1.numero} (client {v1.client}, total {v1.total}).')

        # Vente brouillon (caissier)
        v2 = VenteService.creer(
            succursale=self.succ, domaine=self.domaine, utilisateur=self.caissier,
            client='Marie Tshala')
        VenteService.ajouter_ligne(
            v2, self._variante_par('TSHIRT', 'Bleu', 'L', 'HOMME'), 1, 20000)
        self.stdout.write(f'  vente brouillon : {v2.numero} (client {v2.client}).')

        # Vente validée avec remise (responsable)
        v3 = VenteService.creer(
            succursale=self.succ, domaine=self.domaine, utilisateur=self.responsable,
            remise=5000, client='Patrick Mbuyi', type_paiement='ESPECES', montant_recu=100000)
        VenteService.ajouter_ligne(
            v3, self._variante_par('CHEMISE', 'Blanche', 'M', 'HOMME'), 3, 30000)
        VenteService.valider(v3, par=self.responsable)
        self.stdout.write(f'  vente avec remise : {v3.numero} (client {v3.client}, total {v3.total}).')

    # --- Entrées en brouillon (validation responsable) ----------------------

    def _creer_entrees_brouillon(self):
        if BonEntreeBoutique.objects.exists():
            self.stdout.write('  entrées brouillon déjà présentes.')
            return
        article = ArticleBoutique.objects.get(code='TSHIRT', succursale=self.succ)
        BonEntreeService.creer(
            article=article, succursale=self.succ, domaine=self.domaine,
            quantite=50, cree_par=self.responsable,
            couleur='Vert', taille='M', genre='HOMME',
            prix_unitaire=20000, prix_minimum=17000, seuil_alerte=10)
        article2 = ArticleBoutique.objects.get(code='PANT', succursale=self.succ)
        BonEntreeService.creer(
            article=article2, succursale=self.succ, domaine=self.domaine,
            quantite=30, cree_par=self.responsable,
            couleur='Gris', taille='L', genre='HOMME',
            prix_unitaire=28000, prix_minimum=24000, seuil_alerte=8)
        self.stdout.write('  2 entrée(s) en brouillon créées (à valider par le responsable).')

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
