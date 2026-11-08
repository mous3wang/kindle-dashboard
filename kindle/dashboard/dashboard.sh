#!/bin/sh
# Kindle Dashboard client - Paperwhite 3 (FW 5.16.2.1.1), WinterBreak2 / hdnext
# Fetches a server-rendered PNG every INTERVAL seconds and draws it full-screen
# with eips. The current image is re-drawn every cycle even if it did not
# change: the Kindle framework repaints its own UI over an eips drawing
# whenever the user navigates, so re-drawing is how the picture recovers.
# (v2: a first real-device run proved the v1 "skip redraw when
# unchanged" logic left the home screen on top forever after the launcher
# returned to it. v2 also waits for the UI to settle before the first draw.)
# Everything lives in the user store (/mnt/us/dashboard). Nothing on the
# system partition is touched. A reboot kills the loop and resets the
# preventScreenSaver runtime property, so the Kindle returns to normal.
#
# Usage: dashboard.sh start | stop | status | loop   (loop is internal)
# Optional overrides: DASH_DIR, DASH_URL, DASH_INTERVAL

DIR="${DASH_DIR:-/mnt/us/dashboard}"
# Optional per-device config: a dashboard.conf next to this script may set
# DASH_URL, DASH_BATT_URL and DASH_INTERVAL (see dashboard.conf.example).
[ -f "$DIR/dashboard.conf" ] && . "$DIR/dashboard.conf"
# Defaults below are EXAMPLE addresses - set your real server in
# dashboard.conf (recommended) or edit the defaults here.
URL="${DASH_URL:-http://192.168.0.100:8080/dashboard.png}"
BATT_URL="${DASH_BATT_URL:-http://192.168.0.100:8080/batt}"
INTERVAL="${DASH_INTERVAL:-1800}"

IMG="$DIR/dashboard.png"
TMP="$DIR/dashboard_new.png"
PIDFILE="$DIR/dashboard.pid"
LOG="$DIR/dashboard.log"
HASHFILE="$DIR/dashboard.md5"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG" 2>/dev/null
}

eips_bin() {
    if [ -x /usr/sbin/eips ]; then
        echo /usr/sbin/eips
    else
        echo eips
    fi
}

draw() {
    E="$(eips_bin)"
    "$E" -f -g "$1" 2>/dev/null || "$E" -g "$1" 2>/dev/null
}

prevent_ss() {
    # Runtime-only property of powerd; resets on reboot by itself.
    lipc-set-prop com.lab126.powerd preventScreenSaver "$1" 2>/dev/null || \
    lipc-set-prop -i com.lab126.powerd preventScreenSaver "$1" 2>/dev/null
}

is_running() {
    [ -f "$PIDFILE" ] || return 1
    _pid="$(cat "$PIDFILE" 2>/dev/null)"
    [ -n "$_pid" ] && kill -0 "$_pid" 2>/dev/null
}

check_png() {
    # $1 = file. Must be non-trivial in size and carry a PNG signature
    # (signature check only when od is available).
    _sz="$(wc -c < "$1" 2>/dev/null)"
    [ -n "$_sz" ] && [ "$_sz" -gt 5000 ] || return 1
    if command -v od >/dev/null 2>&1; then
        _sig="$(dd if="$1" bs=1 count=4 2>/dev/null | od -An -tx1 | sed 's/ //g')"
        [ "$_sig" = "89504e47" ] || return 1
    fi
    return 0
}

fetch_once() {
    rm -f "$TMP"
    if command -v wget >/dev/null 2>&1; then
        wget -q -O "$TMP" "$URL" 2>/dev/null || { log "fetch failed (wget)"; return 1; }
    elif command -v curl >/dev/null 2>&1; then
        curl -s -f -o "$TMP" "$URL" 2>/dev/null || { log "fetch failed (curl)"; return 1; }
    else
        log "fetch failed (no wget or curl on device)"
        return 1
    fi
    if ! check_png "$TMP"; then
        log "fetch failed (downloaded file is not a valid PNG)"
        rm -f "$TMP"
        return 1
    fi

    _new=""
    if command -v md5sum >/dev/null 2>&1; then
        _new="$(md5sum "$TMP" 2>/dev/null | cut -d' ' -f1)"
    fi
    _old=""
    [ -f "$HASHFILE" ] && _old="$(cat "$HASHFILE" 2>/dev/null)"

    if [ -n "$_new" ] && [ "$_new" = "$_old" ] && [ -f "$IMG" ]; then
        rm -f "$TMP"
        log "image unchanged"
        return 0
    fi
    if [ -z "$_new" ] && [ -f "$IMG" ]; then
        # No md5sum on device: fall back to a size comparison.
        if [ "$(wc -c < "$TMP")" = "$(wc -c < "$IMG")" ]; then
            rm -f "$TMP"
            log "image size unchanged (no md5sum)"
            return 0
        fi
    fi

    mv "$TMP" "$IMG"
    [ -n "$_new" ] && echo "$_new" > "$HASHFILE"
    log "image updated"
    return 0
}

batt_level() {
    # powerd exposes the percentage via lipc; fall back to sysfs.
    _b=""
    if command -v lipc-get-prop >/dev/null 2>&1; then
        _b="$(lipc-get-prop com.lab126.powerd battLevel 2>/dev/null)"
    fi
    case "$_b" in ''|*[!0-9]*) _b="" ;; esac
    if [ -z "$_b" ]; then
        for _f in /sys/class/power_supply/*/capacity; do
            [ -r "$_f" ] && _b="$(cat "$_f" 2>/dev/null)" && break
        done
    fi
    echo "$_b"
}

report_batt() {
    # Fire-and-forget battery report for the smart-plug charge controller
    # on the server (keep battery between 50% and 90%). Runs in the
    # background so a network hiccup can never stall the picture loop.
    _lvl="$(batt_level)"
    if [ -z "$_lvl" ]; then
        log "battery level unreadable, report skipped"
        return 0
    fi
    log "battery level ${_lvl}%"
    if command -v wget >/dev/null 2>&1; then
        ( wget -q -O /dev/null "${BATT_URL}?level=${_lvl}" 2>/dev/null ) &
    elif command -v curl >/dev/null 2>&1; then
        ( curl -s -m 10 -o /dev/null "${BATT_URL}?level=${_lvl}" 2>/dev/null ) &
    fi
}

run_loop() {
    echo $$ > "$PIDFILE"
    prevent_ss 1
    log "loop started (pid $$, interval ${INTERVAL}s, url $URL)"
    trap 'prevent_ss 0; rm -f "$PIDFILE"; log "loop stopped (signal)"; exit 0' TERM INT
    # The launcher scriptlet returns to the library/home UI right after
    # starting us, and that UI repaint would cover a picture drawn too
    # early. Wait for the UI to settle before the first draw.
    sleep 12
    _first=1
    while true; do
        report_batt
        fetch_once || log "cycle failed, keeping previous image"
        # Always (re)draw the current image: the framework may have
        # repainted its UI over the picture since the last cycle.
        [ -f "$IMG" ] && draw "$IMG"
        if [ "$_first" = "1" ]; then
            _first=0
            # One extra draw shortly after the first, in case a late
            # UI repaint landed after it.
            sleep 20
            [ -f "$IMG" ] && draw "$IMG"
        fi
        sleep "$INTERVAL"
    done
}

do_redraw() {
    # Used when Start is tapped while the loop is already running (for
    # example after the user navigated and the UI covered the picture).
    # Delay first so the launcher's own return-to-home repaint is done.
    sleep 12
    if [ -f "$IMG" ]; then
        draw "$IMG"
        log "manual redraw (Start tapped while running)"
    fi
}

do_start() {
    if is_running; then
        echo "Dashboard is already running - redrawing the picture."
        echo "Do not touch the screen; it will reappear in ~15 seconds."
        if command -v nohup >/dev/null 2>&1; then
            nohup sh "$DIR/dashboard.sh" redraw >> "$LOG" 2>&1 &
        else
            sh "$DIR/dashboard.sh" redraw >> "$LOG" 2>&1 &
        fi
        log "start requested but already running - redraw scheduled"
        return 0
    fi
    rm -f "$PIDFILE"
    prevent_ss 1
    if command -v nohup >/dev/null 2>&1; then
        nohup sh "$DIR/dashboard.sh" loop >> "$LOG" 2>&1 &
    else
        sh "$DIR/dashboard.sh" loop >> "$LOG" 2>&1 &
    fi
    echo "Dashboard started. Do not touch the screen;"
    echo "the picture will appear within ~30 seconds."
    log "start requested"
}

do_stop() {
    if [ -f "$PIDFILE" ]; then
        _pid="$(cat "$PIDFILE" 2>/dev/null)"
        if [ -n "$_pid" ]; then
            kill "$_pid" 2>/dev/null
            sleep 1
            kill -9 "$_pid" 2>/dev/null
        fi
        rm -f "$PIDFILE"
    fi
    if command -v pkill >/dev/null 2>&1; then
        pkill -f "dashboard.sh loop" 2>/dev/null
    fi
    prevent_ss 0
    echo "Dashboard stopped. Screensaver is back to normal."
    echo "The last picture stays on the e-ink screen until you open a book"
    echo "or press the power button - that is normal for e-ink."
    log "stopped by user"
}

do_status() {
    if is_running; then
        echo "Dashboard: RUNNING (pid $(cat "$PIDFILE"))"
    else
        echo "Dashboard: STOPPED"
    fi
    echo "URL: $URL"
    echo "Interval: ${INTERVAL}s"
    if [ -f "$IMG" ]; then
        echo "Current image: $(wc -c < "$IMG") bytes"
    else
        echo "Current image: none downloaded yet"
    fi
    echo "--- last log lines ---"
    if [ -f "$LOG" ]; then
        tail -n 8 "$LOG"
    else
        echo "(no log yet)"
    fi
}

case "$1" in
    start)  do_start ;;
    stop)   do_stop ;;
    status) do_status ;;
    loop)   run_loop ;;
    redraw) do_redraw ;;
    *) echo "usage: dashboard.sh start|stop|status" ;;
esac
