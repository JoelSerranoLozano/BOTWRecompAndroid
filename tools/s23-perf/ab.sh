#!/bin/bash
# ab.sh NAME SECS [LARECOMP_X=1,...]: one A/B run on the S23. Starts the game past the start screen with those switches,
# records logcat (runtime tag + kills), samples CPU clocks / temperature every 5 s, the GPU's clock / busy / cap every
# 5 s (root) and the app's memory every 30 s, then prints tools/log_metrics.py's numbers. Output in logs/NAME.*
set -uo pipefail
S=$(dirname "$(readlink -f "$0")")
A=${ADB:-$HOME/Android/Sdk/platform-tools/adb}
NAME=$1; SECS=$2; ENV=LARECOMP_NO_LAUNCHER=1${3:+,$3}
L=$S/logs; mkdir -p "$L"
PKG=${PKG:-com.botwrecomp.android.s23}
K=/sys/class/kgsl/kgsl-3d0
$A shell am force-stop $PKG
$A logcat -c
$A shell am start -n $PKG/com.botwrecompandroid.BOTWRecompAndroidActivity --es env "$ENV" >/dev/null
echo "[$NAME] started with $ENV; recording ${SECS}s"
timeout "$SECS" $A logcat -v time BOTWRecompAndroid:V lowmemorykiller:V ActivityManager:I libc:F DEBUG:V '*:S' > "$L/$NAME.logcat" &
LC=$!
end=$((SECONDS + SECS)); n=0
: > "$L/$NAME.clocks"; : > "$L/$NAME.mem"; : > "$L/$NAME.gpu"
while [ $SECONDS -lt $end ]; do
    $A shell 'echo "$(date +%T) $(for c in 0 1 2 3 4 5 6 7; do cat /sys/devices/system/cpu/cpu$c/cpufreq/scaling_cur_freq; done | tr "\n" " ") t=$(cat /sys/class/thermal/thermal_zone0/temp)"' >> "$L/$NAME.clocks"
    $A shell "su -c 'echo \$(date +%T) \$(cat $K/gpuclk) \$(cat $K/gpu_busy_percentage | tr -d \" %\") \$(cat $K/max_gpuclk) \$(cat $K/temp)'" >> "$L/$NAME.gpu" 2>/dev/null
    if [ $((n % 6)) -eq 0 ]; then
        $A shell "echo \$(date +%T); dumpsys meminfo $PKG | grep -E 'TOTAL PSS|TOTAL RSS|TOTAL SWAP|Native Heap  |Graphics:|Gfx dev|EGL mtrack|GL mtrack'" >> "$L/$NAME.mem"
    fi
    n=$((n + 1)); sleep 5
done
wait $LC
python3 -I "$S/../log_metrics.py" "$L/$NAME.logcat"
awk '{s+=$2; b+=$3; c+=$4; n++; if ($2 > m) m = $2} END {if (n) printf "gpu clock avg %.0f MHz (max %d), busy avg %.0f%%, cap avg %.0f MHz, %d samples\n", s/n/1e6, m/1e6, b/n, c/n/1e6, n}' "$L/$NAME.gpu"
grep -h -i -E 'low memory|kill|tracking|heap|uclamp' "$L/$NAME.logcat" | tail -8
