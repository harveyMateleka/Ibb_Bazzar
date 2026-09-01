from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Gestion centrale (utilisateurs, rôles, succursales)'

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save

        from .models import User
        from .permissions import restreindre_suppressions_admin

        restreindre_suppressions_admin()

        def creer_profil(sender, instance, created, **kwargs):
            if created:
                User.objects.get_or_create(compte=instance)

        post_save.connect(creer_profil, sender=get_user_model(), dispatch_uid='core_creer_profil')
