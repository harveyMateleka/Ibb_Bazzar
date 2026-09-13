"""Tests du flux commande → tickets → encaissement / facture."""

from decimal import Decimal

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from facturation.models import Etablissement, Facture

from .models import (
    CategorieMenu,
    Commande,
    Imprimante,
    LigneCommande,
    Plat,
    Salle,
    Serveur,
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
        self.serveur_fiche = Serveur.objects.create(nom='Mbala', prenom='Jean')
        self.client.force_login(self.user)

    def _ouvrir(self):
        resp = self.client.post(
            reverse('restauration:commande_nouveau'),
            {
                'source': Commande.Source.TABLETTE,
                'table': self.table.pk,
                'serveur': self.serveur_fiche.pk,
            },
        )
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
        self.assertContains(apercu, 'Aperçu 80 mm')
        self.assertContains(apercu, 'bon-80mm')
        self.assertContains(apercu, 'Poulet braisé')
        self.assertContains(apercu, 'Imprimer la commande')

        retour = self.client.get(reverse('restauration:commande_detail', args=[commande.pk]))
        self.assertEqual(retour.status_code, 200)
        self.assertNotContains(retour, 'Encaisser et afficher')
        self.assertContains(retour, 'Ajouter')
        self.assertContains(retour, '20,00')
        self.assertContains(retour, 'facturation')

    def test_ajout_autorise_apres_validation_et_ouvrir(self):
        commande = self._ouvrir()
        self.client.post(
            reverse('restauration:commande_ajouter', args=[commande.pk]),
            {'plat': self.plat.pk, 'quantite': '1'},
        )
        self.client.post(reverse('restauration:commande_valider', args=[commande.pk]))
        occupee = self.client.post(reverse('restauration:table_ouvrir', args=[self.table.pk]))
        self.assertRedirects(occupee, reverse('restauration:commande_detail', args=[commande.pk]))

        liste = self.client.get(reverse('restauration:commandes'))
        self.assertContains(liste, 'Ouvrir')
        self.assertContains(liste, reverse('restauration:commande_detail', args=[commande.pk]))

        resp = self.client.post(
            reverse('restauration:commande_ajouter', args=[commande.pk]),
            {'plat': self.plat.pk, 'quantite': '1'},
        )
        self.assertEqual(resp.status_code, 302)
        commande.refresh_from_db()
        self.assertEqual(commande.lignes.get().quantite, 2)
        detail = self.client.get(reverse('restauration:commande_detail', args=[commande.pk]))
        self.assertContains(detail, 'Ajouter')
        self.assertContains(detail, 'Poulet braisé')
        self.assertNotContains(detail, 'Encaisser et afficher')

        caisse = self.client.get(reverse('facturation:encaisser', args=[commande.pk]))
        self.assertEqual(caisse.status_code, 200)
        self.assertContains(caisse, 'Encaisser')
        self.assertNotContains(caisse, 'Ajouter')

    def test_bon_commande_serveur_en_liste_select2(self):
        page = self.client.get(reverse('restauration:commande_nouveau'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="id_serveur"')
        self.assertContains(page, '<select')
        self.assertContains(page, 'Jean Mbala')

    def test_ouverture_sans_serveur_refusee(self):
        resp = self.client.post(
            reverse('restauration:commande_nouveau'),
            {
                'source': Commande.Source.TABLETTE,
                'table': self.table.pk,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Commande.objects.exists())
        self.assertContains(resp, 'Choisissez le serveur')

    def test_impression_tous_les_groupes_par_imprimante(self):
        from unittest.mock import patch

        from restauration.impression import imprimer_commande_aux_postes

        imprimante_t, _ = Imprimante.objects.get_or_create(
            nom='Terrasse',
            defaults={'service': ServicePoste.TERRASSE, 'nom_systeme': 'Terrasse'},
        )
        plat_t = Plat.objects.create(
            categorie=self.categorie,
            nom='Jus',
            prix=Decimal('3.00'),
            service=ServicePoste.TERRASSE,
            imprimante=imprimante_t,
            quantite=10,
        )
        commande = Commande.objects.create(
            numero='RST-TEST-PRINT',
            table=self.table,
            utilisateur=self.user,
        )
        LigneCommande.objects.create(
            commande=commande, plat=self.plat, quantite=1,
            prix_unitaire=self.plat.prix, service=ServicePoste.CUISINE,
            imprimante_nom='Cuisine',
        )
        LigneCommande.objects.create(
            commande=commande, plat=plat_t, quantite=2,
            prix_unitaire=plat_t.prix, service=ServicePoste.TERRASSE,
            imprimante_nom='Terrasse',
        )
        with patch(
            'restauration.impression.envoyer_texte_imprimante',
            side_effect=lambda nom, texte: nom,
        ) as envoi:
            resultats = imprimer_commande_aux_postes(commande)
        self.assertEqual(len(resultats), 2)
        self.assertTrue(all(item['ok'] for item in resultats))
        self.assertEqual(envoi.call_count, 2)
        cibles = {appel.args[0] for appel in envoi.call_args_list}
        self.assertEqual(cibles, {'Cuisine', 'Terrasse'})
        self.assertTrue(all(ligne.imprimee for ligne in commande.lignes.all()))

    def test_impression_n_envoie_que_les_ajouts(self):
        from restauration.impression import imprimer_commande_aux_postes

        commande = self._ouvrir()
        self.client.post(
            reverse('restauration:commande_ajouter', args=[commande.pk]),
            {'plat': self.plat.pk, 'quantite': '1'},
        )
        self.client.post(reverse('restauration:commande_valider', args=[commande.pk]))
        with patch(
            'restauration.impression.envoyer_texte_imprimante',
            side_effect=lambda nom, texte: nom,
        ):
            imprimer_commande_aux_postes(commande)
        self.assertTrue(commande.lignes.get().imprimee)

        self.client.post(
            reverse('restauration:commande_ajouter', args=[commande.pk]),
            {'plat': self.plat.pk, 'quantite': '2'},
        )
        self.assertEqual(commande.lignes.count(), 2)
        ajout = commande.lignes.get(imprimee=False)
        self.assertEqual(ajout.quantite, 2)

        apercu = self.client.get(reverse('restauration:commande_tickets', args=[commande.pk]))
        self.assertContains(apercu, 'AJOUT')
        self.assertContains(apercu, 'Imprimer les ajouts')
        self.assertContains(apercu, '2')

        with patch(
            'restauration.impression.envoyer_texte_imprimante',
            side_effect=lambda nom, texte: nom,
        ) as envoi:
            resultats = imprimer_commande_aux_postes(commande)
        self.assertEqual(len(resultats), 1)
        self.assertTrue(resultats[0]['ok'])
        texte = envoi.call_args.args[1]
        self.assertIn('AJOUT', texte)
        self.assertIn('2 x Poulet braisé', texte)
        self.assertEqual(texte.count('Poulet braisé'), 1)
        self.assertTrue(all(ligne.imprimee for ligne in commande.lignes.all()))

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
        self.assertContains(recu, 'Imprimer 80 mm')
        self.assertContains(recu, 'ticket-recu')
        self.assertContains(recu, 'imprimerApercu')
        self.assertContains(recu, 'PU')
        self.assertContains(recu, 'PT')
        self.assertContains(recu, 'Qté')
        self.assertContains(recu, '10,00')
        self.assertContains(recu, 'recu-lignes')
        from facturation.impression import texte_recu
        from facturation.models import Etablissement
        ticket = texte_recu(facture, Etablissement.actuel())
        self.assertIn('PLAT', ticket)
        self.assertIn('QTE', ticket)
        self.assertRegex(ticket, r'Poulet braisé\s+1\s+10\s+10')
        self.assertNotIn('1 x Poulet', ticket)
        self.assertNotContains(recu, 'window.addEventListener("load"')

    def test_recu_imprimer_ajax_garde_l_apercu(self):
        commande = self._ouvrir()
        self.client.post(
            reverse('restauration:commande_ajouter', args=[commande.pk]),
            {'plat': self.plat.pk, 'quantite': '1'},
        )
        self.client.post(reverse('restauration:commande_valider', args=[commande.pk]))
        self.client.post(
            reverse('restauration:commande_encaisser', args=[commande.pk]),
            {'mode_paiement': Commande.ModePaiement.ESPECES},
        )
        facture = Facture.objects.get(commande=commande)
        with patch('facturation.views.imprimer_recu_caisse', return_value='Caisse'):
            resp = self.client.post(
                reverse('facturation:recu_imprimer', args=[facture.pk]),
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['ok'], True)
        apercu = self.client.get(reverse('facturation:recu', args=[facture.pk]))
        self.assertContains(apercu, 'ticket-recu')
        self.assertContains(apercu, 'Imprimer 80 mm')
        self.assertContains(apercu, 'Aperçu du reçu')

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
                    'validate_commande', 'adjust_plat_portions',
                ],
            )],
        )
        self.responsable = utilisateur(
            'responsable_resto',
            'RESPONSABLE',
            [(
                'restauration',
                [
                    'view_restauration', 'create_commande', 'modify_commande',
                    'validate_commande', 'cancel_commande',
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
        serveur, _ = Serveur.objects.get_or_create(nom='Serveur salle', prenom='')
        self.client.post(
            reverse('restauration:commande_nouveau'),
            {
                'source': Commande.Source.TABLETTE,
                'table': self.table.pk,
                'serveur': serveur.pk,
            },
        )
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
        self.assertEqual(resp.status_code, 403)
        commande.refresh_from_db()
        self.assertEqual(commande.statut, Commande.Statut.VALIDEE)

    def test_operateur_ne_peut_pas_annuler_commande_ouverte(self):
        commande = self._commande_ouverte(self.operateur)
        page = self.client.get(reverse('restauration:commande_detail', args=[commande.pk]))
        self.assertNotContains(page, 'Annuler la commande')
        resp = self.client.post(
            reverse('restauration:commande_annuler', args=[commande.pk]),
            {'motif': 'Erreur de saisie'},
        )
        self.assertEqual(resp.status_code, 403)
        commande.refresh_from_db()
        self.assertEqual(commande.statut, Commande.Statut.OUVERTE)

    def test_responsable_peut_annuler_commande_ouverte(self):
        commande = self._commande_ouverte(self.responsable)
        page = self.client.get(reverse('restauration:commande_detail', args=[commande.pk]))
        self.assertContains(page, 'Annuler la commande')
        resp = self.client.post(
            reverse('restauration:commande_annuler', args=[commande.pk]),
            {'motif': 'Client parti'},
        )
        self.assertEqual(resp.status_code, 302)
        commande.refresh_from_db()
        self.assertEqual(commande.statut, Commande.Statut.ANNULEE)

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


class SortieTerrasseAlimenteCommandeTests(TestCase):
    def setUp(self):
        from approvisionnement.models import (
            BonSortie,
            Categorie,
            LigneSortie,
            Produit,
            Service,
            Unite,
        )

        from .models import CompositionPlat

        self.BonSortie = BonSortie
        self.LigneSortie = LigneSortie
        self.CompositionPlat = CompositionPlat

        self.user = User.objects.create_user('magasin', password='pass1234')
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        self.salle, _ = Salle.objects.get_or_create(nom='Salle T')
        self.table, _ = Table.objects.get_or_create(
            salle=self.salle, numero='T1', defaults={'places': 4},
        )
        self.imprimante, _ = Imprimante.objects.get_or_create(
            nom='Terrasse',
            defaults={'service': ServicePoste.TERRASSE, 'nom_systeme': 'Terrasse'},
        )
        self.categorie_menu, _ = CategorieMenu.objects.get_or_create(nom='Boissons')
        self.plat = Plat.objects.create(
            categorie=self.categorie_menu,
            nom='Coca',
            prix=Decimal('2.00'),
            service=ServicePoste.TERRASSE,
            imprimante=self.imprimante,
            quantite=0,
        )
        categorie = Categorie.objects.create(nom='Boissons magasin')
        unite = Unite.objects.create(code='BTL', libelle='Bouteille')
        self.produit = Produit.objects.create(
            code='COCA',
            designation='Coca',
            categorie=categorie,
            unite=unite,
            stock=20,
            seuil_minimum=0,
        )
        self.CompositionPlat.objects.create(
            plat=self.plat,
            produit=self.produit,
            quantite=3,
        )
        self.destination, _ = Service.objects.get_or_create(nom='Terrasse')
        self.serveur_fiche = Serveur.objects.create(nom='Léa', prenom='')
        Etablissement.objects.get_or_create(pk=1, defaults={'nom_societe': 'IBBS BAZAR'})
        self.client.force_login(self.user)

    def _valider_sortie(self, quantite=6):
        bon = self.BonSortie.objects.create(
            numero='SOR-TEST-0001',
            motif='Réassort terrasse',
            destination=self.destination,
            utilisateur=self.user,
        )
        self.LigneSortie.objects.create(bon=bon, produit=self.produit, quantite=quantite)
        bon.valider()
        return bon

    def test_sortie_terrasse_augmente_quantite_plat(self):
        self._valider_sortie(6)
        self.plat.refresh_from_db()
        self.assertEqual(self.plat.quantite, 6)

    def test_sortie_terrasse_permet_ajout_dans_la_commande(self):
        self._valider_sortie(4)
        resp = self.client.post(
            reverse('restauration:commande_nouveau'),
            {
                'source': Commande.Source.TABLETTE,
                'table': self.table.pk,
                'serveur': self.serveur_fiche.pk,
            },
        )
        self.assertEqual(resp.status_code, 302)
        commande = Commande.objects.get(table=self.table, statut=Commande.Statut.OUVERTE)
        resp = self.client.post(
            reverse('restauration:commande_ajouter', args=[commande.pk]),
            {'plat': self.plat.pk, 'quantite': '2'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(commande.lignes.get().quantite, 2)

    def test_sortie_sans_composition_si_meme_nom(self):
        from restauration.models import alimenter_plats_depuis_sortie

        self.plat.compositions.all().delete()
        bon = self.BonSortie.objects.create(
            numero='SOR-TEST-0002',
            motif='Réassort terrasse',
            destination=self.destination,
            utilisateur=self.user,
        )
        self.LigneSortie.objects.create(bon=bon, produit=self.produit, quantite=5)
        alimenter_plats_depuis_sortie(bon)
        self.plat.refresh_from_db()
        self.assertEqual(self.plat.quantite, 5)


class TicketEscPosTests(SimpleTestCase):
    def test_texte_ticket_occupe_80mm(self):
        from .impression import LARGEUR_TICKET, texte_ticket

        commande = SimpleNamespace(
            numero=15,
            nom_emplacement='Table 3',
            nom_serveur='Jean',
            date_validation=timezone.now(),
            date_ouverture=timezone.now(),
        )
        groupe = {
            'libelle': 'Cuisine',
            'lignes': [SimpleNamespace(quantite=2, libelle='Brochette', note='')],
        }
        ticket = texte_ticket(commande, groupe)
        self.assertIn('-' * LARGEUR_TICKET, ticket)
        self.assertEqual(LARGEUR_TICKET, 42)
        self.assertIn('CUISINE', ticket)
        self.assertNotIn('PU', ticket)
        self.assertNotIn('AJOUT', ticket)

    def test_texte_ticket_ajout(self):
        from .impression import texte_ticket

        commande = SimpleNamespace(
            numero=15,
            nom_emplacement='Table 3',
            nom_serveur='Jean',
            date_validation=timezone.now(),
            date_ouverture=timezone.now(),
        )
        groupe = {
            'libelle': 'Cuisine',
            'ajout': True,
            'lignes': [SimpleNamespace(quantite=1, libelle='Brochette', note='')],
        }
        ticket = texte_ticket(commande, groupe)
        self.assertIn('AJOUT', ticket)
        self.assertIn('1 x Brochette', ticket)

    def test_octets_escpos_init_gras_et_coupe(self):
        from .impression import octets_escpos

        brut = octets_escpos('IBBS BAZAR\nCUISINE\n2 x Brochette')
        self.assertIn(b'\x1b@', brut)
        self.assertIn(b'\x1bE\x01', brut)
        self.assertIn(b'IBBS BAZAR', brut)
        self.assertIn(b'CUISINE', brut)
        self.assertIn(b'\x1dV', brut)

    @patch('restauration.impression.lister_imprimantes_windows', return_value=[])
    def test_imprimante_introuvable(self, _liste):
        from .impression import ImpressionError, envoyer_texte_imprimante

        with self.assertRaises(ImpressionError):
            envoyer_texte_imprimante('Inconnue', 'test')
