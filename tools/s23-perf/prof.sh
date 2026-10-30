#!/bin/bash
# prof.sh NAME SECS [extra simpleperf record args]: whole-process profile of the running test app (root), call graphs
# (frame pointers), pulled to the PC and symbolized there with the unstripped libmain.so of the current build.
# Writes logs/NAME.perf.data and a symfs tree; report with rep.sh NAME ...
set -uo pipefail
S=$(dirname "$(readlink -f "$0")"); A=${ADB:-$HOME/Android/Sdk/platform-tools/adb}; L=$S/logs
NAME=$1; SECS=$2; shift 2
PKG=${PKG:-com.botwrecomp.android.s23}
PID=$($A shell pidof $PKG | tr -d '\r'); [ -n "$PID" ] || { echo "not running"; exit 1; }
$A shell "su -c 'echo 0 > /proc/sys/kernel/kptr_restrict; simpleperf record -p $PID -e cpu-clock -f 2000 --call-graph fp --duration $SECS $* -o /data/local/tmp/$NAME.data >/dev/null 2>&1; echo 2 > /proc/sys/kernel/kptr_restrict; chmod 644 /data/local/tmp/$NAME.data'"
$A pull /data/local/tmp/$NAME.data "$L/$NAME.perf.data" >/dev/null
# symfs: the unstripped libmain.so at the device path the samples name
LIBDEV=$($A shell "su -c 'grep -m1 libmain.so /proc/$PID/maps'" | awk '{print $6}' | tr -d '\r')
SYM=$L/symfs; rm -rf "$SYM"; mkdir -p "$SYM$(dirname "$LIBDEV")"
cp "$S"/../../android/botwrecompandroid/app/build/intermediates/cxx/RelWithDebInfo/*/obj/arm64-v8a/libmain.so "$SYM$LIBDEV"
echo "profile: $L/$NAME.perf.data ($(du -h "$L/$NAME.perf.data" | cut -f1)), libmain at $LIBDEV"
