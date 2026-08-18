"""Tests du module Boutique (indépendant de l'Approvisionnement)."""

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
    CategorieBoutique,
    FournisseurBoutique,
    InventaireBoutique,
    MouvementStockBoutique,
    SousCategorieBoutique,
    StockBoutique,
    UniteBoutique,
    Vente,
)
from .services import InventaireBoutiqueService, StockBoutiqueService, VenteService


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

        self.art_a = ArticleBoutique.objects.create(
            code='TSHIRT-N-M', designation='T-shirt noir M',
            categorie=self.cat, sous_categorie=self.sous_cat, unite=self.unite,
            succursale=self.succ_a, domaine=self.domaine,
            prix_achat=10, prix_unitaire=15, prix_minimum=12, prix_maximum=20,
        )
        self.art_b = ArticleBoutique.objects.create(
            code='TSHIRT-N-L', designation='T-shirt noir L',
            categorie=self.cat, sous_categorie=self.sous_cat, unite=self.unite,
            succursale=self.succ_b, domaine=self.domaine,
            prix_achat=10, prix_unitaire=15, prix_minimum=12, prix_maximum=20,
        )

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

    # --- Helpers -----------------------------------------------------------

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

    def _entrer(self, article, quantite, succursale=None, seuil=0, utilisateur=None):
        succursale = succursale or article.succursale
        utilisateur = utilisateur or self.responsable
        if seuil:
            stock = StockBoutique.obtenir(article, succursale, article.domaine)
            stock.seuil_alerte = seuil
            stock.save(update_fields=['seuil_alerte'])
        return StockBoutiqueService.entrer(
            article=article, succursale=succursale, domaine=article.domaine,
            quantite=quantite, utilisateur=utilisateur,
        )

    def _vente(self, user=None, quantite=3, prix=None, montant_recu=None):
        user = user or self.responsable
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=user)
        VenteService.ajouter_ligne(
            vente, self.art_a, quantite, prix or self.art_a.prix_unitaire)
        vente.recalculer()
        # Montant reçu par défaut suffisant (la validation l'exige désormais).
        vente.montant_recu = (
            Decimal(str(montant_recu)) if montant_recu is not None
            else Decimal('999999')
        )
        vente.save(update_fields=['montant_recu'])
        return vente


class TestArticleEtStock(BoutiqueBase):
    def test_creation_article_sans_stock(self):
        """Créer un article ne crée aucun stock."""
        self.assertEqual(StockBoutique.objects.count(), 0)
        ArticleBoutique.objects.create(
            code='NEW', designation='Nouveau',
            succursale=self.succ_a, domaine=self.domaine)
        self.assertEqual(StockBoutique.objects.count(), 0)

    def test_entrees_cumulent_stock_unique(self):
        """Deux entrées = UNE ligne de stock (40 puis 20 → 60) + 2 mouvements."""
        self._entrer(self.art_a, 40)
        self._entrer(self.art_a, 20)
        stocks = StockBoutique.objects.filter(article=self.art_a)
        self.assertEqual(stocks.count(), 1)
        self.assertEqual(stocks.first().quantite, 60)
        mouvements = list(
            MouvementStockBoutique.objects.filter(
                article=self.art_a, type='ENTREE').order_by('date_mouvement')
        )
        self.assertEqual(len(mouvements), 2)
        self.assertEqual(
            [(m.stock_avant, m.stock_apres) for m in mouvements],
            [(0, 40), (40, 60)],
        )

    def test_stock_separe_par_succursale(self):
        """Le même concept d'article a des stocks distincts par succursale."""
        self._entrer(self.art_a, 10)
        self._entrer(self.art_b, 20, succursale=self.succ_b)
        self.assertEqual(
            StockBoutique.objects.get(article=self.art_a, succursale=self.succ_a).quantite, 10)
        self.assertEqual(
            StockBoutique.objects.get(article=self.art_b, succursale=self.succ_b).quantite, 20)

    def test_sortie_stock_insuffisant_refusee(self):
        self._entrer(self.art_a, 5)
        with self.assertRaises(ValidationError):
            StockBoutiqueService.sortir(
                article=self.art_a, succursale=self.succ_a, domaine=self.domaine,
                quantite=99, utilisateur=self.responsable)
        self.assertEqual(
            StockBoutique.objects.get(article=self.art_a, succursale=self.succ_a).quantite, 5)


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
        self.assertTrue(Vente.objects.filter(client='Jean Kalala').exists())

    def test_validation_diminue_stock(self):
        self._entrer(self.art_a, 60)
        vente = self._vente(quantite=3)
        VenteService.valider(vente)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.VALIDEE)
        stock = StockBoutique.objects.get(article=self.art_a, succursale=self.succ_a)
        self.assertEqual(stock.quantite, 57)
        ligne = vente.lignes.first()
        self.assertIsNotNone(ligne.mouvement)
        self.assertEqual(ligne.mouvement.type, 'SORTIE')
        self.assertEqual(ligne.mouvement.stock_apres, 57)

    def test_stock_insuffisant_refuse(self):
        self._entrer(self.art_a, 5)
        vente = self._vente(quantite=99)
        with self.assertRaises(ValidationError):
            VenteService.valider(vente)
        self.assertEqual(
            StockBoutique.objects.get(article=self.art_a, succursale=self.succ_a).quantite, 5)

    def test_prix_inferieur_minimum_refuse(self):
        self._entrer(self.art_a, 10)
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.responsable)
        VenteService.ajouter_ligne(vente, self.art_a, 1, 10)
        with self.assertRaises(ValidationError):
            VenteService.valider(vente)

    def test_prix_superieur_maximum_refuse(self):
        self._entrer(self.art_a, 10)
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.responsable)
        VenteService.ajouter_ligne(vente, self.art_a, 1, 25)
        with self.assertRaises(ValidationError):
            VenteService.valider(vente)

    def test_remise_calculee(self):
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine,
            utilisateur=self.responsable, remise=5)
        VenteService.ajouter_ligne(vente, self.art_a, 2, 15)
        vente.refresh_from_db()
        self.assertEqual(vente.sous_total, 30)
        self.assertEqual(vente.total, 25)

    def test_annulation_brouillon(self):
        vente = self._vente()
        VenteService.annuler(vente)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.ANNULEE)

    def test_vente_ne_touche_pas_approvisionnement(self):
        """La vente boutique n'écrit jamais dans le stock de l'Approvisionnement."""
        self._entrer(self.art_a, 60)
        vente = self._vente(quantite=3)
        VenteService.valider(vente)
        self.assertEqual(MouvementStockAppro.objects.count(), 0)
        self.assertEqual(ArticleAppro.objects.count(), 0)
        self.assertEqual(
            StockBoutique.objects.get(article=self.art_a, succursale=self.succ_a).quantite, 57)

    def test_paiement_insuffisant_refuse(self):
        """Montant reçu < total : la validation est refusée (transaction annulée)."""
        self._entrer(self.art_a, 10)
        vente = self._vente(quantite=2, prix=15, montant_recu=20)  # total 30
        with self.assertRaises(ValidationError):
            VenteService.valider(vente)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.BROUILLON)
        self.assertEqual(
            StockBoutique.objects.get(article=self.art_a, succursale=self.succ_a).quantite, 10)

    def test_validation_bloque_si_paiement_insuffisant(self):
        """Via le formulaire : action Valider avec montant reçu insuffisant."""
        self._entrer(self.art_a, 10)
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.responsable)
        self.client.force_login(self.responsable)
        url = reverse('boutique:vente_detail', kwargs={'pk': vente.pk})
        data = {
            'lignes-TOTAL_FORMS': '1',
            'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0',
            'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-article': self.art_a.pk,
            'lignes-0-quantite': '2',
            'lignes-0-prix_unitaire': '15',
            'lignes-0-id': '',
            'montant_recu': '10',
            'action': 'valider',
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.BROUILLON)
        self.assertEqual(vente.lignes.count(), 1)  # le panier est conservé
        page = self.client.get(url)
        self.assertContains(page, 'montant reçu')

    def test_formset_refuse_prix_sous_minimum(self):
        self._entrer(self.art_a, 10)
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.responsable)
        self.client.force_login(self.responsable)
        url = reverse('boutique:vente_detail', kwargs={'pk': vente.pk})
        data = {
            'lignes-TOTAL_FORMS': '1',
            'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0',
            'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-article': self.art_a.pk,
            'lignes-0-quantite': '2',
            'lignes-0-prix_unitaire': '10',  # < prix_minimum 12
            'lignes-0-id': '',
            'montant_recu': '',
            'action': 'enregistrer',
        }
        self.client.post(url, data)
        vente.refresh_from_db()
        self.assertEqual(vente.lignes.count(), 0)

    def test_formset_refuse_prix_superieur_maximum(self):
        self._entrer(self.art_a, 10)
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.responsable)
        self.client.force_login(self.responsable)
        url = reverse('boutique:vente_detail', kwargs={'pk': vente.pk})
        data = {
            'lignes-TOTAL_FORMS': '1',
            'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0',
            'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-article': self.art_a.pk,
            'lignes-0-quantite': '1',
            'lignes-0-prix_unitaire': '25',  # > prix_maximum 20
            'lignes-0-id': '',
            'montant_recu': '',
            'action': 'enregistrer',
        }
        self.client.post(url, data)
        vente.refresh_from_db()
        self.assertEqual(vente.lignes.count(), 0)


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

    def test_ecart_negatif_ajustement(self):
        self._entrer(self.art_a, 60)
        inv = self._inventaire()
        ligne = inv.lignes.get(article=self.art_a)
        self.assertEqual(ligne.stock_systeme, 60)
        ligne.stock_physique = 57
        ligne.motif = 'ECART_INVENTAIRE'
        ligne.save()
        InventaireBoutiqueService.valider(inv)
        stock = StockBoutique.objects.get(article=self.art_a, succursale=self.succ_a)
        self.assertEqual(stock.quantite, 57)
        ligne.refresh_from_db()
        self.assertIsNotNone(ligne.mouvement)
        self.assertEqual(ligne.mouvement.type, 'AJUSTEMENT')
        self.assertEqual(ligne.mouvement.quantite, -3)
        self.assertEqual(ligne.mouvement.motif, 'ECART_INVENTAIRE')

    def test_ecart_nul_aucun_mouvement(self):
        self._entrer(self.art_a, 60)
        inv = self._inventaire()
        nb_mouvements = MouvementStockBoutique.objects.count()
        InventaireBoutiqueService.valider(inv)
        self.assertEqual(MouvementStockBoutique.objects.count(), nb_mouvements)

    def test_motif_obligatoire_si_ecart(self):
        self._entrer(self.art_a, 60)
        inv = self._inventaire()
        ligne = inv.lignes.get(article=self.art_a)
        ligne.stock_physique = 57
        ligne.save()
        with self.assertRaises(ValidationError):
            InventaireBoutiqueService.valider(inv)


class TestAlerteStockBoutique(BoutiqueBase):
    def test_dedup_active(self):
        """Une seule alerte ACTIVE par (stock, type), pas de doublon."""
        self._entrer(self.art_a, 8, seuil=10)
        self.assertEqual(
            AlerteStockBoutique.objects.filter(stock__article=self.art_a, statut='ACTIVE').count(), 1)
        self._entrer(self.art_a, 1)  # 9, toujours sous le seuil
        self.assertEqual(
            AlerteStockBoutique.objects.filter(stock__article=self.art_a, statut='ACTIVE').count(), 1)
        self.assertEqual(
            AlerteStockBoutique.objects.filter(
                stock__article=self.art_a, type='STOCK_FAIBLE', statut='ACTIVE').count(), 1)

    def test_rupture_a_zero(self):
        self._entrer(self.art_a, 5, seuil=10)
        StockBoutiqueService.sortir(
            article=self.art_a, succursale=self.succ_a, domaine=self.domaine,
            quantite=5, utilisateur=self.responsable)
        self.assertEqual(
            AlerteStockBoutique.objects.filter(
                stock__article=self.art_a, type='RUPTURE', statut='ACTIVE').count(), 1)

    def test_resolution_apres_reeapprovisionnement(self):
        self._entrer(self.art_a, 8, seuil=10)
        self.assertEqual(
            AlerteStockBoutique.objects.filter(stock__article=self.art_a, statut='ACTIVE').count(), 1)
        self._entrer(self.art_a, 20)  # 28 > seuil
        self.assertEqual(
            AlerteStockBoutique.objects.filter(stock__article=self.art_a, statut='ACTIVE').count(), 0)
        self.assertEqual(
            AlerteStockBoutique.objects.filter(
                stock__article=self.art_a, statut='RESOLUE').count(), 1)


class TestPermissionsEtRemises(BoutiqueBase):
    def test_vente_sans_permission_forbidden(self):
        self.client.force_login(self.caissier)
        resp = self.client.get(reverse('boutique:vente_nouvelle'))
        self.assertEqual(resp.status_code, 200)

    def test_validation_sans_permission_forbidden(self):
        vente = self._vente(user=self.caissier)
        self.client.force_login(self.caissier)
        resp = self.client.post(
            reverse('boutique:vente_valider', kwargs={'pk': vente.pk}))
        self.assertEqual(resp.status_code, 403)

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

    def test_client_obligatoire_a_la_creation(self):
        self.client.force_login(self.caissier)
        resp = self.client.post(
            reverse('boutique:vente_nouvelle'),
            {'type_paiement': 'ESPECES', 'montant_recu': '0', 'remise': '0'},
        )
        self.assertEqual(Vente.objects.count(), 0)
        self.assertContains(resp, 'client')


class TestPerimetreBoutique(BoutiqueBase):
    def test_liste_articles_filtree_par_succursale(self):
        self.client.force_login(self.caissier)
        resp = self.client.get(reverse('boutique:articles'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'TSHIRT-N-M')
        self.assertNotContains(resp, 'TSHIRT-N-L')

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
        self.assertNotContains(resp, 'TSHIRT-N-M')
        self.assertNotContains(resp, 'TSHIRT-N-L')


class TestHistoriqueMouvements(BoutiqueBase):
    def setUp(self):
        super().setUp()
        self._entrer(self.art_a, 10)  # une entrée datée d'aujourd'hui

    def test_historique_filtre_par_periode(self):
        """Un mouvement hors période n'apparaît pas dans la liste filtrée."""
        ancien = timezone.now() - timedelta(days=30)
        MouvementStockBoutique.objects.create(
            article=self.art_a, succursale=self.succ_a, domaine=self.domaine,
            type='AJUSTEMENT', quantite=1, stock_avant=10, stock_apres=11,
            date_mouvement=ancien, utilisateur=self.responsable, motif='MOUV_ANCIEN')
        self.client.force_login(self.caissier)
        # Période = aujourd'hui → seule l'entrée du jour apparaît.
        url = reverse('boutique:mouvements') + (
            '?date_debut={0}&date_fin={0}'.format(timezone.localdate().isoformat()))
        resp = self.client.get(url)
        self.assertContains(resp, 'TSHIRT-N-M')
        self.assertNotContains(resp, 'MOUV_ANCIEN')
        # Période = janvier → aucun mouvement.
        resp2 = self.client.get(
            reverse('boutique:mouvements') + '?date_debut=2026-01-01&date_fin=2026-01-31')
        self.assertContains(resp2, 'Aucun mouvement')

    def test_rapport_mouvements(self):
        """Le rapport liste toutes les lignes du filtre et affiche les totaux."""
        self.client.force_login(self.caissier)
        resp = self.client.get(reverse('boutique:mouvements_report'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'TSHIRT-N-M')
        self.assertContains(resp, 'Total')
        # Le rapport n'est pas paginé : la seule entrée du jour est listée.
        self.assertContains(resp, 'Entrée')
