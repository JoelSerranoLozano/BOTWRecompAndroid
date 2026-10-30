#!/bin/bash
# busab.sh NAME SETTLE CYCLES HALF: alongside ab.sh NAME - once the open world shows, waits SETTLE s, then CYCLES times:
# HALF s "normal" (bus_split 1, DDR boost floor as found) and HALF s "boost" (bus_split 0, DDR boost floor 3187 MHz),
# asking for a GPU profile 10 s into each half. The switch times go to logs/NAME.busab ("HH:MM:SS normal|boost").
# Everything back as found at the end (also on Ctrl-C).
S=$(dirname "$(readlink -f "$0")"); A=${ADB:-$HOME/Android/Sdk/platform-tools/adb}
NAME=$1; SETTLE=${2:-100}; CYCLES=${3:-3}; HALF=${4:-30}
PKG=${PKG:-com.botwrecomp.android.s23}
D=/sdcard/Android/data/$PKG/files
K=/sys/class/kgsl/kgsl-3d0; B=/sys/devices/system/cpu/bus_dcvs/DDR
L=$S/logs/$NAME.logcat; OUT=$S/logs/$NAME.busab; : > "$OUT"
BOOST0=$($A shell "su -c 'cat $B/boost_freq'" | tr -d '\r')
restore() { $A shell "su -c 'echo 1 > $K/bus_split; echo $BOOST0 > $B/boost_freq'"; echo "$(date +%T) restored" >> "$OUT"; }
trap 'restore; exit 1' INT TERM
for i in $(seq 1 600); do
    sleep 2
    [ -f "$L" ] || continue
    if grep "\[vk\] t=" "$L" | tail -2 | awk '{for(i=1;i<=NF;i++){if($i=="frame")f[NR]=$(i+1); if($(i+1)=="draws,"){d=$i; gsub(/\(/,"",d); dd[NR]=d}}} END {exit !(NR==2 && f[2]>f[1] && dd[2]/(f[2]-f[1]) >= 2000)}'; then
        echo "[busab] open world seen; cycles in ${SETTLE}s"
        sleep "$SETTLE"
        for c in $(seq 1 "$CYCLES"); do
            for mode in normal boost; do
                if [ $mode = normal ]; then $A shell "su -c 'echo 1 > $K/bus_split; echo $BOOST0 > $B/boost_freq'"
                else $A shell "su -c 'echo 0 > $K/bus_split; echo 3187000 > $B/boost_freq'"; fi
                echo "$($A shell date +%T | tr -d '\r') $mode" >> "$OUT"
                sleep 10; $A shell "touch $D/prof_gpu"; sleep $((HALF - 10))
            done
        done
        restore; echo "[busab] done"; exit 0
    fi
done
echo "[busab] no open world seen"
