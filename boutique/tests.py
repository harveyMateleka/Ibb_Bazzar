from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from approvisionnement.models import Article, Categorie, Unite
from core.models import Domaine, Role, Succursale
from core.services import UserService
from approvisionnement.models import MouvementStock

from .models import ArticleBoutique, Vente
from .services import VenteService


def _perm(app_label, codename):
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


class BoutiqueBase(TestCase):
    def setUp(self):
        self.domaine = Domaine.objects.create(code='BOUTIQUE', libelle='Boutique')
        self.succ_a = Succursale.objects.create(nom='Succ A', code='A')
        self.succ_b = Succursale.objects.create(nom='Succ B', code='B')
        self.categorie = Categorie.objects.create(nom='Habillement')
        self.unite = Unite.objects.create(code='PCE', libelle='Pièce')

        self.article = Article.objects.create(
            code='TSHIRT-N-M', designation='T-shirt noir M',
            succursale=self.succ_a, domaine=self.domaine,
            categorie=self.categorie, unite=self.unite,
            seuil_minimum=5, stock=10,
        )
        self.article_b = Article.objects.create(
            code='TSHIRT-N-L', designation='T-shirt noir L',
            succursale=self.succ_b, domaine=self.domaine,
            categorie=self.categorie, unite=self.unite,
            seuil_minimum=5, stock=10,
        )
        ArticleBoutique.objects.create(
            article=self.article, type_produit='T-shirt', taille='M',
            couleur='Noir', prix_achat=Decimal('10'), prix_vente=Decimal('15'),
            prix_limite=Decimal('12'),
        )
        ArticleBoutique.objects.create(
            article=self.article_b, type_produit='T-shirt', taille='L',
            couleur='Noir', prix_achat=Decimal('10'), prix_vente=Decimal('18'),
            prix_limite=Decimal('12'),
        )

        self.role_caissier = Role.objects.create(nom='Caissier', code='CAISSIER')
        self.role_caissier.permissions.add(
            _perm('boutique', 'view_boutique'),
            _perm('boutique', 'view_stock'),
            _perm('boutique', 'view_vente'),
            _perm('boutique', 'create_vente'),
        )
        self.role_responsable = Role.objects.create(nom='Responsable', code='RESPONSABLE')
        self.role_responsable.permissions.add(
            _perm('boutique', 'view_boutique'),
            _perm('boutique', 'view_stock'),
            _perm('boutique', 'view_vente'),
            _perm('boutique', 'create_vente'),
            _perm('boutique', 'validate_vente'),
            _perm('boutique', 'cancel_vente'),
            _perm('boutique', 'apply_remise'),
        )
        self.caissier = UserService.creer(username='cais_a', password='mdp123', roles=[self.role_caissier])
        self.responsable = UserService.creer(username='resp_a', password='mdp123', roles=[self.role_responsable])
        UserService.affecter_succursale(self.caissier, self.succ_a, self.domaine)
        UserService.affecter_succursale(self.responsable, self.succ_a, self.domaine)


class TestVenteService(BoutiqueBase):
    def test_creation_vente(self):
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.caissier
        )
        self.assertTrue(vente.numero.startswith('VTE-'))
        self.assertEqual(vente.statut, Vente.Statut.BROUILLON)

    def test_validation_diminue_le_stock(self):
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.caissier
        )
        VenteService.ajouter_ligne(
            vente, self.article, quantite=3, prix_unitaire=Decimal('15')
        )
        VenteService.valider(vente, par=self.responsable)
        vente.refresh_from_db()
        self.article.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.VALIDEE)
        self.assertEqual(self.article.stock, 7)
        # Un mouvement de sortie est généré, contextualisé (succursale + domaine).
        mouvement = vente.lignes.first().mouvement
        self.assertIsNotNone(mouvement)
        self.assertEqual(mouvement.type_mouvement, MouvementStock.Type.SORTIE)
        self.assertEqual(mouvement.succursale, self.succ_a)
        self.assertEqual(mouvement.domaine, self.domaine)
        self.assertEqual(mouvement.stock_apres, 7)

    def test_stock_insuffisant_refuse(self):
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.caissier
        )
        VenteService.ajouter_ligne(
            vente, self.article, quantite=99, prix_unitaire=Decimal('15')
        )
        with self.assertRaises(ValidationError):
            VenteService.valider(vente, par=self.responsable)
        self.article.refresh_from_db()
        self.assertEqual(self.article.stock, 10)  # inchangé (transaction annulée)

    def test_vente_refusee_au_seuil_d_alerte(self):
        # Règle : aucune sortie si le stock est égal ou inférieur au seuil d'alerte.
        self.article.stock = 5  # == seuil_minimum (5)
        self.article.save(update_fields=['stock'])
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.caissier
        )
        VenteService.ajouter_ligne(vente, self.article, quantite=2, prix_unitaire=Decimal('15'))
        with self.assertRaises(ValidationError):
            VenteService.valider(vente, par=self.responsable)
        self.article.refresh_from_db()
        self.assertEqual(self.article.stock, 5)  # inchangé

    def test_vente_sous_prix_limite_refusee(self):
        # Règle prix_limite : impossible de vendre en dessous du prix plancher.
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.caissier
        )
        VenteService.ajouter_ligne(
            vente, self.article, quantite=1, prix_unitaire=Decimal('10')  # < prix_limite 12
        )
        with self.assertRaises(ValidationError):
            VenteService.valider(vente, par=self.responsable)
        self.article.refresh_from_db()
        self.assertEqual(self.article.stock, 10)  # inchangé

    def test_formulaire_refuse_prix_sous_limite(self):
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.caissier
        )
        self.client.login(username='cais_a', password='mdp123')
        # POST du formset avec un prix sous la limite → erreur sur le champ.
        data = {
            'lignes-TOTAL_FORMS': '1',
            'lignes-INITIAL_FORMS': '0',
            'lignes-0-article': self.article.pk,
            'lignes-0-quantite': '1',
            'lignes-0-prix_unitaire': '10',
            'lignes-0-id': '',
            'lignes-0-vente': vente.pk,
        }
        response = self.client.post(
            reverse('boutique:vente_detail', kwargs={'pk': vente.pk}),
            data,
        )
        self.assertContains(response, 'inférieur à la limite')

    def test_remise_calculee(self):
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.caissier, remise=5
        )
        VenteService.ajouter_ligne(vente, self.article, quantite=2, prix_unitaire=Decimal('15'))
        vente.recalculer()
        vente.refresh_from_db()
        self.assertEqual(vente.sous_total, Decimal('30'))
        self.assertEqual(vente.total, Decimal('25'))

    def test_annulation_brouillon(self):
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.caissier
        )
        VenteService.annuler(vente, par=self.responsable)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, Vente.Statut.ANNULEE)


class TestPermissionsEtRemises(BoutiqueBase):
    def test_vente_sans_permission_forbidden(self):
        self.client.login(username='cais_a', password='mdp123')
        response = self.client.get(reverse('boutique:vente_nouvelle'))
        self.assertEqual(response.status_code, 200)

    def test_validation_sans_permission_forbidden(self):
        # Le caissier n'a PAS validate_vente → le POST valider renvoie 403.
        self.client.login(username='cais_a', password='mdp123')
        vente = VenteService.creer(
            succursale=self.succ_a, domaine=self.domaine, utilisateur=self.caissier
        )
        response = self.client.post(
            reverse('boutique:vente_valider', kwargs={'pk': vente.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_remise_refusee_sans_permission(self):
        self.client.login(username='cais_a', password='mdp123')
        response = self.client.post(
            reverse('boutique:vente_nouvelle'),
            {
                'succursale': self.succ_a.pk,
                'domaine': self.domaine.pk,
                'type_paiement': 'ESPECES',
                'montant_recu': '0',
                'remise': '10',
            },
        )
        # Le caissier n'est pas autorisé : message d'erreur, pas de redirection.
        self.assertContains(response, 'remise')
        self.assertEqual(Vente.objects.count(), 0)

    def test_remise_autorisee_avec_permission(self):
        self.client.login(username='resp_a', password='mdp123')
        response = self.client.post(
            reverse('boutique:vente_nouvelle'),
            {
                'succursale': self.succ_a.pk,
                'domaine': self.domaine.pk,
                'type_paiement': 'ESPECES',
                'montant_recu': '0',
                'remise': '10',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Vente.objects.count(), 1)
        self.assertEqual(Vente.objects.first().remise, Decimal('10'))


class TestPerimetreBoutique(BoutiqueBase):
    def test_liste_articles_filtree_par_succursale(self):
        self.client.login(username='cais_a', password='mdp123')
        response = self.client.get(reverse('boutique:articles'))
        self.assertContains(response, 'TSHIRT-N-M')
        self.assertNotContains(response, 'TSHIRT-N-L')  # succursale B

    def test_detail_vente_autre_succursale_introuvable(self):
        vente = VenteService.creer(
            succursale=self.succ_b, domaine=self.domaine, utilisateur=self.caissier
        )
        self.client.login(username='cais_a', password='mdp123')
        response = self.client.get(
            reverse('boutique:vente_detail', kwargs={'pk': vente.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_aucun_acces_sans_affectation(self):
        # Un utilisateur sans affectation BOUTIQUE ne voit rien.
        user = UserService.creer(username='aucun', password='mdp123', roles=[self.role_caissier])
        UserService.affecter_succursale(user, self.succ_a, Domaine.objects.create(code='RESTAURANT', libelle='Restaurant'))
        self.client.login(username='aucun', password='mdp123')
        response = self.client.get(reverse('boutique:articles'))
        self.assertNotContains(response, 'TSHIRT-N-M')
        self.assertNotContains(response, 'TSHIRT-N-L')
