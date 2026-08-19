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
    UniteBoutique,
    VarianteArticle,
    Vente,
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
        VenteService.annuler(vente)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.ANNULEE)

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

    def test_validation_refusee_deux_fois(self):
        bon = self._bon()
        BonEntreeService.valider(bon=bon, par=self.responsable)
        with self.assertRaises(ValidationError):
            BonEntreeService.valider(bon=bon, par=self.responsable)

    def test_liste_entrees_necessite_permission(self):
        """Sans validate_entree (caissier), la liste des entrées est refusée (403)."""
        self.client.force_login(self.caissier)
        resp = self.client.get(reverse('boutique:entrees_validation'))
        self.assertEqual(resp.status_code, 403)


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
    def test_remise_refusee_sans_permission(self):
        self.client.force_login(self.caissier)
        resp = self.client.post(
            reverse('boutique:vente_nouvelle'),
            {'client': 'Client test', 'type_paiement': 'ESPECES',
             'montant_recu': '0', 'remise': '10'},
        )
        self.assertEqual(Vente.objects.count(), 0)
        self.assertContains(resp, 'remise')

    def test_remise_autorisee_avec_permission(self):
        self.client.force_login(self.responsable)
        resp = self.client.post(
            reverse('boutique:vente_nouvelle'),
            {'client': 'Client test', 'type_paiement': 'ESPECES',
             'montant_recu': '0', 'remise': '10'},
        )
        self.assertEqual(resp.status_code, 302)
        vente = Vente.objects.first()
        self.assertEqual(vente.remise, 10)

    def test_validation_sans_permission_forbidden(self):
        vente = self._vente(user=self.caissier)
        self.client.force_login(self.caissier)
        resp = self.client.post(
            reverse('boutique:vente_valider', kwargs={'pk': vente.pk}))
        self.assertEqual(resp.status_code, 403)


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
