Oui. Je vais intégrer cette logique directement dans le prompt précédent, en étant plus précis sur ce qui doit être une table métier indépendante et ce qui doit rester un champ de ArticleBoutique.

Il y a aussi une décision que je prends clairement : Catégorie, sous-catégorie, unité et fournisseur peuvent être des tables de référence, tandis que rayon, étagère et emplacement physique peuvent rester directement des champs de l'article si leur gestion ne nécessite pas un référentiel indépendant. Cela évite de créer inutilement une dizaine de tables.

Voici le prompt consolidé.

PROMPT — MODULE BOUTIQUE : ARCHITECTURE MÉTIER, ARTICLES, STOCK, MOUVEMENTS, VENTES ET INVENTAIRES
1. OBJECTIF

Implémenter le module Boutique comme un module métier totalement indépendant du module Approvisionnement.

Le module Approvisionnement existe déjà et doit conserver sa propre logique, ses propres modèles et ses propres données.

La Boutique doit disposer de ses propres modèles pour :

les articles ;
les catégories ;
les sous-catégories ;
les unités ;
les fournisseurs ;
les stocks ;
les mouvements de stock ;
les alertes de stock ;
les ventes ;
les lignes de vente ;
les inventaires ;
les lignes d'inventaire ;
l'historique ;
les rapports.

Le frontend existe déjà. Le backend doit être développé en priorité, puis connecté au frontend existant en conservant exactement le même thème visuel que le module Approvisionnement.

2. SÉPARATION STRICTE APPROVISIONNEMENT / BOUTIQUE

Ne pas utiliser les modèles métier de l'Approvisionnement pour gérer les données de la Boutique.

Architecture :

APPLICATION
│
├── APPROVISIONNEMENT
│   ├── ses articles
│   ├── son stock
│   ├── ses mouvements
│   ├── ses entrées
│   ├── ses sorties
│   └── ses inventaires
│
└── BOUTIQUE
    ├── ses articles
    ├── son stock
    ├── ses mouvements
    ├── ses ventes
    ├── ses inventaires
    ├── ses alertes
    └── ses rapports

Une vente Boutique ne doit jamais modifier le stock du module Approvisionnement.

Une opération Approvisionnement ne doit pas modifier automatiquement le stock Boutique.

3. ANALYSER D'ABORD LES MODÈLES APPROVISIONNEMENT

Avant d'implémenter la Boutique, analyser les modèles existants du module Approvisionnement afin d'identifier les concepts déjà présents :

Article ;
Catégorie ;
Unité ;
Fournisseur ;
Mouvement de stock ;
Inventaire ;
Ligne d'inventaire ;
Sortie ;
Ligne de sortie ;
etc.

Cette analyse sert uniquement à :

comprendre les conventions du projet ;
récupérer les concepts réutilisables ;
éviter les incohérences ;
identifier les composants techniques pouvant être mutualisés.

Ne pas réutiliser directement les modèles métier Approvisionnement lorsque la Boutique doit posséder ses propres données.

4. MODÈLES PRINCIPAUX DE LA BOUTIQUE

Prévoir au minimum une architecture équivalente à :

CategorieBoutique
SousCategorieBoutique
UniteBoutique
FournisseurBoutique


ArticleBoutique


StockBoutique
MouvementStockBoutique
AlerteStockBoutique


VenteBoutique
LigneVenteBoutique


InventaireBoutique
LigneInventaireBoutique

Les noms exacts peuvent suivre les conventions déjà utilisées dans le projet Django.

5. MODÈLE ARTICLE

ArticleBoutique représente le produit, et non son stock.

La création d'un article ne doit donc pas être confondue avec une entrée en stock.

Exemple :

Article :
T-shirt noir
Taille : M
Couleur : Noir

Après création :

Article existe
Stock = 0

Une opération distincte permettra ensuite d'ajouter une quantité au stock.

6. INFORMATIONS DE L'ARTICLE

Le modèle ArticleBoutique doit contenir les informations intrinsèques nécessaires à l'identification, à la classification et à la commercialisation de l'article.

Identification

Prévoir notamment :

code
référence
désignation
description
type
Classification

Utiliser des relations pour les éléments qui constituent de véritables référentiels :

categorie → CategorieBoutique
sous_categorie → SousCategorieBoutique
unite → UniteBoutique

Pour le genre, prévoir une valeur contrôlée selon les besoins :

HOMME
FEMME
MIXTE
ENFANT

ou les valeurs définies dans le cahier des charges.

7. CATÉGORIE ET SOUS-CATÉGORIE

La catégorie ne doit pas être simplement un texte libre dans l'article.

Créer :

CategorieBoutique

et, si nécessaire :

SousCategorieBoutique

Relation :

Categorie
   │
   └── SousCategorie
          │
          ▼
      Article

Exemple :

Catégorie : Vêtements
Sous-catégorie : T-shirts
Article : T-shirt noir M

Cela permettra ensuite de filtrer et de produire des rapports par catégorie.

8. UNITÉ

Créer un référentiel :

UniteBoutique

Exemples :

Pièce
Unité
Lot

L'article possède une unité de gestion.

9. FOURNISSEUR

Créer également un modèle propre à la Boutique :

FournisseurBoutique

avec les informations nécessaires au fournisseur.

L'article peut être associé à un fournisseur principal selon les besoins.

Si plusieurs fournisseurs peuvent fournir le même article, prévoir une relation adaptée plutôt que de limiter artificiellement l'article à un seul fournisseur.

10. LOCALISATION PHYSIQUE DE L'ARTICLE

Ne pas créer automatiquement des tables séparées pour :

rayon ;
étagère ;
emplacement.

Ces informations peuvent rester directement dans ArticleBoutique si elles servent simplement à décrire la localisation physique de l'article.

Exemple :

ArticleBoutique
-----------------------------
rayon
étagère
emplacement

Exemple concret :

Rayon : Homme
Étagère : A3
Emplacement : Haut

Cela évite de complexifier inutilement le modèle.

Ne créer une table Rayon, Etagere ou Emplacement que si le cahier des charges exige une véritable gestion indépendante de ces entités : création, modification, affectation, capacité, historique, etc.

11. AUTRES INFORMATIONS ARTICLE

Prévoir selon le cahier des charges :

taille
couleur
marque
matière
modèle
genre

Les champs doivent rester cohérents avec les besoins réels de la Boutique.

Ne pas créer de tables pour chaque simple caractéristique si elle n'a pas de comportement métier propre.

12. PRIX DE L'ARTICLE

L'article doit conserver ses informations tarifaires :

prix_achat
prix_unitaire
prix_minimum
prix_maximum

Selon les règles métier.

Règle fondamentale

Le prix minimum constitue le plancher de vente.

Donc :

prix_vente >= prix_minimum

Et si un prix maximum est défini :

prix_vente <= prix_maximum

Donc :

prix_minimum ≤ prix_vente ≤ prix_maximum
13. CONTRÔLE DU PRIX LORS D'UNE VENTE

Le contrôle doit être effectué côté backend.

Exemple :

Prix minimum : 15 000 FC
Prix normal : 20 000 FC

Si l'utilisateur tente :

Prix de vente : 12 000 FC

la vente doit être refusée.

Message :

Le prix de vente de 12 000 FC est inférieur au prix minimum autorisé de 15 000 FC pour cet article.

Le frontend peut effectuer une prévalidation, mais le backend reste la source de vérité.

14. MODÈLE STOCK

Créer une table :

StockBoutique

Cette table doit conserver l'état actuel du stock.

Elle ne représente pas l'historique.

Elle répond à la question :

Combien d'unités de cet article avons-nous actuellement ?

Exemple :

Article : T-shirt noir M
Quantité : 55
15. NE PAS CRÉER UNE NOUVELLE LIGNE DE STOCK À CHAQUE ENTRÉE

C'est une règle importante.

Si nous recevons :

17/08 → +40
18/08 → +20

nous ne devons pas obtenir :

Stock
40
20

Nous devons avoir un stock courant unique pour le même contexte :

Article : T-shirt noir M
Stock actuel : 60

Les opérations historiques sont conservées dans MouvementStockBoutique.

16. MOUVEMENT DE STOCK

Créer :

MouvementStockBoutique

Cette table constitue le journal de toutes les variations de stock.

Types possibles :

ENTREE
SORTIE
AJUSTEMENT
RETOUR
CASSE
PERTE

Selon les opérations réellement prévues dans le cahier des charges.

17. STRUCTURE D'UN MOUVEMENT

Chaque mouvement doit conserver au minimum :

article
stock
type
quantite
stock_avant
stock_apres
date
utilisateur
reference
motif
succursale
domaine

Selon le besoin.

Exemple

Première entrée :

Article : T-shirt noir M
Type : ENTREE
Quantité : 40
Stock avant : 0
Stock après : 40
Date : 17/08/2026

Deuxième entrée :

Article : T-shirt noir M
Type : ENTREE
Quantité : 20
Stock avant : 40
Stock après : 60
Date : 18/08/2026
18. RELATION ENTRE STOCK ET MOUVEMENT

La logique doit être :

Article
   │
   ▼
StockBoutique
   │
   │ état actuel
   ▼
Quantité actuelle

et :

Article
   │
   ▼
MouvementStockBoutique
   ├── +40
   ├── +20
   ├── -5
   └── +10

Ainsi :

Stock = 65

et l'historique permet de comprendre comment cette valeur a été obtenue.

19. LE STOCK NE DOIT PAS ÊTRE RECALCULÉ À CHAQUE CONSULTATION

Ne pas utiliser systématiquement :

SUM(entrées) - SUM(sorties)

pour déterminer le stock actuel à chaque requête.

La quantité courante doit être conservée dans :

StockBoutique.quantite

Les mouvements servent à :

tracer ;
auditer ;
expliquer ;
reconstruire ;
contrôler.

Le stock sert à :

connaître immédiatement la quantité disponible ;
effectuer les contrôles ;
afficher le stock ;
permettre les ventes.
20. COHÉRENCE ENTRE STOCK ET MOUVEMENT

Toute modification de stock doit obligatoirement produire un mouvement.

Il ne doit jamais être possible d'avoir :

Stock modifié
+
aucun mouvement

De même, une opération ne doit pas créer un mouvement sans mettre correctement à jour le stock.

Utiliser une transaction atomique.

21. GESTION DE LA CONCURRENCE

Lors d'une modification du stock :

1. récupérer le stock
2. verrouiller la ligne
3. lire la quantité actuelle
4. vérifier la disponibilité
5. calculer la nouvelle quantité
6. mettre à jour Stock
7. créer MouvementStock
8. valider la transaction

Prévoir le verrouillage approprié afin d'éviter qu'une vente simultanée ou plusieurs opérations concurrentes produisent un stock incorrect.

22. SEUIL DE STOCK

Chaque stock peut avoir un seuil d'alerte :

seuil_alerte

Exemple :

Stock actuel : 8
Seuil : 10

Le système doit considérer le stock comme étant en situation d'alerte :

8 <= 10
23. TABLE ALERTE STOCK

Créer une table dédiée :

AlerteStockBoutique

Elle permet de gérer explicitement les alertes générées par le niveau de stock.

Elle peut contenir notamment :

stock
article
type
seuil
quantite_actuelle
statut
date_creation
date_resolution

Selon les besoins :

STOCK_FAIBLE
RUPTURE

par exemple.

24. LOGIQUE DE L'ALERTE

Exemple :

Article : T-shirt noir M
Stock : 8
Seuil : 10

Le système déclenche :

AlerteStock
type = STOCK_FAIBLE
quantite = 8
seuil = 10
statut = ACTIVE

Si le stock tombe à zéro :

quantite = 0

le système peut produire :

type = RUPTURE
25. NE PAS CRÉER DES ALERTES EN DOUBLE

Attention à ne pas générer une nouvelle alerte identique à chaque consultation ou à chaque requête.

Une logique doit déterminer si une alerte active existe déjà.

Exemple :

Stock = 8
Seuil = 10

Une alerte active existe.

Une nouvelle consultation ne doit pas créer :

Alerte #1
Alerte #2
Alerte #3
Alerte #4

Il faut conserver une alerte cohérente avec son cycle de vie :

ACTIVE
RESOLUE

Lorsqu'une nouvelle entrée fait remonter le stock :

Stock = 25

l'alerte peut être considérée comme résolue.

26. STOCK PAR SUCCURSALE ET DOMAINE

Le stock doit respecter la centralisation de l'application.

Un même article peut avoir des stocks différents selon le contexte :

Article : T-shirt noir M
Kinshasa
Boutique
Stock = 60
Lubumbashi
Boutique
Stock = 25

Il faut donc tenir compte du contexte :

article
+
succursale
+
domaine
+
éventuellement emplacement

pour identifier correctement le stock.

27. ENTRÉE EN STOCK

La création d'un article et l'entrée en stock sont deux opérations différentes.

Étape 1

Créer :

T-shirt noir M
Étape 2

Créer une entrée :

Quantité = 40
Étape 3

Le système :

Stock avant = 0
Stock après = 40

et crée le mouvement correspondant.

Étape 4

Une deuxième entrée :

Quantité = 20

produit :

Stock avant = 40
Stock après = 60
28. VENTE = SORTIE DE STOCK

Une vente validée produit automatiquement un mouvement :

type = SORTIE

Exemple :

Stock avant : 60
Quantité vendue : 5
Stock après : 55

La vente et la modification du stock doivent être dans la même transaction.

29. CONTRÔLE DU STOCK AVANT VENTE

Avant validation :

stock disponible >= quantité vendue

Sinon :

Vente refusée

Message clair :

Stock insuffisant pour T-shirt noir M.
Stock disponible : 2.
Quantité demandée : 5.
30. VENTE ET LIGNES DE VENTE

Créer :

VenteBoutique
LigneVenteBoutique

Une vente peut contenir plusieurs articles.

Exemple :

VENTE #V-00025


T-shirt noir M       2 × 20 000
Jean bleu L          1 × 35 000

Chaque ligne conserve le prix réellement appliqué au moment de la vente.

Ne pas recalculer les anciennes ventes à partir du prix actuel de l'article.

31. INVENTAIRE

La Boutique doit disposer de son propre système d'inventaire.

Il faut distinguer :

STOCK THÉORIQUE

et :

STOCK PHYSIQUE

Exemple :

Stock théorique : 60
Stock physique : 57
Écart : -3

Créer :

InventaireBoutique
LigneInventaireBoutique
32. AJUSTEMENT APRÈS INVENTAIRE

Une différence d'inventaire ne doit pas être corrigée silencieusement.

Si :

Théorique = 60
Physique = 57

la validation de l'inventaire produit :

MouvementStock
type = AJUSTEMENT
stock_avant = 60
quantite = -3
stock_apres = 57
motif = ECART_INVENTAIRE

Cela garantit la traçabilité.

33. HISTORIQUE

L'historique Boutique doit permettre de retrouver :

Date
Article
Type de mouvement
Quantité
Stock avant
Stock après
Utilisateur
Référence
Motif
Succursale
Domaine
34. RAPPORTS

Prévoir les bases nécessaires aux rapports :

Ventes
ventes par jour ;
semaine ;
mois ;
période ;
montant ;
quantité ;
nombre de ventes.
Articles
articles les plus vendus ;
quantités vendues ;
chiffre généré ;
stock actuel.
Stock
stock disponible ;
stock faible ;
ruptures ;
mouvements ;
ajustements.
Alertes
alertes actives ;
articles sous seuil ;
ruptures ;
alertes résolues.
35. RÈGLE D'ARCHITECTURE IMPORTANTE

Ne pas mettre toutes les informations dans des tables séparées simplement pour normaliser artificiellement la base.

Doivent être des entités/référentiels indépendants lorsque leur gestion le justifie :
CategorieBoutique
SousCategorieBoutique
UniteBoutique
FournisseurBoutique
Peuvent rester directement dans ArticleBoutique :
taille
couleur
genre
rayon
etagere
emplacement
marque
modele

sauf si le cahier des charges impose une gestion autonome de ces éléments.

Le principe est :

Une information devient une table indépendante lorsqu'elle possède sa propre identité, son propre cycle de vie, ses propres relations ou doit être administrée indépendamment.

Sinon, un champ directement attaché à l'article est préférable.

36. ARCHITECTURE FINALE

La logique globale du module Boutique doit être :

                         BOUTIQUE
                            │
             ┌──────────────┴──────────────┐
             │                             │
             ▼                             ▼
       RÉFÉRENTIELS                    ARTICLES
             │                             │
      ┌──────┼──────┐                      │
      ▼      ▼      ▼                      ▼
  Catégorie Unité Fournisseur          STOCK
                                          │
                          ┌───────────────┼───────────────┐
                          │               │               │
                          ▼               ▼               ▼
                       Entrée           Vente          Ajustement
                          │               │               │
                          └───────────────┼───────────────┘
                                          ▼
                                MOUVEMENT STOCK
                                          │
                                          ▼
                                  HISTORIQUE STOCK
                                          │
                                          ▼
                                  ALERTE STOCK

Et :

VENTE
  │
  └── LigneVente
         │
         ▼
    SORTIE STOCK
         │
         ▼
  MouvementStock
         │
         ▼
   StockBoutique
RÈGLE FINALE À RESPECTER

Article ≠ Stock ≠ Mouvement ≠ Vente ≠ Inventaire ≠ Alerte.

Chacun a une responsabilité précise :

Élément	Responsabilité
Article	Décrit le produit
Stock	Conserve la quantité actuelle
MouvementStock	Trace chaque variation
Vente	Représente l'opération commerciale
Inventaire	Compare le théorique au physique
AlerteStock	Signale une situation de stock nécessitant une attention
Catégorie / Sous-catégorie	Classifie les articles
Unité	Définit l'unité de gestion
Fournisseur	Identifie la source d'approvisionnement

Et surtout, une nouvelle entrée de 20 chemises ne crée pas un nouveau stock : elle crée un nouveau mouvement, tandis que le stock existant passe de 40 → 60.

C'est cette logique qui doit être considérée comme la base officielle du développement du module Boutique.