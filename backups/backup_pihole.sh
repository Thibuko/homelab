#!/bin/bash
set -euo pipefail

CONTAINER="pihole"
DEST="/data/backups/pihole"
MAX_AGE_DAYS=7
TELEPORTER_TIMEOUT="180s"
FIND_INTERVAL_SECONDS=10

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*"
}

log "Début de la sauvegarde pour $CONTAINER."

if ! docker container inspect "$CONTAINER" > /dev/null 2>&1; then
    log "Erreur : conteneur $CONTAINER introuvable ou arrêté."
    exit 1
fi

mkdir -p "$DEST"

# 1. Générer le backup (timeout pour éviter un blocage silencieux)
log "Exécution de teleporter (limite $TELEPORTER_TIMEOUT)."
if ! timeout "$TELEPORTER_TIMEOUT" docker exec "$CONTAINER" pihole-FTL --teleporter > /dev/null 2>&1; then
    log "Erreur : teleporter a échoué ou a expiré."
    exit 1
fi

TELEPORTER_TIMEOUT_SECONDS=${TELEPORTER_TIMEOUT%s}
if ! [[ "$TELEPORTER_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]]; then
    log "Erreur : TELEPORTER_TIMEOUT doit être un entier suivi de 's'."
    exit 1
fi
FIND_MAX_ATTEMPTS=$(( TELEPORTER_TIMEOUT_SECONDS / FIND_INTERVAL_SECONDS ))
if [ "$FIND_MAX_ATTEMPTS" -lt 1 ]; then
    FIND_MAX_ATTEMPTS=1
fi

# 2. Localiser au moins UN fichier (attente que la génération soit finie)
log "Recherche de fichiers teleporter dans le conteneur (toutes les ${FIND_INTERVAL_SECONDS}s, max ${FIND_MAX_ATTEMPTS} tentatives)."
FOUND_ANY=""
for attempt in $(seq 1 "$FIND_MAX_ATTEMPTS"); do
    sleep "$FIND_INTERVAL_SECONDS"
    # On vérifie juste si un fichier existe
    if CHECK_OUTPUT=$(docker exec "$CONTAINER" find / -maxdepth 1 -name "pi-hole*teleporter*.zip" -print | head -n 1); then
        if [ -n "$CHECK_OUTPUT" ]; then
            FOUND_ANY="true"
            break
        fi
    else
        log "Avertissement : la commande de recherche a retourné une erreur (transitoire ?). On réessaie..."
    fi
    log "Aucun fichier trouvé pour l'instant (tentative $attempt/$FIND_MAX_ATTEMPTS). Nouvelle vérification dans ${FIND_INTERVAL_SECONDS}s."
done

if [ -z "$FOUND_ANY" ]; then
    log "Erreur : aucun fichier teleporter détecté après le timeout."
    exit 1
fi

# 3. Récupérer et traiter TOUS les fichiers trouvés (self-healing)
log "Récupération de la liste complète des fichiers de sauvegarde..."
# On récupère tous les fichiers correspondants
ALL_FILES=$(docker exec "$CONTAINER" find / -maxdepth 1 -name "pi-hole*teleporter*.zip" -print)

if [ -z "$ALL_FILES" ]; then
    # Cela ne devrait pas arriver si FOUND_ANY est vrai, mais par sécurité
    log "Erreur inattendue : la liste des fichiers est vide."
    exit 1
fi

for FULL_PATH in $ALL_FILES; do
    BASENAME=$(basename "$FULL_PATH")
    log "Traitement du fichier : $BASENAME"

    # Copie
    if ! docker cp "$CONTAINER:$FULL_PATH" "$DEST/$BASENAME"; then
        log "Erreur : échec de la copie de $BASENAME vers l'hôte."
        # On continue pour essayer les autres fichiers s'il y en a
        continue
    fi

    # Suppression dans le conteneur
    log "Suppression de $BASENAME dans le conteneur."
    if ! docker exec "$CONTAINER" rm -f "$FULL_PATH"; then
        log "Avertissement : échec de la suppression de $FULL_PATH dans le conteneur."
    fi
    
    log "Succès : $BASENAME sauvegardé et nettoyé."
done

# 4. Nettoyage local
log "Purge des sauvegardes de plus de $MAX_AGE_DAYS jours dans $DEST."
find "$DEST" -name "*.zip" -mtime +"$MAX_AGE_DAYS" -delete

log "Opération terminée."