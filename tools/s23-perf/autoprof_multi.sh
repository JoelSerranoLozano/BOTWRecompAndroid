#!/bin/bash
# autoprof_multi.sh NAME DELAY COUNT EVERY: once logs/NAME.logcat shows the open world for DELAY s, asks for COUNT GPU
# profiles (prof_gpu), one every EVERY seconds - with LARECOMP_AB they land in the different stretches.
S=$(dirname "$(readlink -f "$0")"); A=${ADB:-$HOME/Android/Sdk/platform-tools/adb}
NAME=$1; DELAY=${2:-30}; COUNT=${3:-16}; EVERY=${4:-4}
PKG=${PKG:-com.botwrecomp.android.s23}
D=/sdcard/Android/data/$PKG/files
L=$S/logs/$NAME.logcat
for i in $(seq 1 600); do
    sleep 2
    [ -f "$L" ] || continue
    if grep "\[vk\] t=" "$L" | tail -2 | awk '{for(i=1;i<=NF;i++){if($i=="frame")f[NR]=$(i+1); if($(i+1)=="draws,"){d=$i; gsub(/\(/,"",d); dd[NR]=d}}} END {exit !(NR==2 && f[2]>f[1] && dd[2]/(f[2]-f[1]) >= 2000)}'; then
        echo "[autoprof] open world seen; $COUNT profiles in ${DELAY}s, every ${EVERY}s"
        sleep "$DELAY"
        for k in $(seq 1 "$COUNT"); do $A shell "touch $D/prof_gpu"; sleep "$EVERY"; done
        echo "[autoprof] done"; exit 0
    fi
done
echo "[autoprof] no open world seen"
