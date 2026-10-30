#!/bin/bash
# autoprof.sh NAME [DELAY] [WHAT]: alongside ab.sh NAME - once logs/NAME.logcat shows the open world (stats lines with
# >= 2000 draws a frame) for DELAY seconds (default 40), asks the running game for a GPU profile of one frame
# (prof_gpu) and, 10 s later, a frame timeline (prof_timeline). WHAT: gpu, timeline or both (default).
S=$(dirname "$(readlink -f "$0")"); A=${ADB:-$HOME/Android/Sdk/platform-tools/adb}
NAME=$1; DELAY=${2:-40}; WHAT=${3:-both}
PKG=${PKG:-com.botwrecomp.android.s23}
D=/sdcard/Android/data/$PKG/files
L=$S/logs/$NAME.logcat
start=
for i in $(seq 1 600); do
    sleep 2
    [ -f "$L" ] || continue
    if [ -z "$start" ]; then
        # the open world: the last two stats lines' frames and draws
        if grep "\[vk\] t=" "$L" | tail -2 | awk '{for(i=1;i<=NF;i++){if($i=="frame")f[NR]=$(i+1); if($(i+1)=="draws,"){d=$i; gsub(/\(/,"",d); dd[NR]=d}}} END {exit !(NR==2 && f[2]>f[1] && dd[2]/(f[2]-f[1]) >= 2000)}'; then
            start=$SECONDS; echo "[autoprof] open world seen; measuring in ${DELAY}s"
        fi
    elif [ $((SECONDS - start)) -ge "$DELAY" ]; then
        if [ "$WHAT" != timeline ]; then $A shell "touch $D/prof_gpu"; echo "[autoprof] GPU profile asked for"; fi
        if [ "$WHAT" != gpu ]; then
            [ "$WHAT" = both ] && sleep 10
            $A shell "touch $D/prof_timeline"; echo "[autoprof] timeline asked for"
        fi
        exit 0
    fi
done
echo "[autoprof] no open world seen"
