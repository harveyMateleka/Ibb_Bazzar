from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .models import AuditLog, Domaine, Role, Succursale, User, UserSuccursale
from .permissions import require_permission, succursales_autorisees
from .services import PermissionService, RoleService, SuccursaleService, UserService


class BaseCoreTest(TestCase):
    def setUp(self):
        self.mot_de_passe = 'motdepasse123'
        self.role_admin = Role.objects.create(nom='Administrateur', code='ADMIN', est_systeme=True)
        self.role_responsable = Role.objects.create(nom='Responsable', code='RESPONSABLE')
        self.domaine_boutique = Domaine.objects.create(code='BOUTIQUE', libelle='Boutique')
        self.domaine_restaurant = Domaine.objects.create(code='RESTAURANT', libelle='Restaurant')
        self.succ_a = Succursale.objects.create(nom='Succursale A', code='A')
        self.succ_b = Succursale.objects.create(nom='Succursale B', code='B')
        self.responsable = UserService.creer(
            username='resp',
            password=self.mot_de_passe,
            roles=[self.role_responsable],
        )
        self.admin = UserService.creer(
            username='admin_test',
            password=self.mot_de_passe,
            roles=[self.role_admin],
        )
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save(update_fields=['is_staff', 'is_superuser'])


class TestUserService(BaseCoreTest):
    def test_creation_utilisateur(self):
        utilisateur = UserService.creer(
            username='jean',
            password='secret123',
            nom='Dupont',
            prenom='Jean',
            email='jean@ex.fr',
            roles=[self.role_responsable],
            cree_par=self.admin,
        )
        self.assertTrue(utilisateur.check_password('secret123'))
        self.assertEqual(utilisateur.cree_par, self.admin.compte)
        self.assertTrue(utilisateur.roles.filter(code='RESPONSABLE').exists())
        self.assertEqual(utilisateur.get_full_name(), 'Jean Dupont')

    def test_affectation_succursale_et_perimetre(self):
        UserService.affecter_succursale(
            self.responsable, self.succ_a, self.domaine_boutique, principale=True, par=self.admin
        )
        self.assertEqual(list(succursales_autorisees(self.responsable)), [self.succ_a])
        self.assertEqual(
            list(succursales_autorisees(self.responsable, domaine=self.domaine_boutique)),
            [self.succ_a],
        )
        # Domaine non affecté → aucune succursale.
        self.assertEqual(
            list(succursales_autorisees(self.responsable, domaine=self.domaine_restaurant)),
            [],
        )

    def test_succursale_autre_utilisateur_refusee(self):
        UserService.affecter_succursale(self.responsable, self.succ_a, self.domaine_boutique)
        autre = UserService.creer(username='autre', password='secret123')
        UserService.affecter_succursale(autre, self.succ_b, self.domaine_boutique)
        # Le responsable ne voit PAS la succursale B.
        self.assertEqual(list(succursales_autorisees(self.responsable)), [self.succ_a])
        self.assertNotIn(self.succ_b, succursales_autorisees(self.responsable))


class TestActivation(BaseCoreTest):
    def test_desactivation_conserve_historique(self):
        self.assertTrue(self.responsable.is_active)
        self.assertIsNone(self.responsable.date_desactivation)
        self.responsable.deactiver(par=self.admin)
        self.responsable.refresh_from_db()
        self.assertFalse(self.responsable.is_active)
        self.assertIsNotNone(self.responsable.date_desactivation)
        # L'utilisateur existe toujours (pas de suppression physique).
        self.assertTrue(User.objects.filter(pk=self.responsable.pk).exists())

    def test_reactivation(self):
        self.responsable.deactiver(par=self.admin)
        self.responsable.activer(par=self.admin)
        self.responsable.refresh_from_db()
        self.assertTrue(self.responsable.is_active)
        self.assertIsNone(self.responsable.date_desactivation)


class TestPermissions(BaseCoreTest):
    def test_permissions_du_role(self):
        perm = Permission.objects.get(
            content_type__app_label='core', codename='view_utilisateur'
        )
        self.role_admin.permissions.add(perm)
        self.assertTrue(self.admin.has_perm('core.view_utilisateur'))
        # L'utilisateur sans le rôle ne possède pas la permission.
        self.assertFalse(self.responsable.has_perm('core.view_utilisateur'))

    def test_acces_refuse_sans_permission(self):
        # Le responsable n'a aucune permission du catalogue.
        self.assertFalse(self.responsable.has_perm('core.view_audit'))

    def test_decorateur_permission(self):
        @require_permission('core.view_audit')
        def vue_protegee(request):
            return 'OK'

        factory = RequestFactory()
        # Utilisateur sans permission → PermissionDenied.
        requete = factory.get('/')
        requete.user = self.responsable.compte
        with self.assertRaises(PermissionDenied):
            vue_protegee(requete)

    def test_decorateur_permission_accordee(self):
        perm = Permission.objects.get(
            content_type__app_label='core', codename='view_audit'
        )
        self.role_responsable.permissions.add(perm)

        @require_permission('core.view_audit')
        def vue_protegee(request):
            return 'OK'

        factory = RequestFactory()
        requete = factory.get('/')
        requete.user = self.responsable.compte
        self.assertEqual(vue_protegee(requete), 'OK')

    def test_suppression_admin_reservee_au_superuser(self):
        from django.contrib.admin import ModelAdmin

        from .permissions import restreindre_suppressions_admin

        restreindre_suppressions_admin()
        admin = ModelAdmin(Role, None)
        factory = RequestFactory()

        refuse = factory.get('/')
        refuse.user = self.responsable.compte
        self.assertFalse(admin.has_delete_permission(refuse))

        autorise = factory.get('/')
        autorise.user = self.admin.compte
        self.assertTrue(admin.has_delete_permission(autorise))


class TestAudit(BaseCoreTest):
    def test_operation_auditee(self):
        before = AuditLog.objects.count()
        self.responsable.deactiver(par=self.admin)
        self.assertEqual(AuditLog.objects.count(), before + 1)
        trace = AuditLog.objects.filter(action='user.deactivate').latest('id')
        self.assertEqual(trace.utilisateur, self.admin.compte)
        self.assertEqual(trace.objet_id, self.responsable.pk)
        self.assertEqual(trace.nouvelle_valeur, {'actif': False})

    def test_permissions_natives_django(self):
        # Les permissions déclarées dans les Meta des modèles existent en base.
        self.assertTrue(
            Permission.objects.filter(content_type__app_label='core', codename='view_audit').exists()
        )
        self.assertTrue(
            Permission.objects.filter(content_type__app_label='core', codename='create_utilisateur').exists()
        )
        self.assertEqual(PermissionService.nb_permissions(), Permission.objects.count())


class TestAuditOperations(BaseCoreTest):
    def test_modification_auditee(self):
        UserService.modifier(self.responsable, par=self.admin, telephone='123456', fonction='Magasinier')
        trace = AuditLog.objects.filter(action='user.update', objet_id=self.responsable.pk).latest('id')
        self.assertEqual(trace.ancienne_valeur['telephone'], '')
        self.assertEqual(trace.nouvelle_valeur['telephone'], '123456')
        self.assertEqual(trace.nouvelle_valeur['fonction'], 'Magasinier')
        self.responsable.refresh_from_db()
        self.assertEqual(self.responsable.fonction, 'Magasinier')

    def test_changement_role_audite(self):
        UserService.assigner_role(self.responsable, self.role_admin, par=self.admin)
        trace = AuditLog.objects.filter(action='user.role_add', objet_id=self.responsable.pk).latest('id')
        self.assertIn('ADMIN', trace.nouvelle_valeur['roles'])
        self.assertIn('RESPONSABLE', trace.ancienne_valeur['roles'])
        self.assertTrue(self.responsable.roles.filter(code='ADMIN').exists())

    def test_retrait_role_audite(self):
        UserService.retirer_role(self.responsable, self.role_responsable, par=self.admin)
        trace = AuditLog.objects.filter(action='user.role_remove', objet_id=self.responsable.pk).latest('id')
        self.assertNotIn('RESPONSABLE', trace.nouvelle_valeur['roles'])
        self.assertFalse(self.responsable.roles.filter(code='RESPONSABLE').exists())


class TestURLsEtVues(BaseCoreTest):
    def test_connexion_admin(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'admin_test', 'password': self.mot_de_passe},
        )
        # Succès de connexion → redirection (302).
        self.assertEqual(response.status_code, 302)

    def test_connexion_peut_afficher_le_mot_de_passe(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js-password-toggle')
        self.assertContains(response, 'Afficher le mot de passe')
        self.assertContains(response, 'type="password"')

    def test_admin_django(self):
        self.client.login(username='admin_test', password=self.mot_de_passe)
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)


class TestModuleUtilisateurs(BaseCoreTest):
    def test_liste_sans_permission_forbidden(self):
        self.client.login(username='resp', password=self.mot_de_passe)
        response = self.client.get(reverse('core:utilisateur_liste'))
        self.assertContains(
            response,
            'Vous n’avez pas le droit pour ce module',
            status_code=403,
        )
        self.assertContains(
            response,
            'Prière de contacter votre administrateur',
            status_code=403,
        )
        self.assertNotContains(response, '403 Forbidden', status_code=403)

    def test_liste_avec_permission(self):
        self.client.login(username='admin_test', password=self.mot_de_passe)
        response = self.client.get(reverse('core:utilisateur_liste'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.responsable.username)

    def test_profil_visible(self):
        self.client.login(username='admin_test', password=self.mot_de_passe)
        response = self.client.get(
            reverse('core:utilisateur_detail', kwargs={'pk': self.responsable.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.responsable.username)
        self.assertContains(response, 'succursales / domaines')

    def test_desactivation_via_vue(self):
        self.client.login(username='admin_test', password=self.mot_de_passe)
        response = self.client.post(
            reverse('core:utilisateur_desactiver', kwargs={'pk': self.responsable.pk}),
            follow=True,
        )
        self.responsable.refresh_from_db()
        self.assertFalse(self.responsable.is_active)
        self.assertIsNotNone(self.responsable.date_desactivation)
        self.assertEqual(response.status_code, 200)

    def test_desactivation_sans_permission_forbidden(self):
        self.client.login(username='resp', password=self.mot_de_passe)
        response = self.client.post(
            reverse('core:utilisateur_desactiver', kwargs={'pk': self.admin.pk})
        )
        self.assertContains(
            response,
            'Prière de contacter votre administrateur',
            status_code=403,
        )

    def test_auto_desactivation_interdite(self):
        self.client.login(username='admin_test', password=self.mot_de_passe)
        response = self.client.post(
            reverse('core:utilisateur_desactiver', kwargs={'pk': self.admin.pk}),
            follow=True,
        )
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertContains(response, 'propre compte')

    def test_reactivation_via_vue(self):
        self.responsable.deactiver(par=self.admin)
        self.client.login(username='admin_test', password=self.mot_de_passe)
        response = self.client.post(
            reverse('core:utilisateur_activer', kwargs={'pk': self.responsable.pk}),
            follow=True,
        )
        self.responsable.refresh_from_db()
        self.assertTrue(self.responsable.is_active)
        self.assertIsNone(self.responsable.date_desactivation)
        self.assertEqual(response.status_code, 200)

    def test_formulaire_fonction_est_un_select_service(self):
        from approvisionnement.models import Service

        Service.objects.get_or_create(nom='Barbecus')
        self.client.login(username='admin_test', password=self.mot_de_passe)
        response = self.client.get(reverse('core:utilisateur_nouveau'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<select')
        self.assertContains(response, 'Barbecus')
        self.assertContains(response, 'Fonction / service')
        self.assertContains(response, 'js-password-toggle')
        self.assertContains(response, 'id_password')
        self.assertContains(response, 'id_password2')
        self.assertContains(response, 'Afficher le mot de passe')

    def test_nouvel_utilisateur_avec_affectation(self):
        from approvisionnement.models import Service

        self.client.login(username='admin_test', password=self.mot_de_passe)
        succ = Succursale.objects.create(nom='Succursale X', code='X')
        Service.objects.get_or_create(nom='Caissier')
        response = self.client.post(
            reverse('core:utilisateur_nouveau'),
            {
                'username': 'nouveau',
                'first_name': 'Jean',
                'last_name': 'Dupont',
                'email': 'jean@ex.fr',
                'telephone': '123',
                'fonction': 'Caissier',
                'roles': [self.role_responsable.pk],
                'succursale': succ.pk,
                'domaine': self.domaine_boutique.pk,
                'role_affectation': self.role_responsable.pk,
                'password': 'motdepasse123',
                'password2': 'motdepasse123',
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(compte__username='nouveau')
        self.assertTrue(user.check_password('motdepasse123'))
        self.assertEqual(list(user.succursales_autorisees()), [succ])
        # Le contexte est exploitable immédiatement (auto-rempli + verrouillé).
        contexte = user.contexte_actif()
        self.assertTrue(contexte['verrouille'])
        self.assertEqual(contexte['succursale'], succ)
        self.assertEqual(contexte['domaine'], self.domaine_boutique)

    def test_contexte_auto_plusieurs_affectations(self):
        # Plusieurs affectations sans principale → la première sert de contexte.
        succ_b = Succursale.objects.create(nom='Succursale B', code='B2')
        UserService.affecter_succursale(self.responsable, self.succ_a, self.domaine_boutique)
        UserService.affecter_succursale(self.responsable, succ_b, self.domaine_restaurant)
        contexte = self.responsable.contexte_actif()
        self.assertTrue(contexte['verrouille'])
        self.assertIn(contexte['succursale'], (self.succ_a, succ_b))


class TestProfilAnnulation(BaseCoreTest):
    def test_operateur_commande_sans_droit_annuler(self):
        from django.core.management import call_command

        call_command('init_core')
        operateur = Role.objects.get(code='OPERATEUR_COMMANDE')
        self.assertTrue(operateur.permissions.filter(codename='create_commande').exists())
        self.assertFalse(operateur.permissions.filter(codename='cancel_commande').exists())
        direction = Role.objects.get(code='DIRECTION')
        self.assertTrue(direction.permissions.filter(codename='cancel_commande').exists())
        self.assertTrue(direction.permissions.filter(codename='cancel_vente').exists())

    def test_configurer_annulation_sur_le_profil(self):
        perm_create = Permission.objects.get(
            content_type__app_label='restauration', codename='create_commande',
        )
        perm_cancel = Permission.objects.get(
            content_type__app_label='restauration', codename='cancel_commande',
        )
        role = Role.objects.create(nom='Opérateur test', code='OP_TEST')
        role.permissions.add(perm_create)
        self.client.login(username='admin_test', password=self.mot_de_passe)
        response = self.client.get(reverse('core:role_permissions', args=[role.pk]))
        self.assertContains(response, 'Peut annuler une commande')
        self.assertContains(response, 'indépendante')
        self.client.post(
            reverse('core:role_permissions', args=[role.pk]),
            {'permissions': [perm_create.pk, perm_cancel.pk]},
        )
        self.assertTrue(role.permissions.filter(codename='cancel_commande').exists())
        self.assertTrue(role.permissions.filter(codename='create_commande').exists())

    def test_configurer_profil_sans_droit_interdit(self):
        role = Role.objects.create(nom='X', code='XTEST')
        self.client.login(username='resp', password=self.mot_de_passe)
        response = self.client.get(reverse('core:role_permissions', args=[role.pk]))
        self.assertContains(
            response,
            'Vous n’avez pas le droit pour ce module',
            status_code=403,
        )
