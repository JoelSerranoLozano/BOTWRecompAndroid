# Rendimiento en Galaxy S23 (Adreno 740): hallazgos, pruebas y propuestas

Rama `s23-rendimiento` (sobre 0.2.2-beta, 5675618). Cambios sin commit.

| | |
|---|---|
| Móvil | Samsung Galaxy S23 (SM-S911B), Snapdragon 8 Gen 2 for Galaxy, Adreno 740, 8 GB (7,2 GB visibles), One UI / Android 15, root (KernelSU Next) |
| Driver | Turnip v26 (Mesa 26.0.0-devel) |
| Juego | 1.0.0, código del juego compilado en el móvil (sin lista de funciones calientes: todo a -O1) |
| Memoria | modo copia: "memoria del juego en la GPU" apagada en Automático en la Adreno 7xx |
| Escena | mundo abierto, misma partida y mismo sitio, quieto |

Cómo se midió:
- `[vk] t=` / `[pace]` del log (tools/log_metrics.py).
- **A/B dentro de la misma partida** (`LARECOMP_AB`): las variantes se alternan cada 150 fotogramas con el mismo calor. Es la única comparación fiable en este móvil, porque Samsung cambia los relojes según la temperatura.
- Perfil de GPU por pasada (`LARECOMP_GPUPROF_AT` o el archivo `prof_gpu`).
- Línea de tiempo del fotograma (`LARECOMP_FRAME_TIMELINE` o el archivo `prof_timeline`), con el fin de cada envío según el vigilante de fences.
- simpleperf de todo el proceso, simbolizado en el PC.
- Relojes de CPU y GPU y temperaturas, cada 5 s, con root.

---

## 1. Resultado global

| estado | fps mundo abierto | imagen |
|---|---|---|
| Release 0.2.1 del autor | 5–6 | agua blanca (#43, arreglado en 0.2.2) |
| Vigilante de fences + sin señal de timeline + casillas ordenadas, **con** sync lag | 17–20 | **agua blanca** |
| Lo mismo **sin** sync lag (antes de esta tanda) | 14,6–15,4 | correcta |
| **Ahora, sin sync lag**, móvil frío (GPU 571–615 MHz) | **~23** (43 ms/fotograma) | correcta |
| Ahora, sin sync lag, móvil caliente (GPU limitada a ~300 MHz) | ~13–15 | correcta |

El límite actual es **la GPU y el calor**. La GPU trabaja ~38–40 ms por fotograma a ~600 MHz, pero Samsung (SSRM) la baja a 348 y luego a ~300 MHz en 3–5 minutos, también desenchufado: a 40 °C de batería, GPU a 295 MHz y core principal a 1,59 GHz de 3,36.

---

## 2. Hallazgos y cambios

### 2.1 Turnip sobre KGSL: el semáforo timeline (sesión anterior)
El timeline de Turnip sobre KGSL es emulado. Leerlo (`vkGetSemaphoreCounterValue`) y señalarlo en cada `vkQueueSubmit2` hace poll de los puntos pendientes con un `WAITTIMESTAMP` que duerme hasta ~4 ms con un bloqueo cogido. Era el gran atasco del render thread.

- **Vigilante de fences** (`exec.c` fw_*): un hilo espera la fence de cada envío en orden y publica el número terminado. Las esperas y lecturas ya no llaman al driver. `LARECOMP_VK_FENCE_WATCH=0` lo apaga.
- **Sin señal de timeline** cuando el vigilante está activo.
- Hoy, con todo lo demás activado: **vigilante apagado 8,2 fps, encendido ~16–20**.

### 2.2 Casillas de texturas y samplers en orden (sesión anterior)
Antes, cada cambio de casilla del pool vaciaba el render thread (~150 veces por segundo). Ahora se encola en orden (`objects.c`, `LARECOMP_ORDERED_SLOTS=0` lo apaga). A/B: **15,9 → 17,2 fps**. Sin las casillas ordenadas, el juego pasaba 12–14 s de cada 30 esperando al render thread. No afecta al agua.

### 2.3 Agua blanca = sync lag con la GPU como cuello de botella

| vigilante | sync lag | agua | fps |
|---|---|---|---|
| no | sí | bien | 8,2 |
| sí | sí | **blanca** | 19,5–20 |
| sí | no | bien | 15,4 |
| sí | modo 3 (`LARECOMP_SYNC_LAG=3`: espera a las escrituras de vuelta) | bien | 14,6 |

- El agua necesita las escrituras de vuelta **del fotograma actual**, y cualquier retraso de un fotograma la pone blanca.
- En el POCO del autor no se nota porque su GPU termina antes de que el juego lea.
- El modo 3 espera prácticamente al final del fotograma (las escrituras de vuelta están al 96–97 % de sus envíos), así que no ahorra nada.
- **Descartado:** aplicar las escrituras de vuelta solo en las esperas del juego. Hay render targets que comparten memoria (la cadena de luminancia 20x14 → 5x4 → 2x2 en la misma dirección), pero eso no era la causa. Probado y revertido.
- **Recomendación:** con Turnip en Adreno 7xx, *Sync lag* apagado (Video). Con los arreglos de abajo, sin sync lag ya se va más rápido que antes con él.

### 2.4 Lista de copias de vuelta fija de 256 (arreglado)
`gc_back[256]` (modo copia: lo que los shaders escriben y vuelve a la memoria del juego) **descartaba entradas sin avisar** cuando estaba llena, y con la GPU como cuello de botella se llenaba (llegó a necesitar 1024). Ahora crece hasta 8192 y avisa si descarta. `LARECOMP_GC_BACK_MAX=256` restaura el límite antiguo. No era la causa del agua.

### 2.5 Leer en el sitio en vez de copias feedback (Adreno 7xx)
- Antes: 11 copias de 1920x1080 por fotograma (3,25 ms de GPU en el perfil). En Automático, leer en el sitio solo se activa en Adreno 8xx, porque es donde se probó.
- A/B en la 740: **copias 53,9 ms → en el sitio 47,8 ms por fotograma (18,6 → 20,9 fps, +12 %)**. La GPU también baja de 53,1 a 47,1 ms.
- Comprobación visual sin sync lag: agua, suelo, decals e iluminación correctos.
- **Activar:** ajuste `inplace_reads = on` (pantalla de inicio > Driver compatibility) o `LARECOMP_FEEDBACK_INPLACE=1`.
- **Propuesta para el autor:** incluir la Adreno 7xx en Automático.

### 2.6 Sin sync lag la GPU estaba parada un 38 %: el camino crítico era la CPU
- Con sync lag la GPU iba al 99 %; sin él, al 62 %, y su gestor de frecuencia le bajaba el reloj.
- La línea de tiempo (con el fin de cada envío según el vigilante) mostró **~17,5 ms por fotograma con la GPU parada**:
  - la GPU termina el fotograma N;
  - el juego entra en nvnSyncWait 4,6 ms después y pasa **8,8 ms dentro de la espera, cuando la GPU ya había terminado**;
  - 3,6 ms después envía la lista N+1.
- El perfil de CPU: `hle_nvnSyncWait` era el **21 % del hilo principal** (~7,9 ms por fotograma), casi todo `memcmp` en `gcopy_retire`.

### 2.7 Copias de vuelta: comparar solo la más reciente de cada rango (arreglado)
- Las copias de vuelta de un rango residente apuntan todas a la **misma memoria de origen** (el hueco del rango en la arena de la GPU).
- Si el mismo compute shader escribe el mismo rango varias veces por fotograma, en la espera del juego había muchas entradas listas, y cada una comparaba el rango entero con dos `memcmp` por bloque de 256 B.
- Procesar solo la más reciente da exactamente el mismo resultado: los bloques que salta una antigua son un subconjunto de los de la más nueva.
- **A/B sin sync lag: 68,3 → 50,4 ms por fotograma (14,6 → 19,8 fps, +36 %)**. La GPU también baja de 47,5 a 40,2 ms, porque al estar más ocupada sube el reloj.
- Control: `LARECOMP_GC_DEDUP=0` lo apaga; A/B con `gcdedup`.
- **El origen del volumen:** si un shader escribe en memoria global, **todos** sus rangos se tratan como escritos. Eso incluye los buffers enlazados y hasta 16 rangos "aprendidos" de ~320 KB que se añaden a todas las tablas.

### 2.8 Copias de la arena solo en las esperas que leen datos
- Antes se procesaban en ~12 llamadas por fotograma, muchas desde esperas internas del render thread que no necesitan los datos (reutilizar un hueco del anillo, cambiar de bloque temporal).
- Ahora solo en las esperas del juego y en los pasos de CPU en orden de GPU (`renderer_flush`). Las copias simples siguen volviendo antes de reutilizar su bloque.
- Volumen: de ~17 GB a **1,6 GB comparados cada 30 s**, y de ~3 s a 0,56 s de CPU.
- A/B: **+1,5 %** (64,9 → 64,0 ms).
- `LARECOMP_GC_AT_DATA_WAITS=1`; **apagado por defecto**. Con sync lag activado, las copias de la memoria del juego que hace el render thread podrían ver datos un fotograma más viejos.

### 2.9 Enviar a la GPU en cuanto se queda sin trabajo
- Al empezar cada fotograma, el primer envío llevaba pocas pasadas y el segundo llegaba 3,2 ms después: ~4,4 ms de GPU parada por fotograma.
- Ahora, si el vigilante ve la GPU sin trabajo y lo grabado lleva ≥1 ms esperando, se envía en el siguiente límite de pasada, o dentro de una pasada larga.
- A/B: **+1,6 %**. `LARECOMP_VK_DRY_US=1000` por defecto; 0 lo apaga.

### 2.10 Medidas que descartan vías
- **Cortar o no las pasadas largas** (`split`): sin diferencia (49,4 frente a 49,1 ms).
- **Barreras al empezar cada pasada** (`nobarrier`, solo como medida): ~1 %.
- **900p en lugar de 1080p** (ajuste "1x" frente a "Match display"): **+12 %** (75,7 → 67,6 ms; GPU 66,9 → 59,0). No es el +31 % que darían los píxeles: la mayor parte del trabajo de GPU es geometría y coste por draw (~4000 draws por fotograma, ~2200 solo en el G-buffer).

### 2.11 Perfil de GPU actual (1080p, ~571 MHz, 41,5 ms)

| parte | ms | % |
|---|---|---|
| G-buffer (6 targets 1600x900 → 1920x1080, ~2200 draws en 4 trozos) | 15,3 | 37 |
| pasadas de 8 targets (decals / iluminación) | 4,4 | 11 |
| pasadas de 1 target 1600x900 | 4,2 | 10 |
| sombras (solo profundidad) | 3,3 | 8 |
| resto (800x450, presentación 1080p, compute...) | ~14 | 34 |

Ya no hay copias feedback.

### 2.12 CPU actual (perfil de 20 s, móvil frío)
- **Hilo principal del juego:** ~56 % ocupado. El 55 % es código del juego, muy repartido; el `memcmp` ha desaparecido.
- **Render thread:** ~22 ms por fotograma (`draw_` 13,5 %, `stage_set` 11,8 %, `memmove` 11 %). Hoy no limita, pero lo hará si la GPU baja de ~25 ms.
- **Hilos trabajadores del juego:** ~21 % cada uno. Dos hilos más pasan casi todo el tiempo en `sched_yield` (bucles de espera del propio juego).

### 2.13 Térmica (SSRM)
- La GPU va de 615 a 348 y luego ~300 MHz en 3–5 minutos de juego, también desenchufado.
- La CPU: el core principal a 1,59–2,48 GHz y los grandes a 1,29 GHz.
- Cargar por USB mientras se juega empeora la temperatura de la batería, que es lo que dispara los recortes. Para medir: adb por WiFi y cable desenchufado.
- Con root se puede levantar el techo de la GPU (`/sys/class/kgsl/kgsl-3d0/max_gpuclk`, `thermal_pwrlevel`). En la sesión anterior, 719 MHz daban 22,6 fps con sync lag; el precio es mucho calor.

---

## 3. "Memoria del juego en la GPU" (gpu_heap) en 8 GB

**Prueba** (`gpu_heap = 1` en la app de prueba):
- La reserva funciona: `guest heap 3110 MB is GPU memory (placed at 340000000, memory type 1, flags 0xf, storage range 128 MB); draws reach global memory through windows`.
- **Android mata la app por falta de memoria al cargar la partida** (~28 s; el sistema entero estaba en "mem-pressure-event").
- `MemTotal` 7,24 GB. Con KGSL, los 3,1 GB quedan comprometidos de golpe, aunque el juego solo toca ~1,3 GB de su heap (repartidos entre los offsets ~384 MB y ~2688 MB, medido en la sesión anterior).

**Conclusión:** tal como está no se puede usar en el S23. Para que funcione en 8 GB habría que **reservar solo las partes que el juego usa, en trozos**. Es un cambio grande de arquitectura. Lo dejo como recomendación para el autor, con estos datos.

**Cómo podría hacerse** (propuesta, no implementada):
1. **Trozos alineados a la ventana de 128 MB** (`maxStorageBufferRange`; el modo `gwin` ya da a cada draw una ventana de 128 MB del heap). Cada trozo tendría su `VkDeviceMemory` + `VkBuffer`, colocado con `VK_EXT_map_memory_placed` en `HEAP_BASE + i·128 MB`. Las ventanas apuntarían al buffer de su trozo. Las que crucen un límite necesitarían trozos solapados, o ventanas que no crucen.
2. **Colocación perezosa:** un trozo se coloca cuando el juego lo toca por primera vez (el seguimiento de escrituras por página ya existe), o cuando la GPU lo necesita. Al colocarlo tarde hay que copiar lo que ya hay en la memoria anónima y sustituir el mapeo con los hilos del juego parados, como hace el reset.
3. **Convivencia:** mientras haya trozos sin colocar, los draws que lleguen a ellos tendrían que usar el camino de copias. O bien se colocan todos los que el juego llegue a tocar, que con lo medido serían ~1,3–2,3 GB en lugar de 3,1.
4. **Antes de invertir en esto:** medir si compensa. Probar `gpu_heap = 1` con el móvil recién reiniciado y nada más abierto, por si cabe y se puede comparar con el modo copia. Así, ya sin los costes de copia que se han reducido arriba.

Alternativas descartadas o desconocidas:
- **Binding sparse:** Turnip sobre KGSL no parece tenerlo.
- **Reducir el tamaño del heap:** `SetHeapSize` es fijo (3110 MB) y lo pide el juego. `LARECOMP_TOTAL_MEM` no lo cambia.

---

## 4. Pruebas de Turnip: GMEM frente a sysmem (hechas el 2026-10-29)

**Resultado:**
- La GPU se fijó con root a 295 MHz (KGSL `min_pwrlevel` = `max_pwrlevel` = 7) y luego se restauró (8 / 0).
- Sin sync lag, leyendo en el sitio, 3 partidas de 4 min en el mismo sitio, con 2 perfiles de GPU cada una.

| modo | fps | ms por fotograma | GPU ms por fotograma (perfil) | G-buffer | pasadas de 8 targets |
|---|---|---|---|---|---|
| base (`TU_DEBUG=nolrz`, autotune) | **13,6** | 73,3 | 67,7 / 67,9 | 22,7 ms | 7,3 ms |
| `nolrz,sysmem` | 13,5 | 73,9 | 67,9 / 69,1 | 22,7 ms | 7,4 ms |
| `nolrz,gmem` | **6,4** | 156,2 | 154,6 / 151,4 | 59,2 ms | 35,1 ms |

**Conclusión:**
- El autotune de Turnip ya pone en **sysmem** las pasadas grandes: base y sysmem son iguales.
- Forzar GMEM más que duplica el tiempo de GPU: cada tile carga y guarda 6–8 targets a 1080p, y los ~700 draws de cada trozo del G-buffer se repiten por tile.
- Por aquí no hay ganancia. Además, optimizar `loadOp`/`storeOp` no ayudaría, porque en sysmem no hay cargas ni guardados de tiles.
- Lo que cuenta en sysmem es el ancho de banda, el *overdraw* (el LRZ ayudaría, pero da errores en la 740) y el coste por draw.

Planteamiento original de la prueba, para referencia:

**Objetivo:** saber si el G-buffer de 6 targets a 1080p (15 ms, 37 % de la GPU) va mejor en GMEM (tiles) o en sysmem (directo a memoria). Turnip lo decide solo por pasada (autotune). Con 6 targets + profundidad a 1080p, los tiles de GMEM salen pequeños y cada draw se repite en muchos tiles.

**Método:** como `TU_DEBUG` se lee al cargar el driver, no se puede alternar dentro de una partida. Para que el calor no falsee la comparación entre partidas, **fijar con root el reloj de la GPU a 295 MHz**, por debajo del recorte de Samsung (`/sys/class/kgsl/kgsl-3d0/devfreq/min_freq` = `max_freq`). Luego, 3 partidas cortas (~2 min en el mundo cada una), con perfil de GPU y fps:

| prueba | variables de arranque |
|---|---|
| base | `TU_DEBUG=nolrz` (lo actual) |
| sysmem | `TU_DEBUG=nolrz,sysmem` |
| gmem | `TU_DEBUG=nolrz,gmem` |

El runtime no pisa `TU_DEBUG` si ya viene puesta (`device.c`). Hay que mantener `nolrz`: el LRZ da errores a pantalla completa en la 740.

Comparar el total de GPU por fotograma y las filas del G-buffer y de las pasadas de 8 targets. Si alguna variante gana claramente en el G-buffer, el siguiente paso sería forzar ese modo solo para esas pasadas. Turnip no lo permite por pasada desde la API, así que habría que estudiar cómo influir en su autotune: número de draws, attachments, load/store ops.

---

## 4b. Por qué el G-buffer es caro: coste fijo por draw (2026-10-29)

GPU fijada a 295 MHz salvo que se diga otra cosa. Sin sync lag, leyendo en el sitio.

**¿Píxeles o draws?** Resolución alternada en la misma partida (`LARECOMP_AB=150:scale`), 15 perfiles:

| parte | 1080p | 900p (69 % de los píxeles) | proporción |
|---|---|---|---|
| G-buffer (6 targets) | 24,5 ms | 22,6 ms | **0,92** |
| pasadas de 8 targets | 7,0 | 6,5 | 0,94 |
| iluminación a pantalla completa | 7,4 | 5,2 | 0,71 |
| sombras | 5,9 | 5,7 | 0,97 |

Unos 18 de los 24,5 ms del G-buffer no dependen de los píxeles.

**Draw a draw** (`LARECOMP_GPUPROF_DRAWS=1`, una marca de tiempo tras cada draw, que infla algo):
- coste ≈ **12–19 µs fijos por draw + ~3,3 ns por vértice**;
- la parte fija es 9,5–12 ms y la parte por vértice ~2 ms;
- los draws de ≤300 vértices tienen una mediana de 8,5–11 µs;
- sin marcas por draw, el G-buffer sale a ~10 µs por draw (22,7 ms / 2230).
- **Conclusión: está limitado por el coste fijo de cada draw**, no por vértices ni píxeles.

**Estado por draw** (mundo abierto, cada 2 s): 122 000 draws, **95 000 cambios de descriptor sets (78 %)** y 22 600 de pipeline (18 %). Sube ~16 MB por fotograma, sobre todo constantes copiadas por draw. Los sets cambian casi siempre porque las constantes de cada objeto van a una posición nueva del anillo (offsets dinámicos). Los binds redundantes ya se filtran (`ss_need`).

**Coste de los binds** (A/B forzando binds redundantes, `rebind` / `repipe`):

| | GPU ms | coste |
|---|---|---|
| base | 67,5 | |
| + ~700 binds de descriptor sets por fotograma | 69,1 | **~2,3 µs por bind** |
| + ~2700 binds de pipeline por fotograma | 68,9 | ~0,5 µs por bind |

Los ~3200 binds de sets por fotograma suman **~7 ms, un 10–11 % de la GPU**.

**Opciones del compilador de shaders de Turnip (ir3)**, compilando desde cero con `LARECOMP_VK_NO_PIPELINE_CACHE=1` (la caché normal no se toca), partidas separadas:

| `IR3_SHADER_DEBUG` | fps | G-buffer (perfil) | temp. GPU |
|---|---|---|---|
| (base, caché normal) | 13,6 | 22,3–23,2 ms | 48 °C |
| `nopreamble` (1.ª) | **14,8** | 19,9–21,8 ms | 54 °C |
| `nouboopt` | 12,9 | 24,5–26,3 ms | 54 °C |
| `noearlypreamble` | 13,2 | 25,0–25,8 ms | 55 °C |
| control (`nocache`) | 13,2 | 26,0–30,7 ms | 53 °C |
| `nopreamble` (2.ª) | 13,1 | 21,6–26,8 ms | 55 °C |

- `nouboopt` y `noearlypreamble` no ayudan.
- **`nopreamble` no está confirmado:** +9–12 % la primera vez, sin diferencia la segunda.
- **Con el móvil caliente, la GPU rinde distinto aunque su reloj esté fijado** (probablemente la memoria). Los perfiles de una misma partida varían de 64 a 86 ms. Solo valen las comparaciones alternadas dentro de la misma partida.
- Para cerrarlo: varias tandas alternas base/`nopreamble` con el móvil frío, GPU fijada y suelo de DDR fijo.

**`nopreamble` CONFIRMADO (2026-10-30)** con una serie automática A-B-B-A:
- control, sin preámbulos, sin preámbulos, control;
- la partida se carga sola con `LARECOMP_INPUT=700:A:6,760:A:6,820:A:6,880:A:6`, así que la escena es la misma y la cámara no se mueve;
- compilación desde cero en cada partida, GPU fijada a 295 MHz, suelo de DDR 3187 MHz y `bus_split = 0`.

| partida | temp. GPU | fps | GPU por fotograma (3 perfiles) | G-buffer |
|---|---|---|---|---|
| 1. control | 49 °C | 14,90 | 61,3–62,4 ms | 23,4–24,1 ms |
| 2. sin preámbulos | 53 °C | **16,70** | 53,2–56,1 ms | 19,2–22,5 ms |
| 3. sin preámbulos | 55 °C | **16,60** | 55,3–55,5 ms | 19,8 ms |
| 4. control | 55 °C | 14,80 | 60,3–60,7 ms | 22,2–22,7 ms |

- **14,85 → 16,65 fps (+12 %)**: GPU 61,0 → 55,3 ms, G-buffer 23,0 → 19,8 ms.
- 2230 draws de G-buffer en los 12 perfiles.
- Los preámbulos de ir3, que se ejecutan una vez por draw, cuestan más de lo que ahorran con ~4000 draws pequeños por fotograma.

**Integrado** (`device.c`, antes de cargar el driver):
- Automático: `IR3_SHADER_DEBUG=nopreamble` en Adreno 7xx.
- `LARECOMP_IR3_PREAMBLE=1` los deja; `=0` los quita en cualquier GPU.
- Un `IR3_SHADER_DEBUG` ya puesto se respeta.
- Caché de pipelines propia, `cache/vk_pipelines_np.bin`: las claves de la caché del driver no cambian con esa opción, y sin esto se cargarían los shaders con preámbulos. Se recompila una vez.
- Log: `[vk] Turnip shader preambles off (Adreno740v2), IR3_SHADER_DEBUG=nopreamble`.
- **Para el autor:** medirlo en Adreno 8xx antes de ampliar el Automático.

**Memoria** (alternado con root cada 30 s en la misma partida): `bus_split = 0` + suelo de DDR 3187 MHz frente a lo normal (`bus_split = 1`, suelo 547 MHz) da **+3 %** (12,8 → 13,2 fps). La DDR suele estar a ~1,5–1,7 GHz de 4,2 posibles: el gestor no la sube porque el trabajo es de latencia, no de ancho de banda.

**¿Por qué cambian los sets?** (`LARECOMP_LOG_REBIND=1`, carga automática, cada 30 s)

| causa | % de los cambios de sets |
|---|---|
| primer draw de una pasada | 5 % |
| otras texturas, buffers o layout | 19 % |
| **solo un offset de constantes** (≤128 B en el 92 %) | **53 %** |
| dos offsets | 19 % |
| tres o más | 5 % |

Por bloque, los de un solo offset son vértice b4 56 %, b8 26 %, b9 10 %, b5 5 % y fragmento b2 3 %.

**Probado: esos bloques del vértice como *push constants*** (cambio en el traductor + `vkCmdPushConstants`).
- La imagen salía correcta (comprobado con captura) y los cambios de sets bajaron del 78 % al 39 % de los draws.
- **Pero no hubo ninguna mejora** (A-B-B-A automática):
  - a 295 MHz: sin 16,80 fps (GPU 53–54 ms), con 16,70 fps (GPU 54–56 ms);
  - a 220 MHz (Samsung bajó el techo con la batería a 40 °C): 13,10 frente a 13,10.
- El render thread tampoco cambia (21,7 ms).
- **Revertido.** En esta GPU, cualquier cambio de estado entre draws (descriptores o constantes) parece costar parecido.
- Detalle de Turnip: en A7XX no precarga descriptores (solo en A6XX), así que un bind solo reenvía las bases de los sets e invalida la caché de descriptores.

**Ideas para reducir el coste por draw** (sin probar):
- Menos cambios de descriptor sets. Por ejemplo, que el cambio de constantes por objeto no obligue a reenviar todos los descriptores dinámicos del layout: separar los UBO que cambian en un set propio pequeño. También habría que medir cuántos descriptores dinámicos tiene cada layout.
- Constantes por objeto pequeñas en *push constants*: requiere cambios en el traductor de shaders.
- Volver a medir el preámbulo de ir3 con un método fiable.

## 5. Herramientas añadidas para medir

| herramienta | qué hace |
|---|---|
| `LARECOMP_AB=<n>:a+b+c` | Hasta 3 interruptores; alterna todas las combinaciones. `[pace]` lleva el número de fase. Interruptores nuevos: `gcdedup`, `gcwait`, `dry`, `scale` (con `LARECOMP_AB_SCALE`, en unidades de 900 líneas). |
| archivos `prof_gpu` / `prof_timeline` | En la carpeta de datos (`adb shell touch .../files/prof_gpu`): perfil de GPU del siguiente fotograma o línea de tiempo de 4 fotogramas, cuando se quiera. |
| eventos de la línea de tiempo | `gpu: done (watcher)` (fin de cada envío), `render: acquired window image`, `render: frame slot wait`. |
| `[vk] copy-backs, last 30 s` | Entradas, duplicadas, MB comparados y ms (cada 30 s). |
| scripts del PC | En `tools/s23-perf/`, con su README: `ab.sh`, `run_abba2.sh` (A-B-B-A automática), `autoprof*.sh`, `busab.sh`, `prof.sh`/`rep.sh`, y análisis `pace_ab.py`, `timeline.py`, `gpuprof*.py`, `perdraw.py`, `abba2_an.py`, `busab_an.py`. |

## 6. Ajustes en el S23 (app de prueba)

**Ya automático**, sin tocar nada:
- vigilante de fences;
- casillas ordenadas;
- deduplicación de copias de vuelta;
- envío a la GPU cuando se queda sin trabajo;
- **sin preámbulos de ir3** (Adreno 7xx);
- **leer en el sitio** (Automático ahora incluye la Adreno 740);
- **copias de la arena solo en las esperas que leen datos** cuando el sync lag está apagado.

**Ajustes:**
- Video > **Sync lag: apagado** (agua correcta). En la app de prueba ya está a 0.
- Opcional: Video > Internal resolution **1x (900p)**, +12 %.
- Jugar desenchufado si se puede. El calor es el mayor limitador: Samsung baja la GPU a 295 y luego a 220 MHz.

---

## English summary (for the author)

**Galaxy S23 (SM-S911B, Adreno 740, 8 GB), Turnip v26, game 1.0.0, open world.** Release 0.2.1: 5–6 fps. Now: **~23 fps with correct visuals (sync lag off)** on a cool phone, ~13–15 fps once Samsung's SSRM caps the GPU at ~300 MHz (it does within 3–5 min, even unplugged). All numbers are in-run A/Bs (`LARECOMP_AB`) unless noted.

1. **Turnip/KGSL emulated timeline semaphore** stalled the render thread (each read or signal polls pending points with a `WAITTIMESTAMP` that sleeps up to ~4 ms under a lock).
   - Fix: a fence-based completion watcher thread, and no timeline signal while it is on: **8.2 → ~16–20 fps**.
   - Also, texture/sampler pool slot changes are queued in order instead of draining the render thread: 15.9 → 17.2 fps.
2. **White water** on the S23 is the sync lag once the GPU is the bottleneck: the water needs the current frame's write-backs. The POCO's faster GPU hides it.
   - Lag off: correct. `SYNC_LAG=3`: correct, but no faster than lag off.
   - Landing write-backs only at the game's waits did not help (reverted).
   - Suggest sync lag off on Adreno 7xx.
3. **`gc_back[256]` silently dropped copy-backs** when full: 1024 were in flight once GPU-bound. Now growable, with a log on drops.
4. **In-place feedback reads on Adreno 740**: 53.9 → 47.8 ms/frame (+12 %), visuals checked. Suggest including Adreno 7xx in Automatic for `inplace_reads`.
5. **With sync lag off, the GPU sat idle 38 % of the time.** The game spent ~8 ms per frame inside `nvnSyncWait` after the GPU had finished: `gcopy_retire`, two `memcmp` per 256 B block of every ready arena entry.
   - Ready entries of the same range share the same source (the range's arena slot), so only the newest needs comparing.
   - **Result: 68.3 → 50.4 ms/frame (+36 %).**
   - Retiring arena entries only at waits after which the CPU reads guest memory: −90 % bytes compared, +1.5 % (off by default).
   - Root cause of the volume: every range of a storing shader (bound buffers plus up to 16 learned ~320 KB windows) is treated as stored.
6. **Submitting as soon as the GPU runs dry** (watcher sees all work done, ≥1 ms recorded): +1.6 %.
7. **Measured, not worth it:** long-pass splitting (no difference), per-pass full barriers (~1 %).
   - 900p vs 1080p: +12 %. The GPU is mostly geometry/per-draw bound: G-buffer ≈ 2200 draws, 15 ms of 41.5 ms at ~571 MHz.
8. **GPU heap (`gpu_heap = on`) on 8 GB:** placement succeeds (3110 MB, type 1, flags 0xf), but **the app is OOM-killed while loading** (7.24 GB `MemTotal`; KGSL commits the whole 3.1 GB although the game touches ~1.3 GB).
   - Needs chunked, lazy placement (128 MB chunks aligned to the `gwin` windows, placed on first touch).
9. **Turnip rendering mode** (GPU pinned at 295 MHz via root):
   - Default autotune: 13.6 fps, `nolrz,sysmem`: 13.5 fps, `nolrz,gmem`: **6.4 fps** (G-buffer 22.7 → 59 ms).
   - Autotune already renders the big passes in sysmem. Nothing to gain there, and load/store-op tuning wouldn't help.
   - LRZ stays off: full-screen corruption on the 740.

10. **Why the GPU is slow: fixed per-draw cost.**
    - 1080p → 900p cuts the G-buffer only 8 % (24.5 → 22.6 ms at 295 MHz).
    - Per-draw timing fits ~12–19 µs fixed per draw + ~3.3 ns per vertex.
    - 78 % of draws rebind descriptor sets (new dynamic UBO offsets per object), and forced redundant rebinds cost ~2.3 µs of GPU each: ~10 % of the frame.
    - ir3 options: `nouboopt` / `noearlypreamble` are worse.
    - **`nopreamble` confirmed, +12 %** (14.85 → 16.65 fps; G-buffer 23.0 → 19.8 ms). Control/off/off/control cold-compile runs, scripted load (same scene), GPU pinned, DDR floor fixed.
    - Now automatic on Adreno 7xx (`IR3_SHADER_DEBUG=nopreamble` before the driver loads; `LARECOMP_IR3_PREAMBLE` overrides), with a separate pipeline cache file, since the driver's cache keys ignore that flag.
    - Worth measuring on Adreno 8xx.
    - Raising the memory floor (`bus_split=0`, DDR floor 3187 MHz) gives +3 % in-run.
    - Half of the set rebinds had a single ≤128-byte vertex UBO moving (cb4/cb8/cb9/cb5).
    - Moving those into push constants halved the rebinds (78 % → 39 % of draws) but gave **no** fps or GPU-time change in an ABBA. Reverted.
    - `LARECOMP_LOG_REBIND=1` is kept as a diagnostic.

Switches: `LARECOMP_VK_FENCE_WATCH`, `LARECOMP_ORDERED_SLOTS`, `LARECOMP_GC_BACK_MAX`, `LARECOMP_GC_DEDUP`, `LARECOMP_GC_AT_DATA_WAITS`, `LARECOMP_VK_DRY_US`, and `LARECOMP_AB` with up to 3 switches (new: `gcdedup`, `gcwait`, `dry`, `scale`, `rebind`, `repipe`). `prof_gpu` / `prof_timeline` files trigger measurements on demand.
