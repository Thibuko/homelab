#!/bin/bash
# Configuration
HOMARR_DIR="/docker/homarr"
BACKUP_DEST="/data/backups/homarr"
CONTAINER_NAME="homarr"

mkdir -p $BACKUP_DEST

# 1. Arrêter Homarr pour figer la base de données
docker stop $CONTAINER_NAME

# 2. Créer l'archive
tar -czf $BACKUP_DEST/homarr_backup_$(date +%F).tar.gz -C $HOMARR_DIR appdata

# 3. Redémarrer Homarr
docker start $CONTAINER_NAME

# 4. Nettoyage (garde 7 jours)
find $BACKUP_DEST -name "*.tar.gz" -mtime +7 -delete

echo "Backup Homarr terminé."
