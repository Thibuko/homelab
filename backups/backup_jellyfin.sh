#!/bin/bash
# Configuration
CONTAINER_NAME="jellyfin"
SOURCE="/docker/jellyfin/config"
DEST="/data/backups/jellyfin"
TMP_FILE="/tmp/jellyfin_backup_$(date +%F).tar.gz"

mkdir -p $DEST
rm -f /tmp/jellyfin_backup_*.tar.gz

echo "Début du backup Jellyfin..."

# 1. Arrêt du conteneur
docker stop $CONTAINER_NAME

# 2. Création de l'archive en LOCAL (beaucoup plus rapide avec cache=none)
tar -czf $TMP_FILE --exclude='cache' --exclude='metadata/People' -C $SOURCE .

# 3. Redémarrage immédiat
docker start $CONTAINER_NAME

# 4. Déplacement vers le montage CIFS
mv $TMP_FILE $DEST/

# 5. Nettoyage (7 jours)
find $DEST -name "*.tar.gz" -mtime +7 -delete

echo "Backup Jellyfin terminé et déplacé vers /data."
