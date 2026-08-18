"""Tests du module Immobilisations (cycle de vie historisé, indépendant)."""

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.models import Domaine, Role, Succursale
from core.services import UserService

from .models import (
    Affectation,
    Casse,
    CategorieImmobilisation,
    Declassement,
    Deplacement,
    Immobilisation,
    Reparation,
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


class TestImmobilisationService(ImmobilisationBase):
    def test_creation_bien(self):
        self.assertTrue(self.bien.code.startswith('IMM-'))
        self.assertEqual(self.bien.etat_physique, Immobilisation.EtatPhysique.NEUF)
        self.assertEqual(self.bien.statut_administratif, Immobilisation.StatutAdministratif.STOCKE)

    def test_affectation_statut_en_service(self):
        affect = AffectationService.affecter(
            immobilisation=self.bien, succursale=self.succ_a,
            service='Comptabilité', emplacement='Bureau 12', par=self.gestionnaire)
        self.assertEqual(affect.par, self.gestionnaire)
        self.bien.refresh_from_db()
        self.assertEqual(self.bien.statut_administratif, 'EN_SERVICE')
        self.assertEqual(self.bien.service, 'Comptabilité')
        self.assertEqual(self.bien.emplacement, 'Bureau 12')

    def test_affectation_historisée(self):
        AffectationService.affecter(
            immobilisation=self.bien, succursale=self.succ_a,
            service='A', emplacement='E1', par=self.gestionnaire)
        AffectationService.affecter(
            immobilisation=self.bien, succursale=self.succ_a,
            service='B', emplacement='E2', par=self.gestionnaire)
        self.assertEqual(Affectation.objects.filter(immobilisation=self.bien).count(), 2)
        self.assertEqual(Affectation.objects.filter(immobilisation=self.bien, actif=True).count(), 1)
        active = self.bien.affectation_courante
        self.assertEqual(active.service, 'B')

    def test_deplacement_historisé(self):
        AffectationService.affecter(
            immobilisation=self.bien, succursale=self.succ_a,
            service='A', emplacement='E1', par=self.gestionnaire)
        DeplacementService.deplacer(
            immobilisation=self.bien, nouvelle_succursale=self.succ_a,
            nouveau_service='A', nouvel_emplacement='E2',
            motif='Changement', par=self.gestionnaire)
        self.bien.refresh_from_db()
        self.assertEqual(self.bien.emplacement, 'E2')
        dep = Deplacement.objects.get(immobilisation=self.bien)
        self.assertEqual(dep.ancien_emplacement, 'E1')
        self.assertEqual(dep.nouvel_emplacement, 'E2')
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

    def test_casse_declaration_et_evaluation(self):
        casse = CasseService.declarer(
            immobilisation=self.bien, motif='Chute', par=self.gestionnaire)
        self.bien.refresh_from_db()
        self.assertEqual(self.bien.etat_physique, 'CASSE')
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
