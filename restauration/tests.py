"""Tests du flux commande → tickets → encaissement / facture."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from facturation.models import Etablissement, Facture

from .models import (
    CategorieMenu,
    Commande,
    Imprimante,
    LigneCommande,
    Plat,
    Salle,
    ServicePoste,
    Table,
)
from .views import _lignes_poste

User = get_user_model()


class RestaurationFluxTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('serveur', password='pass1234')
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save(update_fields=['is_superuser', 'is_staff'])
        self.salle, _ = Salle.objects.get_or_create(nom='Salle A')
        self.table, _ = Table.objects.get_or_create(
            salle=self.salle, numero='1', defaults={'places': 4},
        )
        self.imprimante, _ = Imprimante.objects.get_or_create(
            nom='Cuisine',
            defaults={'service': ServicePoste.CUISINE, 'nom_systeme': 'Cuisine'},
        )
        self.categorie, _ = CategorieMenu.objects.get_or_create(nom='Plats')
        self.plat = Plat.objects.create(
            categorie=self.categorie,
            nom='Poulet braisé',
            prix=Decimal('10.00'),
            service=ServicePoste.CUISINE,
            imprimante=self.imprimante,
            quantite=5,
            seuil_alerte=2,
        )
        self.plat_zero = Plat.objects.create(
            categorie=self.categorie,
            nom='Poisson grillé',
            prix=Decimal('12.00'),
            service=ServicePoste.CUISINE,
            imprimante=self.imprimante,
            quantite=0,
        )
        Etablissement.objects.get_or_create(
            pk=1,
            defaults={'nom_societe': 'IBBS BAZAR'},
        )
        self.client.force_login(self.user)

    def _ouvrir(self):
        resp = self.client.post(reverse('restauration:table_ouvrir', args=[self.table.pk]))
        self.assertEqual(resp.status_code, 302)
        return Commande.objects.get(table=self.table, statut=Commande.Statut.OUVERTE)

    def test_ajout_refuse_quand_quantite_zero(self):
        commande = self._ouvrir()
        resp = self.client.post(
            reverse('restauration:commande_ajouter', args=[commande.pk]),
            {'plat': self.plat_zero.pk, 'quantite': '1'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(commande.lignes.exists())
        page = self.client.get(reverse('restauration:commande_detail', args=[commande.pk]))
        self.assertContains(page, 'Rupture — 0 disponible')
        self.assertContains(page, 'Indisponible')

    def test_ajout_ok_puis_validation_ouvre_apercu_sans_imprimer(self):
        commande = self._ouvrir()
        self.client.post(
            reverse('restauration:commande_ajouter', args=[commande.pk]),
            {'plat': self.plat.pk, 'quantite': '2'},
        )
        self.assertEqual(commande.lignes.get().quantite, 2)
        self.assertEqual(Plat.objects.get(pk=self.plat.pk).quantite, 5)

        resp = self.client.post(reverse('restauration:commande_valider', args=[commande.pk]))
        self.assertRedirects(resp, reverse('restauration:commande_tickets', args=[commande.pk]))
        commande.refresh_from_db()
        self.assertEqual(commande.statut, Commande.Statut.VALIDEE)
        self.assertEqual(Plat.objects.get(pk=self.plat.pk).quantite, 3)

        apercu = self.client.get(reverse('restauration:commande_tickets', args=[commande.pk]))
        self.assertContains(apercu, 'Aperçu avant impression')
        self.assertContains(apercu, 'Poulet braisé')
        self.assertContains(apercu, 'Envoyer à')

    def test_encaissement_cree_facture_et_apercu_recu(self):
        commande = self._ouvrir()
        self.client.post(
            reverse('restauration:commande_ajouter', args=[commande.pk]),
            {'plat': self.plat.pk, 'quantite': '1'},
        )
        self.client.post(reverse('restauration:commande_valider', args=[commande.pk]))
        resp = self.client.post(
            reverse('restauration:commande_encaisser', args=[commande.pk]),
            {'mode_paiement': Commande.ModePaiement.ESPECES},
        )
        facture = Facture.objects.get(commande=commande)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('facturation:recu', args=[facture.pk]), resp['Location'])
        commande.refresh_from_db()
        self.assertEqual(commande.statut, Commande.Statut.PAYEE)

        recu = self.client.get(reverse('facturation:recu', args=[facture.pk]))
        self.assertContains(recu, 'Aperçu du reçu')
        self.assertContains(recu, 'Envoyer à l’imprimante caisse')
        self.assertNotContains(recu, 'window.addEventListener("load"')

    def test_poste_voit_ligne_apres_encaissement(self):
        commande = self._ouvrir()
        self.client.post(
            reverse('restauration:commande_ajouter', args=[commande.pk]),
            {'plat': self.plat.pk, 'quantite': '1'},
        )
        commande.valider(self.user)
        commande.encaisser(Commande.ModePaiement.ESPECES)
        lignes = list(_lignes_poste(ServicePoste.CUISINE))
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].commande_id, commande.pk)

    def test_reserver_refuse_stock_a_zero(self):
        with self.assertRaises(ValidationError):
            self.plat_zero.reserver(1)

    def test_totaux_ignorent_lignes_annulees(self):
        commande = Commande.objects.create(
            numero='RST-TEST-0001',
            table=self.table,
            utilisateur=self.user,
        )
        LigneCommande.objects.create(
            commande=commande,
            plat=self.plat,
            quantite=1,
            prix_unitaire=Decimal('10.00'),
            statut=LigneCommande.Statut.ANNULEE,
        )
        LigneCommande.objects.create(
            commande=commande,
            plat=self.plat,
            quantite=2,
            prix_unitaire=Decimal('10.00'),
        )
        self.assertEqual(commande.total, Decimal('20.00'))


class ProfilsRestaurationTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Permission

        from core.models import Role

        self.salle, _ = Salle.objects.get_or_create(nom='Salle A')
        self.table, _ = Table.objects.get_or_create(
            salle=self.salle, numero='2', defaults={'places': 4},
        )
        self.imprimante, _ = Imprimante.objects.get_or_create(
            nom='Cuisine',
            defaults={'service': ServicePoste.CUISINE, 'nom_systeme': 'Cuisine'},
        )
        self.categorie, _ = CategorieMenu.objects.get_or_create(nom='Plats')
        self.plat = Plat.objects.create(
            categorie=self.categorie,
            nom='Riz',
            prix=Decimal('5.00'),
            service=ServicePoste.CUISINE,
            imprimante=self.imprimante,
            quantite=10,
        )
        Etablissement.objects.get_or_create(pk=1, defaults={'nom_societe': 'IBBS BAZAR'})

        def utilisateur(username, code, paires):
            user = User.objects.create_user(username, password='pass1234')
            role, _ = Role.objects.get_or_create(code=code, defaults={'nom': code})
            perms = []
            for app, names in paires:
                perms += list(
                    Permission.objects.filter(
                        content_type__app_label=app, codename__in=names
                    )
                )
            role.permissions.set(perms)
            user.profil.roles.add(role)
            return user

        self.operateur = utilisateur(
            'operateur',
            'OPERATEUR_COMMANDE',
            [(
                'restauration',
                [
                    'view_restauration', 'create_commande', 'modify_commande',
                    'validate_commande', 'cancel_commande', 'adjust_plat_portions',
                ],
            )],
        )
        self.caissier = utilisateur(
            'caissiere',
            'CAISSIER',
            [
                ('restauration', ['view_restauration', 'encaisser_commande']),
                ('facturation', ['view_facture']),
            ],
        )

    def _commande_ouverte(self, user):
        self.client.force_login(user)
        self.client.post(reverse('restauration:table_ouvrir', args=[self.table.pk]))
        return Commande.objects.get(table=self.table, statut=Commande.Statut.OUVERTE)

    def test_operateur_retire_ligne_avant_validation_pas_apres(self):
        commande = self._commande_ouverte(self.operateur)
        self.client.post(
            reverse('restauration:commande_ajouter', args=[commande.pk]),
            {'plat': self.plat.pk, 'quantite': '1'},
        )
        ligne = commande.lignes.get()
        self.assertEqual(
            self.client.post(
                reverse('restauration:commande_ligne_supprimer', args=[commande.pk, ligne.pk])
            ).status_code,
            302,
        )
        self.assertFalse(commande.lignes.exists())

        self.client.post(
            reverse('restauration:commande_ajouter', args=[commande.pk]),
            {'plat': self.plat.pk, 'quantite': '1'},
        )
        self.client.post(reverse('restauration:commande_valider', args=[commande.pk]))
        commande.refresh_from_db()
        self.assertEqual(commande.statut, Commande.Statut.VALIDEE)

        resp = self.client.post(
            reverse('restauration:commande_annuler', args=[commande.pk]),
            {'motif': 'Erreur'},
        )
        self.assertEqual(resp.status_code, 302)
        commande.refresh_from_db()
        self.assertEqual(commande.statut, Commande.Statut.VALIDEE)

    def test_caissier_encaisse_sans_annuler_la_facture(self):
        commande = Commande.objects.create(
            numero='RST-TEST-CAISSE',
            table=self.table,
            utilisateur=self.operateur,
        )
        LigneCommande.objects.create(
            commande=commande,
            plat=self.plat,
            quantite=1,
            prix_unitaire=Decimal('5.00'),
        )
        commande.valider(self.operateur)

        self.client.force_login(self.caissier)
        self.assertEqual(
            self.client.get(reverse('restauration:commande_detail', args=[commande.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(reverse('restauration:commande_valider', args=[commande.pk])).status_code,
            403,
        )
        resp = self.client.post(
            reverse('restauration:commande_encaisser', args=[commande.pk]),
            {'mode_paiement': Commande.ModePaiement.ESPECES},
        )
        self.assertEqual(resp.status_code, 302)
        commande.refresh_from_db()
        self.assertEqual(commande.statut, Commande.Statut.PAYEE)

        resp = self.client.post(
            reverse('restauration:commande_annuler', args=[commande.pk]),
            {'motif': 'Trop tard'},
        )
        self.assertEqual(resp.status_code, 403)
        commande.refresh_from_db()
        self.assertEqual(commande.statut, Commande.Statut.PAYEE)
