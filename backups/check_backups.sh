#!/bin/bash
set -euo pipefail

# --- Configuration ---
TOKEN="8583822011:AAFt86QGWBhOCOOJ79QrDm_pou--W57Ya2M"
CHAT_ID="8563154176"
BACKUP_DIR="/data/backups"
DATE_TODAY=$(date +%F)
DATE_YESTERDAY=$(date -d "yesterday" +%F)
HOSTNAME=$(hostname)
TELEGRAM_API="https://api.telegram.org/bot${TOKEN}/sendMessage"
CURL_CONNECT_TIMEOUT=10
CURL_MAX_TIME=60
CURL_RETRIES=3
CURL_RETRY_DELAY=5

# --- Logging helper ---
log() {
    printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

send_telegram() {
    local text="$1"
    local label="$2"
    local attempt=1
    while [ "$attempt" -le "$CURL_RETRIES" ]; do
        local tmp_response
        tmp_response=$(mktemp)
        local curl_status=0

        log "Envoi du message Telegram ($label) via $TELEGRAM_API (tentative $attempt/$CURL_RETRIES)"

        local http_code
        http_code=$(curl -4 -sS \
            --connect-timeout "$CURL_CONNECT_TIMEOUT" \
            --max-time "$CURL_MAX_TIME" \
            -w '%{http_code}' \
            -o "$tmp_response" \
            -X POST "$TELEGRAM_API" \
            --data-urlencode "chat_id=$CHAT_ID" \
            --data-urlencode "text=$text" \
            --data-urlencode "parse_mode=Markdown") || curl_status=$?

        if [ "$http_code" = "200" ]; then
            log "Message Telegram ($label) envoyé avec succès (HTTP 200)"
            rm -f "$tmp_response"
            return 0
        fi

        log "Échec de l'envoi Telegram ($label) : HTTP ${http_code:-unknown}, code curl $curl_status"
        if [ -s "$tmp_response" ]; then
            log "Réponse Telegram ($label) : $(cat "$tmp_response")"
        fi
        rm -f "$tmp_response"

        if [ "$attempt" -lt "$CURL_RETRIES" ]; then
            log "Nouvelle tentative d'envoi ($label) dans ${CURL_RETRY_DELAY}s"
            sleep "$CURL_RETRY_DELAY"
        fi

        attempt=$((attempt + 1))
    done

    log "Abandon de l'envoi Telegram ($label) après $CURL_RETRIES tentatives"
    return 1
}

log "Début du rapport de sauvegarde pour $HOSTNAME ($DATE_TODAY)"

# --- Liste des services ---
SERVICES=("pihole" "homarr" "convertx" "jellyfin" "servarr" "docker" "immich" "npm")
HOSTS=("immich" "network" "proxy" "servarr")

printf -v MESSAGE_SERVICES '📊 *Backups - (%s)*\n\n' "$DATE_TODAY"

for SERVICE in "${SERVICES[@]}"; do
    log "Vérification du service $SERVICE"
    # Fichier du jour
    FILE_TODAY=$(find "$BACKUP_DIR/$SERVICE" -name "*$DATE_TODAY*" -type f -size +100c | head -n 1)
    # Fichier de la veille
    FILE_YESTERDAY=$(find "$BACKUP_DIR/$SERVICE" -name "*$DATE_YESTERDAY*" -type f -size +100c | head -n 1)

    if [ -n "$FILE_TODAY" ]; then
        SIZE_TODAY=$(du -sh "$FILE_TODAY" | cut -f1)
        log "Service $SERVICE : fichier du jour $FILE_TODAY ($SIZE_TODAY)"

        # Calcul de la taille de la veille pour comparaison
        if [ -n "$FILE_YESTERDAY" ]; then
            SIZE_YESTERDAY=$(du -sh "$FILE_YESTERDAY" | cut -f1)
            COMPARISON=" (vs $SIZE_YESTERDAY hier)"
            log "Service $SERVICE : fichier de la veille $FILE_YESTERDAY ($SIZE_YESTERDAY)"
        else
            COMPARISON=" (1er backup)"
            log "Service $SERVICE : aucun backup la veille"
        fi

        printf -v MESSAGE_SERVICES '%s✅ *%s* : %s %s\n' "$MESSAGE_SERVICES" "$SERVICE" "$SIZE_TODAY" "$COMPARISON"
    else
        printf -v MESSAGE_SERVICES '%s❌ *%s* : *ABSENT (Absent)*\n' "$MESSAGE_SERVICES" "$SERVICE"
        log "Service $SERVICE : aucun backup trouvé pour aujourd'hui"
    fi
done

# --- Ajout de la vérification des backups Docker par host ---
printf -v MESSAGE_DOCKER '🖥 *Docker - (%s)*\n\n' "$DATE_TODAY"
log "Vérification des backups Docker par host"
for HOST_ITEM in "${HOSTS[@]}"; do
    # Docker configs can be very small, so we do not enforce a minimum size
    FILE_HOST=$(find "$BACKUP_DIR/docker" -maxdepth 1 -type f -name "${HOST_ITEM}_docker_configs_${DATE_TODAY}.tar.gz" | head -n 1)
    FILE_HOST_YESTERDAY=$(find "$BACKUP_DIR/docker" -maxdepth 1 -type f -name "${HOST_ITEM}_docker_configs_${DATE_YESTERDAY}.tar.gz" | head -n 1)

    if [ -n "$FILE_HOST" ]; then
        SIZE_HOST=$(du -sh "$FILE_HOST" | cut -f1)
        log "Docker $HOST_ITEM : fichier du jour $FILE_HOST ($SIZE_HOST)"
        if [ -n "$FILE_HOST_YESTERDAY" ]; then
            SIZE_HOST_YESTERDAY=$(du -sh "$FILE_HOST_YESTERDAY" | cut -f1)
            HOST_COMPARISON=" (vs $SIZE_HOST_YESTERDAY hier)"
            log "Docker $HOST_ITEM : fichier de la veille $FILE_HOST_YESTERDAY ($SIZE_HOST_YESTERDAY)"
        else
            HOST_COMPARISON=" (1er backup)"
            log "Docker $HOST_ITEM : aucun backup la veille"
        fi
        printf -v MESSAGE_DOCKER '%s✅ %s : %s%s\n' "$MESSAGE_DOCKER" "$HOST_ITEM" "$SIZE_HOST" "$HOST_COMPARISON"
    else
        printf -v MESSAGE_DOCKER '%s❌ %s : *ABSENT*\n' "$MESSAGE_DOCKER" "$HOST_ITEM"
        log "Docker $HOST_ITEM : aucun backup trouvé pour aujourd'hui"
    fi
done

# --- Envoi vers Telegram ---
log "Longueur du message services : ${#MESSAGE_SERVICES} caractères"
send_telegram "$MESSAGE_SERVICES" "services"

log "Longueur du message docker : ${#MESSAGE_DOCKER} caractères"
send_telegram "$MESSAGE_DOCKER" "docker"

log "Fin du script de rapport de sauvegarde"
