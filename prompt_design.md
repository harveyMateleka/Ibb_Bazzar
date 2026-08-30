Règles UI/UX impératives

1. Bordures arrondies (border-radius)

Valeur maximale autorisée : 15px pour tous les éléments (boutons, inputs, cartes, panneaux).

Aucun élément ne doit avoir un border-radius supérieur à 15px.

Valeur conseillée : entre 5px et 15px selon l'élément.

2. Espacement des boutons (marges)

Tous les boutons (pas seulement ceux de la vente) doivent respecter une marge minimale de 5px en haut et en bas.

Aucun bouton ne doit être collé :

Contre un autre élément (input, texte, bord de panneau).

Contre le bord supérieur ou inférieur de son conteneur.

Appliquer systématiquement : margin-top: 5px; margin-bottom: 5px; (ou padding équivalent).

3. Dimensions des deux panneaux

Le panneau de droite (détail/panier) est actuellement trop petit en largeur.

Action : Redimensionner le panneau de droite pour qu'il ait la même largeur que le panneau de gauche.

Les deux panneaux doivent occuper des espaces égaux en largeur (ex. flex: 1 ou grid-template-columns: 1fr 1fr).

La hauteur des deux panneaux doit rester égale (alignement vertical parfait).

Rappel des autres corrections déjà validées

Suppression des filtres (recherche uniquement par nom dans table des variantes).

Affichage horizontal (carrousel) avec groupes de 2 cartes.

Chargement correct des prix (normal et minimum) dans les cartes de gauche.

Séparation visuelle entre les deux panneaux.

Effet neumorphisme (box-shadow) sur les deux panneaux.

Résultat attendu
Une interface avec des arrondis modérés (≤ 15px), des boutons correctement espacés (marge ≥ 5px), et deux panneaux de largeur égale, bien alignés et harmonieux.