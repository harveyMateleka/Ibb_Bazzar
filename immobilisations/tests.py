"""Tests du module Immobilisations (cycle de vie historisé, indépendant)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Domaine, Role, Succursale
from core.services import UserService

from .models import (
    Affectation,
    Casse,
    CategorieImmobilisation,
    Declassement,
    Deplacement,
    Emplacement,
    Immobilisation,
    Reparation,
    Service,
)
from .services import (
    AffectationService,
    CasseService,
    DeclassementService,
    DeplacementService,
    ImmobilisationService,
    ReparationService,
)


class ImmobilisationBase(TestCase):
    def setUp(self):
        self.domaine = Domaine.objects.create(code='IMMOBILISATIONS', libelle='Immobilisations')
        self.restaurant = Domaine.objects.create(code='RESTAURANT', libelle='Restaurant')
        self.succ_a = Succursale.objects.create(code='SA', nom='Succursale A')
        self.succ_b = Succursale.objects.create(code='SB', nom='Succursale B')
        self.cat = CategorieImmobilisation.objects.create(nom='Informatique', code='INFO')

        self.role_gestionnaire = self._role('GESTIONNAIRE', [
            'view_asset', 'create_asset', 'update_asset', 'assign_asset',
            'move_asset', 'repair_asset', 'report_damage_asset', 'decommission_asset',
            'validate_asset'])
        self.role_lecteur = self._role('LECTEUR', ['view_asset'])

        self.gestionnaire = self._user('gest', self.role_gestionnaire, self.succ_a)
        self.lecteur = self._user('lecteur', self.role_lecteur, self.succ_a)
        self.bien = ImmobilisationService.creer(
            designation='PC Dell', succursale=self.succ_a, domaine=self.domaine,
            categorie=self.cat, numero_serie='S1', valeur_acquisition=1000,
            par=self.gestionnaire)
        self._valider(self.bien)

    def _valider(self, bien):
        """Soumet puis valide un bien (les opérations exigent un bien validé)."""
        ImmobilisationService.soumettre(immobilisation=bien, par=self.gestionnaire)
        ImmobilisationService.valider(immobilisation=bien, par=self.gestionnaire)

    @staticmethod
    def _permission(codename):
        return Permission.objects.get(content_type__app_label='immobilisations', codename=codename)

    def _role(self, code, codenames):
        role = Role.objects.create(nom=code, code=code)
        role.permissions.set([self._permission(c) for c in codenames])
        return role

    def _user(self, username, role, succursale):
        profil = UserService.creer(username=username, password='pass1234', roles=[role])
        UserService.affecter_succursale(
            profil, succursale, self.domaine, principale=True, role=role)
        return profil.compte

    def _bien_declasse(self):
        """Bien déclassé (statut DECLASSE), hors du système pour les non-privilégiés."""
        bien = ImmobilisationService.creer(
            designation='PC déclassé', succursale=self.succ_a, domaine=self.domaine,
            categorie=self.cat, numero_serie='S-DEC', valeur_acquisition=500,
            par=self.gestionnaire)
        self._valider(bien)
        dec = DeclassementService.demander(
            immobilisation=bien, motif='Hors service', par=self.gestionnaire)
        DeclassementService.valider(declassement=dec, par=self.gestionnaire)
        bien.refresh_from_db()
        self.assertEqual(bien.statut_administratif, 'DECLASSE')
        return bien


class TestImmobilisationService(ImmobilisationBase):
    def test_creation_bien(self):
        self.assertTrue(self.bien.code.startswith('IMM-'))
        self.assertEqual(self.bien.etat_physique, Immobilisation.EtatPhysique.NEUF)
        self.assertEqual(self.bien.statut_administratif, Immobilisation.StatutAdministratif.STOCKE)
        self.assertEqual(self.bien.quantite_achetee, 1)

    def test_creation_avec_quantite_achetee(self):
        bien = ImmobilisationService.creer(
            designation='Chaises', succursale=self.succ_a, domaine=self.domaine,
            quantite_achetee=12, par=self.gestionnaire)
        self.assertEqual(bien.quantite_achetee, 12)

    def test_affectation_statut_en_service(self):
        svc = Service.objects.create(nom='Comptabilité')
        emp = Emplacement.objects.create(nom='Bureau 12', service=svc)
        affect = AffectationService.affecter(
            immobilisation=self.bien, succursale=self.succ_a,
            service=svc, emplacement=emp, par=self.gestionnaire)
        self.assertEqual(affect.par, self.gestionnaire)
        self.bien.refresh_from_db()
        self.assertEqual(self.bien.statut_administratif, 'EN_SERVICE')
        self.assertEqual(self.bien.service, svc)
        self.assertEqual(self.bien.emplacement, emp)

    def test_emplacement_doit_appartenir_au_service(self):
        compta = Service.objects.create(nom='Comptabilité')
        direction = Service.objects.create(nom='Direction')
        bureau = Emplacement.objects.create(nom='Bureau 12', service=compta)
        with self.assertRaises(ValidationError):
            AffectationService.affecter(
                immobilisation=self.bien, succursale=self.succ_a,
                service=direction, emplacement=bureau, par=self.gestionnaire)

    def test_affectation_partielle_par_quantite(self):
        lot = ImmobilisationService.creer(
            designation='Chaises', succursale=self.succ_a, domaine=self.domaine,
            quantite_achetee=5, par=self.gestionnaire)
        self._valider(lot)
        svc_a = Service.objects.create(nom='A')
        svc_b = Service.objects.create(nom='B')
        emp_1 = Emplacement.objects.create(nom='E1', service=svc_a)
        emp_2 = Emplacement.objects.create(nom='E2', service=svc_b)
        AffectationService.affecter(
            immobilisation=lot, succursale=self.succ_a,
            service=svc_a, emplacement=emp_1, quantite=2, par=self.gestionnaire)
        AffectationService.affecter(
            immobilisation=lot, succursale=self.succ_a,
            service=svc_b, emplacement=emp_2, quantite=3,
            commentaire='Solde du lot', par=self.gestionnaire)
        self.assertEqual(Affectation.objects.filter(immobilisation=lot, actif=True).count(), 2)
        lot.refresh_from_db()
        self.assertEqual(lot.quantite_affectee, 5)
        self.assertEqual(lot.quantite_restante, 0)

    def test_reste_a_affecter_deduit_casse_et_declassement(self):
        lot = ImmobilisationService.creer(
            designation='Chaises', succursale=self.succ_a, domaine=self.domaine,
            quantite_achetee=5, par=self.gestionnaire)
        self._valider(lot)
        svc = Service.objects.create(nom='A')
        emp = Emplacement.objects.create(nom='E1', service=svc)
        aff = AffectationService.affecter(
            immobilisation=lot, succursale=self.succ_a,
            service=svc, emplacement=emp, quantite=2, par=self.gestionnaire)
        self.assertEqual(lot.quantite_restante, 3)
        CasseService.declarer(
            immobilisation=lot, motif='Chute', par=self.gestionnaire,
            affectation=aff, quantite=1)
        DeclassementService.demander(
            immobilisation=lot, motif='Usure', par=self.gestionnaire,
            affectation=aff, quantite=1)
        lot.refresh_from_db()
        aff.refresh_from_db()
        self.assertEqual(lot.quantite_restante, 1)
        self.assertEqual(lot.quantite_affectee, 2)
        self.assertEqual(aff.quantite, 2)
        self.assertTrue(aff.actif)
        self.assertEqual(lot.quantite_cassee, 1)
        self.assertEqual(lot.quantite_declassee, 1)

    def test_affectation_refusee_si_quantite_depassee(self):
        svc = Service.objects.create(nom='A')
        emp = Emplacement.objects.create(nom='E1', service=svc)
        with self.assertRaises(ValidationError):
            AffectationService.affecter(
                immobilisation=self.bien, succursale=self.succ_a,
                service=svc, emplacement=emp, quantite=2, par=self.gestionnaire)

    def test_deplacement_historisé(self):
        svc = Service.objects.create(nom='A')
        emp_1 = Emplacement.objects.create(nom='E1', service=svc)
        emp_2 = Emplacement.objects.create(nom='E2', service=svc)
        AffectationService.affecter(
            immobilisation=self.bien, succursale=self.succ_a,
            service=svc, emplacement=emp_1, par=self.gestionnaire)
        DeplacementService.deplacer(
            immobilisation=self.bien, nouvelle_succursale=self.succ_a,
            nouveau_service=svc, nouvel_emplacement=emp_2,
            motif='Changement', par=self.gestionnaire)
        self.bien.refresh_from_db()
        self.assertEqual(self.bien.emplacement, emp_2)
        dep = Deplacement.objects.get(immobilisation=self.bien)
        self.assertEqual(dep.ancien_emplacement, emp_1)
        self.assertEqual(dep.nouvel_emplacement, emp_2)
        self.assertEqual(dep.quantite, 1)
        self.assertEqual(dep.par, self.gestionnaire)
        self.assertEqual(
            Affectation.objects.filter(
                immobilisation=self.bien, actif=True, emplacement=emp_2,
            ).get().quantite,
            1,
        )

    def test_deplacement_partiel_par_quantite(self):
        lot = ImmobilisationService.creer(
            designation='Tables', succursale=self.succ_a, domaine=self.domaine,
            quantite_achetee=5, par=self.gestionnaire)
        self._valider(lot)
        svc = Service.objects.create(nom='A')
        emp_1 = Emplacement.objects.create(nom='E1', service=svc)
        emp_2 = Emplacement.objects.create(nom='E2', service=svc)
        source = AffectationService.affecter(
            immobilisation=lot, succursale=self.succ_a,
            service=svc, emplacement=emp_1, quantite=5, par=self.gestionnaire)
        DeplacementService.deplacer(
            affectation=source, nouveau_service=svc, nouvel_emplacement=emp_2,
            quantite=2, par=self.gestionnaire)
        source.refresh_from_db()
        self.assertTrue(source.actif)
        self.assertEqual(source.quantite, 3)
        dest = Affectation.objects.get(
            immobilisation=lot, actif=True, emplacement=emp_2)
        self.assertEqual(dest.quantite, 2)

    def test_reparation_cycle(self):
        rep = ReparationService.declarer(
            immobilisation=self.bien, motif='Écran', cout=500, par=self.gestionnaire)
        self.bien.refresh_from_db()
        self.assertEqual(self.bien.etat_physique, 'A_REPARER')
        self.assertEqual(self.bien.statut_administratif, 'EN_REPARATION')
        ReparationService.terminer(reparation=rep, par=self.gestionnaire)
        self.bien.refresh_from_db()
        self.assertEqual(self.bien.etat_physique, 'BON')
        self.assertEqual(self.bien.statut_administratif, 'EN_SERVICE')

    def test_bien_en_reparation_non_affectable(self):
        """Règle métier : un bien en réparation ne peut pas être affecté."""
        ReparationService.declarer(immobilisation=self.bien, motif='Écran', par=self.gestionnaire)
        with self.assertRaises(ValidationError):
            AffectationService.affecter(
                immobilisation=self.bien, succursale=self.succ_a, par=self.gestionnaire)

    def test_bien_en_reparation_non_deplacable(self):
        """Règle métier : un bien en réparation ne peut pas être déplacé."""
        ReparationService.declarer(immobilisation=self.bien, motif='Écran', par=self.gestionnaire)
        with self.assertRaises(ValidationError):
            DeplacementService.deplacer(
                immobilisation=self.bien, nouvelle_succursale=self.succ_a, par=self.gestionnaire)

    def test_bien_en_reparation_peut_etre_declare_casse(self):
        """Un bien en réparation peut être déclaré cassé."""
        ReparationService.declarer(immobilisation=self.bien, motif='Écran', par=self.gestionnaire)
        casse = CasseService.declarer(immobilisation=self.bien, motif='Chute', par=self.gestionnaire)
        self.assertEqual(casse.par, self.gestionnaire)

    def test_bien_en_reparation_peut_etre_demande_declassement(self):
        """Un bien en réparation peut être demandé au déclassement."""
        ReparationService.declarer(immobilisation=self.bien, motif='Écran', par=self.gestionnaire)
        dec = DeclassementService.demander(
            immobilisation=self.bien, motif='Usure', par=self.gestionnaire)
        self.assertEqual(dec.statut, Declassement.Statut.DEMANDE)

    def test_casse_declaration_et_evaluation(self):
        casse = CasseService.declarer(
            immobilisation=self.bien, motif='Chute', par=self.gestionnaire)
        self.bien.refresh_from_db()
        self.assertEqual(self.bien.etat_physique, 'CASSE')
        self.assertEqual(casse.quantite, 1)
        # Le responsable du dommage est facultatif.
        self.assertEqual(casse.responsable_dommage, '')

    def test_casse_enregistre_le_responsable_du_dommage(self):
        casse = CasseService.declarer(
            immobilisation=self.bien, motif='Chute',
            responsable_dommage='Jean M.', par=self.gestionnaire)
        self.assertEqual(casse.responsable_dommage, 'Jean M.')

    def test_casse_enregistre_date_dommage(self):
        from django.utils import timezone
        jour = timezone.localdate()
        casse = CasseService.declarer(
            immobilisation=self.bien, motif='Chute',
            date_dommage=jour, par=self.gestionnaire)
        self.assertEqual(casse.date_dommage, jour)
        # Décision réparable → en réparation
        CasseService.evaluer(casse=casse, decision='REPARABLE', par=self.gestionnaire)
        self.bien.refresh_from_db()
        self.assertEqual(self.bien.statut_administratif, 'EN_REPARATION')
        # Décision déclassement → déclassé
        casse2 = CasseService.declarer(immobilisation=self.bien, motif='Irréparable', par=self.gestionnaire)
        CasseService.evaluer(casse=casse2, decision='DECLASSEMENT', par=self.gestionnaire)
        self.bien.refresh_from_db()
        self.assertEqual(self.bien.statut_administratif, 'DECLASSE')

    def test_declassement_demande_validation(self):
        dec = DeclassementService.demander(
            immobilisation=self.bien, motif='Usure', par=self.gestionnaire)
        self.assertEqual(dec.statut, Declassement.Statut.DEMANDE)
        self.bien.refresh_from_db()
        self.assertNotEqual(self.bien.statut_administratif, 'DECLASSE')  # pas avant validation
        DeclassementService.valider(declassement=dec, par=self.gestionnaire)
        dec.refresh_from_db()
        self.bien.refresh_from_db()
        self.assertEqual(dec.statut, Declassement.Statut.VALIDE)
        self.assertEqual(dec.valide_par, self.gestionnaire)
        self.assertEqual(self.bien.statut_administratif, 'DECLASSE')

    def test_acteur_obligatoire(self):
        with self.assertRaises(ValidationError):
            AffectationService.affecter(
                immobilisation=self.bien, succursale=self.succ_a, par=None)


class TestValidationBien(ImmobilisationBase):
    """Cycle de validation du bien : brouillon → en attente → validé/rejeté,
    champs entretien/durée facultatifs, validation par lots."""

    def _brouillon(self, designation='PC brouillon'):
        return ImmobilisationService.creer(
            designation=designation, succursale=self.succ_a, domaine=self.domaine,
            par=self.gestionnaire)

    def test_creation_brouillon_avec_entretien_et_duree(self):
        b = ImmobilisationService.creer(
            designation='PC spé', succursale=self.succ_a, domaine=self.domaine,
            categorie=self.cat, numero_serie='S2', valeur_acquisition=900,
            periode_entretien=6, duree_vie=5, par=self.gestionnaire)
        self.assertEqual(b.statut_validation, 'BROUILLON')
        self.assertEqual(b.periode_entretien, 6)
        self.assertEqual(b.duree_vie, 5)

    def test_creation_sans_entretien_ni_duree(self):
        b = self._brouillon()
        self.assertIsNone(b.periode_entretien)
        self.assertIsNone(b.duree_vie)

    def test_soumission_puis_validation(self):
        b = self._brouillon()
        ImmobilisationService.soumettre(immobilisation=b, par=self.gestionnaire)
        b.refresh_from_db()
        self.assertEqual(b.statut_validation, 'EN_ATTENTE')
        self.assertEqual(b.soumis_par, self.gestionnaire)
        self.assertIsNotNone(b.date_soumission)
        ImmobilisationService.valider(immobilisation=b, par=self.gestionnaire)
        b.refresh_from_db()
        self.assertEqual(b.statut_validation, 'VALIDE')
        self.assertEqual(b.valide_par, self.gestionnaire)
        self.assertIsNotNone(b.date_validation)

    def test_rejet_avec_motif(self):
        b = self._brouillon()
        ImmobilisationService.soumettre(immobilisation=b, par=self.gestionnaire)
        ImmobilisationService.rejeter(
            immobilisation=b, par=self.gestionnaire, motif='Document manquant')
        b.refresh_from_db()
        self.assertEqual(b.statut_validation, 'REJETE')
        self.assertEqual(b.motif_rejet, 'Document manquant')

    def test_rejet_sans_motif_refuse(self):
        b = self._brouillon()
        ImmobilisationService.soumettre(immobilisation=b, par=self.gestionnaire)
        with self.assertRaises(ValidationError):
            ImmobilisationService.rejeter(immobilisation=b, par=self.gestionnaire, motif='')

    def test_validation_d_un_brouillon_refusee(self):
        b = self._brouillon()
        with self.assertRaises(ValidationError):
            ImmobilisationService.valider(immobilisation=b, par=self.gestionnaire)

    def test_operation_bloquee_sur_bien_non_valide(self):
        b = self._brouillon()
        with self.assertRaises(ValidationError):
            AffectationService.affecter(
                immobilisation=b, succursale=self.succ_a, par=self.gestionnaire)

    def test_validation_par_lots(self):
        b1 = self._brouillon('A')
        b2 = self._brouillon('B')
        b3 = self._brouillon('C')
        ImmobilisationService.soumettre(immobilisation=b1, par=self.gestionnaire)
        ImmobilisationService.soumettre(immobilisation=b2, par=self.gestionnaire)
        nb_v, nb_i = ImmobilisationService.valider_plusieurs(
            biens=[b1, b2, b3], par=self.gestionnaire)
        self.assertEqual((nb_v, nb_i), (2, 1))
        b1.refresh_from_db(); b2.refresh_from_db(); b3.refresh_from_db()
        self.assertEqual(b1.statut_validation, 'VALIDE')
        self.assertEqual(b2.statut_validation, 'VALIDE')
        self.assertEqual(b3.statut_validation, 'BROUILLON')

    def test_validation_view_sans_permission_403(self):
        b = self._brouillon()
        ImmobilisationService.soumettre(immobilisation=b, par=self.gestionnaire)
        self.client.force_login(self.lecteur)  # view_asset seul
        resp = self.client.post(
            reverse('immobilisations:bien_valider', kwargs={'pk': b.pk}))
        self.assertEqual(resp.status_code, 403)

    def test_validation_ouvre_l_affectation(self):
        b = self._brouillon()
        ImmobilisationService.soumettre(immobilisation=b, par=self.gestionnaire)
        self.client.force_login(self.gestionnaire)
        resp = self.client.post(
            reverse('immobilisations:bien_valider', kwargs={'pk': b.pk}))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp.url,
            reverse('immobilisations:affectation_nouvelle', kwargs={'pk': b.pk}),
        )
        b.refresh_from_db()
        self.assertEqual(b.statut_validation, Immobilisation.StatutValidation.VALIDE)
        self.assertIsNone(b.affectation_courante)


class TestPerimetreEtPermissions(ImmobilisationBase):
    def test_liste_biens_sans_permission_forbidden(self):
        user = UserService.creer(username='aucun', password='pass1234')
        self.client.force_login(user.compte)
        resp = self.client.get(reverse('immobilisations:biens'))
        self.assertEqual(resp.status_code, 403)

    def test_utilisateur_autre_domaine_ne_voit_rien(self):
        # L'utilisateur n'a qu'une affectation RESTAURANT → périmètre vide.
        self.lecteur.affectations_succursales.update(domaine=self.restaurant)
        self.client.force_login(self.lecteur)
        resp = self.client.get(reverse('immobilisations:biens'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.bien.code)

    def test_lecteur_voit_mais_ne_peut_pas_affecter(self):
        self.client.force_login(self.lecteur)
        resp = self.client.get(reverse('immobilisations:biens'))
        self.assertContains(resp, self.bien.code)
        # Affecter exige assign_asset → 403 pour le lecteur.
        resp2 = self.client.get(
            reverse('immobilisations:affectation_nouvelle', kwargs={'pk': self.bien.pk}))
        self.assertEqual(resp2.status_code, 403)


class TestBiensDeclasses(ImmobilisationBase):
    """Un bien déclassé disparaît du système ; seuls superuser / détenteur de la
    permission view_declassified_asset le voient ; aucune opération applicative."""

    def setUp(self):
        super().setUp()
        self.bien_declasse = self._bien_declasse()

    def test_masque_sans_droit(self):
        self.client.force_login(self.lecteur)  # view_asset seul
        resp = self.client.get(reverse('immobilisations:biens'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.bien.code)          # le bien actif reste visible
        self.assertNotContains(resp, self.bien_declasse.code)  # le déclassé est masqué
        self.assertNotContains(resp, 'Inclure les biens déclassés')  # pas de case pour lui

    def test_visible_superuser(self):
        admin = get_user_model().objects.create_superuser(username='super', password='x')
        self.client.force_login(admin)
        resp = self.client.get(reverse('immobilisations:biens'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Inclure les biens déclassés')  # la case est proposée
        # Le bien déclassé apparaît dès que la case est cochée (?declasses=1).
        resp2 = self.client.get(reverse('immobilisations:biens') + '?declasses=1')
        self.assertContains(resp2, self.bien_declasse.code)

    def test_visible_avec_permission(self):
        perm = Permission.objects.get(
            content_type__app_label='immobilisations', codename='view_declassified_asset')
        self.lecteur.user_permissions.add(perm)
        self.client.force_login(self.lecteur)
        resp = self.client.get(reverse('immobilisations:biens') + '?declasses=1')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.bien_declasse.code)

    def test_detail_interdit_sans_droit(self):
        self.client.force_login(self.lecteur)
        resp = self.client.get(
            reverse('immobilisations:bien_detail', kwargs={'pk': self.bien_declasse.pk}))
        self.assertEqual(resp.status_code, 404)  # existence masquée

    def test_detail_ok_privelegie(self):
        admin = get_user_model().objects.create_superuser(username='super2', password='x')
        self.client.force_login(admin)
        resp = self.client.get(
            reverse('immobilisations:bien_detail', kwargs={'pk': self.bien_declasse.pk}))
        self.assertEqual(resp.status_code, 200)

    def test_actions_bloquees_sur_bien_declasse(self):
        # Aucune opération applicative ne peut réactiver un bien déclassé
        # (seule la modification du statut en admin le permet).
        with self.assertRaises(ValidationError):
            AffectationService.affecter(
                immobilisation=self.bien_declasse, succursale=self.succ_a,
                par=self.gestionnaire)
        with self.assertRaises(ValidationError):
            DeplacementService.deplacer(
                immobilisation=self.bien_declasse, nouvelle_succursale=self.succ_a,
                par=self.gestionnaire)


class TestProfilsLogistique(ImmobilisationBase):
    """Chargé : saisie / signalement. Responsable : validation uniquement."""

    def setUp(self):
        super().setUp()
        self.role_charge = self._role('CHARGE_LOGISTIQUE', [
            'view_asset', 'create_asset', 'update_asset', 'assign_asset',
            'move_asset', 'repair_asset', 'report_damage_asset', 'decommission_asset',
        ])
        self.role_resp = self._role('RESPONSABLE_LOGISTIQUE', [
            'view_asset', 'validate_asset', 'view_declassified_asset',
        ])
        self.charge = self._user('charge_log', self.role_charge, self.succ_a)
        self.responsable = self._user('resp_log', self.role_resp, self.succ_a)

    def test_charge_enregistre_et_signale_sans_valider(self):
        self.client.force_login(self.charge)
        resp = self.client.get(reverse('immobilisations:bien_nouveau'))
        self.assertEqual(resp.status_code, 200)
        form = resp.context['form']
        self.assertIn('quantite_achetee', form.fields)
        self.assertNotIn('succursale', form.fields)
        self.assertNotIn('service', form.fields)
        self.assertNotIn('emplacement', form.fields)

        resp = self.client.post(reverse('immobilisations:bien_nouveau'), {
            'designation': 'Lot de tables',
            'valeur_acquisition': '1500',
            'quantite_achetee': '8',
        })
        self.assertEqual(resp.status_code, 302)
        cree = Immobilisation.objects.get(designation='Lot de tables')
        self.assertEqual(cree.quantite_achetee, 8)
        self.assertEqual(cree.succursale, self.succ_a)
        self.assertIsNone(cree.service)
        self.assertIsNone(cree.emplacement)
        self.assertEqual(
            self.client.get(
                reverse('immobilisations:affectation_nouvelle', kwargs={'pk': self.bien.pk})
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse('immobilisations:casse_declarer', kwargs={'pk': self.bien.pk})
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.get(
                reverse('immobilisations:declassement_demander', kwargs={'pk': self.bien.pk})
            ).status_code,
            302,
        )

        brouillon = ImmobilisationService.creer(
            designation='Table', succursale=self.succ_a, domaine=self.domaine,
            par=self.charge)
        ImmobilisationService.soumettre(immobilisation=brouillon, par=self.charge)
        self.assertEqual(
            self.client.get(
                reverse('immobilisations:affectation_nouvelle', kwargs={'pk': brouillon.pk})
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                reverse('immobilisations:bien_valider', kwargs={'pk': brouillon.pk})
            ).status_code,
            403,
        )

        casse = CasseService.declarer(
            immobilisation=self.bien, motif='Chute', par=self.charge)
        self.assertEqual(
            self.client.post(
                reverse(
                    'immobilisations:casse_evaluer',
                    kwargs={'pk': self.bien.pk, 'casse_pk': casse.pk},
                ),
                {'decision': 'REPARABLE'},
            ).status_code,
            403,
        )

        demande = DeclassementService.demander(
            immobilisation=self.bien, motif='Usure', par=self.charge)
        self.assertEqual(
            self.client.post(
                reverse(
                    'immobilisations:declassement_valider',
                    kwargs={'pk': self.bien.pk, 'dec_pk': demande.pk},
                )
            ).status_code,
            403,
        )

    def test_responsable_valide_entree_casse_et_declassement(self):
        self.client.force_login(self.responsable)
        self.assertEqual(
            self.client.get(reverse('immobilisations:bien_nouveau')).status_code, 403)
        self.assertEqual(
            self.client.get(
                reverse('immobilisations:affectation_nouvelle', kwargs={'pk': self.bien.pk})
            ).status_code,
            403,
        )

        brouillon = ImmobilisationService.creer(
            designation='Chaise', succursale=self.succ_a, domaine=self.domaine,
            par=self.charge)
        ImmobilisationService.soumettre(immobilisation=brouillon, par=self.charge)
        resp = self.client.get(reverse('immobilisations:bien_detail', kwargs={'pk': brouillon.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Valider le bien')
        self.assertNotContains(resp, 'id_service')
        resp = self.client.post(
            reverse('immobilisations:bien_valider', kwargs={'pk': brouillon.pk}))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp.url,
            reverse('immobilisations:bien_detail', kwargs={'pk': brouillon.pk}),
        )
        brouillon.refresh_from_db()
        self.assertEqual(brouillon.statut_validation, Immobilisation.StatutValidation.VALIDE)
        self.assertEqual(brouillon.statut_administratif, Immobilisation.StatutAdministratif.STOCKE)
        self.assertIsNone(brouillon.affectation_courante)

        casse = CasseService.declarer(
            immobilisation=self.bien, motif='Choc', par=self.charge)
        resp = self.client.post(
            reverse(
                'immobilisations:casse_evaluer',
                kwargs={'pk': self.bien.pk, 'casse_pk': casse.pk},
            ),
            {'decision': 'REPARABLE'},
        )
        self.assertEqual(resp.status_code, 302)
        casse.refresh_from_db()
        self.assertEqual(casse.decision, Casse.Decision.REPARABLE)

        autre = ImmobilisationService.creer(
            designation='Armoire', succursale=self.succ_a, domaine=self.domaine,
            par=self.charge)
        self._valider(autre)
        demande = DeclassementService.demander(
            immobilisation=autre, motif='Hors service', par=self.charge)
        resp = self.client.post(
            reverse(
                'immobilisations:declassement_valider',
                kwargs={'pk': autre.pk, 'dec_pk': demande.pk},
            )
        )
        self.assertEqual(resp.status_code, 302)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, Declassement.Statut.VALIDE)

    def test_charge_affecte_apres_validation(self):
        self.client.force_login(self.charge)
        svc = Service.objects.create(nom='Comptabilité')
        emp = Emplacement.objects.create(nom='Bureau 1', service=svc)
        resp = self.client.get(
            reverse('immobilisations:affectation_nouvelle', kwargs={'pk': self.bien.pk}))
        self.assertEqual(resp.status_code, 200)
        form = resp.context['form']
        self.assertEqual(list(form.fields), [
            'quantite', 'service', 'emplacement', 'date_affectation', 'commentaire',
        ])
        self.assertContains(resp, 'data-filtre-emplacements')
        self.assertContains(resp, f'data-service="{emp.service_id}"')
        resp = self.client.post(
            reverse('immobilisations:affectation_nouvelle', kwargs={'pk': self.bien.pk}),
            {
                'quantite': 1,
                'service': svc.pk,
                'emplacement': emp.pk,
                'date_affectation': timezone.localdate().isoformat(),
                'commentaire': 'Mise en service',
            },
        )
        self.assertEqual(resp.status_code, 302)
        aff = Affectation.objects.get(immobilisation=self.bien, actif=True)
        self.assertEqual(aff.quantite, 1)
        self.assertEqual(aff.service, svc)
        self.assertEqual(aff.emplacement, emp)
        self.assertEqual(aff.commentaire, 'Mise en service')

    def test_charge_deplace_depuis_la_grille(self):
        self.client.force_login(self.charge)
        svc = Service.objects.create(nom='Comptabilité')
        emp_1 = Emplacement.objects.create(nom='Bureau 1', service=svc)
        emp_2 = Emplacement.objects.create(nom='Bureau 2', service=svc)
        aff = AffectationService.affecter(
            immobilisation=self.bien, succursale=self.succ_a,
            service=svc, emplacement=emp_1, par=self.charge)
        resp = self.client.get(reverse('immobilisations:deplacements'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.bien.code)
        self.assertContains(resp, 'Bureau 1')
        resp = self.client.get(
            reverse(
                'immobilisations:deplacement_depuis_affectation',
                kwargs={'aff_pk': aff.pk},
            )
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context['form'].fields), [
            'quantite', 'nouveau_service', 'nouvel_emplacement',
        ])
        self.assertContains(resp, f'data-service="{emp_2.service_id}"')
        resp = self.client.post(
            reverse(
                'immobilisations:deplacement_depuis_affectation',
                kwargs={'aff_pk': aff.pk},
            ),
            {
                'quantite': 1,
                'nouveau_service': svc.pk,
                'nouvel_emplacement': emp_2.pk,
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.bien.refresh_from_db()
        self.assertEqual(self.bien.emplacement, emp_2)

    def test_charge_declare_casse_avec_service_et_quantite(self):
        self.client.force_login(self.charge)
        svc = Service.objects.create(nom='Comptabilité')
        emp = Emplacement.objects.create(nom='Bureau 1', service=svc)
        aff = AffectationService.affecter(
            immobilisation=self.bien, succursale=self.succ_a,
            service=svc, emplacement=emp, par=self.charge)
        resp = self.client.get(
            reverse('immobilisations:casse_declarer', kwargs={'pk': self.bien.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Choisir')
        self.assertContains(resp, 'Service d’affectation')
        self.assertContains(resp, 'Emplacement')
        self.assertContains(resp, 'Quantité cassée')
        self.assertContains(resp, 'Cause')
        self.assertContains(resp, 'Commentaire')
        resp = self.client.post(
            reverse('immobilisations:casse_declarer', kwargs={'pk': self.bien.pk}),
            {
                'affectation_id': aff.pk,
                'quantite': 1,
                'motif': 'Chute',
                'description': 'Écran fêlé',
            },
        )
        self.assertEqual(resp.status_code, 302)
        casse = Casse.objects.get(immobilisation=self.bien)
        self.assertEqual(casse.service, svc)
        self.assertEqual(casse.emplacement, emp)
        self.assertEqual(casse.quantite, 1)
        self.assertEqual(casse.motif, 'Chute')
        self.assertEqual(casse.description, 'Écran fêlé')
        aff.refresh_from_db()
        self.assertTrue(aff.actif)
        self.assertEqual(aff.quantite, 1)
        self.bien.refresh_from_db()
        self.assertEqual(self.bien.quantite_restante, 0)
        self.assertEqual(self.bien.quantite_cassee, 1)
        self.assertEqual(self.bien.quantite_affectee, 1)

    def test_charge_demande_declassement_avec_affectation(self):
        self.client.force_login(self.charge)
        svc = Service.objects.create(nom='Comptabilité')
        emp = Emplacement.objects.create(nom='Bureau 1', service=svc)
        aff = AffectationService.affecter(
            immobilisation=self.bien, succursale=self.succ_a,
            service=svc, emplacement=emp, par=self.charge)
        resp = self.client.get(
            reverse('immobilisations:declassement_demander', kwargs={'pk': self.bien.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Choisir')
        self.assertContains(resp, 'Service d’affectation')
        self.assertContains(resp, 'Emplacement')
        self.assertContains(resp, 'Quantité à déclasser')
        resp = self.client.post(
            reverse('immobilisations:declassement_demander', kwargs={'pk': self.bien.pk}),
            {
                'affectation_id': aff.pk,
                'quantite': 1,
                'motif': 'Hors d’usage',
            },
        )
        self.assertEqual(resp.status_code, 302)
        dec = Declassement.objects.get(immobilisation=self.bien)
        self.assertEqual(dec.service, svc)
        self.assertEqual(dec.emplacement, emp)
        self.assertEqual(dec.quantite, 1)
        self.assertEqual(dec.motif, 'Hors d’usage')
        aff.refresh_from_db()
        self.assertTrue(aff.actif)
        self.assertEqual(aff.quantite, 1)
        self.bien.refresh_from_db()
        self.assertEqual(self.bien.quantite_restante, 0)
        self.assertEqual(self.bien.quantite_declassee, 1)
        self.assertEqual(self.bien.quantite_affectee, 1)
