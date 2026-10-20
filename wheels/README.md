Ce dossier peut contenir les paquets téléchargés pour une construction hors ligne :

python -m pip download --only-binary=:all: -r requirements.txt -d wheels

docker compose build --build-arg PIP_NO_INDEX=1

Les fichiers .whl ne sont pas suivis par Git. La construction normale utilise PyPI.
