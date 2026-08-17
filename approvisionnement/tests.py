from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Domaine, Role, Succursale
from core.services import UserService
from approvisionnement.forms import BonApprovisionnementForm
from approvisionnement.models import (
    Article,
    BonApprovisionnement,
    BonSortie,
    Categorie,
    Fournisseur,
    Inventaire,
    LigneApprovisionnement,
    LigneSortie,
    Service,
    Unite,
)


def _permission(codename):
    return Permission.objects.get(
        content_type__app_label='approvisionnement',
        codename=codename,
    )


class ApprovisionnementBase(TestCase):
    """Contexte : succursales A/B, domaines BOUTIQUE et RESTAURANT.

    Approvisionnement est un MODULE transversal : le stock et les bons sont
    contextualisés par (succursale, domaine), et le périmètre d'accès est
    l'intersection des succursales ET des domaines d'affectation de l'utilisateur.
    """

    def setUp(self):
        self.domaine_boutique = Domaine.objects.create(code='BOUTIQUE', libelle='Boutique')
        self.domaine_restaurant = Domaine.objects.create(code='RESTAURANT', libelle='Restaurant')
        self.succ_a = Succursale.objects.create(nom='Succursale A', code='A')
        self.succ_b = Succursale.objects.create(nom='Succursale B', code='B')
        self.categorie = Categorie.objects.create(nom='Épicerie')
        self.unite = Unite.objects.create(code='KG', libelle='Kilogramme')

        self.article_a = Article.objects.create(
            code='ART1', designation='Article A',
            succursale=self.succ_a, domaine=self.domaine_boutique,
            categorie=self.categorie, unite=self.unite,
        )
        self.article_b = Article.objects.create(
            code='ART1', designation='Article B',
            succursale=self.succ_b, domaine=self.domaine_boutique,
            categorie=self.categorie, unite=self.unite,
        )
        self.article_resto = Article.objects.create(
            code='ART1', designation='Riz restaurant',
            succursale=self.succ_a, domaine=self.domaine_restaurant,
            categorie=self.categorie, unite=self.unite,
        )
        self.fournisseur = Fournisseur.objects.create(nom='Fournisseur X')

        self.role_magasinier = Role.objects.create(nom='Magasinier', code='MAGASINIER')
        self.role_magasinier.permissions.add(
            _permission('view_approvisionnement'),
            _permission('create_approvisionnement'),
            _permission('view_sortie'),
            _permission('create_sortie'),
        )
        self.role_responsable = Role.objects.create(nom='Responsable', code='RESPONSABLE')
        self.role_responsable.permissions.add(
            _permission('view_approvisionnement'),
            _permission('validate_approvisionnement'),
            _permission('view_historique'),
            _permission('view_inventaire'),
            _permission('create_inventaire'),
        )

        self.magasinier_a = UserService.creer(
            username='mag_a', password='mdp123', roles=[self.role_magasinier]
        )
        self.magasinier_b = UserService.creer(
            username='mag_b', password='mdp123', roles=[self.role_magasinier]
        )
        self.responsable = UserService.creer(
            username='resp', password='mdp123', roles=[self.role_responsable]
        )
        UserService.affecter_succursale(self.magasinier_a, self.succ_a, self.domaine_boutique)
        UserService.affecter_succursale(self.magasinier_b, self.succ_b, self.domaine_boutique)
        UserService.affecter_succursale(self.responsable, self.succ_a, self.domaine_boutique)


class TestSeparationStocksParSuccursale(ApprovisionnementBase):
    def test_meme_code_dans_deux_succursales(self):
        self.assertEqual(Article.objects.filter(code='ART1').count(), 3)
        self.assertEqual(self.article_a.succursale, self.succ_a)
        self.assertEqual(self.article_b.succursale, self.succ_b)

    def test_code_unique_par_succursale_et_domaine(self):
        # Doublon strict : même code + même succursale + même domaine.
        with self.assertRaises(Exception):
            Article.objects.create(
                code='ART1', designation='Doublon',
                succursale=self.succ_a, domaine=self.domaine_boutique,
                categorie=self.categorie, unite=self.unite,
            )

    def test_sortie_refusee_quand_stock_au_seuil(self):
        # Règle : aucune sortie si le stock est égal au seuil d'alerte.
        self.article_a.stock = 3
        self.article_a.seuil_minimum = 3
        self.article_a.save(update_fields=['stock', 'seuil_minimum'])
        service = Service.objects.create(nom='Cuisine')
        bon = BonSortie.objects.create(
            numero='SOR-2026-0001',
            succursale=self.succ_a,
            domaine=self.domaine_boutique,
            motif='Sortie test',
            destination=service,
            utilisateur=self.magasinier_a,
        )
        LigneSortie.objects.create(bon=bon, article=self.article_a, quantite=1)
        with self.assertRaises(ValidationError):
            bon.valider()
        self.article_a.refresh_from_db()
        self.assertEqual(self.article_a.stock, 3)  # inchangé

    def test_sortie_au_dessus_du_seuil_acceptee(self):
        # Stock strictement au-dessus du seuil → la sortie est acceptée.
        self.article_a.stock = 8
        self.article_a.seuil_minimum = 5
        self.article_a.save(update_fields=['stock', 'seuil_minimum'])
        service = Service.objects.create(nom='Cuisine')
        bon = BonSortie.objects.create(
            numero='SOR-2026-0002',
            succursale=self.succ_a,
            domaine=self.domaine_boutique,
            motif='Sortie test',
            destination=service,
            utilisateur=self.magasinier_a,
        )
        LigneSortie.objects.create(bon=bon, article=self.article_a, quantite=2)
        bon.valider()
        self.article_a.refresh_from_db()
        self.assertEqual(self.article_a.stock, 6)

    def test_mouvement_ne_touche_que_sa_succursale(self):
        bon = BonApprovisionnement.objects.create(
            numero='APP-2026-0010',
            succursale=self.succ_a,
            domaine=self.domaine_boutique,
            fournisseur=self.fournisseur,
            utilisateur=self.magasinier_a,
        )
        LigneApprovisionnement.objects.create(bon=bon, article=self.article_a, quantite=5)
        bon.valider()
        mouvement = bon.lignes.first().mouvement
        self.assertEqual(mouvement.succursale, self.succ_a)
        self.assertEqual(mouvement.domaine, self.domaine_boutique)
        self.article_a.refresh_from_db()
        self.assertEqual(self.article_a.stock, 5)
        # Ni la succursale B, ni le domaine Restaurant ne sont impactés.
        self.article_b.refresh_from_db()
        self.assertEqual(self.article_b.stock, 0)
        self.article_resto.refresh_from_db()
        self.assertEqual(self.article_resto.stock, 0)

    def test_stock_separe_par_succursale_ET_domaine(self):
        # Même code, même succursale, domaine différent → stock distinct.
        self.assertEqual(
            Article.objects.filter(code='ART1', succursale=self.succ_a).count(),
            2,
        )
        self.assertEqual(self.article_a.stock, 0)
        self.assertEqual(self.article_resto.stock, 0)


class TestPermissionsVues(ApprovisionnementBase):
    def test_non_connecte_redirige(self):
        response = self.client.get(reverse('approvisionnement:dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_avec_permission(self):
        self.client.login(username='mag_a', password='mdp123')
        response = self.client.get(reverse('approvisionnement:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_validation_sans_permission_forbidden(self):
        # Le magasinier n'a PAS validate_approvisionnement.
        self.client.login(username='mag_a', password='mdp123')
        response = self.client.get(reverse('approvisionnement:entree_validation'))
        self.assertEqual(response.status_code, 403)

    def test_validation_avec_permission(self):
        self.client.login(username='resp', password='mdp123')
        response = self.client.get(reverse('approvisionnement:entree_validation'))
        self.assertEqual(response.status_code, 200)

    def test_creer_entree_avec_permission(self):
        self.client.login(username='mag_a', password='mdp123')
        response = self.client.get(reverse('approvisionnement:entree_nouveau'))
        self.assertEqual(response.status_code, 200)


class TestFiltrageParSuccursale(ApprovisionnementBase):
    def _bon(self, numero, succursale, utilisateur, domaine=None):
        return BonApprovisionnement.objects.create(
            numero=numero,
            succursale=succursale,
            domaine=domaine or self.domaine_boutique,
            fournisseur=self.fournisseur,
            utilisateur=utilisateur,
        )

    def test_liste_entrees_filtree(self):
        bon_a = self._bon('APP-2026-0001', self.succ_a, self.magasinier_a)
        bon_b = self._bon('APP-2026-0002', self.succ_b, self.magasinier_b)
        self.client.login(username='mag_a', password='mdp123')
        response = self.client.get(reverse('approvisionnement:entree'))
        self.assertContains(response, bon_a.numero)
        self.assertNotContains(response, bon_b.numero)

    def test_detail_bon_autre_succursale_introuvable(self):
        bon_b = self._bon('APP-2026-0002', self.succ_b, self.magasinier_b)
        self.client.login(username='mag_a', password='mdp123')
        response = self.client.get(
            reverse('approvisionnement:entree_detail', kwargs={'pk': bon_b.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_mouvements_du_dashboard_filtres(self):
        # Bons VALIDÉS → ils alimentent le journal Approvisionnement.
        bon_a = self._bon('APP-2026-0001', self.succ_a, self.magasinier_a)
        LigneApprovisionnement.objects.create(bon=bon_a, article=self.article_a, quantite=5)
        bon_a.valider()
        bon_b = self._bon('APP-2026-0002', self.succ_b, self.magasinier_b)
        LigneApprovisionnement.objects.create(bon=bon_b, article=self.article_b, quantite=3)
        bon_b.valider()
        self.client.login(username='mag_a', password='mdp123')
        response = self.client.get(reverse('approvisionnement:dashboard'))
        self.assertContains(response, 'APP-2026-0001')
        self.assertNotContains(response, 'APP-2026-0002')

    def test_articles_du_dashboard_filtres(self):
        self.client.login(username='mag_a', password='mdp123')
        response = self.client.get(reverse('approvisionnement:dashboard'))
        self.assertContains(response, 'Article A')          # succ A / Boutique
        self.assertNotContains(response, 'Article B')       # autre succursale
        self.assertNotContains(response, 'Riz restaurant')  # autre domaine

    def test_filtrage_domaine_activite(self):
        # Utilisateur affecté à la succursale A MAIS uniquement pour le domaine
        # RESTAURANT → il ne voit que le stock RESTAURANT, pas la BOUTIQUE.
        user_resto = UserService.creer(
            username='resto', password='mdp123', roles=[self.role_magasinier]
        )
        UserService.affecter_succursale(user_resto, self.succ_a, self.domaine_restaurant)

        self.client.login(username='resto', password='mdp123')
        response = self.client.get(reverse('approvisionnement:dashboard'))
        self.assertEqual(response.status_code, 200)  # a bien la permission du module
        self.assertContains(response, 'Riz restaurant')
        self.assertNotContains(response, 'Article A')


class TestReglesMetier(ApprovisionnementBase):
    """Règles : succursale/domaine auto + verrouillés ; fournisseur/quantité modifiables."""

    def test_contexte_auto_et_verrouille(self):
        # Utilisateur avec UNE seule affectation → contexte verrouillé + pré-rempli.
        contexte = self.magasinier_a.contexte_actif()
        self.assertTrue(contexte['verrouille'])
        self.assertEqual(contexte['succursale'], self.succ_a)
        self.assertEqual(contexte['domaine'], self.domaine_boutique)

        form = BonApprovisionnementForm(
            succursales=Succursale.objects.all(),
            domaines=Domaine.objects.all(),
            contexte=contexte,
        )
        self.assertTrue(form.fields['succursale'].disabled)
        self.assertTrue(form.fields['domaine'].disabled)
        self.assertEqual(form.fields['succursale'].initial, self.succ_a)
        self.assertEqual(form.fields['domaine'].initial, self.domaine_boutique)

    def test_succursale_forcee_sur_post(self):
        # Le POST tente une autre succursale mais elle est ignorée : le bon est
        # créé sur le contexte de l'utilisateur (cohérence).
        autre_fournisseur = Fournisseur.objects.create(nom='F2')
        self.client.login(username='mag_a', password='mdp123')
        response = self.client.post(
            reverse('approvisionnement:entree_nouveau'),
            {
                'date_approvisionnement': '2026-08-17T10:00',
                'succursale': self.succ_b.pk,  # tenté, mais ignoré (verrouillé)
                'domaine': self.domaine_restaurant.pk,  # tenté, mais ignoré
                'fournisseur': autre_fournisseur.pk,
                'reference': '',
                'commentaire': '',
                'lignes-TOTAL_FORMS': '0',
                'lignes-INITIAL_FORMS': '0',
                'lignes-MIN_NUM_FORMS': '0',
                'lignes-MAX_NUM_FORMS': '1000',
            },
        )
        self.assertEqual(response.status_code, 302)
        bon = BonApprovisionnement.objects.latest('id')
        self.assertEqual(bon.succursale, self.succ_a)
        self.assertEqual(bon.domaine, self.domaine_boutique)

    def test_entree_avec_articles_et_quantites(self):
        # Le formulaire de création accepte directement articles + quantités.
        self.client.login(username='mag_a', password='mdp123')
        response = self.client.post(
            reverse('approvisionnement:entree_nouveau'),
            {
                'date_approvisionnement': '2026-08-17T10:00',
                'fournisseur': self.fournisseur.pk,
                'reference': '',
                'commentaire': '',
                'lignes-TOTAL_FORMS': '1',
                'lignes-INITIAL_FORMS': '0',
                'lignes-MIN_NUM_FORMS': '0',
                'lignes-MAX_NUM_FORMS': '1000',
                'lignes-0-article': self.article_a.pk,
                'lignes-0-quantite': '5',
            },
        )
        self.assertEqual(response.status_code, 302)
        bon = BonApprovisionnement.objects.latest('id')
        self.assertEqual(bon.lignes.count(), 1)
        ligne = bon.lignes.first()
        self.assertEqual(ligne.article, self.article_a)
        self.assertEqual(ligne.quantite, 5)
        # Contexte verrouillé respecté.
        self.assertEqual(bon.succursale, self.succ_a)
        self.assertEqual(bon.domaine, self.domaine_boutique)

    def test_superuser_contexte_libre(self):
        admin = UserService.creer(username='sup', password='mdp123')
        admin.is_superuser = True
        admin.save(update_fields=['is_superuser'])
        contexte = admin.contexte_actif()
        self.assertFalse(contexte['verrouille'])
        form = BonApprovisionnementForm(
            succursales=Succursale.objects.all(),
            domaines=Domaine.objects.all(),
            contexte=contexte,
        )
        self.assertFalse(form.fields['succursale'].disabled)

    def test_validation_modifie_fournisseur_et_quantite(self):
        bon = BonApprovisionnement.objects.create(
            numero='APP-2026-0020',
            succursale=self.succ_a,
            domaine=self.domaine_boutique,
            fournisseur=self.fournisseur,
            utilisateur=self.responsable,
        )
        ligne = LigneApprovisionnement.objects.create(bon=bon, article=self.article_a, quantite=5)
        autre_fournisseur = Fournisseur.objects.create(nom='F2')

        self.client.login(username='resp', password='mdp123')
        response = self.client.post(
            reverse('approvisionnement:entree_validation_detail', kwargs={'pk': bon.pk}),
            {
                'fournisseur': autre_fournisseur.pk,
                'reference': 'REF-X',
                'commentaire': '',
                'lignes-TOTAL_FORMS': '1',
                'lignes-INITIAL_FORMS': '1',
                'lignes-MIN_NUM_FORMS': '0',
                'lignes-MAX_NUM_FORMS': '1000',
                'lignes-0-id': ligne.pk,
                'lignes-0-quantite': '3',
                'lignes-0-DELETE': '',
                'action': 'valider',
            },
        )
        self.assertEqual(response.status_code, 302)  # redirection vers l'impression
        bon.refresh_from_db()
        self.assertEqual(bon.statut, BonApprovisionnement.Statut.VALIDE)
        self.assertEqual(bon.fournisseur, autre_fournisseur)
        self.assertEqual(bon.reference, 'REF-X')
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite, 3)
        self.article_a.refresh_from_db()
        self.assertEqual(self.article_a.stock, 3)  # stock augmenté de la NOUVELLE quantité

    def test_inventaire_un_article(self):
        self.client.login(username='resp', password='mdp123')
        response = self.client.post(
            reverse('approvisionnement:inventaire_nouveau'),
            {
                'date_inventaire': '2026-08-17',
                'succursale': self.succ_a.pk,
                'domaine': self.domaine_boutique.pk,
                'portee': 'ARTICLE',
                'article': self.article_a.pk,
                'commentaire': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        inventaire = Inventaire.objects.latest('id')
        self.assertEqual(inventaire.lignes.count(), 1)
        self.assertEqual(inventaire.lignes.first().article, self.article_a)

    def test_inventaire_complet(self):
        self.client.login(username='resp', password='mdp123')
        response = self.client.post(
            reverse('approvisionnement:inventaire_nouveau'),
            {
                'date_inventaire': '2026-08-17',
                'succursale': self.succ_a.pk,
                'domaine': self.domaine_boutique.pk,
                'portee': 'COMPLET',
                'article': '',
                'commentaire': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        inventaire = Inventaire.objects.latest('id')
        # Seuls les articles du périmètre (succ_a + BOUTIQUE) : article_a uniquement.
        self.assertEqual(
            list(inventaire.lignes.values_list('article_id', flat=True)),
            [self.article_a.pk],
        )

    def test_inventaire_article_sans_article_invalide(self):
        self.client.login(username='resp', password='mdp123')
        response = self.client.post(
            reverse('approvisionnement:inventaire_nouveau'),
            {
                'date_inventaire': '2026-08-17',
                'succursale': self.succ_a.pk,
                'domaine': self.domaine_boutique.pk,
                'portee': 'ARTICLE',
                'article': '',
                'commentaire': '',
            },
        )
        self.assertEqual(response.status_code, 200)  # re-rendu du formulaire
        self.assertContains(response, 'Sélectionnez l’article')
        self.assertEqual(Inventaire.objects.count(), 0)
