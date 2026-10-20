# Onde — Atelier XMLTV

Application web personnelle pour VPS, écrite indépendamment de XML-TV-Fr. Configurez plusieurs pages de programmes TV, récupérez leurs données et servez un guide XMLTV à vos lecteurs EPG.

## Démarrage local

Python 3.12 recommandé.

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python server.py
```

Le serveur écoute sur le port 3000, sur l'interface locale par défaut. Aucun compte ni source n'est préconfiguré. Les réglages et programmes sont enregistrés dans `data/state.json` (écriture atomique). Sauvegardez ce dossier.

## Sur votre VPS avec Docker Compose

```sh
docker compose up -d --build
```

Le volume `onde-data` conserve la configuration. Le port publié est limité à `127.0.0.1:3000` : placez votre reverse proxy HTTPS devant ce port. Protégez l'ensemble du service par une authentification au niveau du proxy, ou définissez **les deux** variables `ONDE_USER` et `ONDE_PASSWORD` dans le service Compose, avec des valeurs privées fournies par votre gestionnaire de secrets. Le navigateur demandera alors une connexion. Utilisez HTTPS ; les identifiants Basic ne sont pas chiffrés par HTTP. L'authentification s'applique aussi aux flux XML ; configurez votre lecteur en conséquence.

Ce service est un outil d'administration personnel : un utilisateur autorisé peut demander des URL depuis le VPS, y compris sur son réseau local. Ne le rendez pas accessible à des utilisateurs non fiables. Le serveur intégré convient à un usage personnel derrière un proxy, sans authentification multi-utilisateur.

Variables : `HOST` (défaut `127.0.0.1`, `0.0.0.0` dans Docker), `PORT` (3000), `ONDE_DATA` (dossier `data`), `ONDE_USER`, `ONDE_PASSWORD`.

## Configurer une source

1. Ouvrez **Sources & chaînes**, indiquez le nom de la chaîne, son identifiant XMLTV unique et l'URL de sa page de programmes.
2. Essayez **JSON-LD** si la page contient des événements avec `name`, `startDate` et `endDate` (le nom peut aussi être sous `workPerformed.name`).
3. Sinon, choisissez **HTML / CSS** et renseignez le bloc de chaque programme, son titre, son début et sa fin. La syntaxe `.debut@datetime` lit l'attribut `datetime` ; `h3` lit le texte.
4. Les dates doivent être complètes au format ISO 8601. Si elles n'ont pas de décalage, le fuseau de la source est utilisé. Les sites qui n'affichent que `20:30` nécessitent un connecteur supplémentaire.
5. Cliquez sur **Récupérer les programmes**. Les résultats apparaissent dans le guide ; choisissez la date concernée. L'affichage utilise Europe/Paris.

Chaque source correspond actuellement à une chaîne. Vous pouvez la modifier ou la supprimer. Une collecte réussie remplace les programmes de cette chaîne ; une collecte échouée conserve ses derniers résultats et affiche une erreur. La collecte est séquentielle, avec un délai de 25 secondes par requête et une limite de 5 Mo par page.

Une URL seule ne permet pas de décoder tous les sites. Cette version ne lance pas de navigateur JavaScript, ne gère ni connexion à un fournisseur, ni CAPTCHA, ni pagination, ni repli entre plusieurs fournisseurs d'une même chaîne. Elle ne reprend pas les connecteurs de l'archive. Respectez les conditions du site source et limitez la fréquence des collectes.

## Flux XMLTV et automatisation

- `/guide.xml` : guide UTF-8.
- `/guide.xml.gz` : même guide compressé gzip.
- `POST /api/grab` avec un corps `{}` : collecte de toutes les sources.

Vous pouvez appeler ce dernier endpoint avec un minuteur système ou cron pour programmer les mises à jour. Sans authentification, sur le VPS local :

```sh
curl --fail --silent --show-error -X POST -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:3000/api/grab
```

Avec authentification, utilisez un fichier de configuration curl privé pour les identifiants. La réponse JSON contient `errors` : une collecte partiellement échouée renvoie un HTTP 200 avec les erreurs par source. Aucune planification n'est activée automatiquement.

## Vérification

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check public/app.js
```

Le test fonctionnel lance deux serveurs temporaires et exerce configuration multi-source, collecte JSON-LD et HTML, export XML et gzip, persistance, conservation des programmes en cas d'échec et suppression de source. Les sites tiers réels dépendent des URL et sélecteurs que vous configurerez.

Si la construction Docker n'a pas accès à PyPI (DNS isolé), téléchargez préalablement les paquets depuis une machine disposant d'un accès HTTPS vérifié :

```sh
.venv/bin/python -m pip download --only-binary=:all: -r requirements.txt -d wheels
docker compose build --build-arg PIP_NO_INDEX=1
docker compose up -d --no-build
```

## Source TF1 demandée

URL cible : `https://www.tf1.fr/tf1/direct`. Sa collecte n'est pas encore validée : le proxy de l'environnement cloud refuse actuellement l'accès au domaine `www.tf1.fr`. Ce domaine a été ajouté au brouillon des paramètres réseau. Après application de cette modification, il faudra inspecter la page pour déterminer si le guide est présent dans le HTML, les données structurées ou une requête JavaScript. Aucun connecteur TF1 fonctionnel n'est annoncé à ce stade.
