# ESTADO.md — memoria detallada del proyecto

Última actualización: **13-07-2026** (commit `757f3bc`, 46 tests).
Complementa a CLAUDE.md (instrucciones de sesión) y ARQUITECTURA.md (diseño).

## 1. Cronología de fases (todas verificadas con tests)

| Commit | Hito |
|---|---|
| `b490bd6` | **F1 — Núcleo**: config pydantic, proyecto-carpeta (estado atómico + events.jsonl), DoE N-dimensional, puente R único (deepgp), bucle AL reanudable, DemoSolver pool-based, CLI, casos demo 2D/4D empaquetados |
| `7874bbc` | **DoE `factorial_3`** (hallazgo del autor): el híbrido rendía peor en 2D (29 sims vs 16–18 del TFM); la malla 3^D equiespaciada reproduce el Caso 1 del TFM exacto → demo 2D converge en 18 sims (modo completo, tol 0,001) |
| `ea1b651` | **F4 — Adaptador RS2 real**: materiales POR NOMBRE, CaseResult tipado, overrides de ejecutable, `new`/`check [--simulate]`; humo verificado (SRF 1,46 en 144 s) |
| `d219170` | **F3 — Validación y explotación**: LOOCV con refits reales, masiva vs FEM independiente, curva K-S vs n, muestreo de truncadas estilo RS2 (cuantiles LHS), MCS + PoF con IC |
| `61c19d2` | **F2 — Dashboard Streamlit**: 8 páginas, i18n EN/ES conmutable, curva de convergencia en vivo, helpers en `geosurrogate.ui.common` |
| `be4f582` | Comando **`testset`** (lote LHS independiente con el solver real, reanudable) + registro del detalle de fallos en el bucle |
| `0f8ed06` | **Informes HTML** autocontenidos (CLI + botón UI) + integración del testset en la página Validación + demo 3D empaquetada |
| `14dfeab` | **Ciclo 3D completo**: testset 80/80, masiva + K-S, MCS 100k, informe; fix IC regla del tres con 0 fallos |
| `c43f424` / `0452323` / `49aac63` | Iteración UX tras pruebas del autor: fix KeyError en Training recién lanzado; banner «Modelo entrenado» + globos + barra de presupuesto; barras de progreso en validación (por refit) y explotación/masiva (por etapas); blindaje de concurrencia (workdirs R por PID, botones deshabilitados en vuelo, staleness) |
| `e1fca86` / `7879d12` | Figuras de validación sin títulos (regeneradas las existentes); página Validación en 2 secciones conceptuales (interna LOOCV / independiente masiva+K-S) con bloque guiado de dataset (pool demo / generar con FEM / **subir Excel** — idea del autor); diseño del viaje desde cero registrado |
| `c569a0a` | **Flujo guiado**: auto-LOOCV al terminar el entrenamiento (fase `auto_validation` visible) + breadcrumb «Siguiente paso» navegable en todas las páginas |
| `90fbffc` | **Viaje desde cero en la UI**: pestaña «New from FEM model (.fez)» (upload → `discover_materials` one-shot → editor de variables con `st.data_editor` → DoE recomendado por D → crear proyecto con el `.fez` copiado dentro) + botón Preflight en página Model |
| `b3a2cfe` | Fix `StreamlitDuplicateElementId` (las pestañas renderizan todo a la vez): `key=` único en TODOS los botones + test AST que lo exige |
| `757f3bc` | **ALC paralelo** (`cores=` en el worker R): 153,7 s → 12,0 s (12,8×) sobre 1000 candidatos en el caso 3D real; ranking top-5 idéntico, e2e verde. Hallazgo colateral: los valores ALC de deepgp 1.2.1 salen denormales (~1e-315) también en producción — underflow preexistente, ranking se preserva; investigación pendiente |

## 2. Resultados verificados (los números que avalan el producto)

### Casos demo empaquetados (`demo_cases/`, sin ningún `.fez`, todo dato es RS2 real)
| Caso | D | Pool | Origen |
|---|---|---|---|
| `slope_2d` | 2 | 516 | TFM Caso 1 (talud homogéneo, derivado de tutorial Rocscience): 16 train + 500 LHS |
| `embankment_4d` | 4 | 551 | TFM Caso 2 (tutorial Embankment): 51 train + 500 LHS |
| `embankment_3d` | 3 | 109 | **Dogfooding**: generado POR geosurrogate (29 train + 80 testset) |

### Verificación contra el TFM (demo 2D)
- Masiva: **R² = 0,9972** vs 502 RS2 reales (el TFM reportó 0,997) · K-S D = 0,036, p = 0,904 (no se rechaza H0) · LOOCV cobertura ±2σ = 100 % · PoF(SRF<1) = 0,349 [0,342–0,355] con 20k MCS.
- Convergencia en modo completo con `factorial_3`: 18 sims (9 DoE + 9 AL), dentro del rango 16–18 del TFM original.

### Caso real 3D (Embankment, 3 variables; `runs/embankment_3d`, NO borrar)
- Variables: coh y φ de `embankment` + coh de `sand`; φ de `sand` fija = 35° (= media TFM, verificado).
- Entrenamiento: **convergió con 29 sims** (27 factorial + 2 AL), error 0,0054 < tol 0,01. FEM ~3,2 min/sim (esquinas) vs 144 s el humo central. ALC sobre 1000 candidatos ≈ 150 s/iter (optimizado en `757f3bc`: ahora ~12 s con `cores=`).
- LOOCV: R² = 0,9841, RMSE = 0,011, cobertura 90 % (n = 29).
- Testset: 80/80 ok, 3 h 06 min, cero fallos (`validation/testset_n80_seed777.xlsx`).
- Masiva: **R² = 0,9880**, RMSE = 0,0068, K-S D = 0,075, p = 0,979 (no se rechaza H0).
- MCS 100k: SRF 1,449 ± 0,058; **PoF(<1,3) = 0 → cota < 3·10⁻⁵ al 95 %** (regla del tres). Esperable: el corte 3D es muy seguro bajo sus distribuciones.
- Informe HTML completo en `runs/embankment_3d/report/`.

### Corridas del autor probando la UI (demo 4D)
- Convergió con 56 sims, error 0,00066 (tol 0,001); LOOCV R² = 0,9841, RMSE = 0,0102, cobertura 98,2 %. (Curiosidad verificada: su R² coincide con el del 3D hasta el 4.º decimal por casualidad genuina — difieren en el 6.º.)

## 3. Bugs cazados y lecciones (memoria institucional)

1. Colisión de kwargs `n_train` entre métricas propias y diagnósticos R → namespacing `r_*`.
2. **Falsa convergencia tras crash-resume** (mismo dataset + misma semilla MCMC → delta = 0 exacto) → la superficie guardada lleva sidecar con su `n_train`; solo se compara si el modelo vio datos nuevos. La salvaguarda ya evitó un falso positivo en producción (relanzamiento del 3D).
3. **Rutas relativas rompen `saveAs` de RS2** (proceso externo con su propio cwd) → raíz de proyecto siempre absoluta.
4. Abortos dejan `RS2`/`Interpret` huérfanos ocupando puertos → error accionable; cerrar por PID, jamás taskkill global.
5. **Doble clic = dos LOOCV concurrentes** compartiendo workdir R → se corrompieron y murieron sin output → workdirs por PID + botones deshabilitados en vuelo + progreso visible + staleness 4 min.
6. KeyError `error_max` al renderizar Training recién lanzado (solo eventos DoE, columna inexistente) → guard de columna + test del estado intermedio.
7. **Las pestañas de Streamlit renderizan todo a la vez** → dos botones con la misma etiqueta traducida colisionan en el ID autogenerado → `key=` en todos los botones + test AST.
8. IC binomial degenerado con p = 0 (aprox. normal → 6e-18) → regla del tres (3/n).
9. `--fast` (350 muestras posteriores vs 1000) tiene suelo de ruido MCMC ≈ 0,002: no puede converger con tolerancias finas; métricas presentables = modo completo.
10. `ConnectionResetError [WinError 10054]` en la terminal del servidor Streamlit en Windows = ruido benigno del websocket al rerenderizar; ignorar.
11. PowerShell 5.1 destroza argumentos con comillas dobles internas (`git commit -m`): evitarlas en los mensajes.

## 4. Conceptos que el autor cuida especialmente (responder con precisión)

- **Validación interna vs independiente**: LOOCV no necesita datos extra; masiva y K-S exigen FEM que el modelo nunca vio. La comparación masiva es PAREADA: mismos inputs exactos evaluados por surrogate y por FEM; entrenamientos disjuntos del testset.
- **Estabilidad ≠ exactitud**: el `error_max` del bucle (superficie sobre malla LHS fija, semilla 999, generada en Python) es criterio de parada; la exactitud la dan las validaciones.
- Formulación K-S rigurosa siempre (herencia de su TFM; el tribunal era sensible y el producto hereda el estándar).

## 5. Pendientes (al detalle)

1. **F5 publicación**: identidad git real + amend ANTES del push (actual: `Geovanny Benavides <geovanny.benavides@example.com>`, provisional); repo privado GitHub (el autor pospuso conectar `gh`/credenciales); README escaparate (el actual es stub) con capturas/GIF del dashboard; CI GitHub Actions (ubuntu + R + deepgp; el e2e corre sin RS2 gracias al DemoSolver).
2. **Backlog ARQ §15**: informe auto al completar validación · replay animado de `events.jsonl` · visor de geometría del `.fez` · sensibilidad (tornado) en exploitation · triangular en el editor del wizard · n recomendado de testset en UI · casos demo `cliff_6d`/`cliff_8d` (¡decisión de procedencia pendiente! usan el modelo del acantilado real del TFM).
3. Menor: PoF ilustrativa en demo 3D (threshold 1,40 → PoF ≈ 0,20) si el dueño lo pide.
4. Contexto TFM (solo si el autor lo trae): la defensa es junio 2026; el repo del TFM tiene su propio CLAUDE.md y flujo de redacción, ajeno a este proyecto.

## 6. Cómo retomar en 30 segundos

```powershell
cd G:\TFM_GeovannyBenavides\geosurrogate
.\.venv\Scripts\python -m pytest -q     # 46 verdes esperados
.\.venv\Scripts\geosurrogate ui         # dashboard en localhost:8501
```
Demo rápida: Home → New from demo case → slope_2d → Training → Start
(converge ~6 min en modo completo; auto-LOOCV al acabar; seguir el
breadcrumb hasta el informe).
