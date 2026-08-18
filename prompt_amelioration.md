je veux que tu enregistre ces nouvelles exigences fonctionnelles et UX pour les intégrer ensuite au prompt, sans encore réécrire toute l'architecture.

Voici précisément ce qui est ajouté à la logique de création/validation d'une vente Boutique :

1. Vente en deux étapes

Étape 1 — Informations générales de la vente

Afficher uniquement les informations qui peuvent être renseignées avant de connaître les articles :

client ;
succursale / contexte Boutique ;
mode de paiement ;
autres informations générales nécessaires.
NB:supprime le champs montant_reçus  dans l'etape premiere 

Étape 2 — Articles et validation

Cette étape contient :

ajout des articles ;
quantité ;
prix unitaire ;
montant total ;
montant reçu ;
reste / monnaie à rendre ;
validation finale.
etc.....

Le montant reçu saisi par l'utilisateur doit être enregistré avec la vente.
Le système doit calculer automatiquement :
Monnaie = Montant reçu - Total vente
et contrôler que le paiement est cohérent.

NB: actuellement meme si le montant recus est inferieur au total prix cela passe au lieu que le system bloque cela avec un message à l'utilisateur

3. Message après chaque opération

Chaque soumission importante doit produire immédiatement un retour visuel clair.

Exemples :

Succès :

Vente enregistrée avec succès.

Erreur :

Impossible d'enregistrer la vente. Veuillez vérifier les informations saisies.

Cela doit être appliqué aux opérations pertinentes, pas uniquement à la vente :

création ;
modification ;
suppression ;
ajout ;
validation ;
entrée stock ;
sortie stock ;
inventaire ;
etc.

L'utilisateur doit toujours savoir si son opération a réussi ou échoué.

4. Prix unitaire automatiquement prérempli

Dans l'ajout d'un article :

Article
Quantité
Prix unitaire

Lorsqu'un article est sélectionné :

afficher le prix normal ;
afficher le prix minimum ;
afficher éventuellement le prix maximum ;
préremplir automatiquement le champ Prix unitaire avec le prix normal de l'article.

Actuellement, le composant affiche les prix mais ne renseigne pas automatiquement le prix unitaire : corriger ce comportement.

L'utilisateur pourra éventuellement modifier le prix unitaire selon ses permissions et les règles métier, notamment le contrôle du prix minimum.


5. Ne pas afficher trois lignes d'articles par défaut

Actuellement, l'interface affiche plusieurs blocs identiques pour ajouter les articles.

Ce comportement doit être supprimé.

Il doit y avoir une seule ligne de saisie initiale :

Article | Quantité | Prix unitaire | Montant | Action

L'utilisateur ajoute son premier article.

Puis :

+ Ajouter un article

permet d'ajouter dynamiquement une nouvelle ligne.

Exemple :

┌──────────────────────────────────────────────────────┐
│ Article     Quantité   Prix unitaire   Montant       │
│ T-shirt M      2          20 000       40 000   🗑   │
└──────────────────────────────────────────────────────┘


[ + Ajouter un article ]

Puis après ajout :

T-shirt M       2    20 000    40 000
Jean bleu       1    35 000    35 000
Polo blanc      3    15 000    45 000

Les lignes sont donc créées dynamiquement, et non préaffichées trois fois.

Le bouton de suppression doit permettre de retirer une ligne du panier.

6. Logique UX recherchée

Le fonctionnement doit être proche d'un panier :

Sélectionner article
        ↓
Quantité
        ↓
Prix automatiquement prérempli
        ↓
Ajouter au panier
        ↓
Article ajouté
        ↓
Nouvelle ligne disponible
        ↓
Ajouter éventuellement un autre article

Le formulaire reste donc compact et ne prend pas inutilement de place.

7. Résultat attendu

La deuxième étape devrait globalement être organisée ainsi :

┌─────────────────────────────────────────────┐
│ ARTICLES                                    │
│                                             │
│ Article | Qté | Prix | Montant | Action     │
│ T-shirt |  2  | 20k  | 40k     | 🗑         │
│ Jean    |  1  | 35k  | 35k     | 🗑         │
│                                             │
│ [+ Ajouter un article]                      │
└─────────────────────────────────────────────┘


Total :             75 000 FC
Montant reçu :      80 000 FC
Monnaie :             5 000 FC


             [ Valider la vente ]

Et après validation réussie :

Vente enregistrée avec succès.

8. le controle du saisie du prix unitaire ne se fait pas, meme quand le prix et inférieur au prix minimal ou suppérieur au prix maximal , le system n'intercepte rien jusque la pour bloquer cette erreur.

Le formulaire doit ensuite être remis dans un état cohérent pour permettre une nouvelle vente, selon le comportement actuel de l'application.

J'ai donc bien séparé dans cette logique les informations générales de la vente, le panier dynamique, le paiement et le retour utilisateur après opération.