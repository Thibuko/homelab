#!/bin/bash
# Configuration
CONTAINER_NAME="immich_postgres"
DB_USER="postgres"
DB_NAME="immich"
DEST="/data/backups/immich"
HOSTNAME=$(hostname)
DATE=$(date +%F)

mkdir -p $DEST

echo "--- Début backup Immich DB ($HOSTNAME) ---"

# 1. Dump de la base de données PostgreSQL
# Cette méthode est propre et évite les problèmes de fichiers verrouillés
docker exec -t $CONTAINER_NAME pg_dumpall -c -U $DB_USER > $DEST/${HOSTNAME}_immich_db_${DATE}.sql

# 2. Compression immédiate pour gagner de la place (très efficace sur du .sql)
gzip -f $DEST/${HOSTNAME}_immich_db_${DATE}.sql

# 3. Rotation : on garde les 7 derniers jours
find $DEST -name "${HOSTNAME}_immich_db_*.sql.gz" -mtime +7 -delete

echo "Backup Immich terminé : ${HOSTNAME}_immich_db_${DATE}.sql.gz"
