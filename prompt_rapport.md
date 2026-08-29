OBJECTIF GÉNÉRAL

Mettre en place une véritable gestion des rapports pour les modules :

1. Gestion des Boutiques
2. Gestion des Immobilisations

Et mettre en place une impression spécifique des ventes sous forme de ticket thermique de 80 mm.

IMPORTANT :

Le frontend existe déjà.

Conserver exactement le thème, le design, les composants, les couleurs, les espacements et la présentation générale de l'application.

NE PAS créer un nouveau design.

Avant toute modification, analyser les modèles, services, endpoints, composants et logiques déjà existants.

Ne pas créer de doublons lorsqu'une fonctionnalité existe déjà.

==================================================
PARTIE 1 — CENTRE DE RAPPORTS
==================================================

Créer une interface centralisée permettant d'accéder aux rapports des différents modules.

L'objectif est de permettre à l'utilisateur autorisé de :

- sélectionner le type de rapport ;
- appliquer des filtres ;
- visualiser les résultats ;
- imprimer le rapport ;
- éventuellement exporter le rapport selon les fonctionnalités déjà prévues dans le projet.

L'interface doit rester cohérente avec le design actuel.

==================================================
PARTIE 2 — FILTRES COMMUNS
==================================================

Les rapports doivent pouvoir être filtrés selon les critères réellement pertinents.

Prévoir notamment :

- date de début ;
- date de fin ;
- succursale ;
- domaine d'activité ;
- statut ;
- utilisateur lorsque pertinent.

IMPORTANT :

La succursale et le domaine d'activité doivent respecter les droits et le contexte de l'utilisateur connecté.

Un utilisateur ne doit jamais pouvoir consulter ou imprimer les données d'une succursale ou d'un domaine auquel il n'a pas accès simplement en modifiant un filtre frontend.

Les contrôles doivent également être effectués côté backend.

==================================================
PARTIE 3 — RAPPORTS BOUTIQUE
==================================================

Créer au minimum les rapports suivants.

--------------------------------------------------
3.1 RAPPORT DES VENTES
--------------------------------------------------

Permettre de consulter les ventes réalisées.

Filtres :

- aujourd'hui ;
- date de début / date de fin ;
- période personnalisée ;
- succursale ;
- domaine d'activité ;
- utilisateur ;
- statut de la vente ;
- mode de paiement lorsque disponible.

Informations possibles :

- numéro de vente ;
- date ;
- client ;
- utilisateur ;
- succursale ;
- domaine d'activité ;
- montant ;
- remise ;
- montant reçu ;
- monnaie ;
- statut.

Le rapport doit permettre de calculer les totaux de la période.

Exemples :

Total des ventes :
XXX

Nombre de ventes :
XX

Total des remises :
XXX

Total encaissé :
XXX

--------------------------------------------------
3.2 RAPPORT DES VENTES JOURNALIÈRES
--------------------------------------------------

Permettre de sélectionner une journée.

Exemple :

24/08/2026

Afficher toutes les ventes de cette journée.

Prévoir également les totaux :

- nombre de ventes ;
- montant total des ventes ;
- total des remises ;
- total encaissé ;
- autres agrégats déjà disponibles dans le système.

--------------------------------------------------
3.3 RAPPORT DES VENTES PÉRIODIQUES
--------------------------------------------------

Permettre de saisir :

Date début
Date fin

Exemple :

01/08/2026 → 24/08/2026

Afficher toutes les ventes correspondant à cette période.

Calculer automatiquement les totaux.

--------------------------------------------------
3.4 RAPPORT MENSUEL
--------------------------------------------------

Permettre de sélectionner :

- mois ;
- année.

Afficher les ventes du mois.

Prévoir les totaux correspondants.

--------------------------------------------------
3.5 RAPPORT DES ARTICLES
--------------------------------------------------

Créer un rapport permettant de consulter les articles enregistrés dans la boutique.

Afficher notamment :

- code article ;
- désignation ;
- succursale ;
- domaine d'activité ;
- statut ;
- autres informations existantes et pertinentes.

Filtres :

- catégorie ;
- type article ;
- statut ;
- succursale ;
- domaine d'activité.

--------------------------------------------------
3.6 RAPPORT DES VARIANTES
--------------------------------------------------

Créer un rapport spécifique aux VarianteArticle.

Afficher toutes les variantes existantes.

Exemples d'informations :

- article parent ;
- type article ;
- genre ;
- couleur ;
- taille ;
- stock ;
- prix de référence ;
- prix minimum ;
- seuil d'alerte ;
- statut ;
- succursale ;
- domaine d'activité.

Permettre de rechercher et filtrer les variantes.

--------------------------------------------------
3.7 RAPPORT DES VARIANTES CRÉÉES SUR UNE PÉRIODE
--------------------------------------------------

Permettre de rechercher les variantes nouvellement créées.

Filtres :

Date début
Date fin

Exemple :

01/08/2026 → 24/08/2026

Afficher les variantes créées pendant cette période.

--------------------------------------------------
3.8 RAPPORT DU STOCK
--------------------------------------------------

Créer un rapport permettant de connaître l'état du stock.

Afficher notamment :

- article ;
- variante ;
- quantité disponible ;
- seuil d'alerte ;
- niveau du stock ;
- prix ;
- succursale ;
- domaine d'activité.

Permettre de filtrer :

- stock normal ;
- stock faible ;
- stock en alerte ;
- rupture de stock.

--------------------------------------------------
3.9 RAPPORT DES MOUVEMENTS DE STOCK
--------------------------------------------------

Créer un rapport des mouvements de stock.

Afficher :

- date ;
- variante ;
- type de mouvement ;
- quantité ;
- utilisateur ;
- motif ;
- référence de l'opération ;
- succursale ;
- domaine d'activité.

Types :

- entrée ;
- sortie ;
- ajustement ;
- autres types déjà présents dans le système.

Permettre un filtrage par période.

--------------------------------------------------
3.10 RAPPORT DES INVENTAIRES
--------------------------------------------------

Créer un rapport des inventaires réalisés.

Afficher notamment :

- numéro d'inventaire ;
- date ;
- utilisateur ;
- statut ;
- succursale ;
- domaine d'activité ;
- nombre de variantes concernées ;
- écarts constatés.

Lorsque les données existent :

- stock système ;
- stock physique ;
- écart ;
- motif de l'écart.

==================================================
PARTIE 4 — RAPPORTS IMMOBILISATION
==================================================

Créer des rapports spécifiques au module Immobilisation.

--------------------------------------------------
4.1 RAPPORT DES IMMOBILISATIONS
--------------------------------------------------

Afficher les biens enregistrés.

Informations selon les modèles existants :

- code ;
- désignation ;
- catégorie/type ;
- état ;
- statut ;
- localisation ;
- succursale ;
- domaine d'activité ;
- responsable ou utilisateur affecté ;
- date d'acquisition ;
- autres informations existantes.

Filtres :

- type ;
- état ;
- statut ;
- succursale ;
- domaine d'activité ;
- période lorsque pertinent.

--------------------------------------------------
4.2 RAPPORT DES AFFECTATIONS
--------------------------------------------------

Créer un rapport spécifique aux affectations des immobilisations.

Permettre de filtrer par :

- date début ;
- date fin ;
- bien ;
- utilisateur/personne affectée ;
- succursale ;
- domaine d'activité ;
- statut.

Afficher :

- bien ;
- personne/utilisateur affecté ;
- date d'affectation ;
- lieu ;
- responsable ;
- date de fin si elle existe ;
- statut.

Exemple :

01/08/2026 → 24/08/2026

→ afficher toutes les affectations réalisées pendant cette période.

--------------------------------------------------
4.3 RAPPORT DES DÉPLACEMENTS
--------------------------------------------------

Créer un rapport des déplacements des immobilisations.

Filtres :

- période ;
- bien ;
- origine ;
- destination ;
- succursale ;
- domaine d'activité ;
- utilisateur.

Afficher :

- bien ;
- date ;
- origine ;
- destination ;
- motif ;
- utilisateur ;
- statut.

--------------------------------------------------
4.4 RAPPORT DES BIENS CASSÉS
--------------------------------------------------

Créer un rapport spécifique aux immobilisations déclarées cassées.

Filtres :

- période ;
- bien ;
- type/catégorie ;
- succursale ;
- domaine d'activité ;
- statut.

Afficher notamment :

- bien ;
- date de déclaration ;
- état ;
- motif de casse ;
- utilisateur ;
- statut du traitement.

--------------------------------------------------
4.5 RAPPORT PAR ÉTAT
--------------------------------------------------

Permettre de filtrer les immobilisations selon leur état.

Exemples selon les valeurs existantes :

- bon état ;
- mauvais état ;
- cassé ;
- en réparation ;
- etc.

NE PAS inventer de nouvelles valeurs si elles existent déjà dans le modèle.

Le rapport doit utiliser les valeurs réellement définies dans le système.

--------------------------------------------------
4.6 RAPPORT DES DÉPLACEMENTS / AFFECTATIONS PAR PÉRIODE
--------------------------------------------------

Prévoir une interface permettant à l'utilisateur de construire facilement son rapport.

Exemple :

Type de rapport :
[ Affectations ]

Bien :
[ Tous ]

Type :
[ Tous ]

Statut :
[ Tous ]

Date début :
[ 01/08/2026 ]

Date fin :
[ 24/08/2026 ]

[ FILTRER ]

[ IMPRIMER ]

Même principe pour :

- déplacements ;
- casses ;
- états ;
- autres opérations d'immobilisation.

==================================================
PARTIE 5 — IMPRESSION DES RAPPORTS
==================================================

Lorsqu'un utilisateur clique sur :

IMPRIMER

Le système doit générer un rapport propre et imprimable.

Le rapport doit contenir :

- titre du rapport ;
- période sélectionnée ;
- succursale ;
- domaine d'activité ;
- filtres appliqués ;
- date de génération ;
- utilisateur ayant généré le rapport ;
- tableau des résultats ;
- totaux lorsque pertinents.

IMPORTANT :

Le rapport doit refléter EXACTEMENT les filtres appliqués.

Exemple :

Rapport des ventes
Période : 01/08/2026 → 24/08/2026
Succursale : Succursale A
Domaine : Boutique

Le document imprimé ne doit contenir que les données correspondant à ces critères.

==================================================
PARTIE 6 — IMPRESSION DES VENTES : TICKET 80 MM
==================================================

IMPORTANT :

L'impression d'une vente individuelle est différente des rapports.

Une vente doit pouvoir être imprimée sous forme de ticket thermique de 80 mm.

Le format doit être adapté aux imprimantes thermiques de caisse.

NE PAS générer une facture A4 pour cette fonctionnalité.

Format :

80 mm de largeur.

La hauteur doit être dynamique selon le contenu.

==================================================
PARTIE 7 — STRUCTURE DU TICKET
==================================================

S'inspirer de la structure générale du ticket fourni comme référence visuelle.

Le ticket doit être compact et optimisé pour une imprimante thermique.

Structure générale :

--------------------------------
         [LOGO]
      [NOM ENTREPRISE]
      [INFORMATIONS]
--------------------------------

N° VENTE : XXXXX
DATE : XX/XX/XXXX
UTILISATEUR : XXXXX

--------------------------------
ARTICLE       QTÉ    PRIX    TOTAL
--------------------------------

Article 1     2      XXX     XXX
Article 2     1      XXX     XXX

--------------------------------

SOUS-TOTAL              XXX
REMISE                   XXX
TOTAL                    XXX

MONTANT REÇU            XXX
MONNAIE                  XXX

--------------------------------

       MERCI POUR VOTRE ACHAT
--------------------------------

IMPORTANT :

Les informations définitives qui doivent apparaître sur le ticket seront définies à partir des données reel.

NE PAS inventer des informations commerciales ou fiscales non prévues.

Le modèle montré dans l'image sert uniquement de référence pour :

- le format ;
- la largeur ;
- la structure compacte ;
- la présentation d'un ticket de caisse.

Ne pas reproduire les éléments de l'image qui ne concernent pas notre application.

==================================================
PARTIE 8 — DONNÉES DU TICKET
==================================================

Le ticket doit récupérer dynamiquement les données de la vente.

Il ne faut jamais écrire les données en dur.

Récupérer notamment :

- numéro de vente ;
- date ;
- utilisateur ;
- articles/variantes ;
- quantité ;
- prix unitaire ;
- montant par ligne ;
- remise ;
- total ;
- montant reçu ;
- monnaie ;
- autres informations validées ultérieurement.

==================================================
PARTIE 9 — IMPRESSION APRÈS VALIDATION
==================================================

L'action « Imprimer » doit être disponible selon le workflow de vente existant.

Une vente soumise à validation ne doit pas être considérée comme une vente définitive simplement parce qu'elle a été créée.

L'impression du ticket définitif doit respecter le statut de validation prévu par le système.

Une vente validée peut être imprimée.

==================================================
PARTIE 10 — SÉCURITÉ DES RAPPORTS
==================================================

Les rapports doivent respecter les permissions de l'utilisateur.

Un utilisateur ne doit voir que les données auxquelles son rôle lui donne accès.

Les filtres :

- succursale ;
- domaine d'activité ;
- utilisateur ;
- etc.

doivent être contrôlés côté backend.

NE JAMAIS considérer le frontend comme une couche de sécurité.

==================================================
PARTIE 11 — PERFORMANCE
==================================================

Les rapports peuvent contenir beaucoup de données.

Ne pas charger inutilement toutes les données en frontend.

Analyser les possibilités de :

- filtrage backend ;
- pagination ;
- agrégation backend ;
- génération du rapport côté serveur.

Pour les rapports importants, privilégier les requêtes backend optimisées.

Exemple :

Pour un rapport de ventes mensuel de plusieurs milliers de ventes :

NE PAS charger toutes les ventes dans le navigateur uniquement pour calculer le total.

Les agrégations doivent être réalisées côté backend lorsque cela est pertinent.

==================================================
PARTIE 12 — DATA TABLE
==================================================

Les résultats des rapports affichés à l'écran doivent utiliser le système DataTable déjà demandé.

Ils doivent disposer lorsque pertinent de :

- pagination ;
- recherche ;
- tri ;
- filtres ;
- nombre de résultats.

Les mêmes composants doivent être réutilisés afin de conserver une expérience homogène.

==================================================
PARTIE 13 — ORGANISATION DE L'INTERFACE
==================================================

Créer une interface claire de type :

RAPPORTS

[ Boutique ]
[ Immobilisation ]

Puis selon le module :

BOUTIQUE

- Ventes
- Ventes journalières
- Ventes périodiques
- Ventes mensuelles
- Articles
- Variantes
- Variantes créées
- Stock
- Mouvements de stock
- Inventaires

IMMOBILISATION

- Immobilisations
- Affectations
- Déplacements
- Casses
- États

L'utilisateur sélectionne le rapport puis dispose des filtres correspondants.

==================================================
PARTIE 14 — NE PAS DUPLIQUER LA LOGIQUE
==================================================

Avant de créer les rapports :

analyser les modèles et services existants.

Réutiliser :

- Vente ;
- LigneVente ;
- Article ;
- VarianteArticle ;
- Stock ;
- MouvementStock ;
- Inventaire ;
- Immobilisation ;
- Affectation ;
- Déplacement ;
- Casse ;
- autres modèles existants.

Ne pas créer une deuxième table uniquement pour stocker les rapports.

IMPORTANT :

Un rapport est une VUE / EXTRACTION des données existantes.

Il ne faut pas créer inutilement une table :

RapportVente
RapportStock
RapportImmobilisation

sauf nécessité technique explicitement justifiée.

Les rapports doivent être construits à partir des données métier existantes.

==================================================
PARTIE 15 — RÉSULTAT FINAL ATTENDU
==================================================

L'application doit disposer de deux fonctionnalités complémentaires :

1. RAPPORTS

Permettant d'analyser et d'imprimer les données de gestion.

2. IMPRESSION D'UNE VENTE

Permettant d'imprimer une vente validée sous forme de ticket thermique 80 mm.

Architecture fonctionnelle :

BOUTIQUE
    │
    ├── Ventes
    │      └── Impression ticket 80 mm
    │
    ├── Articles
    ├── Variantes
    ├── Stock
    ├── Mouvements
    └── Inventaires
             │
             ↓
          RAPPORTS

IMMOBILISATION
    │
    ├── Biens
    ├── Affectations
    ├── Déplacements
    ├── Casses
    └── États
             │
             ↓
          RAPPORTS

Tous les rapports doivent respecter :

- permissions ;
- succursale ;
- domaine d'activité ;
- période ;
- filtres ;
- données réellement présentes dans la base.

Ne pas casser les fonctionnalités existantes.
Ne pas créer de doublons.
Conserver le design actuel.
Analyser l'existant avant toute modification.

OBJECTIF

Corriger deux problèmes distincts dans le système d'impression :

1. L'impression des tickets de vente doit réellement être configurée en 80 mm, y compris lorsque la fenêtre native d'impression du navigateur est ouverte.

2. L'impression des rapports doit produire un document propre et professionnel, sans afficher les composants d'interface tels que les filtres, DataTable, pagination ou boutons.

IMPORTANT :

NE PAS refaire toute la logique existante.

Analyser d'abord le code actuel, notamment :

- la page d'impression d'une vente ;
- le composant/template utilisé pour afficher le ticket ;
- les styles CSS du ticket ;
- les règles `@media print` existantes ;
- les règles `@page` existantes ;
- la fonction/bouton « Imprimer » ;
- la page des rapports ;
- les composants DataTable ;
- les filtres ;
- le template utilisé lors de l'impression des rapports.

Conserver le design actuel lorsqu'il est correct et corriger uniquement les problèmes décrits ci-dessous.

==================================================
PARTIE 1 — TICKET DE VENTE 80 MM
==================================================

PROBLÈME ACTUEL

Il existe déjà une page d'impression qui reçoit l'identifiant de la vente.

Cette page affiche correctement le ticket à l'écran.

Le ticket est visuellement centré et sa largeur correspond déjà à environ 80 mm.

Cependant, lorsqu'on clique sur « Imprimer » :

→ le navigateur ouvre la fenêtre d'impression ;
→ le contenu est alors traité comme une page A4 ;
→ le ticket n'est plus réellement imprimé dans son format 80 mm.

Le problème concerne donc principalement le FORMAT D'IMPRESSION et non le contenu du ticket.

==================================================
1.1 — ANALYSER LA PAGE D'IMPRESSION EXISTANTE
==================================================

Avant toute modification, identifier exactement :

- la route/page d'impression ;
- le composant qui reçoit l'ID/index de la vente ;
- le template du ticket ;
- le bouton « Imprimer » ;
- les CSS écran ;
- les CSS d'impression ;
- les éventuels `@media print` ;
- les éventuels `@page`.

NE PAS recréer une nouvelle page si celle qui existe peut être corrigée.

==================================================
1.2 — FORMAT PHYSIQUE DU TICKET
==================================================

Le ticket de vente doit être configuré pour une largeur physique de :

80 mm

La largeur du papier doit être définie explicitement dans les styles d'impression.

Le contenu doit utiliser cette largeur et non une largeur A4.

Le rendu doit être adapté aux imprimantes thermiques de 80 mm.

La hauteur doit rester dynamique selon le contenu du ticket.

NE PAS utiliser une hauteur fixe de type A4.

==================================================
1.3 — CSS D'IMPRESSION
==================================================

Vérifier et corriger les règles d'impression.

Utiliser une configuration d'impression adaptée au format 80 mm, notamment :

- `@page` ;
- `@media print` ;
- largeur du ticket ;
- marges d'impression ;
- padding ;
- centrage.

Le moteur d'impression du navigateur doit recevoir les informations nécessaires pour considérer le document comme un ticket de 80 mm.

IMPORTANT :

Le fait que le ticket ait `width: 80mm` à l'écran ne suffit PAS.

Il faut également que la feuille d'impression soit configurée correctement.

==================================================
1.4 — ÉVITER LE FORMAT A4
==================================================

Lorsque l'utilisateur clique sur :

« Imprimer »

le contenu du ticket ne doit pas être conçu comme une page A4 contenant un ticket de 80 mm au centre.

Ce comportement est incorrect.

Il faut que le document imprimable lui-même soit défini comme un document de largeur 80 mm.

Incorrect :

PAGE A4
┌─────────────────────────────┐
│                             │
│       TICKET 80 MM          │
│                             │
└─────────────────────────────┘

Correct :

PAPIER 80 MM
┌──────────────────┐
│      TICKET      │
│                  │
│      80 MM       │
│                  │
└──────────────────┘

==================================================
1.5 — MARGES
==================================================

Supprimer les marges inutiles du navigateur pour l'impression du ticket.

Le ticket doit utiliser au maximum la largeur utile du papier 80 mm.

Éviter :

- marges A4 ;
- padding excessif ;
- espaces latéraux inutiles.

Conserver toutefois un petit espace intérieur si nécessaire pour éviter que le contenu soit coupé par certaines imprimantes thermiques.

==================================================
1.6 — CENTRAGE
==================================================

Le ticket doit rester correctement centré dans son propre format.

Le centrage ne doit pas signifier :

« centrer un ticket de 80 mm sur une page A4 ».

Le centrage doit être réalisé à l'intérieur du document de 80 mm.

==================================================
1.7 — APERÇU ET IMPRESSION
==================================================

L'aperçu à l'écran doit continuer à fonctionner.

Mais il faut vérifier séparément :

A. rendu écran

ET

B. rendu impression.

Le rendu impression doit respecter réellement :

Largeur = 80 mm.

==================================================
1.8 — DONNÉES DU TICKET
==================================================

Ne pas modifier les données métier du ticket.

Conserver les informations déjà prévues :

- entreprise ;
- logo si existant ;
- numéro de vente ;
- date ;
- utilisateur ;
- articles/variantes ;
- quantités ;
- prix ;
- sous-total ;
- remise ;
- total ;
- montant reçu ;
- monnaie ;
- autres informations déjà prévues.

Le présent prompt concerne le FORMAT et le RENDU d'impression.

==================================================
1.9 — TEST OBLIGATOIRE
==================================================

Après modification, tester :

1. ouverture de la page d'impression ;
2. affichage du ticket ;
3. clic sur Imprimer ;
4. ouverture de la fenêtre native d'impression ;
5. vérification du format papier ;
6. vérification de la largeur du ticket ;
7. vérification que le contenu n'est pas transformé en page A4.

Tester également avec :

- une vente contenant peu d'articles ;
- une vente contenant beaucoup d'articles.

La hauteur doit s'adapter au contenu.

==================================================
PARTIE 2 — RAPPORTS IMPRIMABLES
==================================================

PROBLÈME ACTUEL

La page des rapports fonctionne correctement pour le filtrage et l'affichage interactif.

Cependant, lorsque l'utilisateur clique sur « Imprimer » :

- les champs de filtrage sont imprimés ;
- le DataTable est imprimé ;
- la pagination est imprimée ;
- les contrôles de recherche sont imprimés ;
- les boutons/interface sont imprimés ;
- l'ensemble ressemble à une capture de l'interface plutôt qu'à un véritable rapport.

Ce comportement doit être corrigé.

==================================================
2.1 — DISTINCTION ÉCRAN / RAPPORT
==================================================

Il faut distinguer clairement :

INTERFACE ÉCRAN

et

DOCUMENT IMPRIMÉ.

À L'ÉCRAN :

Conserver :

- filtres ;
- DataTable ;
- recherche ;
- pagination ;
- boutons ;
- actions ;
- autres composants interactifs.

À L'IMPRESSION :

NE PAS afficher :

- filtres ;
- champs de recherche ;
- DataTable en tant que composant interactif ;
- pagination ;
- boutons ;
- actions ;
- menus ;
- éléments de navigation ;
- composants d'interface inutiles.

L'impression doit produire un véritable document de rapport.

==================================================
2.2 — STRUCTURE DU RAPPORT IMPRIMÉ
==================================================

Le rapport imprimé doit avoir une structure simple et professionnelle.

Exemple :

                 [LOGO]

             NOM ENTREPRISE

              TITRE DU RAPPORT

             Période : XX/XX/XXXX
                    à
                 XX/XX/XXXX

------------------------------------------------

DONNÉES DU RAPPORT

------------------------------------------------

[Tableau simple des résultats]

------------------------------------------------

Totaux / synthèse si nécessaire

------------------------------------------------

Date de génération : XX/XX/XXXX

==================================================

IMPORTANT :

Il ne s'agit PAS de reproduire exactement le ticket de vente.

La référence au ticket concerne uniquement la DISPOSITION VISUELLE DE L'EN-TÊTE :

- logo centré ;
- nom de l'entreprise centré ;
- titre centré ;
- informations contextuelles centrées ;
- date/période centrée.

Ne pas reprendre la structure commerciale du ticket.

==================================================
2.3 — EN-TÊTE DU RAPPORT
==================================================

L'en-tête doit être entièrement centré.

Actuellement, certains éléments sont désordonnés :

- titre à gauche ;
- période au centre ;
- date décalée ;
- utilisateur ailleurs.

Corriger cela.

La disposition attendue est :

                    LOGO

              NOM ENTREPRISE

               TITRE RAPPORT

             Période : ...
             Date : ...

Tous ces éléments doivent être alignés et centrés.

==================================================
2.4 — INFORMATIONS DE L'EN-TÊTE
==================================================

Afficher uniquement les informations réellement pertinentes.

Selon le rapport :

- logo ;
- nom de l'entreprise ;
- titre du rapport ;
- période ;
- date de génération.

Si l'utilisateur ayant généré le rapport est nécessaire selon les règles métier :

l'afficher proprement dans l'en-tête ou dans une zone discrète du rapport.

NE PAS disperser les informations dans plusieurs colonnes.

==================================================
2.5 — FILTRES
==================================================

Les filtres restent disponibles À L'ÉCRAN.

Exemple :

Date début
Date fin
Service
Succursale
Domaine
Statut
etc.

L'utilisateur peut les utiliser normalement.

Mais lorsqu'il clique sur :

« Imprimer »

les champs eux-mêmes ne doivent PAS apparaître dans le document imprimé.

En revanche, leurs VALEURS peuvent être affichées dans l'en-tête du rapport lorsqu'elles sont pertinentes.

Exemple :

À L'ÉCRAN :

Date début : 01/08/2026
Date fin : 24/08/2026
Service : Boutique
Statut : Validée

À L'IMPRESSION :

RAPPORT DES VENTES

Période : 01/08/2026 — 24/08/2026
Service : Boutique
Statut : Validée

Pas les champs de formulaire.

==================================================
2.6 — DATATABLE
==================================================

Le DataTable est un composant INTERACTIF destiné à l'écran.

Il ne doit pas être imprimé comme composant DataTable.

À l'impression, produire un tableau statique propre.

Par exemple :

----------------------------------------------------------
N° Vente | Date | Client | Montant | Statut
----------------------------------------------------------
V-001    | ...  | ...    | ...     | Validée
V-002    | ...  | ...    | ...     | Validée
----------------------------------------------------------

NE PAS imprimer :

- barre de recherche ;
- pagination ;
- « 1-10 sur 50 » ;
- boutons ;
- contrôles DataTable ;
- sélecteur du nombre de lignes ;
- éléments interactifs.

==================================================
2.7 — RAPPORT SIMPLE
==================================================

Le rapport imprimé doit ressembler à un véritable document administratif.

Il doit avoir :

- un en-tête propre ;
- un titre ;
- une période ;
- éventuellement les critères utilisés ;
- un tableau de données ;
- une synthèse ;
- les totaux lorsque nécessaire ;
- une date de génération.

Il ne doit pas ressembler à une page web imprimée.

==================================================
2.8 — RAPPORTS CONCERNÉS
==================================================

Cette règle doit s'appliquer à TOUS les rapports :

BOUTIQUE :

- ventes ;
- ventes journalières ;
- ventes périodiques ;
- ventes mensuelles ;
- articles ;
- variantes ;
- stock ;
- mouvements de stock ;
- inventaires ;
- autres rapports existants.

IMMOBILISATION :

- immobilisations ;
- affectations ;
- déplacements ;
- casses ;
- états ;
- autres rapports existants.

==================================================
2.9 — CSS PRINT
==================================================

Analyser les styles d'impression existants.

Utiliser correctement :

`@media print`

pour masquer les éléments d'interface.

Exemples d'éléments à masquer lors de l'impression :

- `.filters`
- `.datatable-controls`
- `.pagination`
- `.search`
- `.actions`
- `.buttons`
- navigation
- menus

IMPORTANT :

Ne pas appliquer aveuglément ces noms de classes.

Identifier les classes/composants réellement utilisés dans le projet.

==================================================
2.10 — RAPPORT ET TICKET SONT DEUX FORMATS DIFFÉRENTS
==================================================

NE PAS appliquer le format 80 mm du ticket aux rapports.

TICKET :

→ 80 mm
→ imprimante thermique
→ vente individuelle
→ format compact.

RAPPORT :

→ document papier normal ;
→ tableau lisible ;
→ en-tête professionnel ;
→ format adapté au volume de données.

La seule chose commune entre les deux est la logique de présentation de l'EN-TÊTE :

- logo centré ;
- entreprise centrée ;
- titre centré ;
- informations contextuelles centrées.

==================================================
PARTIE 3 — NE PAS DUPLIQUER LES DONNÉES
==================================================

Le rapport imprimé doit utiliser exactement les résultats du rapport filtré.

Ne pas effectuer une deuxième logique métier différente uniquement pour l'impression.

Le backend doit fournir les données correspondant aux filtres.

Le frontend peut ensuite présenter :

VERSION ÉCRAN :
DataTable interactif

VERSION IMPRESSION :
tableau statique imprimable.

==================================================
PARTIE 4 — VÉRIFICATIONS AVANT MODIFICATION
==================================================

Avant de coder :

1. identifier la page actuelle d'impression de vente ;
2. identifier ses CSS ;
3. identifier le bouton Imprimer ;
4. identifier les règles `@media print` ;
5. identifier les règles `@page` ;
6. identifier la page des rapports ;
7. identifier le composant DataTable ;
8. identifier les composants de filtres ;
9. identifier les styles des rapports ;
10. identifier les composants d'en-tête.

Puis proposer/modifier uniquement ce qui est nécessaire.

==================================================
RÉSULTAT ATTENDU
==================================================

TICKET DE VENTE :

Page d'impression existante
        ↓
Affichage ticket correct
        ↓
Imprimer
        ↓
Format papier 80 mm
        ↓
Ticket réellement imprimé en 80 mm

ET NON :

Page A4
        ↓
Ticket de 80 mm centré
        ↓
Impression A4


RAPPORT :

Interface écran
        ↓
Filtres
        ↓
DataTable
        ↓
Résultats
        ↓
Imprimer
        ↓
Rapport propre

Le document imprimé contient :

LOGO CENTRÉ

NOM ENTREPRISE CENTRÉ

TITRE DU RAPPORT CENTRÉ

PÉRIODE / INFORMATIONS PERTINENTES CENTRÉES

--------------------------------
TABLEAU SIMPLE DES DONNÉES
--------------------------------

TOTAUX / SYNTHÈSE

DATE DE GÉNÉRATION

Et ne contient PAS :

- filtres sous forme de champs ;
- DataTable interactif ;
- pagination ;
- barre de recherche ;
- boutons ;
- menus ;
- éléments d'interface.

==================================================
CONTRAINTE FINALE
==================================================

NE PAS modifier les règles métier existantes.

NE PAS supprimer les fonctionnalités de filtrage.

NE PAS supprimer DataTable de l'interface écran.

DataTable reste utilisé à l'écran.

Il doit simplement être remplacé/transformé par une présentation statique adaptée à l'impression.

NE PAS transformer les rapports en tickets 80 mm.

NE PAS transformer les tickets en rapports A4.

Respecter strictement la distinction :

VENTE → TICKET THERMIQUE 80 MM

RAPPORT → DOCUMENT DE RAPPORT NORMAL

Conserver le thème général de l'application et harmoniser uniquement la disposition des en-têtes avec celle du ticket.


Objectif
Transformer le rendu actuel du rapport pour qu'il corresponde au modèle ci-dessous :

Modèle attendu (similaire à la 1ʳᵉ image)

Un en-tête avec : titre, période, date de génération, auteur.

Un tableau classique (sans grille de datatable, sans colonnes interactives, sans pagination ni recherche).

Des totaux clairs en bas (nombre de ventes, total des ventes, total des remises, total encaissé, monnaie).

Une zone pour signature/cachet en bas.

Aucun élément d'interface (boutons, icônes, cases à cocher, barre de recherche, etc.).

Exemple de rendu souhaité (inspiré de votre 1ʳᵉ image) :

text
RAPPORT DES VENTES - BOUTIQUE  
Période : du 2026-08-26 au 2026-08-26  
Généré le : 26/08/2026 20:30 par jey  

| N°          | DATE            | CLIENT          | PAIEMENT  | UTILISATEUR  | REMISE | TOTAL     | REÇU      |
|-------------|-----------------|-----------------|-----------|--------------|--------|-----------|-----------|
| VTE-2026-0005| 26/08/2026 11:00| Test prix proposé| Espèces   | responsable  | 0,00   | 16002,00  | 99999,0   |
| VTE-2026-0006| 26/08/2026 20:28| Joyce           | Espèces   | jey          | 0,00   | 16000,00  | 20000,0   |

NOMBRE DE VENTES : 2  
TOTAL DES VENTES : 32002,00  
TOTAL DES REMISES : 0  
TOTAL ENCAISSÉ : 119999,00  
MONNAIE : 87997,00  

SIGNATURE / CACHET :
Actions à réaliser

Supprimer la capture d'écran

Le rapport ne doit plus être une image de la page, mais un document HTML/CSS ou PDF généré à partir des données brutes.

Remplacer la datatable par un tableau statique

Pas de librairie DataTable (pas de recherche, pas de tri, pas de pagination).

Un simple <table> avec bordures fines (uniquement pour la lisibilité, pas de grille interactive).

En-têtes de colonnes clairs et alignés.

Conserver uniquement les données essentielles

Aucune colonne supplémentaire (pas d'actions, pas de checkbox).

Mise en forme sobre

Police lisible (ex. Arial, 10-12px).

Alignement des nombres à droite, texte à gauche.

Pas de couleurs vives (rester sur du noir/blanc/gris).

Résultat attendu
Un rapport clair, professionnel, imprimable, sans aucun élément d'interface dynamique, ressemblant strictement à l'exemple fourni.