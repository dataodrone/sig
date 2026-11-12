# AI Segmentation Local (gratuit, 100 % local)

Plugin QGIS du même type que les plugins de segmentation IA payants (type « AI Segmentation »), mais **entièrement gratuit et local** : aucun compte, aucune clé API, aucun abonnement, aucun crédit. Les modèles sont ouverts (SAM + CLIP), téléchargés une seule fois puis utilisés hors ligne sur votre machine (CPU suffisant, pas besoin de carte graphique).

## Ce que fait le plugin

- **Mode automatique** : vous dessinez une zone sur votre image, vous tapez ce que vous cherchez (« bâtiments », « arbres », « panneaux solaires »…) et vous obtenez tous les objets correspondants sous forme de polygones vectoriels, avec un score de confiance.
- **Mode semi-auto** : vous cliquez sur un objet (clic gauche, plusieurs clics possibles ; clic droit = point négatif) et vous obtenez son contour propre.

Fonctionne sur n'importe quelle couche raster : GeoTIFF, JPG, PNG, et fonds de carte en ligne (WMS, tuiles XYZ).

## Installation

1. Copiez le dossier `ai_segmentation_local` dans le dossier des plugins de votre profil QGIS
   (`%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins` sous Windows,
   `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins` sous Linux,
   `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins` sous macOS),
   ou bien zippez-le et installez-le via *Extensions → Installer depuis un ZIP*.
2. Activez « AI Segmentation Local » dans le gestionnaire d'extensions.
3. Au premier lancement, cliquez sur **« Run detection »** : le plugin installe automatiquement PyTorch (CPU) et les bibliothèques dans son propre dossier `.deps`, puis télécharge les modèles ouverts (~700 Mo au total, une seule fois, sources publiques). Ensuite, tout fonctionne **hors ligne**.

## Utilisation

1. Ouvrez une couche raster (ou un fond de carte en ligne).
2. Choisissez le mode, puis cliquez sur **« Draw a detection zone »** (mode auto) ou **« Click the object »** (mode semi-auto).
3. Pressez **« Run detection (local, free) »**.
4. Les polygones arrivent dans la couche mémoire « AI Segmentation (local) » (champs : `label`, `confidence`, `area_m2`, `mode`). Exportez-les en GeoPackage avec le bouton prévu.

## Confidentialité

Rien n'est envoyé sur le réseau pendant l'inférence : l'image reste sur votre machine. Seuls les poids des modèles (fichiers publics) sont téléchargés au premier run.

## Limites

- Sur CPU, la détection automatique est pensée pour des zones modestes (la zone est rééchantillonnée à 1536 px max). Pour de très grandes étendues, découpez en plusieurs zones.
- La correspondance texte ↔ objet repose sur CLIP : les libellés anglais donnent généralement de meilleurs résultats (« buildings », « trees », « solar panels »).

## Licence

MIT — code libre, réutilisable sans restriction.
