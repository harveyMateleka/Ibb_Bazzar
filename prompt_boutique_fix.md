RESTRUCTURATION DE L'ARCHITECTURE ARTICLE → VARIANTE → STOCK
CONTEXTE

Nous devons faire évoluer le module « Gestion des Boutiques » du backend existant.

IMPORTANT :
- Le frontend existe déjà.
- Le design et le thème visuel existants doivent être conservés.
- Le module Approvisionnement existe déjà et possède sa propre logique.
- Ne pas casser les fonctionnalités existantes.
- Ne pas créer de doublons de modèles, tables, services ou fonctionnalités déjà présents.
- Avant toute modification, analyser les modèles, relations, serializers, views/viewsets, services, permissions, URLs et migrations existants afin de réutiliser ce qui existe lorsque cela est pertinent.
- Cette évolution concerne principalement l'architecture des données du module Boutique.

OBJECTIF PRINCIPAL

Modifier l'architecture actuelle afin de séparer clairement :

1. L'article générique / parent.
2. La variante précise de cet article.
3. Le stock de cette variante.
4. Les mouvements de stock de cette variante.

La règle fondamentale devient :

ARTICLE
    ↓
VARIANTE ARTICLE
    ↓
STOCK
    ↓
MOUVEMENTS DE STOCK

Le stock ne doit PLUS être calculé directement au niveau de l'article.

Le stock doit être géré et calculé au niveau de la VARIANTE ARTICLE.

==================================================
ÉTAPE 1 — ANALYSER L'ARCHITECTURE EXISTANTE
==================================================

Avant de coder :

- rechercher le modèle Article existant ;
- rechercher le modèle Stock existant ;
- rechercher les modèles liés aux mouvements de stock ;
- rechercher les modèles liés aux catégories, sous-catégories, fournisseurs, unités, emplacements, etc. ;
- rechercher les relations avec les succursales ;
- rechercher les relations avec les domaines d'activité ;
- rechercher les références utilisées par les ventes ;
- rechercher les références utilisées par les inventaires ;
- rechercher les alertes de stock ;
- rechercher les relations avec le module Approvisionnement.

Identifier précisément les éléments qui doivent être conservés, modifiés ou déplacés.

NE PAS supprimer une table existante sans vérifier toutes ses dépendances.

NE PAS recréer une fonctionnalité qui existe déjà.

==================================================
ÉTAPE 2 — NOUVELLE RESPONSABILITÉ DU MODÈLE ARTICLE
==================================================

Le modèle Article doit devenir le niveau « parent » ou « générique ».

Lors de la création d'un article, conserver uniquement les informations d'identification générales :

- code_article ;
- designation ;
- succursale ;
- domaine_activite.

Exemple :

Article
-------------------------
id
code_article = CHEM-001
designation = Chemise
succursale = Succursale A
domaine_activite = Boutique

À ce niveau, NE PAS stocker les caractéristiques propres à une variante.

Ne pas mettre directement dans Article :

- couleur ;
- taille ;
- genre ;
- marque ;
- modèle ;
- catégorie ;
- sous-catégorie ;
- rayon ;
- étage ;
- emplacement ;
- unité ;
- état ;
- prix ;
- seuil d'alerte ;
- quantité de stock.

Ces informations ne doivent plus définir l'identité générale de l'article parent.

==================================================
ÉTAPE 3 — CRÉER / UTILISER LE MODÈLE VARIANTE ARTICLE
==================================================

Créer un modèle VarianteArticle s'il n'existe pas déjà une structure équivalente.

IMPORTANT :
Avant de créer un nouveau modèle, rechercher si une table existante peut remplir exactement cette fonction.

La VarianteArticle appartient à un Article parent.

Relation :

Article 1 ─────── N VarianteArticle

Exemple :

Article :
CHEM-001 — Chemise

Variantes :

CHEM-001-V1
Couleur = Noir
Taille = M
Genre = Homme

CHEM-001-V2
Couleur = Blanc
Taille = L
Genre = Homme

CHEM-001-V3
Couleur = Bleu
Taille = M
Genre = Homme

La variante représente donc une version concrète et identifiable du produit.

==================================================
ÉTAPE 4 — ATTRIBUTS DE LA VARIANTE ARTICLE
==================================================

Les informations détaillées doivent être rattachées à VarianteArticle et non plus directement à Article.

Selon les modèles déjà présents dans le projet, réutiliser les relations existantes.

La variante peut notamment porter :

- article parent ;
- origine ;
- catégorie ;
- sous-catégorie ;
- unité ;
- modèle ;
- marque ;
- couleur ;
- taille ;
- genre ;
- rayon ;
- étage ;
- emplacement ;
- état ;
- statut ;
- prix minimum ;
- prix unitaire ;
- seuil d'alerte ;
- autres caractéristiques actuellement prévues par le cahier des charges.

IMPORTANT :

Ne pas transformer automatiquement chaque champ en nouvelle table.

Réutiliser les tables de référence existantes lorsqu'elles existent déjà.

Conserver la logique actuelle de l'entreprise.

==================================================
ÉTAPE 5 — MODÈLE STOCK
==================================================

Le modèle Stock doit maintenant être rattaché à VarianteArticle.

Relation principale :

VarianteArticle 1 ─────── N Stock

ou, si la logique métier impose une seule position de stock par variante et par contexte :

VarianteArticle 1 ─────── N Stock
avec unicité selon le contexte concerné.

Le Stock ne doit PLUS être directement rattaché uniquement à Article.

Exemple :

Article :
Chemise

Variante :
Noir / M / Homme

Stock :
40 pièces

Autre variante :

Article :
Chemise

Variante :
Blanc / L / Homme

Stock :
25 pièces

Le système doit donc pouvoir distinguer :

Chemise Noir/M = 40
Chemise Blanc/L = 25

==================================================
ÉTAPE 6 — QUANTITÉ DE STOCK
==================================================

La quantité actuelle doit appartenir au niveau de la variante/contexte de stock.

Le système doit être capable de connaître :

- quantité actuelle ;
- stock avant opération ;
- quantité entrée ;
- quantité sortie ;
- stock après opération.

Le stock d'un article parent peut être obtenu comme une agrégation des stocks de ses variantes si l'interface a besoin d'afficher un total.

Exemple :

Chemise
    Noir/M = 40
    Noir/L = 20
    Blanc/M = 15

Stock total de l'article Chemise :

40 + 20 + 15 = 75

IMPORTANT :

Ce total est une agrégation.

Il ne doit pas devenir une deuxième source de vérité indépendante.

La source opérationnelle du stock reste la variante/contexte de stock.

==================================================
ÉTAPE 7 — MOUVEMENT DE STOCK
==================================================

Les mouvements doivent être rattachés à la variante/au stock concerné.

Exemple :

Variante :
Chemise Noir/M

Mouvement 1 :
Entrée +40

Mouvement 2 :
Entrée +20

Mouvement 3 :
Sortie -5

Stock actuel :
55

Le mouvement doit conserver au minimum la traçabilité nécessaire :

- variante concernée ;
- stock concerné ;
- type de mouvement ;
- quantité ;
- stock avant ;
- stock après ;
- date ;
- utilisateur ;
- origine/référence de l'opération lorsque nécessaire.

NE PAS perdre l'historique des mouvements existants.

==================================================
ÉTAPE 8 — ENTRÉE EN STOCK
==================================================

L'interface « Entrée en stock » doit maintenant fonctionner autour de la VarianteArticle.

Processus :

1. sélectionner l'Article parent ;
2. créer ou sélectionner sa VarianteArticle ;
3. renseigner les caractéristiques de la variante ;
4. renseigner la quantité ;
5. renseigner les informations de stock nécessaires ;
6. enregistrer le stock ;
7. créer le mouvement d'entrée correspondant.

Exemple :

Article :
CHEM-001 — Chemise

Variante :
Noir / M / Homme

Entrée :

Quantité = 40
Prix minimum = 15 000
Prix unitaire = 20 000
Seuil d'alerte = 5

Le système crée/réutilise la variante correspondante puis enregistre le stock et son mouvement.

==================================================
ÉTAPE 9 — ÉVITER LES DOUBLONS DE VARIANTES
==================================================

Le système doit empêcher la création accidentelle de deux variantes identiques pour un même article.

Avant de créer une variante, vérifier si une variante équivalente existe déjà selon les attributs qui définissent son identité métier.

Exemple :

Article :
Chemise

Variante existante :
Noir / M / Homme

Si l'utilisateur tente de recréer :

Chemise
Noir / M / Homme

le système doit détecter la variante existante et proposer de l'utiliser plutôt que de créer un doublon.

IMPORTANT :

La définition exacte de l'unicité doit être déterminée à partir de la logique existante du projet et du cahier des charges.

==================================================
ÉTAPE 10 — ALERTES DE STOCK
==================================================

Les alertes doivent désormais être évaluées au niveau de la variante.

Exemple :

Variante :
Chemise Noir/M

Stock actuel = 4
Seuil d'alerte = 5

Alors :

alerte_stock = ACTIVE

Si :

Stock actuel = 8
Seuil = 5

Alors :

alerte_stock = INACTIVE

Ne plus calculer l'alerte uniquement au niveau de l'article parent.

==================================================
ÉTAPE 11 — VENTES
==================================================

Adapter la logique des ventes afin qu'une vente référence une VarianteArticle ou le Stock correspondant à la variante.

Une vente de :

Chemise Noir/M

doit diminuer le stock de :

Chemise Noir/M

et jamais le stock global de l'article Chemise de manière ambiguë.

Exemple :

Avant :
Chemise Noir/M = 40

Vente :
-3

Après :
Chemise Noir/M = 37

Créer le mouvement de sortie correspondant.

==================================================
ÉTAPE 12 — INVENTAIRES
==================================================

Adapter également les inventaires.

L'inventaire doit comparer le stock système et le stock physique au niveau de la variante.

Exemple :

Variante :
Chemise Noir/M

Stock système = 40
Stock physique = 37
Écart = -3

L'ajustement doit concerner cette variante précise.

Ne jamais faire un ajustement uniquement sur Article lorsque plusieurs variantes existent.

==================================================
ÉTAPE 13 — COMPATIBILITÉ AVEC L'APPROVISIONNEMENT
==================================================

Le module Approvisionnement reste un module séparé.

NE PAS fusionner Approvisionnement et Boutique.

Identifier les relations nécessaires entre :

Approvisionnement
    ↓
Article / VarianteArticle
    ↓
Stock

Conserver la logique d'approvisionnement existante.

Si une table d'approvisionnement existante peut être liée à la VarianteArticle, adapter la relation proprement sans recréer une deuxième logique d'approvisionnement.

==================================================
ÉTAPE 14 — MIGRATION DES DONNÉES EXISTANTES
==================================================

Avant toute migration destructive, analyser les données existantes.

Si les anciennes données contiennent directement :

Article + couleur + taille + quantité

elles devront être restructurées vers :

Article
   ↓
VarianteArticle
   ↓
Stock

Ne pas supprimer les données existantes.

Prévoir une migration propre si des données sont déjà présentes.

==================================================
ÉTAPE 15 — API / BACKEND
==================================================

Adapter :

- Models ;
- migrations ;
- serializers ;
- views/viewsets ;
- services ;
- filtres ;
- permissions existantes ;
- endpoints ;
- validations ;
- requêtes de stock ;
- requêtes de vente ;
- requêtes d'inventaire ;
- alertes.

Le frontend existe déjà.

Ne pas refaire le frontend à cette étape.

Préparer cependant les réponses API de manière cohérente afin que le frontend existant puisse être adapté ultérieurement si nécessaire.

==================================================
ÉTAPE 16 — RÈGLE ABSOLUE
==================================================

La nouvelle architecture de référence doit être :

Article
    │
    ├── VarianteArticle
    │       │
    │       └── Stock
    │               │
    │               └── MouvementStock
    │
    ├── VarianteArticle
    │       │
    │       └── Stock
    │
    └── VarianteArticle

Le stock ne doit plus être considéré comme une propriété directe de l'Article.

Le stock est toujours contextualisé par une VarianteArticle.

Le stock global d'un Article n'est qu'une agrégation des stocks de ses variantes.

==================================================
CONTRAINTE FINALE
==================================================

Avant de modifier le code :

1. analyser l'architecture actuelle ;
2. identifier les modèles existants ;
3. identifier les relations existantes ;
4. identifier les fonctionnalités déjà implémentées ;
5. proposer les modifications nécessaires ;
6. éviter les doublons ;
7. préserver les données ;
8. effectuer les migrations nécessaires ;
9. tester les relations Article → VarianteArticle → Stock → MouvementStock ;
10. vérifier que les ventes, inventaires et alertes utilisent désormais les variantes.

NE PAS commencer par recréer tout le module.

Modifier uniquement ce qui est nécessaire pour atteindre cette nouvelle architecture.

scénario: 
Par exemple :

Écran 1 :
Créer Article
    ↓
CHEM-001 — Chemise

puis :

Écran 2 :
Créer la variante / mettre en stock
    ↓
Noir
M
Homme
Marque X
Modèle Y
Rayon A
...
40 pièces

L'interface peut parfaitement être appelée « Entrée en stock », tout en créant derrière elle :

Article
    ↓
VarianteArticle
    ↓
Stock
    ↓
MouvementStock

Et ça, à mon avis, mérite d'être distingué avant de figer tes modèles.

NB: avant d'executé montre moi ce que tu as compris puis le plan d'action

La règle métier que tu viens de préciser est importante : il faut empêcher la création d'une deuxième variante identique, mais surtout ne pas empêcher le réapprovisionnement d'une variante existante.

Je structurerais cette modification comme un prompt indépendant, à donner après les prompts précédents.

PROMPT — GESTION DU RÉAPPROVISIONNEMENT D'UNE VARIANTE EXISTANTE
OBJECTIF
Nouvelle entrée :
+20


Stock :
24


→ alerte résolue selon la logique existante.


TEST 5 — Tentative de doublon


Créer exactement la même variante sans quantité d'entrée destinée au réapprovisionnement.


→ ne pas créer une deuxième variante.


Le système doit réutiliser la variante existante ou demander à l'utilisateur s'il souhaite effectuer une nouvelle entrée.


TEST 6 — Validation


Une nouvelle entrée sur une variante existante est soumise.


→ statut PENDING_VALIDATION.


Le stock ne doit pas être définitivement augmenté avant validation si cette règle est applicable.


Après validation :


→ stock augmenté ;
→ mouvement créé ;
→ historique conservé.


==================================================
RÉSULTAT FINAL ATTENDU
==================================================


La logique finale doit être :


Article
    ↓
VarianteArticle
    ↓
Stock
    ↓
MouvementStock


Pour une nouvelle combinaison :


Article
    ↓
Nouvelle VarianteArticle
    ↓
Stock initial
    ↓
Mouvement ENTRÉE


Pour une variante existante :


Article
    ↓
VarianteArticle EXISTANTE
    ↓
Stock EXISTANT
    ↓
Nouvelle entrée
    ↓
Stock augmenté
    ↓
NOUVEAU MouvementStock


Ne jamais créer une deuxième variante uniquement parce qu'une nouvelle quantité du même produit arrive.


L'objectif est de conserver une seule identité de variante et un historique complet de toutes ses entrées et sorties.
La règle centrale à faire comprendre à ton agent

L'unicité porte sur la variante, pas sur l'entrée en stock.

Donc :

Même variante ≠ même entrée.

Une variante Chemise / Noir / M peut recevoir 10, 20, puis 50 pièces à des dates différentes. On garde une seule variante, un stock courant, et plusieurs mouvements d'entrée qui permettent de reconstruire tout l'historique.

C'est cette distinction qui va éviter que ton contrôle anti-doublon bloque le réapprovisionnement. Ensuite, comme tu l'as prévu, on pourra passer à la vente, qui devra elle aussi travailler directement avec la VarianteArticle/Stock, et non avec l'Article parent.