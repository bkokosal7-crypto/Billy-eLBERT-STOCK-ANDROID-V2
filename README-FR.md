# Billy-eLBERT STOCK — préparation Android

Ce dossier contient le `main.py` fourni et un workflow GitHub Actions pour tenter de construire un APK Android ARM64 avec l'outil officiel Qt for Python `pyside6-android-deploy`.

## Important
- Ce ZIP **n'est pas encore un APK**. La compilation Android doit s'exécuter sur le runner Linux de GitHub Actions, avec le SDK/NDK et les wheels Android.
- Le `main.py` passe la vérification de syntaxe Python, mais cela ne prouve pas que toutes les fonctions de l'application fonctionnent sous Android.
- Le fichier source recherche le dossier `Ressources` (avec deux « s ») à côté de `main.py`. Si tu utilises le logo ou une base initiale, ajoute le dossier réel `Ressources/` au dépôt GitHub avant de lancer la compilation.
- Le programme contient quelques opérations propres à Windows (par exemple `os.startfile`). Elles peuvent nécessiter une adaptation si elles sont exécutées sous Android. Il faut donc tester l'APK sur téléphone après compilation.

## Étapes GitHub
1. Crée un dépôt GitHub, par exemple `Billy-eLBERT-STOCK-ANDROID`.
2. Envoie à la racine du dépôt `main.py`, le dossier `Ressources` (s'il existe), et le dossier `.github/workflows/`.
3. Dans GitHub, ouvre **Actions**.
4. Sélectionne **Construire APK Android - Billy-eLBERT STOCK**.
5. Appuie sur **Run workflow** puis confirme.
6. Attends que le travail se termine en vert. Si l'étape échoue, ouvre cette étape et récupère le journal d'erreur.
7. Dans la page du workflow terminé, sous **Artifacts**, télécharge `Billy-eLBERT-STOCK-APK-ARM64`.
8. Décompresse l'archive téléchargée et installe `Billy-eLBERT-STOCK-ARM64.apk` sur ton téléphone Android. Il peut être nécessaire d'autoriser l'installation depuis cette source.

## Si la compilation échoue
Envoie le journal complet de l'étape rouge. Il faut corriger l'erreur réelle affichée par Qt/Buildozer, sans remplacer ton application par un autre framework.
