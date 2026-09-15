# Rapport de régression extraction V6

Les dossiers ADEIS, GEOTEHNIKA, EUROMEDIA, DMT, STERIFIL, FLUX VERT n’ont pas
été relancés dans ce lot (extracteur V6 non modifié).

Changements mapping susceptibles d’affecter les valeurs **sans** toucher V6 :

- CA dérivé : plus de `usable or 0` — une composante manquante ⇒ CA non utilisable
- Achats : plus de fallback « l’autre composante »
- Dettes CT : somme déterministe crédits trésorerie + escompte, pas first-wins
- Multi-liasse : conflit SOURCE_CONFLICT au lieu de first-wins
- Score axe 3 : plus de médianes Transport par défaut

Avant relance V6 : noter le nombre de champs usable par dossier.
Après : usable ne doit pas augmenter en transformant des suspects en valides.
Si un dossier n’est plus scorable, c’est préférable à un faux score.
