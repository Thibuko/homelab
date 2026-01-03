#!/bin/bash
# Configuration
SOURCE="/docker"
HOSTNAME=$(hostname)
DATE=$(date +%F)
DEST="/data/backups/docker"
FILENAME="${HOSTNAME}_docker_configs_${DATE}.tar.gz"

mkdir -p $DEST

echo "--- Début backup configs Docker ($HOSTNAME) ---"

# 1. On se déplace dans /docker pour avoir des chemins relatifs propres dans l'archive
cd $SOURCE

# 2. On cherche et on compresse tous les compose et .env
find . -maxdepth 2 -name 'compose.y*ml' -o -name '.env' | tar -czf $DEST/$FILENAME -T -

# 3. Rotation : on garde les 7 derniers jours
find $DEST -name "*_docker_configs_*.tar.gz" -mtime +7 -delete

echo "Backup des configurations terminé : $DEST/$FILENAME"
