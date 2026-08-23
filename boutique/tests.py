"""Tests du module Boutique — architecture Article → Variante → Stock → Mouvement."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from approvisionnement.models import Article as ArticleAppro
from approvisionnement.models import MouvementStock as MouvementStockAppro
from core.models import Domaine, Role, Succursale
from core.services import UserService

from .models import (
    AlerteStockBoutique,
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
    VenteLigne,
)
from .services import (
    BonEntreeService,
    InventaireBoutiqueService,
    StockBoutiqueService,
    VarianteService,
    VenteService,
)


class BoutiqueBase(TestCase):
    def setUp(self):
        self.domaine = Domaine.objects.create(code='BOUTIQUE', libelle='Boutique')
        self.restaurant = Domaine.objects.create(code='RESTAURANT', libelle='Restaurant')
        self.succ_a = Succursale.objects.create(code='SA', nom='Succursale A')
        self.succ_b = Succursale.objects.create(code='SB', nom='Succursale B')

        self.cat = CategorieBoutique.objects.create(nom='Vêtements', code='VET')
        self.sous_cat = SousCategorieBoutique.objects.create(categorie=self.cat, nom='T-shirts', code='TSH')
        self.unite = UniteBoutique.objects.create(nom='Pièce', code='PCE')
        self.tissu_coton = TypeTissuArticle.objects.create(nom='Coton', code='COT')
        self.tissu_poly = TypeTissuArticle.objects.create(nom='Polyester', code='POL')
        self.fournisseur = FournisseurBoutique.objects.create(nom='Fournisseur 1')

        self.art_tshirt = ArticleBoutique.objects.create(
            code='TSHIRT', designation='T-shirt IBBS',
            succursale=self.succ_a, domaine=self.domaine)
        self.art_tshirt_b = ArticleBoutique.objects.create(
            code='TSHIRT', designation='T-shirt IBBS',
            succursale=self.succ_b, domaine=self.domaine)
        self.art_jean = ArticleBoutique.objects.create(
            code='JEAN', designation='Jean IBBS',
            succursale=self.succ_b, domaine=self.domaine)

        self.role_caissier = self._role(
            'CAISSIER',
            ['view_boutique', 'view_stock', 'view_vente', 'create_vente'],
        )
        self.role_responsable = self._role(
            'RESPONSABLE',
            ['view_boutique', 'view_stock', 'view_vente', 'create_vente',
             'validate_vente', 'cancel_vente', 'apply_remise', 'adjust_stock'],
        )
        self.caissier = self._user('caissier', self.role_caissier)
        self.responsable = self._user('responsable', self.role_responsable)

        self.var_noir_m = self._variante(self.art_tshirt, 'Noir', 'M', 'HOMME',
                                        prix_unitaire=15, prix_minimum=12, prix_maximum=20)
        self.var_noir_l = self._variante(self.art_tshirt, 'Noir', 'L', 'HOMME',
                                         prix_unitaire=15, prix_minimum=12, prix_maximum=20)
        self.var_b_leu_m = self._variante(self.art_tshirt_b, 'Bleu', 'M', 'HOMME',
                                          prix_unitaire=15, prix_minimum=12, prix_maximum=20)
        self.var_jean = self._variante(self.art_jean, 'Bleu', '32', 'HOMME',
                                       prix_unitaire=35, prix_minimum=30, prix_maximum=45)

    # --- Helpers -----------------------------------------------------------

    def _variante(self, article, couleur, taille, genre, **kwargs):
        return VarianteService.creer_ou_trouver(
            article=article, couleur=couleur, taille=taille, genre=genre,
            par=self.responsable, **kwargs)[0]

    @staticmethod
    def _permission(codename):
        return Permission.objects.get(content_type__app_label='boutique', codename=codename)

    def _role(self, code, codenames):
        role = Role.objects.create(nom=code, code=code)
        role.permissions.set([self._permission(c) for c in codenames])
        return role

    def _user(self, username, role):
        user = UserService.creer(username=username, password='pass1234', roles=[role])
        UserService.affecter_succursale(
            user, self.succ_a, self.domaine, principale=True, role=role)
        return user

    def _entrer(self, variante, quantite, seuil=0):
        if seuil:
            variante.seuil_alerte = seuil
            variante.save(update_fields=['seuil_alerte'])
        return StockBoutiqueService.entrer(
            variante=variante, quantite=quantite, utilisateur=self.responsable)

    def _vente(self, user=None, quantite=3, prix=None, montant_recu=None):
        user = user or self.responsable
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=user)
        VenteService.ajouter_ligne(
            vente, self.var_noir_m, quantite, prix or self.var_noir_m.prix_unitaire)
        vente.recalculer()
        vente.montant_recu = (
            Decimal(str(montant_recu)) if montant_recu is not None else Decimal('999999'))
        vente.save(update_fields=['montant_recu'])
        return vente


class TestArticleEtVariante(BoutiqueBase):
    def test_creation_article_sans_variante_ni_stock(self):
        """Créer un article parent ne crée ni variante, ni stock."""
        art = ArticleBoutique.objects.create(
            code='NEW', designation='Nouveau',
            succursale=self.succ_a, domaine=self.domaine)
        self.assertEqual(art.variantes.count(), 0)
        self.assertEqual(StockBoutique.objects.count(), 0)

    def test_entrees_cumulent_stock_de_variante_unique(self):
        """Deux entrées sur la même variante = UNE ligne de stock (40 puis 20 → 60)."""
        self._entrer(self.var_noir_m, 40)
        self._entrer(self.var_noir_m, 20)
        stocks = StockBoutique.objects.filter(variante=self.var_noir_m)
        self.assertEqual(stocks.count(), 1)
        self.assertEqual(stocks.first().quantite, 60)
        mouvements = list(MouvementStockBoutique.objects.filter(
            variante=self.var_noir_m, type='ENTREE').order_by('date_mouvement'))
        self.assertEqual(len(mouvements), 2)
        self.assertEqual([(m.stock_avant, m.stock_apres) for m in mouvements], [(0, 40), (40, 60)])

    def test_variantes_distinctes_stocks_distincts(self):
        """Noir/M et Noir/L sont des variantes différentes avec des stocks distincts."""
        self._entrer(self.var_noir_m, 10)
        self._entrer(self.var_noir_l, 20)
        self.assertEqual(
            StockBoutique.objects.get(variante=self.var_noir_m).quantite, 10)
        self.assertEqual(
            StockBoutique.objects.get(variante=self.var_noir_l).quantite, 20)

    def test_stock_agrege_de_l_article(self):
        """Le stock total de l'article = somme des stocks de ses variantes."""
        self._entrer(self.var_noir_m, 40)
        self._entrer(self.var_noir_l, 20)
        self.assertEqual(self.art_tshirt.stock_total, 60)

    def test_anti_doublon_variante(self):
        """Une variante identique (couleur/taille/genre) est réutilisée, pas dupliquée."""
        v, cree = VarianteService.creer_ou_trouver(
            article=self.art_tshirt, couleur='Noir', taille='M', genre='HOMME',
            prix_unitaire=20, par=self.responsable)
        self.assertFalse(cree)
        self.assertEqual(v.pk, self.var_noir_m.pk)
        self.assertEqual(VarianteArticle.objects.filter(article=self.art_tshirt).count(), 2)

    def test_code_variante_sequentiel(self):
        """Le code variante est généré automatiquement et séquentiel (V1, V2, V3…)."""
        v3, _ = VarianteService.creer_ou_trouver(
            article=self.art_tshirt, couleur='Bleu', taille='M', genre='HOMME',
            par=self.responsable)
        v4, _ = VarianteService.creer_ou_trouver(
            article=self.art_tshirt, couleur='Rouge', taille='M', genre='HOMME',
            par=self.responsable)
        self.assertEqual(v3.code_variante, 'TSHIRT-V3')
        self.assertEqual(v4.code_variante, 'TSHIRT-V4')

    def test_code_article_duplique_refuse(self):
        """Créer un article avec un code déjà pris (même succursale) est refusé."""
        self.client.force_login(self.responsable)
        resp = self.client.post(
            reverse('boutique:article_nouveau'),
            {'code': 'TSHIRT', 'designation': 'Doublon'},
        )
        self.assertEqual(
            ArticleBoutique.objects.filter(code='TSHIRT', succursale=self.succ_a).count(), 1)
        self.assertContains(resp, 'existe déjà')

    def test_variante_porte_la_devise(self):
        """La devise vit sur la variante (défaut FC), plus sur l'article."""
        self.assertFalse(hasattr(self.art_tshirt, 'devise'))
        self.assertEqual(self.var_noir_m.devise, 'FC')
        v_usd, _ = VarianteService.creer_ou_trouver(
            article=self.art_tshirt, couleur='Vert', taille='M', genre='HOMME',
            devise='USD', par=self.responsable)
        self.assertEqual(v_usd.devise, 'USD')

    def test_variante_distincte_par_type_tissu(self):
        """Le type de tissu fait partie de l'identité : 2 tissus = 2 variantes."""
        v1, c1 = VarianteService.creer_ou_trouver(
            article=self.art_tshirt, couleur='Noir', taille='S', genre='HOMME',
            type_tissu=self.tissu_coton, par=self.responsable)
        v2, c2 = VarianteService.creer_ou_trouver(
            article=self.art_tshirt, couleur='Noir', taille='S', genre='HOMME',
            type_tissu=self.tissu_poly, par=self.responsable)
        self.assertTrue(c1 and c2)
        self.assertNotEqual(v1.pk, v2.pk)
        self.assertNotEqual(v1.label, v2.label)

    def test_anti_doublon_avec_type_tissu(self):
        """Même combinaison + même tissu → la variante est réutilisée (pas de doublon)."""
        v1, c1 = VarianteService.creer_ou_trouver(
            article=self.art_tshirt, couleur='Vert', taille='M', genre='HOMME',
            type_tissu=self.tissu_coton, par=self.responsable)
        v2, c2 = VarianteService.creer_ou_trouver(
            article=self.art_tshirt, couleur='Vert', taille='M', genre='HOMME',
            type_tissu=self.tissu_coton, par=self.responsable)
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(v1.pk, v2.pk)

    def test_sortie_stock_insuffisant_refusee(self):
        self._entrer(self.var_noir_m, 5)
        with self.assertRaises(ValidationError):
            StockBoutiqueService.sortir(
                variante=self.var_noir_m, quantite=99, utilisateur=self.responsable)
        self.assertEqual(
            StockBoutique.objects.get(variante=self.var_noir_m).quantite, 5)


class TestVenteService(BoutiqueBase):
    def test_creation_vente(self):
        vente = self._vente()
        self.assertTrue(vente.numero.startswith('VTE-'))
        self.assertEqual(vente.statut, Vente.Statut.BROUILLON)

    def test_vente_enregistre_le_client(self):
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine,
            utilisateur=self.responsable, client='Jean Kalala')
        self.assertEqual(vente.client, 'Jean Kalala')

    def test_validation_diminue_le_stock_de_la_variante(self):
        """La vente diminue le stock de la variante vendue, pas une autre."""
        self._entrer(self.var_noir_m, 60)
        self._entrer(self.var_noir_l, 60)
        vente = self._vente(quantite=3)  # var_noir_m
        VenteService.valider(vente)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.VALIDEE)
        self.assertEqual(
            StockBoutique.objects.get(variante=self.var_noir_m).quantite, 57)
        # La variante non vendue reste intacte.
        self.assertEqual(
            StockBoutique.objects.get(variante=self.var_noir_l).quantite, 60)
        ligne = vente.lignes.first()
        self.assertIsNotNone(ligne.mouvement)
        self.assertEqual(ligne.mouvement.type, 'SORTIE')
        self.assertEqual(ligne.mouvement.variante, self.var_noir_m)

    def test_stock_insuffisant_refuse(self):
        self._entrer(self.var_noir_m, 5)
        vente = self._vente(quantite=99)
        with self.assertRaises(ValidationError):
            VenteService.valider(vente)
        self.assertEqual(
            StockBoutique.objects.get(variante=self.var_noir_m).quantite, 5)

    def test_prix_inferieur_minimum_refuse(self):
        self._entrer(self.var_noir_m, 10)
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.responsable)
        VenteService.ajouter_ligne(vente, self.var_noir_m, 1, 10)
        with self.assertRaises(ValidationError):
            VenteService.valider(vente)

    def test_prix_superieur_maximum_refuse(self):
        self._entrer(self.var_noir_m, 10)
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.responsable)
        VenteService.ajouter_ligne(vente, self.var_noir_m, 1, 25)
        with self.assertRaises(ValidationError):
            VenteService.valider(vente)

    def test_paiement_insuffisant_refuse(self):
        self._entrer(self.var_noir_m, 10)
        vente = self._vente(quantite=2, prix=15, montant_recu=20)  # total 30
        with self.assertRaises(ValidationError):
            VenteService.valider(vente)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.BROUILLON)
        self.assertEqual(
            StockBoutique.objects.get(variante=self.var_noir_m).quantite, 10)

    def test_remise_calculee(self):
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine,
            utilisateur=self.responsable, remise=5)
        VenteService.ajouter_ligne(vente, self.var_noir_m, 2, 15)
        vente.refresh_from_db()
        self.assertEqual(vente.sous_total, 30)
        self.assertEqual(vente.total, 25)

    def test_annulation_brouillon(self):
        vente = self._vente()
        VenteService.annuler(vente, commentaire='Annulée pour cause de test')
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.ANNULEE)

    def test_annulation_sans_commentaire_refuse(self):
        """Annuler sans commentaire est refusé (le commentaire est obligatoire)."""
        vente = self._vente()
        with self.assertRaises(ValidationError):
            VenteService.annuler(vente)

    def test_vente_ne_touche_pas_approvisionnement(self):
        self._entrer(self.var_noir_m, 60)
        vente = self._vente(quantite=3)
        VenteService.valider(vente)
        self.assertEqual(MouvementStockAppro.objects.count(), 0)
        self.assertEqual(ArticleAppro.objects.count(), 0)
        self.assertEqual(
            StockBoutique.objects.get(variante=self.var_noir_m).quantite, 57)


class TestBonEntreeBoutique(BoutiqueBase):
    def _bon(self, couleur='Vert', quantite=25):
        return BonEntreeService.creer(
            article=self.art_tshirt, succursale=self.succ_a, domaine=self.domaine,
            quantite=quantite, cree_par=self.responsable,
            couleur=couleur, taille='M', genre='HOMME',
            prix_unitaire=20, prix_minimum=17, seuil_alerte=5)

    def test_entree_enregistre_brouillon_sans_stock(self):
        """L'enregistrement crée un brouillon : ni variante, ni stock immédiat."""
        bon = self._bon()
        self.assertEqual(bon.statut, BonEntreeBoutique.Statut.BROUILLON)
        self.assertFalse(
            VarianteArticle.objects.filter(article=self.art_tshirt, couleur='Vert').exists())
        self.assertEqual(
            StockBoutique.objects.filter(variante__article=self.art_tshirt).count(), 0)

    def test_validation_cree_variante_stock_et_mouvement(self):
        """La validation crée la variante, le stock et le mouvement d'entrée."""
        bon = self._bon()
        BonEntreeService.valider(bon=bon, par=self.responsable)
        bon.refresh_from_db()
        self.assertEqual(bon.statut, BonEntreeBoutique.Statut.VALIDE)
        self.assertEqual(bon.valide_par, self.responsable)
        self.assertIsNotNone(bon.date_validation)
        var = VarianteArticle.objects.get(article=self.art_tshirt, couleur='Vert', taille='M')
        self.assertEqual(StockBoutique.objects.get(variante=var).quantite, 25)
        self.assertTrue(
            MouvementStockBoutique.objects.filter(variante=var, type='ENTREE').exists())

    def test_entree_transmet_la_devise_a_la_variante(self):
        """La devise choisie à l'entrée est transmise à la variante créée.
        (Sur un réapprovisionnement, la variante existante garde SA devise.)"""
        bon = BonEntreeService.creer(
            article=self.art_tshirt, succursale=self.succ_a, domaine=self.domaine,
            quantite=5, cree_par=self.responsable,
            couleur='Rouge', taille='L', genre='HOMME',
            devise='EUR', prix_unitaire=20)
        BonEntreeService.valider(bon=bon, par=self.responsable)
        var = VarianteArticle.objects.get(
            article=self.art_tshirt, couleur='Rouge', taille='L', genre='HOMME')
        self.assertEqual(var.devise, 'EUR')

    def test_entree_transmet_type_tissu(self):
        """Le type de tissu choisi à l'entrée est transmis à la variante créée."""
        bon = BonEntreeService.creer(
            article=self.art_tshirt, succursale=self.succ_a, domaine=self.domaine,
            quantite=5, cree_par=self.responsable,
            couleur='Rouge', taille='S', genre='HOMME',
            type_tissu=self.tissu_coton, prix_unitaire=20)
        BonEntreeService.valider(bon=bon, par=self.responsable)
        var = VarianteArticle.objects.get(
            article=self.art_tshirt, couleur='Rouge', taille='S', genre='HOMME',
            type_tissu=self.tissu_coton)
        self.assertEqual(var.type_tissu, self.tissu_coton)

    def test_validation_refusee_deux_fois(self):
        bon = self._bon()
        BonEntreeService.valider(bon=bon, par=self.responsable)
        with self.assertRaises(ValidationError):
            BonEntreeService.valider(bon=bon, par=self.responsable)

    def test_entree_variante_existante_reeapprovisionnement(self):
        """Nouvelle entrée sur une variante existante = réapprovisionnement autorisé :
        brouillon créé, aucune deuxième variante."""
        nb_avant = VarianteArticle.objects.filter(article=self.art_tshirt).count()
        bon = self._bon(couleur='Noir')  # la variante Noir/M existe (var_noir_m)
        self.assertEqual(bon.statut, BonEntreeBoutique.Statut.BROUILLON)
        self.assertEqual(
            VarianteArticle.objects.filter(article=self.art_tshirt).count(), nb_avant)
        self.assertFalse(
            StockBoutique.objects.filter(variante=self.var_noir_m).exists())

    def test_validation_reeapprovisionne_variante_existante(self):
        """Valider une entrée dont la variante existe réutilise la variante, augmente
        son stock et crée un mouvement d'entrée — sans jamais créer de doublon."""
        nb_avant = VarianteArticle.objects.filter(article=self.art_tshirt).count()
        bon = self._bon(couleur='Noir')  # variante Noir/M existe (var_noir_m)
        BonEntreeService.valider(bon=bon, par=self.responsable)
        bon.refresh_from_db()
        self.assertEqual(bon.statut, BonEntreeBoutique.Statut.VALIDE)
        self.assertEqual(
            VarianteArticle.objects.filter(article=self.art_tshirt).count(), nb_avant)
        self.assertEqual(
            StockBoutique.objects.get(variante=self.var_noir_m).quantite, 25)
        self.assertTrue(
            MouvementStockBoutique.objects.filter(
                variante=self.var_noir_m, type='ENTREE').exists())

    def test_liste_entrees_necessite_permission(self):
        """Sans validate_entree (caissier), la liste des entrées est refusée (403)."""
        self.client.force_login(self.caissier)
        resp = self.client.get(reverse('boutique:entrees_validation'))
        self.assertEqual(resp.status_code, 403)

    def test_entree_annulee_avec_commentaire(self):
        """Le responsable annule une entrée brouillon avec un commentaire visible."""
        bon = self._bon()
        BonEntreeService.annuler(bon=bon, par=self.responsable, commentaire='Facture erronée')
        bon.refresh_from_db()
        self.assertEqual(bon.statut, BonEntreeBoutique.Statut.ANNULEE)
        self.assertEqual(bon.commentaire, 'Facture erronée')
        # Une entrée annulée ne peut pas être validée ensuite.
        with self.assertRaises(ValidationError):
            BonEntreeService.valider(bon=bon, par=self.responsable)


class TestInventaireBoutique(BoutiqueBase):
    def _inventaire(self):
        return InventaireBoutiqueService.creer(
            date_inventaire=timezone.localdate(),
            succursale=self.succ_a,
            domaine=self.domaine,
            utilisateur=self.responsable,
            commentaire='',
            portee=InventaireBoutique.Portee.COMPLET,
        )

    def test_ecart_negatif_ajustement_sur_variante(self):
        self._entrer(self.var_noir_m, 60)
        inv = self._inventaire()
        ligne = inv.lignes.get(variante=self.var_noir_m)
        self.assertEqual(ligne.stock_systeme, 60)
        ligne.stock_physique = 57
        ligne.motif = 'ECART_INVENTAIRE'
        ligne.save()
        InventaireBoutiqueService.valider(inv)
        self.assertEqual(
            StockBoutique.objects.get(variante=self.var_noir_m).quantite, 57)
        ligne.refresh_from_db()
        self.assertIsNotNone(ligne.mouvement)
        self.assertEqual(ligne.mouvement.type, 'AJUSTEMENT')
        self.assertEqual(ligne.mouvement.quantite, -3)

    def test_ecart_nul_aucun_mouvement(self):
        self._entrer(self.var_noir_m, 60)
        inv = self._inventaire()
        nb_mouvements = MouvementStockBoutique.objects.count()
        InventaireBoutiqueService.valider(inv)
        self.assertEqual(MouvementStockBoutique.objects.count(), nb_mouvements)

    def test_motif_obligatoire_si_ecart(self):
        self._entrer(self.var_noir_m, 60)
        inv = self._inventaire()
        ligne = inv.lignes.get(variante=self.var_noir_m)
        ligne.stock_physique = 57
        ligne.save()
        with self.assertRaises(ValidationError):
            InventaireBoutiqueService.valider(inv)


class TestAlerteStockBoutique(BoutiqueBase):
    def test_dedup_active_par_variante(self):
        self._entrer(self.var_noir_m, 8, seuil=10)
        self.assertEqual(
            AlerteStockBoutique.objects.filter(stock__variante=self.var_noir_m, statut='ACTIVE').count(), 1)
        self._entrer(self.var_noir_m, 1)  # 9, toujours sous le seuil
        self.assertEqual(
            AlerteStockBoutique.objects.filter(stock__variante=self.var_noir_m, statut='ACTIVE').count(), 1)

    def test_rupture_a_zero(self):
        self._entrer(self.var_noir_m, 5, seuil=10)
        StockBoutiqueService.sortir(
            variante=self.var_noir_m, quantite=5, utilisateur=self.responsable)
        self.assertEqual(
            AlerteStockBoutique.objects.filter(
                stock__variante=self.var_noir_m, type='RUPTURE', statut='ACTIVE').count(), 1)

    def test_resolution_apres_reeapprovisionnement(self):
        self._entrer(self.var_noir_m, 8, seuil=10)
        self.assertEqual(
            AlerteStockBoutique.objects.filter(stock__variante=self.var_noir_m, statut='ACTIVE').count(), 1)
        self._entrer(self.var_noir_m, 20)  # 28 > seuil
        self.assertEqual(
            AlerteStockBoutique.objects.filter(stock__variante=self.var_noir_m, statut='ACTIVE').count(), 0)


class TestPermissionsEtRemises(BoutiqueBase):
    def _post_vente(self, data_extra):
        data = {
            'client': 'Client test', 'type_paiement': 'ESPECES',
            'montant_recu': '100', 'remise': '0',
            'lignes-TOTAL_FORMS': '1', 'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '1', 'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-variante': str(self.var_noir_m.pk),
            'lignes-0-quantite': '1', 'lignes-0-prix_unitaire': '15',
            'lignes-0-remise': '0',
        }
        data.update(data_extra)
        return self.client.post(reverse('boutique:vente_nouvelle'), data)

    def test_remise_refusee_sans_permission(self):
        self._entrer(self.var_noir_m, 5)
        self.client.force_login(self.caissier)
        resp = self._post_vente({'remise': '10'})
        self.assertEqual(Vente.objects.count(), 0)
        self.assertContains(resp, 'remise')  # message d'erreur affiché

    def test_remise_autorisee_avec_permission(self):
        self._entrer(self.var_noir_m, 5)
        self.client.force_login(self.responsable)
        resp = self._post_vente({'remise': '10'})
        self.assertEqual(resp.status_code, 302)
        vente = Vente.objects.first()
        self.assertEqual(vente.remise, 10)

    def test_approbation_sans_permission_forbidden(self):
        vente = self._vente(user=self.caissier)
        self.client.force_login(self.caissier)
        resp = self.client.post(
            reverse('boutique:vente_approuver', kwargs={'pk': vente.pk}))
        self.assertEqual(resp.status_code, 403)


class TestVenteWorkflow(BoutiqueBase):
    """Workflow unique : soumettre → VALIDEE (sorties) ou PENDING_VALIDATION."""

    def _soumettre(self, lignes, montant_recu=999999, remise=0, client='Workflow'):
        return VenteService.soumettre(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.responsable,
            client=client, montant_recu=montant_recu, remise=remise,
            lignes=lignes, par=self.responsable)

    def test_soumettre_prix_sous_reference_pending(self):
        """Prix min ≤ prix < référence → PENDING_VALIDATION, AUCUNE sortie."""
        self._entrer(self.var_noir_m, 10)
        vente = self._soumettre([(self.var_noir_m, 2, 13)])  # 12 ≤ 13 < 15
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.PENDING_VALIDATION)
        self.assertEqual(
            StockBoutique.objects.get(variante=self.var_noir_m).quantite, 10)
        self.assertFalse(
            MouvementStockBoutique.objects.filter(
                variante=self.var_noir_m, type='SORTIE').exists())

    def test_soumettre_prix_egal_reference_validee(self):
        """Prix == référence → VALIDEE + sorties immédiates."""
        self._entrer(self.var_noir_m, 10)
        vente = self._soumettre([(self.var_noir_m, 2, 15)])
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.VALIDEE)
        self.assertEqual(
            StockBoutique.objects.get(variante=self.var_noir_m).quantite, 8)
        self.assertTrue(
            MouvementStockBoutique.objects.filter(
                variante=self.var_noir_m, type='SORTIE').exists())

    def test_soumettre_prix_sous_minimum_refuse(self):
        """Prix < minimum → refus, aucune vente créée (transaction annulée)."""
        self._entrer(self.var_noir_m, 10)
        with self.assertRaises(ValidationError):
            self._soumettre([(self.var_noir_m, 2, 10)])
        self.assertFalse(Vente.objects.filter(client='Workflow').exists())

    def test_soumettre_prix_superieur_reference_refuse(self):
        """Prix > référence → refus, aucune vente créée."""
        self._entrer(self.var_noir_m, 10)
        with self.assertRaises(ValidationError):
            self._soumettre([(self.var_noir_m, 2, 20)])
        self.assertFalse(Vente.objects.filter(client='Workflow').exists())

    def test_soumettre_transaction_annulee_si_une_ligne_erronnee(self):
        """Une ligne bloquante annule toute la vente (aucune ligne créée)."""
        self._entrer(self.var_noir_m, 10)
        self._entrer(self.var_noir_l, 10)
        with self.assertRaises(ValidationError):
            self._soumettre([(self.var_noir_m, 2, 15), (self.var_noir_l, 1, 10)])
        self.assertFalse(Vente.objects.filter(client='Workflow').exists())
        self.assertEqual(VenteLigne.objects.count(), 0)

    def test_approuver_vente_pending(self):
        """Approuver une PENDING_VALIDATION crée les sorties et passe VALIDEE."""
        self._entrer(self.var_noir_m, 10)
        vente = self._soumettre([(self.var_noir_m, 2, 13)])
        self.assertEqual(vente.statut, Vente.Statut.PENDING_VALIDATION)
        VenteService.approuver(vente, par=self.responsable)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.VALIDEE)
        self.assertEqual(
            StockBoutique.objects.get(variante=self.var_noir_m).quantite, 8)
        self.assertTrue(
            MouvementStockBoutique.objects.filter(
                variante=self.var_noir_m, type='SORTIE').exists())

    def test_approuver_deja_validee_refuse(self):
        """Une vente déjà approuvée ne peut pas être ré-approuvée (anti-double)."""
        self._entrer(self.var_noir_m, 10)
        vente = self._soumettre([(self.var_noir_m, 2, 15)])
        self.assertEqual(vente.statut, Vente.Statut.VALIDEE)
        with self.assertRaises(ValidationError):
            VenteService.approuver(vente, par=self.responsable)

    def test_vente_annulee_avec_commentaire(self):
        """Annuler une vente en attente enregistre la raison (commentaire) du responsable."""
        self._entrer(self.var_noir_m, 10)
        vente = self._soumettre([(self.var_noir_m, 2, 13)])  # PENDING_VALIDATION
        VenteService.annuler(vente, par=self.responsable, commentaire='Prix jugé incohérent')
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.ANNULEE)
        self.assertEqual(vente.commentaire, 'Prix jugé incohérent')


class TestPerimetreBoutique(BoutiqueBase):
    def test_liste_articles_filtree_par_succursale(self):
        self.client.force_login(self.caissier)
        resp = self.client.get(reverse('boutique:articles'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'TSHIRT')
        self.assertNotContains(resp, 'JEAN')

    def test_detail_vente_autre_succursale_introuvable(self):
        vente_b = VenteService.creer(
            succursale=self.succ_b, domaine=self.domaine, utilisateur=self.responsable)
        self.client.force_login(self.caissier)
        resp = self.client.get(
            reverse('boutique:vente_detail', kwargs={'pk': vente_b.pk}))
        self.assertEqual(resp.status_code, 404)

    def test_aucun_acces_sans_affectation(self):
        role = self._role('OPERATEUR', ['view_boutique', 'view_stock'])
        user = UserService.creer(username='resto', password='pass1234', roles=[role])
        UserService.affecter_succursale(
            user, self.succ_a, self.restaurant, principale=True, role=role)
        self.client.force_login(user)
        resp = self.client.get(reverse('boutique:articles'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'TSHIRT')

    def test_vente_variantes_avec_principale_autre_domaine(self):
        """Régression : la vue vente charge les variantes BOUTIQUE même quand la
        principale de l'utilisateur appartient à un autre domaine (RESTAURANT).
        Le contexte du module Boutique vient de l'affectation BOUTIQUE."""
        user = UserService.creer(
            username='caissier_boutique', password='pass1234', roles=[self.role_caissier])
        UserService.affecter_succursale(
            user, self.succ_a, self.restaurant, principale=True, role=self.role_caissier)
        UserService.affecter_succursale(
            user, self.succ_a, self.domaine, principale=False, role=self.role_caissier)
        self.client.force_login(user)
        resp = self.client.get(reverse('boutique:vente_nouvelle'))
        self.assertEqual(resp.status_code, 200)
        # La variante BOUTIQUE de la succursale A est chargée dans le select.
        self.assertContains(resp, str(self.var_noir_m))
        # Pas de variante de la succursale B (hors contexte BOUTIQUE).
        self.assertNotContains(resp, str(self.var_jean))


class TestHistoriqueMouvements(BoutiqueBase):
    def setUp(self):
        super().setUp()
        self._entrer(self.var_noir_m, 10)  # une entrée datée d'aujourd'hui

    def test_historique_filtre_par_periode(self):
        ancien = timezone.now() - timedelta(days=30)
        MouvementStockBoutique.objects.create(
            variante=self.var_noir_m, succursale=self.succ_a, domaine=self.domaine,
            type='AJUSTEMENT', quantite=1, stock_avant=10, stock_apres=11,
            date_mouvement=ancien, utilisateur=self.responsable, motif='MOUV_ANCIEN')
        self.client.force_login(self.caissier)
        url = reverse('boutique:mouvements') + (
            '?date_debut={0}&date_fin={0}'.format(timezone.localdate().isoformat()))
        resp = self.client.get(url)
        self.assertContains(resp, 'TSHIRT')
        self.assertNotContains(resp, 'MOUV_ANCIEN')
        resp2 = self.client.get(
            reverse('boutique:mouvements') + '?date_debut=2026-01-01&date_fin=2026-01-31')
        self.assertContains(resp2, 'Aucun mouvement')

    def test_rapport_mouvements(self):
        self.client.force_login(self.caissier)
        resp = self.client.get(reverse('boutique:mouvements_report'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'TSHIRT')
        self.assertContains(resp, 'Total')


class TestTableauxBoutique(BoutiqueBase):
    def test_articles_pagines(self):
        for i in range(28):
            ArticleBoutique.objects.create(
                code=f'PAGE-{i:02d}', designation=f'Article page {i}',
                succursale=self.succ_a, domaine=self.domaine)
        self.client.force_login(self.caissier)
        resp = self.client.get(reverse('boutique:articles'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'pagination')
        resp2 = self.client.get(reverse('boutique:articles'), {'page': '2'})
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, 'pagination')

    def test_inventaire_brouillon_tableau_editable(self):
        inv = InventaireBoutiqueService.creer(
            date_inventaire=timezone.localdate(),
            succursale=self.succ_a, domaine=self.domaine,
            utilisateur=self.responsable, portee='COMPLET')
        self.client.force_login(self.responsable)
        resp = self.client.get(
            reverse('boutique:inventaire_detail', kwargs={'pk': inv.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ligne-inventaire')
        self.assertContains(resp, 'stock_physique')

    def test_inventaire_valide_filtre_ecart(self):
        self._entrer(self.var_noir_m, 10)
        inv = InventaireBoutiqueService.creer(
            date_inventaire=timezone.localdate(),
            succursale=self.succ_a, domaine=self.domaine,
            utilisateur=self.responsable, portee='COMPLET')
        ligne = inv.lignes.get(variante=self.var_noir_m)
        ligne.stock_physique = 7
        ligne.motif = 'ECART'
        ligne.save()
        InventaireBoutiqueService.valider(inv, par=self.responsable)
        self.client.force_login(self.responsable)
        url = reverse('boutique:inventaire_detail', kwargs={'pk': inv.pk})
        avec = self.client.get(url, {'ecart': 'avec'})
        self.assertContains(avec, 'ECART')  # la variante écartée apparaît (motif)
        sans = self.client.get(url, {'ecart': 'sans'})
        self.assertNotContains(sans, 'ECART')  # la variante écartée est exclue
