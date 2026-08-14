from django.contrib import admin

from .models import Acteur, Article, Categorie, Fonctionnalite, Fournisseur, Module, Unite


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    search_fields = ['nom']


@admin.register(Acteur)
class ActeurAdmin(admin.ModelAdmin):
    search_fields = ['nom']


@admin.register(Fonctionnalite)
class FonctionnaliteAdmin(admin.ModelAdmin):
    list_display = ['code', 'libelle', 'module', 'priorite']
    list_filter = ['module', 'acteurs']
    search_fields = ['code', 'libelle']
    filter_horizontal = ['acteurs']


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    search_fields = ['nom']


@admin.register(Unite)
class UniteAdmin(admin.ModelAdmin):
    list_display = ['code', 'libelle']
    search_fields = ['code', 'libelle']


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ['nom', 'telephone', 'email']
    search_fields = ['nom']


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['code', 'designation', 'categorie', 'unite', 'seuil_minimum', 'stock', 'en_alerte']
    list_filter = ['categorie', 'unite']
    search_fields = ['code', 'designation']
    readonly_fields = ['stock']
    fieldsets = (
        (None, {
            'fields': ('code', 'designation', 'categorie', 'unite', 'seuil_minimum'),
        }),
        ('Stock (mis à jour par les mouvements)', {
            'fields': ('stock',),
        }),
    )

    @admin.display(boolean=True, description='alerte')
    def en_alerte(self, obj):
        return obj.en_alerte
