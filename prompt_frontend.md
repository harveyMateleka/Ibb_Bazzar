OBJECTIF

Améliorer l'ensemble des interfaces frontend des modules Boutique et Immobilisation en standardisant :

1. les tableaux avec DataTable ;
2. les champs Select avec Select2.

IMPORTANT :

Le design actuel doit être CONSERVÉ.

Il ne faut pas créer un nouveau thème.

Il faut intégrer DataTable et Select2 dans le thème et les composants déjà existants.

==================================================
PARTIE A — DATATABLE
==================================================

1. INTÉGRATION

Importer/intégrer la bibliothèque DataTable déjà utilisée ou prévue par le projet.

Avant d'installer une nouvelle bibliothèque :

→ vérifier si une implémentation DataTable existe déjà dans le projet.

Si elle existe :

→ la réutiliser et la généraliser.

Si elle n'existe pas :

→ intégrer proprement la bibliothèque appropriée conformément à la stack frontend existante.

==================================================
2. TABLEAUX CONCERNÉS
==================================================

Tous les tableaux importants des modules suivants doivent utiliser DataTable :

MODULE BOUTIQUE

- Articles
- Variantes
- Stocks
- Mouvements de stock
- Ventes
- Lignes de vente si elles sont affichées dans un tableau
- Inventaires
- Lignes d'inventaire
- Alertes de stock
- Fournisseurs
- Catégories
- Sous-catégories
- Unités
- autres tableaux du module Boutique

MODULE IMMOBILISATION

- Immobilisations
- Affectations
- Déplacements
- Casses
- États
- autres tableaux du module Immobilisation

MODULE UTILISATEURS

Si les écrans existent déjà :

- Utilisateurs
- Rôles
- Permissions
- Profils
- Audit
- Activations/désactivations
- autres listes importantes

==================================================
3. PAGINATION
==================================================

Tous les grands tableaux doivent disposer d'une pagination.

Exemple :

10 / 25 / 50 / 100 éléments par page

Utiliser les options déjà prévues par le projet si elles existent.

==================================================
4. RECHERCHE
==================================================

Les tableaux doivent permettre de rechercher facilement les données.

Exemples :

Recherche d'un article
Recherche d'une variante
Recherche d'une vente
Recherche d'une immobilisation
Recherche d'un utilisateur

==================================================
5. FILTRAGE
==================================================

Lorsque cela est pertinent, ajouter des filtres adaptés aux données.

Exemples Boutique :

- succursale ;
- domaine d'activité ;
- catégorie ;
- type article ;
- genre ;
- couleur ;
- taille ;
- statut ;
- état du stock.

Exemples Immobilisation :

- succursale ;
- domaine d'activité ;
- état ;
- statut ;
- affectation ;
- localisation.

Exemples Utilisateurs :

- rôle ;
- statut ;
- activation ;
- succursale ;
- domaine d'activité.

Ne pas ajouter des filtres artificiels lorsqu'ils n'ont pas de valeur métier.

==================================================
6. TRI
==================================================

Permettre le tri des colonnes lorsque cela est pertinent :

- date ;
- quantité ;
- prix ;
- statut ;
- nom ;
- référence ;
- etc.

==================================================
7. COMPATIBILITÉ AVEC LES DONNÉES
==================================================

Si les tableaux utilisent des données paginées côté backend :

→ adapter DataTable à cette architecture.

NE PAS charger inutilement des milliers de données côté navigateur.

Analyser d'abord si le projet utilise :

- pagination frontend ;
- pagination backend ;
- API paginée.

Conserver l'architecture existante lorsqu'elle est adaptée.

==================================================
PARTIE B — SELECT2
==================================================

1. INTÉGRATION

Importer/intégrer Select2 pour les champs Select nécessitant une recherche.

Avant toute installation :

→ vérifier si Select2 est déjà présent dans le projet.

S'il existe :

→ le réutiliser.

==================================================
2. TOUS LES SELECT PERTINENTS

Les Select importants doivent permettre une recherche.

Exemples Boutique :

- Article
- Variante
- TypeArticle
- Catégorie
- Sous-catégorie
- Couleur
- Taille
- Genre
- Fournisseur
- Unité
- Succursale
- Domaine d'activité

Exemples Immobilisation :

- Immobilisation
- Catégorie
- Fournisseur
- Utilisateur
- Responsable
- Affectation
- Succursale
- Domaine d'activité
- etc.

Exemples Utilisateurs :

- Utilisateur
- Rôle
- Permission
- Succursale
- Domaine d'activité
- etc.

==================================================
3. RECHERCHE DANS LES SELECT

Un utilisateur doit pouvoir taper pour rechercher une option.

Exemple :

TypeArticle :

[ Rechercher un type... ]

L'utilisateur tape :

« vêt »

→ Vêtement

Le Select ne doit donc plus nécessiter de parcourir manuellement une longue liste.

==================================================
4. SELECT AVEC BEAUCOUP DE DONNÉES

Pour les relations comportant potentiellement beaucoup d'enregistrements :

ne pas charger inutilement toute la base dans le navigateur.

Exemples :

- utilisateurs ;
- articles ;
- variantes ;
- fournisseurs.

Si l'API le permet, utiliser une recherche distante/autocomplete avec Select2.

==================================================
5. DESIGN
==================================================

Select2 doit être visuellement intégré au thème actuel.

IMPORTANT :

NE PAS créer une apparence différente du reste de l'application.

Respecter :

- couleurs ;
- bordures ;
- hauteur ;
- typographie ;
- arrondis ;
- icônes ;
- espacements.

==================================================
6. RÉUTILISABILITÉ
==================================================

Créer si nécessaire un composant/helper Select2 réutilisable afin d'éviter de répéter le même code dans chaque formulaire.

Même principe pour DataTable.

Objectif :

avoir une intégration cohérente dans tous les modules.

==================================================
7. MODULES CONCERNÉS
==================================================

Appliquer cette standardisation au minimum à :

BOUTIQUE
IMMOBILISATION
UTILISATEURS

et à tous les écrans existants où les tableaux ou Select nécessitent ces fonctionnalités.

==================================================
8. NE PAS CASSER L'EXISTANT
==================================================

Avant modification :

analyser les composants existants.

Ne pas remplacer brutalement les tableaux existants.

Ne pas supprimer les filtres existants.

Ne pas supprimer les paginations existantes.

Ne pas supprimer les Select existants.

Améliorer les composants en conservant leur logique métier.

==================================================
RÉSULTAT FINAL

Tous les tableaux importants doivent bénéficier d'une expérience homogène :

- pagination ;
- recherche ;
- filtrage ;
- tri ;
- affichage cohérent.

Tous les Select importants doivent permettre :

- recherche ;
- sélection ;
- affichage cohérent ;
- gestion efficace des longues listes.

Le tout doit rester strictement conforme au design actuel de l'application.