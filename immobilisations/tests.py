"""Tests du module Immobilisations (cycle de vie historisé, indépendant)."""

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.models import Domaine, Role, Succursale, User
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
            'move_asset', 'repair_asset', 'report_damage_asset', 'decommission_asset'])
        self.role_lecteur = self._role('LECTEUR', ['view_asset'])

        self.gestionnaire = self._user('gest', self.role_gestionnaire, self.succ_a)
        self.lecteur = self._user('lecteur', self.role_lecteur, self.succ_a)
        self.bien = ImmobilisationService.creer(
            designation='PC Dell', succursale=self.succ_a, domaine=self.domaine,
            categorie=self.cat, numero_serie='S1', valeur_acquisition=1000,
            par=self.gestionnaire)

    @staticmethod
    def _permission(codename):
        return Permission.objects.get(content_type__app_label='immobilisations', codename=codename)

    def _role(self, code, codenames):
        role = Role.objects.create(nom=code, code=code)
        role.permissions.set([self._permission(c) for c in codenames])
        return role

    def _user(self, username, role, succursale):
        user = UserService.creer(username=username, password='pass1234', roles=[role])
        UserService.affecter_succursale(
            user, succursale, self.domaine, principale=True, role=role)
        return user

    def _bien_declasse(self):
        """Bien déclassé (statut DECLASSE), hors du système pour les non-privilégiés."""
        bien = ImmobilisationService.creer(
            designation='PC déclassé', succursale=self.succ_a, domaine=self.domaine,
            categorie=self.cat, numero_serie='S-DEC', valeur_acquisition=500,
            par=self.gestionnaire)
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

    def test_affectation_statut_en_service(self):
        svc = Service.objects.create(nom='Comptabilité')
        emp = Emplacement.objects.create(nom='Bureau 12')
        affect = AffectationService.affecter(
            immobilisation=self.bien, succursale=self.succ_a,
            service=svc, emplacement=emp, par=self.gestionnaire)
        self.assertEqual(affect.par, self.gestionnaire)
        self.bien.refresh_from_db()
        self.assertEqual(self.bien.statut_administratif, 'EN_SERVICE')
        self.assertEqual(self.bien.service, svc)
        self.assertEqual(self.bien.emplacement, emp)

    def test_affectation_historisée(self):
        svc_a = Service.objects.create(nom='A')
        svc_b = Service.objects.create(nom='B')
        emp_1 = Emplacement.objects.create(nom='E1')
        emp_2 = Emplacement.objects.create(nom='E2')
        AffectationService.affecter(
            immobilisation=self.bien, succursale=self.succ_a,
            service=svc_a, emplacement=emp_1, par=self.gestionnaire)
        AffectationService.affecter(
            immobilisation=self.bien, succursale=self.succ_a,
            service=svc_b, emplacement=emp_2, par=self.gestionnaire)
        self.assertEqual(Affectation.objects.filter(immobilisation=self.bien).count(), 2)
        self.assertEqual(Affectation.objects.filter(immobilisation=self.bien, actif=True).count(), 1)
        active = self.bien.affectation_courante
        self.assertEqual(active.service, svc_b)

    def test_deplacement_historisé(self):
        svc = Service.objects.create(nom='A')
        emp_1 = Emplacement.objects.create(nom='E1')
        emp_2 = Emplacement.objects.create(nom='E2')
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
        self.assertEqual(dep.par, self.gestionnaire)

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
        # Le responsable du dommage est facultatif.
        self.assertEqual(casse.responsable_dommage, '')

    def test_casse_enregistre_le_responsable_du_dommage(self):
        casse = CasseService.declarer(
            immobilisation=self.bien, motif='Chute',
            responsable_dommage='Jean M.', par=self.gestionnaire)
        self.assertEqual(casse.responsable_dommage, 'Jean M.')
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


class TestPerimetreEtPermissions(ImmobilisationBase):
    def test_liste_biens_sans_permission_forbidden(self):
        user = UserService.creer(username='aucun', password='pass1234')
        self.client.force_login(user)
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
        admin = User.objects.create_superuser(username='super', password='x')
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
        admin = User.objects.create_superuser(username='super2', password='x')
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
