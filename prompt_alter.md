CONTEXTE

Je travaille actuellement sur le module « Gestion des immobilisations ».

Le frontend existe déjà et possède déjà son design, ses composants et une partie de la logique.

AVANT TOUTE MODIFICATION, tu dois impérativement analyser le projet existant afin de déterminer si les fonctionnalités demandées ci-dessous existent déjà, même partiellement.

==================================================
RÈGLE ABSOLUE — ANALYSER AVANT DE CODER
==================================================

NE COMMENCE PAS directement par créer des modèles, champs, vues, endpoints ou composants.

Tu dois d'abord rechercher dans le projet :

- les modèles Django existants ;
- les migrations ;
- les serializers ;
- les views / ViewSets ;
- les URLs ;
- les services ;
- les permissions ;
- les règles métier ;
- les statuts ;
- les systèmes de validation existants ;
- les composants frontend ;
- les formulaires ;
- les DataTables existants ;
- les composants de tableaux ;
- les composants de sélection ;
- les fonctions d'impression ou de rapport si elles sont concernées.

Pour chaque fonctionnalité demandée, déterminer :

1. Est-ce qu'elle existe déjà ?
2. Si oui, où ?
3. Est-elle complète ?
4. Est-elle partiellement implémentée ?
5. Est-elle utilisée ailleurs dans l'application ?
6. Peut-elle être réutilisée ?
7. Est-il nécessaire de la modifier ou simplement de l'étendre ?

NE CRÉE PAS une deuxième logique lorsqu'une logique équivalente existe déjà.

NE CRÉE PAS un nouveau modèle si un modèle existant peut remplir exactement le même rôle.

NE CRÉE PAS une nouvelle API si un endpoint existant peut être étendu proprement.

NE CRÉE PAS un nouveau composant DataTable si le projet possède déjà un composant réutilisable.

NE SUPPRIME PAS une logique existante sans justification.

NE CASSE PAS les fonctionnalités existantes.

==================================================
ÉTAPE 1 — AUDIT DU MODULE IMMOBILISATION
==================================================

Commence par analyser la structure actuelle du module Immobilisation.

Identifie notamment :

- modèle Bien / Immobilisation ;
- modèle de catégorie/type si existant ;
- modèle d'affectation ;
- modèle de déplacement ;
- modèle de casse ;
- modèle de statut ;
- système de validation ;
- utilisateurs responsables ;
- permissions ;
- historique/audit ;
- tableaux frontend ;
- formulaires de création/modification.

Présente mentalement la relation entre ces éléments avant de modifier le code.

==================================================
ÉTAPE 2 — PÉRIODE D'ENTRETIEN
==================================================

OBJECTIF

Ajouter une « période d'entretien » lors de la création d'un bien immobilier / bien d'immobilisation.

IMPORTANT :

Avant d'ajouter un nouveau champ, rechercher si une information équivalente existe déjà dans le modèle.

Rechercher notamment des champs comme :

- entretien ;
- maintenance ;
- période d'entretien ;
- intervalle d'entretien ;
- fréquence d'entretien ;
- maintenance_period ;
- maintenance_interval ;
- prochaine_maintenance ;
- next_maintenance ;
- ou toute autre logique équivalente.

Si un champ existe déjà et répond au besoin :

→ le réutiliser ou l'étendre.

Si la logique existe partiellement :

→ la compléter.

Seulement si aucune logique équivalente n'existe :

→ ajouter le champ nécessaire au modèle du bien.

==================================================
RÈGLE MÉTIER — PÉRIODE D'ENTRETIEN
==================================================

Lors de la création d'un bien, l'utilisateur doit pouvoir définir sa période/fréquence d'entretien.

La conception exacte du champ doit respecter l'architecture déjà utilisée dans le projet.

Ne pas imposer arbitrairement un nouveau type de données si une structure existante peut être réutilisée.

Exemple possible selon l'architecture existante :

- durée en mois ;
- fréquence ;
- date de prochain entretien ;
- intervalle d'entretien.

Mais avant de choisir, analyser ce qui existe déjà dans le projet et dans le cahier des charges.

==================================================
ÉTAPE 3 — DURÉE DE VIE DU BIEN
==================================================

OBJECTIF

Ajouter la « durée de vie » lors de la création d'un bien.

Avant toute création :

rechercher si le modèle possède déjà une information équivalente :

- durée de vie ;
- durée d'utilisation ;
- durée d'amortissement ;
- lifetime ;
- useful_life ;
- lifespan ;
- durée prévue ;
- etc.

Si elle existe :

→ la réutiliser.

Si elle existe partiellement :

→ l'étendre.

Si elle n'existe pas :

→ ajouter le champ approprié.

==================================================
RÈGLE IMPORTANTE
==================================================

Ne pas confondre :

DURÉE DE VIE

et

PÉRIODE D'ENTRETIEN.

Ce sont deux informations différentes.

La durée de vie représente la durée prévue d'utilisation du bien.

La période d'entretien représente la fréquence ou période à laquelle le bien doit faire l'objet d'un entretien.

Ces deux notions doivent rester distinctes dans le modèle, sauf si le modèle métier existant démontre clairement qu'elles sont déjà correctement représentées.

==================================================
ÉTAPE 4 — VALIDATION D'UN BIEN
==================================================

OBJECTIF

Ajouter ou compléter le système de validation des biens.

Mais avant de créer cette fonctionnalité :

ANALYSER IMPÉRATIVEMENT LE SYSTÈME DE VALIDATION EXISTANT.

Rechercher :

- statuts de validation ;
- statut brouillon ;
- statut en attente ;
- statut validé ;
- statut rejeté ;
- responsable ;
- validateur ;
- utilisateur créateur ;
- historique des validations ;
- permissions de validation ;
- notifications éventuelles ;
- validation utilisée dans d'autres modules.

==================================================
RÈGLE DE VALIDATION
==================================================

Si un système de validation générique existe déjà dans l'application :

→ NE PAS créer un deuxième système.

→ Réutiliser le système existant pour les immobilisations.

Si aucun système approprié n'existe :

→ implémenter la validation conformément à l'architecture générale de l'application.

Le bien doit pouvoir suivre un cycle de validation cohérent avec les autres modules.

Exemple logique :

Création
↓
Brouillon / En attente de validation
↓
Validation par responsable
↓
Validé

Ou, si le projet possède déjà d'autres statuts :

→ respecter strictement les statuts existants.

==================================================
ÉTAPE 5 — VALIDATION PAR LOTS
==================================================

OBJECTIF

Permettre au responsable de valider plusieurs biens simultanément.

Exemple :

Bien 001
Bien 002
Bien 003
Bien 004

L'utilisateur sélectionne :

☑ Bien 001
☑ Bien 002
☑ Bien 003

Puis :

[ VALIDER LA SÉLECTION ]

Le système doit traiter la validation des biens sélectionnés.

==================================================
AVANT DE CODER
==================================================

Rechercher si le projet possède déjà :

- sélection multiple ;
- checkbox dans les tableaux ;
- action groupée ;
- bulk action ;
- bulk validation ;
- validation multiple ;
- endpoint de validation par lot.

Si une fonctionnalité similaire existe déjà :

→ la réutiliser.

Si elle existe dans un autre module :

→ généraliser/réutiliser proprement le mécanisme au lieu de recréer une nouvelle architecture.

==================================================
RÈGLES DE VALIDATION PAR LOT
==================================================

Le système doit :

1. permettre de sélectionner plusieurs biens ;
2. vérifier que l'utilisateur possède la permission de validation ;
3. vérifier que les biens sont dans un état permettant leur validation ;
4. valider uniquement les biens éligibles ;
5. empêcher la validation d'un bien déjà validé si les règles existantes l'interdisent ;
6. conserver l'utilisateur ayant effectué la validation ;
7. conserver la date/heure de validation ;
8. respecter l'audit existant ;
9. retourner un résultat clair à l'utilisateur.

Si certains biens ne peuvent pas être validés :

→ ne pas compromettre toute l'opération sans raison.

Le comportement doit respecter le système transactionnel déjà utilisé dans le projet.

==================================================
ÉTAPE 6 — DATATABLE / TABLEAUX
==================================================

OBJECTIF

Tous les tableaux du module Immobilisation doivent utiliser le composant DataTable/Grid prévu dans le projet.

Cela concerne notamment :

- liste des biens ;
- affectations ;
- déplacements ;
- casses ;
- validations ;
- historiques ;
- autres tableaux du module.

==================================================
RÈGLE ABSOLUE
==================================================

AVANT DE CRÉER OU D'IMPORTER UN NOUVEAU DATATABLE :

rechercher dans le frontend si une bibliothèque ou un composant DataTable existe déjà.

Identifier :

- bibliothèque utilisée ;
- composant commun ;
- configuration ;
- pagination ;
- recherche ;
- tri ;
- filtrage ;
- sélection multiple ;
- actions ;
- responsive ;
- export éventuel.

Si le projet possède déjà un DataTable :

→ réutiliser exactement ce composant.

NE PAS installer une deuxième bibliothèque de DataTable.

NE PAS créer plusieurs systèmes de tableau concurrents.

==================================================
ÉTAPE 7 — DATATABLE ET VALIDATION PAR LOTS
==================================================

Le DataTable utilisé pour la liste des biens doit, lorsque nécessaire, permettre :

- sélection individuelle ;
- sélection multiple ;
- checkbox ;
- action de validation groupée ;
- pagination ;
- recherche ;
- filtrage ;
- tri ;
- affichage du statut.

La sélection multiple doit être intégrée au DataTable existant.

Ne pas créer une interface séparée uniquement pour la validation par lots si le tableau actuel peut accueillir cette fonctionnalité.

==================================================
ÉTAPE 8 — BACKEND
==================================================

Commencer par le backend.

Analyser puis modifier uniquement ce qui est nécessaire :

- modèles ;
- migrations ;
- serializers ;
- services ;
- views/ViewSets ;
- endpoints ;
- permissions ;
- validation métier ;
- transactions ;
- audit.

Les nouvelles fonctionnalités doivent respecter l'architecture existante.

Ne pas dupliquer les règles métier.

Les contrôles doivent être réalisés côté backend même si le frontend possède également des contrôles.

==================================================
ÉTAPE 9 — FRONTEND
==================================================

Après le backend, intégrer les nouvelles fonctionnalités dans le frontend existant.

Conserver strictement :

- le thème ;
- les couleurs ;
- les composants ;
- la mise en page ;
- les formulaires ;
- les conventions UI ;
- les DataTables existants.

Ajouter uniquement :

- période d'entretien ;
- durée de vie ;
- statut/éléments de validation si nécessaire ;
- sélection multiple ;
- validation par lots ;
- DataTable/Grid là où il manque.

==================================================
ÉTAPE 10 — MIGRATIONS ET COMPATIBILITÉ
==================================================

Avant de créer une migration :

vérifier la structure actuelle des modèles.

Les nouvelles migrations doivent être compatibles avec les données existantes.

Ne pas supprimer ou renommer brutalement un champ existant sans vérifier son utilisation.

Si une modification de champ existant est nécessaire :

→ analyser ses dépendances avant de l'effectuer.

==================================================
ÉTAPE 11 — TESTS
==================================================

Après implémentation, vérifier :

1. création d'un bien ;
2. période d'entretien ;
3. durée de vie ;
4. modification d'un bien ;
5. affichage des nouvelles informations ;
6. création d'un bien en attente de validation ;
7. validation individuelle ;
8. validation par lots ;
9. refus d'une validation sans permission ;
10. conservation de l'audit ;
11. DataTable ;
12. pagination ;
13. recherche ;
14. filtrage ;
15. sélection multiple ;
16. action de validation groupée ;
17. absence de régression sur les fonctionnalités existantes.

==================================================
RÉSULTAT ATTENDU
==================================================

À la fin :

MODULE IMMOBILISATION

Bien
├── Informations existantes
├── Période d'entretien
├── Durée de vie
└── Statut de validation

Validation
├── Validation individuelle
└── Validation par lots

Tableaux
├── DataTable/Grid
├── Recherche
├── Filtrage
├── Pagination
├── Tri
└── Sélection multiple lorsque nécessaire

==================================================
CONTRAINTE FINALE — TRÈS IMPORTANTE
==================================================

Tu dois fonctionner selon cette règle pour CHAQUE modification :

ANALYSER
↓
RECHERCHER L'EXISTANT
↓
IDENTIFIER LES LOGIQUES RÉUTILISABLES
↓
VÉRIFIER LES DÉPENDANCES
↓
DÉTERMINER CE QUI MANQUE RÉELLEMENT
↓
ÉTENDRE L'EXISTANT SI POSSIBLE
↓
CRÉER UNIQUEMENT CE QUI N'EXISTE PAS
↓
TESTER
↓
VÉRIFIER LES RÉGRESSIONS

NE PAS :

- dupliquer les modèles ;
- dupliquer les endpoints ;
- dupliquer les validations ;
- dupliquer les composants DataTable ;
- dupliquer les permissions ;
- dupliquer les règles métier ;
- supprimer une logique existante sans nécessité ;
- réécrire inutilement des fonctionnalités déjà opérationnelles.

L'objectif est d'ÉTENDRE l'application existante, pas de reconstruire le module Immobilisation.
==================================================
CONTRAINTE — NOUVEAUX CHAMPS OPTIONNELS
==================================================

IMPORTANT :

AUCUN DES CHAMPS AJOUTÉS DANS LE CADRE DE CETTE MODIFICATION NE DOIT ÊTRE OBLIGATOIRE.

Cela concerne notamment :

- période d'entretien ;
- durée de vie du bien ;
- tout champ supplémentaire éventuellement ajouté pour la validation ;
- tout autre champ créé spécifiquement dans le cadre de cette demande.

Ces champs doivent être facultatifs.

L'utilisateur doit pouvoir :

- créer un bien sans renseigner la période d'entretien ;
- créer un bien sans renseigner la durée de vie ;
- créer un bien sans renseigner les nouveaux champs ajoutés dans cette évolution.

==================================================
BACKEND
==================================================

Au niveau du modèle Django et de l'API :

- ne pas rendre ces nouveaux champs obligatoires ;
- autoriser les valeurs NULL lorsque nécessaire ;
- autoriser les valeurs vides lorsque le type de champ le nécessite ;
- ne pas ajouter de validation `required=True` pour ces champs ;
- ne pas ajouter de contrainte `NOT NULL` pour ces nouveaux champs ;
- ne pas bloquer la création ou la modification d'un bien lorsque ces informations ne sont pas renseignées.

Les serializers doivent également considérer ces champs comme facultatifs.

==================================================
FRONTEND
==================================================

Dans les formulaires de création et de modification :

- ne pas afficher ces champs comme obligatoires ;
- ne pas ajouter d'astérisque `*` indiquant qu'ils sont obligatoires ;
- ne pas empêcher la soumission du formulaire lorsqu'ils sont vides ;
- ne pas afficher d'erreur de validation lorsque ces champs ne sont pas renseignés.

Si une valeur est renseignée, elle doit évidemment être validée selon les règles métier correspondantes.

==================================================
RÈGLE GÉNÉRALE
==================================================

Pour toute cette évolution :

NOUVEAU CHAMP
      ↓
OPTIONNEL PAR DÉFAUT
      ↓
L'utilisateur peut le laisser vide
      ↓
Le système doit quand même permettre
la création/modification du bien.

Cette règle est prioritaire pour tous les nouveaux champs ajoutés dans cette tâche.

Ne pas modifier le caractère obligatoire des champs existants du modèle.

Si un champ existant est déjà obligatoire, conserver son comportement actuel.

La demande concerne UNIQUEMENT les nouveaux champs ajoutés dans cette évolution.