from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from core.models import Role
from core.services import UserService

from .models import BonApprovisionnement, Categorie, Fournisseur, Produit, Unite

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
