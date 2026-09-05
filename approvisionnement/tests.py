from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from core.models import Role
from core.services import UserService

from .models import BonApprovisionnement, BonSortie, Categorie, Fournisseur, Produit, Service, Unite

User = get_user_model()


class ProfilsApprovisionnementTests(TestCase):
    def setUp(self):
        self.categorie = Categorie.objects.create(nom='Vivres')
        self.unite = Unite.objects.create(code='KG', libelle='Kg')
        self.fournisseur = Fournisseur.objects.create(nom='Fournisseur test')
        self.produit = Produit.objects.create(
            code='RIZ',
            designation='Riz',
            categorie=self.categorie,
            unite=self.unite,
            stock=10,
        )

        self.magasinier = self._utilisateur(
            'magasinier',
            'MAGASINIER',
            [
                (
                    'approvisionnement',
                    [
                        'view_approvisionnement', 'create_approvisionnement',
                        'view_sortie', 'create_sortie',
                        'view_inventaire', 'create_inventaire',
                        'view_rapport_approvisionnement',
                    ],
                ),
            ],
        )
        self.comptable = self._utilisateur(
            'comptable',
            'COMPTABLE',
            [
                (
                    'approvisionnement',
                    [
                        'view_approvisionnement', 'validate_approvisionnement',
                        'view_sortie', 'validate_sortie',
                        'view_inventaire', 'validate_inventaire',
                        'view_rapport_approvisionnement',
                    ],
                ),
            ],
        )

    def _utilisateur(self, username, code, paires):
        profil = UserService.creer(username=username, password='pass1234')
        role, _ = Role.objects.get_or_create(code=code, defaults={'nom': code})
        perms = []
        for app, names in paires:
            perms += list(
                Permission.objects.filter(
                    content_type__app_label=app, codename__in=names
                )
            )
        role.permissions.set(perms)
        profil.roles.add(role)
        return profil.compte

    def _bon(self, user):
        return BonApprovisionnement.objects.create(
            numero='APP-TEST-0001',
            fournisseur=self.fournisseur,
            utilisateur=user,
        )

    def test_magasinier_enregistre_sans_valider(self):
        self.client.force_login(self.magasinier)
        self.assertEqual(
            self.client.get(reverse('approvisionnement:entree_nouveau')).status_code, 200)
        self.assertEqual(
            self.client.get(reverse('approvisionnement:rapport')).status_code, 200)
        bon = self._bon(self.magasinier)
        self.assertEqual(
            self.client.get(reverse('approvisionnement:entree_validation')).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse('approvisionnement:entree_valider', args=[bon.pk])
            ).status_code,
            403,
        )

    def test_comptable_valide_sans_enregistrer(self):
        self.client.force_login(self.comptable)
        self.assertEqual(
            self.client.get(reverse('approvisionnement:entree_nouveau')).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse('approvisionnement:entree_validation')).status_code,
            200,
        )
        self.assertFalse(
            self.comptable.has_perm('approvisionnement.cancel_approvisionnement')
        )
        self.assertFalse(self.comptable.has_perm('approvisionnement.cancel_sortie'))


class ImpressionBordereaux80mmTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('impr', 'impr@test.local', 'pass1234')
        self.categorie = Categorie.objects.create(nom='Vivres')
        self.unite = Unite.objects.create(code='KG', libelle='Kg')
        self.fournisseur = Fournisseur.objects.create(nom='Fournisseur test')
        self.client.force_login(self.user)

    def test_entree_impression_ticket_80mm(self):
        bon = BonApprovisionnement.objects.create(
            numero='APP-TEST-IMP-1',
            fournisseur=self.fournisseur,
            utilisateur=self.user,
            statut=BonApprovisionnement.Statut.VALIDE,
        )
        resp = self.client.get(reverse('approvisionnement:entree_imprimer', args=[bon.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'bon-80mm')
        self.assertContains(resp, '80mm')
        self.assertNotContains(resp, 'bon-doc')

    def test_sortie_impression_ticket_80mm(self):
        destination, _ = Service.objects.get_or_create(nom='Terrasse')
        bon = BonSortie.objects.create(
            numero='SOR-TEST-IMP-1',
            motif='Réassort',
            destination=destination,
            utilisateur=self.user,
            statut=BonSortie.Statut.VALIDE,
        )
        resp = self.client.get(reverse('approvisionnement:sortie_imprimer', args=[bon.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'bon-80mm')
        self.assertContains(resp, '80mm')
        self.assertNotContains(resp, 'bon-doc')


class SortieBarbecusVivreFraisTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('bbq', 'bbq@test.local', 'pass1234')
        self.frais = Categorie.objects.create(nom='Vivre frais', nombre_portions=4)
        self.boissons = Categorie.objects.create(nom='Boissons')
        unite = Unite.objects.create(code='PC', libelle='Pièce')
        self.poulet = Produit.objects.create(
            code='PLT',
            designation='Poulet entier',
            categorie=self.frais,
            unite=unite,
            stock=20,
        )
        self.soda = Produit.objects.create(
            code='SOD',
            designation='Soda cola',
            categorie=self.boissons,
            unite=unite,
            stock=20,
        )
        self.destination = Service.objects.create(nom='Barbecus')
        self.client.force_login(self.user)

    def test_sortie_barbecus_propose_seulement_vivre_frais(self):
        bon = BonSortie.objects.create(
            numero='SOR-BBQ-1',
            motif='Réassort barbecus',
            destination=self.destination,
            utilisateur=self.user,
        )
        resp = self.client.get(reverse('approvisionnement:sortie_detail', args=[bon.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'vivre frais')
        self.assertContains(resp, 'Poulet entier')
        self.assertNotContains(resp, 'Soda cola')

    def test_validation_refuse_produit_hors_vivre_frais(self):
        from django.core.exceptions import ValidationError

        from approvisionnement.models import LigneSortie

        bon = BonSortie.objects.create(
            numero='SOR-BBQ-2',
            motif='Réassort barbecus',
            destination=self.destination,
            utilisateur=self.user,
        )
        LigneSortie.objects.create(bon=bon, produit=self.soda, quantite=1)
        with self.assertRaises(ValidationError):
            bon.valider()

    def test_tableau_de_bord_affiche_comparaison(self):
        resp = self.client.get(reverse('approvisionnement:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'comparaison-appro')
        self.assertContains(resp, 'Entrées')
        self.assertContains(resp, 'Sorties')
