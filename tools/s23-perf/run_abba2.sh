#!/bin/bash
# run_abba2.sh TAG "ENV_A" "ENV_B" [SECS] [SETTLE]: A / B / B / A, the game loaded by scripted A presses (same save, same
# camera), GPU pinned at 295 MHz, DDR floor 3187 MHz and bus_split 0, 3 GPU profiles from SETTLE s into the world.
# Runs logs/<TAG>N_a|b.*. Everything restored at the end.
S=$(dirname "$(readlink -f "$0")"); A=${ADB:-$HOME/Android/Sdk/platform-tools/adb}
TAG=$1; EA=$2; EB=$3; SECS=${4:-230}; SETTLE=${5:-70}
K=/sys/class/kgsl/kgsl-3d0; B=/sys/devices/system/cpu/bus_dcvs/DDR
BOOST0=$($A shell "su -c 'cat $B/boost_freq'" | tr -d '\r')
pin() { $A shell "su -c 'echo 7 > $K/max_pwrlevel; echo 7 > $K/min_pwrlevel; echo 0 > $K/bus_split; echo 3187000 > $B/boost_freq'"; }
restore() { $A shell "su -c 'echo 0 > $K/max_pwrlevel; echo 8 > $K/min_pwrlevel; echo 1 > $K/bus_split; echo $BOOST0 > $B/boost_freq'"; echo "[abba] restored"; }
trap 'restore; exit 1' INT TERM
COMMON=LARECOMP_FEEDBACK_INPLACE=1,LARECOMP_SYNC_LAG=0,LARECOMP_GC_AT_DATA_WAITS=1,LARECOMP_LOG_PACE=1,LARECOMP_INPUT=700:A:6,760:A:6,820:A:6,880:A:6
i=0
for v in a b b a; do
    i=$((i + 1))
    case $v in a) E=$EA ;; b) E=$EB ;; esac
    NAME=${TAG}${i}_$v
    pin
    echo "[abba] $NAME ($E): $($A shell 'dumpsys battery | grep -E "^  temperature"' | tr -d '\r')"
    bash "$S/autoprof_multi.sh" "$NAME" "$SETTLE" 3 20 > "$S/logs/$NAME.autoprof" 2>&1 &
    bash "$S/ab.sh" "$NAME" "$SECS" "$COMMON${E:+,$E}" > "$S/logs/$NAME.out" 2>&1
    wait
done
restore
