CORRECTION UX — SAISIE DES LIGNES D'INVENTAIRE

Modifier l'interface de création/validation d'un inventaire afin que toutes les informations de comptage soient saisies directement dans les lignes du tableau.

1. Ne plus afficher les champs en dessous du tableau

Actuellement, pour chaque produit, le système affiche séparément :

le stock système ;
un champ pour le stock physique ;
un champ pour le motif.

Avec 40 produits, cela produit énormément de champs et oblige l'utilisateur à faire beaucoup de scroll.

Supprimer cette présentation.

Il ne doit plus y avoir de blocs de saisie supplémentaires sous ou à côté du tableau pour chaque produit.

2. Tout intégrer directement dans le tableau

Le tableau d'inventaire doit devenir directement éditable.

Structure souhaitée :

Article	Stock système	Stock physique	Écart	Motif
T-shirt noir M	60	[ 57 ]	-3	[ Casse ]
Jean bleu L	30	[ 30 ]	0	[ — ]
Polo blanc M	25	[ 28 ]	+3	[ Écart constaté ]
Stock système

La colonne Stock système doit afficher automatiquement la quantité actuellement enregistrée dans StockBoutique.

Elle est affichée directement dans la ligne.

Exemple :

Stock système : 60

Cette valeur sert de référence et ne doit pas être modifiée manuellement par l'utilisateur.

Stock physique

La colonne Stock physique doit être un champ de saisie directement intégré dans la ligne :

[ 57 ]

Lors du chargement de l'inventaire, le champ peut être initialisé avec la valeur du stock système si c'est le comportement souhaité.

L'utilisateur peut ensuite modifier cette valeur avec la quantité réellement comptée.

3. Calcul automatique de l'écart

Dès que l'utilisateur modifie le stock physique, calculer automatiquement :

Écart = Stock physique - Stock système

Exemple :

Stock système : 60
Stock physique : 57
Écart : -3

Si :

Stock système : 25
Stock physique : 28

alors :

Écart : +3

Si :

Stock système : 30
Stock physique : 30

alors :

Écart : 0

Le calcul doit se faire ligne par ligne et en temps réel.

4. Motif directement dans la ligne

La colonne Motif doit également être un champ directement intégré au tableau.

Par exemple :

[ Sélectionner un motif ▼ ]

ou, si le système utilise un champ texte :

[ Motif........................ ]

L'utilisateur doit pouvoir renseigner le motif sur la même ligne que l'article concerné.

Exemple :

T-shirt noir M | 60 | [57] | -3 | [Casse ▼]

et non :

T-shirt noir M | 60 | [57]


Motif :
[Casse]
5. Une ligne = un article = toutes ses données

Chaque ligne doit être autonome.

Elle doit contenir au minimum :

Article
Stock système
Stock physique
Écart
Motif

Ainsi, même avec 100 articles, l'utilisateur peut parcourir le tableau et effectuer directement les corrections nécessaires.

6. Modification ligne par ligne

L'utilisateur doit pouvoir modifier directement :

le stock physique ;
le motif.

Sans ouvrir une nouvelle page.

Sans ouvrir une fenêtre supplémentaire.

Sans avoir plusieurs formulaires séparés.

Exemple :

┌───────────────┬──────────────┬────────────────┬───────┬────────────────────┐
│ Article       │ Stock système│ Stock physique │ Écart │ Motif              │
├───────────────┼──────────────┼────────────────┼───────┼────────────────────┤
│ T-shirt noir  │ 60           │ [ 57 ]         │ -3    │ [ Casse ▼ ]        │
│ Jean bleu     │ 30           │ [ 30 ]         │  0    │ [ Aucun ▼ ]        │
│ Polo blanc    │ 25           │ [ 28 ]         │ +3    │ [ Écart ▼ ]        │
└───────────────┴──────────────┴────────────────┴───────┴────────────────────┘
7. Pagination obligatoire

Tous les tableaux importants du module Boutique doivent être paginés.

Cela concerne notamment :

inventaires ;
lignes d'inventaire ;
stocks ;
mouvements de stock ;
ventes ;
articles ;
alertes.

Ne jamais charger inutilement 100, 500 ou 1 000 lignes dans une seule page.

Exemple :

Articles : 1–20 sur 100


[ < ] [1] [2] [3] [4] [5] [ > ]

La pagination doit idéalement être gérée côté backend pour éviter de charger inutilement toutes les données.

8. Filtrage des tableaux

Ajouter également des filtres pertinents.

Pour l'inventaire, prévoir au minimum la possibilité de filtrer/rechercher :

article ;
catégorie ;
stock avec écart ;
stock sans écart ;
motif ;
éventuellement emplacement/succursale selon le contexte.

Exemple :

Recherche article : [ T-shirt........ ]


Statut :
[ Tous ▼ ]


[ Rechercher ]

Cela devient particulièrement important lorsque l'inventaire contient beaucoup d'articles.

9. Attention à la valeur du stock système

Le stock système affiché dans une ligne d'inventaire doit correspondre au stock au moment où l'inventaire est constitué/initialisé, selon la logique métier retenue.

Il ne faut pas que l'utilisateur commence un inventaire avec :

Stock système = 60

puis que des ventes interviennent et que l'interface change silencieusement la référence à :

Stock système = 55

pendant que l'utilisateur compte physiquement.

Il faut donc figer correctement la quantité théorique de référence de la ligne d'inventaire lorsque l'inventaire est lancé, afin que la comparaison reste cohérente.

10. Validation finale

Lorsque toutes les lignes nécessaires sont renseignées :

[ Valider l'inventaire ]

Le backend doit :

vérifier les données ;
calculer/valider les écarts ;
enregistrer les lignes d'inventaire ;
créer les mouvements d'ajustement nécessaires pour les écarts ;
mettre à jour le stock courant ;
enregistrer l'utilisateur ayant effectué l'opération ;
clôturer l'inventaire ;
retourner un message clair de succès ou d'erreur.

Exemple :

Inventaire INV-2026-001 validé avec succès. 3 articles présentent un écart et ont été ajustés.

Le principe UX à retenir

Le tableau devient lui-même le formulaire.

Au lieu de :

Tableau
↓
Produit 1 → champ stock → champ motif
↓
Produit 2 → champ stock → champ motif
↓
Produit 3 → champ stock → champ motif
↓
...

faire :

TABLEAU ÉDITABLE


Article | Système | Physique | Écart | Motif
         │           │          │        │
         │           └── saisie └calcul  └── saisie

C'est beaucoup plus adapté à un inventaire de 40, 100 ou plusieurs centaines d'articles, tout en conservant exactement le même thème, les mêmes composants et le même design général que le module Approvisionnement.