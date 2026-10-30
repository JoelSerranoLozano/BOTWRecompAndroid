#!/bin/bash
# rep.sh NAME [simpleperf report args]: host report of logs/NAME.perf.data with the symfs from prof.sh
S=$(dirname "$(readlink -f "$0")"); L=$S/logs; NAME=$1; shift
exec "${ANDROID_NDK:-$HOME/Android/Sdk/ndk/30.0.16248370}"/simpleperf/bin/linux/x86_64/simpleperf report -i "$L/$NAME.perf.data" --symfs "$L/symfs" "$@" 2>/dev/null
