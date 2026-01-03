#!/bin/bash
# Configuration
SOURCE="/docker/servarr"
DEST="/data/backups/servarr"
TMP_FILE="/tmp/servarr_full_backup_$(date +%F).tar.gz"

mkdir -p $DEST
rm -f /tmp/servarr_full_backup_*.tar.gz

echo "Début du backup de la stack Servarr..."

# 1. On stoppe toute la stack d'un coup pour figer les bases SQLite
cd $SOURCE
docker compose down

# 2. Archive complète en excluant les dossiers inutiles
# On exclut les logs et les backups internes pour chaque appli
tar -czf $TMP_FILE \
    --exclude='**/logs' \
    --exclude='**/Backups' \
    --exclude='qbittorrent/BT_backup' \
    -C $SOURCE .

# 3. On relance la stack immédiatement
docker compose up -d

# 4. On déplace l'archive vers le stockage CIFS
mv $TMP_FILE $DEST/

# 5. Nettoyage (7 jours)
find $DEST -name "*.tar.gz" -mtime +7 -delete

echo "Backup Servarr terminé avec succès."
