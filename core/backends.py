"""Permissions portées par les rôles dynamiques (core.Role)."""


class RolePermissionBackend:
    """Complète ModelBackend : un rôle accorde ses permissions Django."""

    def authenticate(self, request, **kwargs):
        return None

    def has_perm(self, user_obj, perm, obj=None):
        if not getattr(user_obj, 'is_authenticated', False):
            return False
        if not getattr(user_obj, 'is_active', False):
            return False
        profil = getattr(user_obj, 'profil', None)
        if profil is None:
            return False
        app_label, _, codename = perm.partition('.')
        if not app_label or not codename:
            return False
        return profil.roles.filter(
            permissions__content_type__app_label=app_label,
            permissions__codename=codename,
        ).exists()
