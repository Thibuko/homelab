#!/bin/bash
# Configuration
SOURCE="/docker/convertx"
DEST="/data/backups/convertx"
CONTAINER_NAME="convertx" # À vérifier avec 'docker ps'

mkdir -p $DEST

# 1. On fige le conteneur pour éviter la corruption de la DB SQLite (WAL)
docker stop $CONTAINER_NAME

# 2. Création de l'archive (on exclut les médias)
tar -czf $DEST/convertx_backup_$(date +%F).tar.gz \
    -C $SOURCE compose.yml \
    -C $SOURCE/data mydb.sqlite mydb.sqlite-shm mydb.sqlite-wal

# 3. Redémarrage
docker start $CONTAINER_NAME

# 4. Nettoyage (7 jours)
find $DEST -name "*.tar.gz" -mtime +7 -delete

echo "Backup ConvertX terminé."
