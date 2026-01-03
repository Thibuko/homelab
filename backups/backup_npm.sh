#!/bin/bash
# Configuration
SOURCE="/docker/npm"  # À ajuster selon votre chemin réel
DEST="/data/backups/npm"
CONTAINER_NAME="nginx-proxy-manager"
HOSTNAME=$(hostname)
DATE=$(date +%F)
TMP_FILE="/tmp/${HOSTNAME}_npm_backup_${DATE}.tar.gz"

mkdir -p $DEST

echo "--- Début backup NPM ($HOSTNAME) ---"

# 1. Arrêt de NPM pour figer la base SQLite
docker stop $CONTAINER_NAME

# 2. Archive complète (Config + Certificats)
# On inclut tout le dossier car il est léger
tar -czf $TMP_FILE -C $SOURCE .

# 3. Redémarrage immédiat
docker start $CONTAINER_NAME

# 4. Transfert vers le stockage CIFS
mv $TMP_FILE $DEST/

# 5. Rotation (7 jours)
find $DEST -name "${HOSTNAME}_npm_backup_*.tar.gz" -mtime +7 -delete

echo "Backup NPM terminé."
