# Performance measurement scripts (Android, used on a Galaxy S23)

Host-side scripts that drive the test build over adb (`ADB=` to override the SDK's adb, `ANDROID_SERIAL=` for a
WiFi device, `PKG=` for the package, default `com.botwrecomp.android.s23`). Several need root on the phone (GPU clock
and bus nodes, simpleperf). Output goes to `logs/` here (ignored by git). Findings: `docs/S23-RENDIMIENTO-INFORME.md`.

| script | what it does |
|---|---|
| `ab.sh NAME SECS [ENV]` | Start the game with `LARECOMP_*` switches (comma list), record logcat, CPU / GPU clocks and temperatures, memory; print `tools/log_metrics.py`'s numbers |
| `autoprof.sh NAME [DELAY] [gpu\|timeline\|both]` | Once `ab.sh`'s log shows the open world, ask for a GPU profile / frame timeline (`prof_gpu` / `prof_timeline` files) |
| `autoprof_multi.sh NAME DELAY COUNT EVERY` | Several GPU profiles at intervals (for `LARECOMP_AB` stretches) |
| `run_abba2.sh TAG "ENV_A" "ENV_B" [SECS] [SETTLE]` | A / B / B / A runs with the game loaded by scripted input (same scene), GPU pinned at 295 MHz and the DDR floor raised; restores everything |
| `busab.sh NAME SETTLE CYCLES HALF` | Alternate the GPU bus vote / DDR floor from outside during one run |
| `prof.sh NAME SECS` / `rep.sh NAME ...` | simpleperf whole-process profile, symbolized on the PC with the unstripped `libmain.so` |
| `pace_ab.py LOG [SKIP] [a+b]` | `LARECOMP_AB` + `LARECOMP_LOG_PACE`: frame period / GPU / render thread per stretch |
| `gpuprof.py LOG [N]`, `gpuprof_ab.py LOG N`, `perdraw.py LOG` | GPU profiles by kind of work, per stretch, per draw (`LARECOMP_GPUPROF_DRAWS`) |
| `timeline.py LOG` | `LARECOMP_FRAME_TIMELINE`: game / render thread / GPU lanes, GPU idle gaps |
| `abba2_an.py TAG [SETTLE]`, `busab_an.py NAME` | Summaries of `run_abba2.sh` / `busab.sh` runs |

Only in-run comparisons (`LARECOMP_AB`, or switches alternated within one run) or A/B/B/A series are reliable on a
phone: the SoC's thermal limits change clocks (GPU and memory) from one run to the next.
