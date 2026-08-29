PROMPT — AJUSTEMENTS DU WORKFLOW DE VENTE
CONSIGNE GÉNÉRALE — À RESPECTER AVANT CHAQUE ÉTAPE

Avant de commencer chaque modification :

Lire le code actuellement implémenté.
Identifier précisément comment fonctionne actuellement :
Vente ;
LigneVente ;
les statuts ;
le prix normal ;
le prix minimum ;
le prix proposé ;
le prix retenu ;
le calcul des montants ;
le panier ;
la soumission ;
le traitement par le responsable ;
la confirmation par l'opérateur ;
le mouvement de stock.
Vérifier si la logique demandée existe déjà.
Réutiliser et corriger la logique existante plutôt que créer une nouvelle logique parallèle.
Ne pas créer de doublons de champs, fonctions, vues, services ou validations.
Ne pas casser les fonctionnalités qui fonctionnent déjà.
Après chaque étape, tester uniquement la partie concernée avant de passer à l'étape suivante.
ÉTAPE 1 — UNE LIGNE ANNULÉE NE DOIT PAS ÊTRE CONFIRMÉE SANS PRIX RETENU

Corriger la logique de confirmation de la vente.

Une vente ne doit pas pouvoir être confirmée si une ligne destinée à être exécutée ne possède pas de prix retenu valide.

Le responsable doit obligatoirement prendre une décision sur chaque ligne qui doit participer à la vente.

Pour chaque ligne, il doit donc exister un prix final/reténu permettant de déterminer le montant réellement facturé.

Exemple
Article : Chemise
Prix normal : 30 000
Prix minimum : 25 000
Prix proposé : 27 000
Prix retenu : 26 000

Le prix retenu est celui qui sera utilisé pour le montant final.

Cas d'une ligne annulée

Si une ligne est annulée/invalide et qu'elle ne possède pas de prix retenu alors que cette ligne doit encore être prise en compte dans la vente :

→ la confirmation doit être bloquée.

Afficher un message explicite indiquant au responsable/opérateur ce qui manque.

Ne pas simplement laisser la vente échouer silencieusement.

Attention

Avant d'implémenter cette règle, analyser le comportement actuel des lignes annulées.

Ne pas supposer qu'une ligne annulée doit toujours bloquer la vente : déterminer dans le code si elle est censée être retirée de la vente finale ou si elle nécessite une décision complémentaire.

L'objectif est d'éviter qu'une vente soit confirmée avec une ligne sans prix final exploitable.

ÉTAPE 2 — LE RESPONSABLE DOIT OBLIGATOIREMENT RETENIR UN PRIX

Dans l'interface du responsable, chaque ligne qui doit être exécutée doit permettre au responsable de déterminer clairement le prix retenu.

Le responsable peut :

accepter le prix normal ;
accepter le prix proposé ;
proposer un autre prix autorisé ;
invalider/annuler la ligne lorsque le produit ne doit pas être vendu.

Mais au moment où une ligne est destinée à être exécutée :

prix_retenu ≠ NULL

et le prix doit être valide selon les règles métier existantes.

Le prix retenu doit être contrôlé par rapport au prix minimum :

prix_retenu >= prix_minimum

Si cette règle existe déjà, la réutiliser.

ÉTAPE 3 — AJOUTER UNE POSSIBILITÉ DE MODIFIER LE TRAITEMENT

Le responsable doit pouvoir modifier le traitement d'une vente lorsque cela est nécessaire.

Il faut notamment gérer le cas où :

le responsable a invalidé une ligne ;
il souhaite revenir sur sa décision ;
il veut modifier le statut d'une ligne ;
il veut réexaminer une ligne ;
une erreur a été commise lors du traitement.

Ajouter une action Modifier dans l'interface du responsable, uniquement si cette action n'existe pas déjà.

Cette action doit permettre de revenir sur le traitement selon les règles métier autorisées.

Exemple
Vente
 ├── Ligne A → Validée
 ├── Ligne B → Annulée
 └── Ligne C → Validée

Le responsable clique sur :

Modifier le traitement

Il peut alors réexaminer les lignes et modifier les décisions autorisées.

Important

Ne pas permettre de modifier arbitrairement une vente déjà confirmée et ayant déjà généré un mouvement de stock.

Il faut vérifier les statuts existants avant de définir les transitions autorisées.

ÉTAPE 4 — CORRIGER DÉFINITIVEMENT LA LOGIQUE DU PRIX RETENU

Il y a actuellement une incohérence importante :

Le prix retenu semble rester égal au prix normal alors que le total de la facture utilise parfois un autre montant.

Cette incohérence doit être supprimée.

Nouvelle règle

Le prix retenu est le prix réellement utilisé pour calculer la vente finale.

Exemple normal :

Prix normal    : 30 000
Prix minimum   : 25 000
Prix proposé   : 30 000
Prix retenu    : 30 000

Montant :

30 000 × quantité
Exemple avec réduction
Prix normal    : 30 000
Prix minimum   : 25 000
Prix proposé   : 27 000
Prix retenu    : 27 000

La facture doit alors utiliser :

27 000 × quantité

et non :

30 000 × quantité
ÉTAPE 5 — LE TOTAL DE LA VENTE DOIT ÊTRE BASÉ SUR LE PRIX RETENU

Corriger le calcul afin d'avoir une seule source de vérité.

Pour chaque ligne :

montant_final = quantité × prix_retenu

Puis :

total_vente = somme(montant_final de toutes les lignes exécutées)

Les lignes annulées ne doivent pas entrer dans le montant final de la vente.

Exemple
Chemise
Qté : 2
Prix normal : 30 000
Prix retenu : 27 000

Montant normal = 60 000
Montant final  = 54 000

La facture doit afficher 54 000, pas 60 000.

ÉTAPE 6 — DISTINGUER LES MONTANTS POUR ÉVITER TOUTE CONFUSION

Conserver les informations nécessaires pour permettre au responsable de comprendre l'écart.

Pour chaque ligne :

Article / Variante
Quantité
Prix normal
Prix minimum
Prix proposé
Prix retenu
Montant normal
Montant final
Écart
Statut
Exemple
Prix normal     : 30 000
Prix proposé    : 27 000
Prix retenu     : 26 000

Montant normal  : 60 000
Montant final   : 52 000
Écart           : 8 000

Le prix retenu doit donc être cohérent avec le montant final.

Il ne doit plus être possible d'avoir :

Prix affiché : 30 000
Total calculé : 28 000

sans explication.

ÉTAPE 7 — SUPPRIMER LA SAISIE DU MONTANT REÇU

Modifier le formulaire de vente afin que l'utilisateur ne saisisse plus manuellement le montant reçu.

Le champ montant reçu ne doit plus être présenté dans l'interface de saisie si cela n'est pas nécessaire.

Nouvelle règle

Le montant reçu doit être calculé automatiquement :

montant_reçu = total_de_la_facture

Donc si :

Total facture = 52 000

alors :

Montant reçu = 52 000

Cela évite les incohérences de saisie.

IMPORTANT

Si le champ existe déjà en base de données et qu'il est utilisé ailleurs :

ne pas le supprimer automatiquement.

Vérifier d'abord :

où il est utilisé ;
s'il est nécessaire pour les anciennes ventes ;
s'il est utilisé dans les reçus ;
s'il est utilisé dans les rapports ;
s'il est utilisé dans les calculs.

Si nécessaire, conserver le champ en base mais ne plus permettre sa saisie manuelle dans le nouveau formulaire.

ÉTAPE 8 — CONSERVER LES CALCULS EXISTANTS DE MONNAIE

Vérifier la logique actuelle concernant :

total ;
montant reçu ;
monnaie ;
remise.

Ne pas supprimer les calculs existants sans analyse.

Avec la nouvelle règle :

montant_reçu = total_facture

la monnaie devrait naturellement être cohérente avec cette valeur selon la logique de paiement existante.

Adapter uniquement ce qui est nécessaire.

ÉTAPE 9 — NE JAMAIS VIDER LE PANIER EN CAS D'ERREUR

C'est un point très important pour l'expérience utilisateur.

Actuellement, lorsqu'une soumission du panier rencontre une erreur, le panier peut être vidé.

Corriger ce comportement.

Si la soumission échoue :

Panier avant soumission
        ↓
Validation
        ↓
ERREUR
        ↓
Panier CONSERVÉ

Le panier doit rester exactement avec :

les mêmes variantes ;
les mêmes quantités ;
les mêmes prix proposés ;
les mêmes informations saisies.

L'utilisateur doit pouvoir corriger l'erreur puis resoumettre.

ÉTAPE 10 — TRANSACTION : NE PAS PERSISTER PARTIELLEMENT UNE VENTE EN CAS D'ERREUR

Analyser le processus actuel de création/soumission.

Il ne faut pas avoir un scénario comme :

Ligne 1 enregistrée
Ligne 2 enregistrée
Ligne 3 → erreur
→ panier vidé

ou :

Vente créée
+
certaines lignes enregistrées
+
erreur
+
état incohérent

Utiliser la logique transactionnelle déjà présente dans le projet si elle existe.

Si la soumission échoue, l'utilisateur doit pouvoir corriger son panier sans perdre ses données.

ÉTAPE 11 — VALIDATION FINALE AVANT CONFIRMATION

Au moment où l'opérateur clique sur :

Confirmer la vente

le système doit effectuer les contrôles finaux.

Vérifier notamment :

Pour chaque ligne exécutée
Variante valide
Quantité valide
Stock disponible
Prix retenu présent
Prix retenu >= prix minimum
Statut de ligne compatible avec l'exécution

Puis seulement après :

Calcul du total
        ↓
Confirmation
        ↓
Mouvement SORTIE
        ↓
Décrémentation du stock
ÉTAPE 12 — NE PAS DÉCLENCHER LE STOCK AVANT LA CONFIRMATION

Conserver impérativement la règle déjà définie :

Responsable
    ↓
Traite la vente
    ↓
PAS DE MOUVEMENT STOCK
    ↓
Opérateur
    ↓
Confirme
    ↓
MOUVEMENT SORTIE
    ↓
STOCK DIMINUÉ

Le responsable peut donc modifier le traitement sans provoquer prématurément une sortie de stock.

ÉTAPE 13 — TESTS OBLIGATOIRES

Après les modifications, tester ces scénarios.

Test 1 — Vente normale
Prix normal = 30 000
Prix proposé = 30 000
Prix retenu = 30 000

→ vente confirmable.

Test 2 — Prix proposé inférieur au prix normal
Prix normal = 30 000
Prix minimum = 25 000
Prix proposé = 27 000
Prix retenu = 27 000

→ total basé sur 27 000.

Test 3 — Prix inférieur au minimum
Prix normal = 30 000
Prix minimum = 25 000
Prix retenu = 20 000

→ confirmation interdite.

Test 4 — Prix retenu absent
Prix normal = 30 000
Prix proposé = 27 000
Prix retenu = NULL

→ confirmation interdite.

Test 5 — Ligne annulée

Une ligne est annulée par le responsable.

→ elle ne doit pas être incluse dans le total final ni dans la sortie de stock si le workflow la retire effectivement de la vente.

Test 6 — Modification du traitement

Le responsable traite une vente.

→ il peut utiliser l'action Modifier pour revenir au traitement lorsque le statut le permet.

Test 7 — Montant reçu

Total :

52 000

→ montant reçu automatiquement :

52 000

→ aucun champ permettant à l'opérateur de saisir arbitrairement une autre valeur.

Test 8 — Erreur pendant la soumission

Ajouter plusieurs articles puis provoquer volontairement une erreur.

Résultat attendu :

❌ Soumission refusée
✅ Message d'erreur clair
✅ Panier conservé
✅ Quantités conservées
✅ Prix proposés conservés
Test 9 — Confirmation

Après traitement responsable :

Aucun mouvement de stock

Après confirmation opérateur :

Mouvement SORTIE créé
Stock diminué
Vente confirmée
CONSIGNE FINALE

Ne réalise pas toutes ces modifications en une seule fois.

Travaille exactement dans cet ordre :

1. Prix retenu obligatoire
        ↓
2. Traitement/modification responsable
        ↓
3. Correction du calcul prix retenu → montant final
        ↓
4. Suppression de la saisie montant reçu
        ↓
5. Conservation du panier en cas d'erreur
        ↓
6. Vérification du workflow stock
        ↓
7. Tests complets

Après chaque étape :

Lire le code existant → modifier uniquement ce qui est nécessaire → tester → vérifier qu'aucun doublon ni régression n'a été introduit → seulement ensuite passer à l'étape suivante.

Ne change surtout pas le fonctionnement du stock ou des mouvements existants sans avoir identifié exactement où et quand ils sont actuellement déclenchés.