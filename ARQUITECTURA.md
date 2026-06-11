# Arquitectura del prototipo — "geosurrogate" (nombre provisional)

**Fecha:** 10-06-2026 · **Estado:** propuesta para revisión del autor · **Origen:** TFM RS2↔deepgp (G:\TFM_GeovannyBenavides\RS2Scripting_VSC)

Plataforma de análisis de fiabilidad para estabilidad de taludes: construye un *surrogate model* de Procesos Gaussianos con *active learning* sobre un modelo FEM (RS2 en v1), lo valida y lo explota para análisis probabilísticos masivos. Dashboard local para máquinas que ya disponen de licencia RS2; modo demo autocontenido que no requiere RS2 ni R.

---

## 1. Objetivo y alcance de la v1

- **Usuario objetivo v1:** ingeniero geotécnico con RS2 licenciado en su máquina Windows (el perfil de las empresas que ya usan el software a diario).
- **Entregable v1:** aplicación local (Streamlit) + paquete Python instalable + modo demo con los casos del TFM precalculados.
- **Fuera de alcance v1:** ejecución remota/multiusuario, otros solvers (PLAXIS, FLAC), portado del GP a Python. La arquitectura los deja preparados (ver §5.1 y §13).
- **Regla de oro:** este prototipo **no toca** el directorio del TFM. Los datos de los casos demo se **copian** (solo lectura) desde las rutas indicadas en §8.3.

## 2. Principios de diseño

1. **Núcleo desacoplado de la UI.** El paquete `geosurrogate` nunca importa Streamlit. La UI es un cliente más; la CLI es otro. Migrar a FastAPI+React en fase comercial no toca el pipeline.
2. **Solver como adaptador.** Todo acceso al FEM pasa por la interfaz `FEMSolver`. RS2 es la primera implementación; el modo demo es la segunda. PLAXIS/FLAC serán la tercera y cuarta sin cambiar nada más.
3. **Configuración única y declarativa.** Un `project.yaml` por análisis es la única fuente de verdad. La UI lo edita, el pipeline lo lee, el informe lo documenta. Cero constantes en cabeceras.
4. **Trabajos largos = procesos observables y reanudables.** El bucle corre en proceso aparte; su estado vive en disco (`state.json` + `events.jsonl`); la UI solo observa. Un cierre del navegador o un corte no pierden nada: el dataset es la fuente de verdad y cada iteración es idempotente.
5. **Los datos sobreviven a las herramientas.** Dataset en parquet con export a Excel; figuras regenerables desde datos; nada de PNGs como único registro.

## 3. Vista de capas

```
┌────────────────────────────────────────────────────────────┐
│ UI — Streamlit (app/)                                      │
│ asistente de 8 pasos · observa state.json/events.jsonl     │
├────────────────────────────────────────────────────────────┤
│ CLI (geosurrogate run / ui / demo)                         │
├────────────────────────────────────────────────────────────┤
│ NÚCLEO — paquete src/geosurrogate/                         │
│  config · project · doe · activelearning · validation ·    │
│  exploitation · reporting                                  │
│        │                          │                        │
│  ┌─────▼──────┐            ┌──────▼───────┐                │
│  │ solvers/   │            │ surrogate/   │                │
│  │ (adaptador)│            │ (puente R)   │                │
│  └─────┬──────┘            └──────┬───────┘                │
├────────┼──────────────────────────┼────────────────────────┤
│   RS2 Modeler/Interpreter    Rscript + deepgp              │
│   (puertos locales)          (proceso por llamada)         │
└────────────────────────────────────────────────────────────┘
        ▲ modo demo: DemoSolver sustituye a RS2 con una
          tabla de resultados reales precalculados (§8)
```

## 4. Estructura de directorios del repositorio

```
geosurrogate/
├─ pyproject.toml               # paquete instalable; entry points CLI
├─ README.md                    # escaparate GitHub (capturas, GIF, quickstart)
├─ LICENSE                      # pendiente de decisión (§13)
├─ .gitignore
├─ ARQUITECTURA.md              # este documento
├─ src/geosurrogate/
│  ├─ __init__.py
│  ├─ cli.py                    # geosurrogate run|ui|demo
│  ├─ config.py                 # modelos pydantic de project.yaml (§6.3)
│  ├─ project.py                # crear/abrir proyecto; estado; eventos (§6.4)
│  ├─ solvers/
│  │  ├─ base.py                # interfaz FEMSolver + tipos (§6.1)
│  │  ├─ rs2.py                 # adaptador RS2Scripting (Modeler+Interpreter)
│  │  └─ demo.py                # DemoSolver: oráculo de resultados precalculados (§8)
│  ├─ doe/
│  │  ├─ lhs.py                 # LHS y LHS-Maximin (scipy.stats.qmc)
│  │  ├─ pem.py                 # vértices 2^D + selección K-Means
│  │  └─ hybrid.py              # muestreo híbrido LHS+PEM (contribución del TFM)
│  ├─ surrogate/
│  │  ├─ r_bridge.py            # contrato Python↔R (§6.2)
│  │  └─ r/fit_predict_alc.R    # ÚNICO script R, N-dimensional
│  ├─ activelearning/
│  │  ├─ loop.py                # máquina de estados del bucle AL
│  │  └─ runner.py              # JobRunner: lanza/observa/pausa el proceso
│  ├─ validation/
│  │  ├─ loocv.py               # R², RMSE, cobertura ±2σ
│  │  ├─ ks.py                  # K-S dos muestras; curva D y p-value vs n
│  │  └─ massive.py             # contraste contra simulaciones FEM independientes
│  ├─ exploitation/
│  │  ├─ sampling.py            # normal/lognormal/triangular/uniforme + truncamiento
│  │  ├─ montecarlo.py          # MCS sobre el surrogate; PoF = P[SRF < umbral]
│  │  └─ sensitivity.py         # tornado y sensibilidad condicionada
│  └─ reporting/
│     ├─ figures.py             # figuras plotly (UI) + matplotlib (informe)
│     └─ report.py              # informe HTML/PDF + export Excel
├─ app/                         # Streamlit; importa el núcleo, nunca al revés
│  ├─ Home.py                   # selector/creador de proyectos; acceso a demos
│  ├─ pages/
│  │  ├─ 1_Modelo.py            # .fez o caso demo; geometría; materiales detectados
│  │  ├─ 2_Variables.py         # matriz material×propiedad; contador de dimensión
│  │  ├─ 3_Distribuciones.py    # familia+parámetros+truncamiento por variable
│  │  ├─ 4_DoE.py               # estrategia, tamaños, semilla; preview; coste estimado
│  │  ├─ 5_Entrenamiento.py     # lanzar/pausar/reanudar; convergencia en vivo; log
│  │  ├─ 6_Validacion.py        # LOOCV + curva K-S; validación masiva opcional
│  │  ├─ 7_Explotacion.py       # MCS, histograma SRF, PoF, sensibilidad
│  │  └─ 8_Informe.py           # generar y descargar informe + Excel
│  └─ components/               # visor de geometría, editor de matriz de variables,
│                               # gráfico de convergencia, tarjeta de estado del job
├─ demo_cases/                  # datos, no código (§8)
│  ├─ registry.yaml
│  ├─ slope_2d/  embankment_4d/  cliff_6d/
├─ tests/
│  ├─ test_config.py  test_doe.py  test_sampling.py
│  ├─ test_r_bridge.py          # se omite si no hay R en la máquina
│  └─ test_e2e_demo.py          # pipeline completo con DemoSolver (sin licencias)
└─ docs/                        # capturas, GIF para README/LinkedIn
```

## 5. Módulos del núcleo: responsabilidades

| Módulo | Responsabilidad | Hereda de (TFM) |
|---|---|---|
| `config` | Validar y tipar `project.yaml` (pydantic); valores por defecto sensatos | constantes de cabecera de ~20 scripts |
| `project` | Ciclo de vida del proyecto-carpeta; escritura atómica; eventos | gestión manual de carpetas |
| `solvers.rs2` | Abrir modelo, listar materiales, asignar (c, φ) **por nombre**, calcular, extraer SRF, dibujar geometría; gestión de puertos/procesos propia (sin `taskkill` global); reintentos | `Ingest_from_excel_*`, `orquestador_*` (mitad RS2), `Tharsis_extract_malla` (know-how de malla) |
| `doe` | LHS/Maximin/PEM/híbrido/factorial 3^D, N-dimensional con semillas explícitas | `generar_doe_*`, `LHS_sampling` |
| `surrogate.r_bridge` | Una llamada limpia a R: ajustar GP + predecir + ALC; errores tipados; log | `acquisition_*.R`, `*_slave*.R` (×16 → 1) |
| `activelearning` | Bucle DoE→fit→ALC→FEM→append→convergencia; reanudable; presupuesto y tolerancia | `orquestador_*` (mitad bucle) |
| `validation` | LOOCV, curva K-S vs n, validación masiva; devuelve métricas+figuras como objetos | `validar_loocv_*`, `analisis_convergencia_ks_*`, `validacion_masiva_*` |
| `exploitation` | Muestreo de distribuciones (truncadas), MCS sobre el surrogate, PoF, sensibilidad | `simulador_montecarlo_*`, `analisis_sensibilidad_*` |
| `reporting` | Informe HTML/PDF reproducible + export Excel | `Scripts_imagenes_TFM` (parcial) |

### 5.1 La interfaz `FEMSolver` (§ contrato 1)

```python
@dataclass
class MaterialInfo:
    name: str            # nombre en el modelo (clave estable para el usuario)
    index: int           # índice interno del solver (nunca expuesto en la UI)
    criterion: str       # "mohr_coulomb" en v1
    current_values: dict # c, phi actuales (defaults para la UI)

@dataclass
class CaseResult:
    case_id: str
    srf: float | None
    status: Literal["ok", "fem_error", "no_convergence", "timeout"]
    elapsed_s: float
    fem_file: Path | None   # según política de retención

class FEMSolver(Protocol):
    def connect(self) -> None: ...
    def list_materials(self, model: Path) -> list[MaterialInfo]: ...
    def get_geometry(self, model: Path) -> GeometryData: ...   # contornos/malla para dibujar
    def run_case(self, model: Path, assignments: dict[str, float],
                 workdir: Path, case_id: str) -> CaseResult: ...
    def shutdown(self) -> None: ...
```

`assignments` se indexa por `variable.id` del config; el adaptador resuelve material+propiedad. Un fallo FEM devuelve `CaseResult` con estado tipado — nunca un string `"ERROR"` dentro del dataset (el bucle registra el fallo en el log de eventos y excluye la fila del entrenamiento).

### 5.2 PLAXIS/FLAC en el futuro

Una clase nueva en `solvers/` por software (ambos tienen API Python). Nada más cambia: DoE, AL, validación y explotación son agnósticos. Único requisito transversal: que el output escalar sea configurable (SRF en RS2; FoS equivalente en otros).

## 6. Contratos clave

### 6.1 `project.yaml` (esquema de configuración)

```yaml
project:
  name: "Dique — ejemplo Rocscience"
  schema_version: 1
solver:
  type: rs2                      # rs2 | demo
  model_file: model/embankment.fez
  rscript_path: "C:/Program Files/R/R-4.5.3/bin/Rscript.exe"
  ports: {modeler: 60054, interpreter: 60055}
  timeout_s: 1800
  fem_retention: keep_all        # keep_all | keep_failed | keep_none
variables:
  - id: coh_m1
    material: "Embankment"       # por NOMBRE; el adaptador resuelve el índice
    property: cohesion
    training_bounds: [26.3, 86.2]    # dominio del surrogate (caja de entrenamiento)
    distribution:                    # distribución probabilística para explotación
      family: lognormal              # normal | lognormal | triangular | uniform
      mean: 50.0
      std: 10.0
      truncate: [26.3, 86.2]         # truncada a la caja por defecto
  - id: phi_m1
    material: "Embankment"
    property: friction_angle
    training_bounds: [42.1, 50.2]
    distribution: {family: normal, mean: 46.0, std: 1.3}
doe:
  strategy: hybrid_lhs_pem       # lhs | lhs_maximin | pem | hybrid_lhs_pem | factorial_3
  n_lhs: 40
  n_pem: 40
  seed: 42
active_learning:
  acquisition: alc
  tolerance: 0.01                # error máx. entre superficies consecutivas
  max_iterations: 50
  budget_total_sims: 120         # corte duro de presupuesto FEM
  n_candidates: 1000
  refresh_candidates: true       # malla nueva por iteración (decisión explícita; ver §12)
  validation_grid: {n: 10000, seed: 999}
  seed: 123
surrogate:
  engine: deepgp_r
  mcmc: {nmcmc: 3000, burn: 1000, thin: 2}
  kernel: exp2
  separable: true
exploitation:
  mcs_samples: 100000
  failure_threshold: 1.0         # PoF = P[SRF < 1.0]
  seed: 7
```

Notas de diseño: `training_bounds` (dónde es válido el surrogate) y `distribution` (qué es probable) son conceptos separados a propósito — en la UI se visualizan juntos (la densidad dibujada dentro de la caja). La matriz de correlaciones entre variables queda como extensión futura del bloque `variables`.

### 6.2 Contrato Python↔R (§ contrato 2)

Un único script `fit_predict_alc.R`, agnóstico a la dimensión (lee las columnas que recibe). **El escalado se hace siempre en Python** (en el TFM estaba duplicado en cada script R); R recibe X∈[0,1]^D e y estandarizada.

| Dirección | Archivo | Contenido |
|---|---|---|
| Py → R | `work/train.csv` | columnas `x1..xD`, `y` (escaladas) |
| Py → R | `work/predict.csv` | filas a predecir: candidatos + malla de validación (concatenadas; columna `set` ∈ {cand, valid}) |
| Py → R | `work/params.json` | nmcmc, burn, thin, kernel, separable, semilla, flag ALC |
| R → Py | `work/predictions.csv` | `mean`, `s2` por fila de predict.csv |
| R → Py | `work/alc.csv` | score ALC por fila del subconjunto `cand` |
| R → Py | `work/diagnostics.json` | tiempos, warnings, parámetros MCMC efectivos |

`r_bridge.py` invoca `Rscript` con timeout, captura stdout/stderr al log del proyecto y lanza excepciones tipadas (`RNotFound`, `RScriptError(stderr=...)`). La selección del mejor candidato, la desestandarización y el criterio de parada viven en Python.

### 6.3 Estado y eventos (§ contrato 3)

`state.json` (escritura atómica: tmp + replace):

```json
{"phase": "active_learning", "status": "running", "pid": 12345,
 "iteration": 12, "n_samples": 92, "error_max": 0.018,
 "budget_used": 92, "budget_total": 120,
 "started_at": "2026-06-10T18:02:11", "updated_at": "2026-06-10T19:14:03"}
```

`events.jsonl` (append-only; alimenta la curva en vivo y el replay del modo demo):

```json
{"ts": "...", "type": "doe_case_done", "case_id": "Case_0017", "srf": 2.41, "elapsed_s": 184}
{"ts": "...", "type": "al_iteration", "iter": 12, "error_max": 0.018, "x_next": {...}, "srf_pred": 2.07}
{"ts": "...", "type": "phase_change", "from": "active_learning", "to": "validation"}
```

Pausar = la UI escribe `control.json {"request":"pause"}`; el bucle lo lee entre iteraciones y termina limpio. Reanudar = relanzar el proceso: reconstruye su posición desde dataset + state.

## 7. Anatomía de un proyecto de análisis (carpeta de trabajo)

```
MiAnalisis/
├─ project.yaml          # configuración (única fuente de verdad)
├─ state.json            # estado vivo del job
├─ events.jsonl          # histórico de eventos
├─ control.json          # solicitudes UI→job (pause/stop)
├─ dataset.csv           # dataset acumulado (inputs + SRF + metadatos por caso);
│                        #   CSV en F1 (KB, legible, diffeable); parquet cuando el volumen lo justifique
├─ dataset.xlsx          # export para el usuario (regenerado, nunca fuente)
├─ model/                # copia del .fez subido
├─ fem/                  # Case_*.fez según política de retención
├─ surrogate/            # work/ del puente R + diagnósticos por iteración
├─ validation/           # métricas.json + figuras
├─ exploitation/         # muestras MCS, PoF, sensibilidad
├─ report/               # informe final HTML/PDF
└─ log/run.log           # log completo con timestamps
```

## 8. Modo demo (la pieza clave para GitHub/LinkedIn)

### 8.1 Tres niveles, de menor a mayor requisito

| Nivel | Qué ve el usuario | Requiere |
|---|---|---|
| **Galería** | Resultados finales de cada caso: validación, PoF, sensibilidad, métricas | Nada (ni R ni RS2) — funciona en Streamlit Cloud |
| **Replay grabado** | El bucle AL "ejecutándose": curva de convergencia animada reproduciendo `events.jsonl` real grabado | Nada — ideal para el GIF de LinkedIn y la demo pública |
| **Demo viva** | El bucle AL ejecutándose de verdad (deepgp reentrenando) contra el oráculo de datos | R local (no RS2) — para talleres y evaluación seria |

### 8.2 `DemoSolver`: active learning sobre *pool*

El truco que hace honesta la demo viva: en modo demo, la malla de candidatos del AL se restringe al conjunto de puntos con SRF **ya simulado en RS2** (entrenamiento + validación masiva del TFM, ~550 puntos por caso). El bucle elige de ese *pool* y el `DemoSolver` "simula" devolviendo el valor real por lookup (con latencia configurable, 0 s o realista). Resultado: **cada SRF mostrado en la demo es un resultado FEM real**, no una interpolación — un argumento potente al presentarla. El AL basado en pool es además una variante estándar en la literatura.

### 8.3 Casos demo y procedencia de datos (copiar, nunca mover)

**Decisión del autor (10-06-2026):** la demo v1 incluye solo los casos derivados de ejemplos de Rocscience (2D y 4D). Los casos del acantilado real (6D/8D) quedan aplazados.

| Caso demo | D | Estado | Origen de datos (TFM, solo lectura) |
|---|---|---|---|
| `slope_2d` — talud homogéneo | 2 | v1 | `Prueba_Geometria_3/Reporte_SRF_Final.xlsx` (16) + `LHS_500_Geometria_3.xlsx` (500) → pool 516 |
| `embankment_4d` — dique 2 materiales | 4 | v1 | `Prueba_Geometria_5/Reporte_SRF_Final.xlsx` (51) + `LHS_500_Geometria_5.xlsx` (500) → pool 551 |
| `embankment_3d` — dique, 3 variables | 3 | planificado (F4) | **Se generará con la propia herramienta** (*dogfooding*) sobre `Embankment.fez`: cohesión y fricción del material 1 + solo cohesión del material 2 (la 4.ª variable fija en su media). No existe dataset previo: los datos 4D del TFM varían siempre las 4 variables y ningún punto cae en el corte 3D |
| `cliff_6d` / `cliff_8d` | 6/8 | aplazados | Pendiente decisión de procedencia (modelo real) |

Nota de diseño que motiva el caso 3D: **la dimensionalidad emerge de la selección de variables** (qué casillas se marcan en la matriz material×propiedad). El config admite cualquier subconjunto; D no está cableada en ninguna parte del núcleo.

**No se distribuye ningún `.fez`.** Cada caso demo empaqueta: `case.yaml` (config equivalente), `lookup.csv` (inputs→SRF reales), `geometry.json` (contornos extraídos una sola vez vía API para dibujar la sección; F4) y `results/` (métricas y figuras finales; F3). Son datos derivados: legalmente mucho más limpios que redistribuir modelos, y pesan KB.

## 9. Flujo extremo a extremo (modo real RS2)

1. **UI páginas 1–4** construyen `project.yaml`: subir `.fez` → `solver.list_materials()` puebla la matriz de variables → distribuciones y caja de entrenamiento → DoE con preview y coste estimado (n × tiempo medio por simulación, medido en la primera).
2. **Página 5** lanza `geosurrogate run <proyecto>` (proceso aparte). El bucle: fase DOE (simula el diseño inicial) → fase AL (fit GP → ALC → mejor candidato → FEM → append → ¿error máx < tolerancia o presupuesto agotado?) → fase VALIDATION (LOOCV + curva K-S automáticas). La UI refresca cada ~2 s leyendo state/events.
3. **Páginas 6–8** consumen artefactos: validación (con la formulación rigurosa: *"no se rechaza H₀ al nivel α = 0,05"*), explotación (MCS de 10⁵ muestras sobre el surrogate en segundos, PoF, tornado) e informe descargable.

## 10. Pruebas y CI

- Unitarias sin dependencias externas: `config`, `doe`, `sampling` (propiedades estadísticas con semillas fijas).
- `test_r_bridge`: marcada `skipif` sin R; en GitHub Actions se instala R + deepgp (ubuntu) — el puente queda probado en CI.
- `test_e2e_demo`: **pipeline completo** (DoE→AL→validación) con `DemoSolver` en CI, sin ninguna licencia. Es el test que protege todo el flujo y un sello de calidad visible en el README (badge).
- RS2 real: suite manual documentada (`tests/manual_rs2.md`) para ejecutar en máquina licenciada.

## 11. Stack y dependencias

Python ≥ 3.11 · `pydantic` v2, `pandas` + `pyarrow`, `scipy`, `scikit-learn`, `streamlit`, `plotly`, `RS2Scripting` (solo modo real) · R 4.5.3 + `deepgp` (solo modo real y demo viva). Pin de versiones en `pyproject.toml`; las versiones de referencia ya están verificadas en el TFM (`RS2Scripting_VSC/requirements.txt` y README).

## 12. Mejoras que el prototipo corrige del pipeline del TFM

| Problema diagnosticado (10-06-2026) | Solución aquí |
|---|---|
| ~74 scripts duplicados por dimensión | Módulos N-dimensionales únicos (§5) |
| Constantes dispersas y rutas hardcodeadas | `project.yaml` + descubrimiento de materiales (§6.1) |
| Índices de material `[0],[2],[3],[4]` frágiles | Referencia por nombre, resuelta por el adaptador (§5.1) |
| Excel Maestro reescrito sin atomicidad | parquet + escritura atómica; xlsx solo como export (§7) |
| `"ERROR"` como string en el dataset | `CaseResult.status` tipado; fallos fuera del entrenamiento (§5.1) |
| Malla de candidatos fija por efecto colateral del seed | `refresh_candidates` explícito en config (§6.1) |
| `taskkill` global y `sleep` fijos | Gestión de procesos propia con reintentos (§5) |
| Sin logs ni trazabilidad de tiempos | `run.log` + `events.jsonl` con duración por caso (§6.3) |
| Escalado duplicado en cada script R | Escalado centralizado en Python; R agnóstico (§6.2) |

## 13. Decisiones (resueltas por el autor el 10-06-2026)

1. **Casos demo:** opción (c) — v1 con 2D+4D; los del acantilado real, después. Añadido el caso **3D** (`embankment_3d`) generado con la propia herramienta en F4 (ver §8.3).
2. **Nombre:** `geosurrogate`, confirmado.
3. **Idioma UI:** **conmutable EN/ES desde el día 1** mediante diccionarios de traducción (`app/i18n/en.json`, `app/i18n/es.json` + helper `t(key)` y selector en la barra lateral). Idioma por defecto: inglés. El coste es bajo si se construye así desde el principio; lo caro es retrofitarlo. Núcleo, CLI y logs permanecen en inglés.
4. **Licencia y visibilidad:** repo **privado** durante la construcción; decisión open-core vs escaparate se pospone a F5.
5. **Umbral de PoF:** configurable por proyecto (`exploitation.failure_threshold`, por defecto 1,0; 1,3 en el caso demo 4D para una PoF no nula).
6. **Estrategia de DoE por dimensionalidad** (10-06-2026): `factorial_3` (malla 3^D equiespaciada: esquinas + puntos medios + centro) para los casos de baja dimensión (D ≤ 3; en 2D reproduce exactamente los 9 puntos del Caso 1 del TFM y converge en menos simulaciones que el híbrido); `hybrid_lhs_pem` para D ≥ 4, donde 3^D se vuelve inviable. La estrategia se elige por proyecto en `doe.strategy`; guarda de seguridad: `factorial_3` rechaza D > 5.
7. **Versión de RS2 por máquina** (11-06-2026): la localización del ejecutable es automática — RS2Scripting resuelve "la instalación más reciente" vía registro de Windows (`HKLM\SOFTWARE\Rocscience\RS2 <generación>`), así que el usuario típico no configura nada. Para instalaciones no estándar o múltiples versiones existen los overrides opcionales `solver.rs2_modeler_executable` / `solver.rs2_interpreter_executable`. El acoplamiento real es **paquete ↔ aplicación**: la versión de `RS2Scripting` instalada con pip debe corresponder a la generación de RS2 de la máquina (por eso el extra `[rs2]` no fija versión y el README lo documenta). El comando `geosurrogate check [--simulate]` actúa como *preflight*: conexión, materiales del modelo contra las variables configuradas y, opcionalmente, una simulación de humo cronometrada.

## 14. Plan de construcción por fases

| Fase | Contenido | Criterio de "hecho" |
|---|---|---|
| **F1 — Núcleo + demo 2D** | `config`, `project`, `doe`, `r_bridge`, `loop`, `runner`, `DemoSolver`; caso `slope_2d` empaquetado | `geosurrogate demo run slope_2d` reproduce por CLI la convergencia del TFM de principio a fin |
| **F2 — UI mínima** | `Home` + páginas 1–5 en modo demo; replay grabado; curva en vivo | Demo navegable completa sin R ni RS2 |
| **F3 — Validación y explotación** | Páginas 6–8; LOOCV, K-S, MCS, PoF, sensibilidad, informe | Galería completa de los casos demo; informe descargable |
| **F4 — Modo real RS2** | `solvers/rs2.py`: descubrimiento, geometría, ejecución, reintentos; **generar el dataset del caso demo `embankment_3d` con la propia herramienta** (*dogfooding*) | Análisis nuevo end-to-end sobre `Embankment.fez` en tu máquina; caso 3D empaquetado en `demo_cases/` |
| **F5 — Publicación** | README con GIF, CI verde, demo pública (galería+replay) en Streamlit Cloud, decisión de licencia | Enlace público listo para LinkedIn |

Orden de dependencias: F1 → F2 → (F3 ∥ F4) → F5. Las fases 1–3 no necesitan RS2 en absoluto: se pueden construir y verificar íntegramente con los datos ya calculados del TFM.

## 15. Backlog inmediato (tras F1–F4)

1. **Validación del caso 3D real** — pendiente de orden del autor (no lanzar LOOCV/masiva hasta que la dé). El comando `geosurrogate testset` ya está **construido y probado** (11-06-2026): LHS independiente en la caja de entrenamiento (semilla 777, distinta de las de entrenamiento), simulación con el solver real, reanudable (parcial CSV tras cada caso), salida lista para `validate --massive --ks --test-xlsx`; rechaza proyectos demo (ahí se usa `--use-pool`).
2. Empaquetado del 3D como caso demo (`tools/build_demo_cases.py` + registry) cuando termine la corrida.
3. UI — **viaje desde cero con un solo `.fez`** (diseño acordado con el autor, 11-06-2026). **Implementado (11-06-2026): LOOCV automática al terminar el entrenamiento** (`active_learning.auto_loocv`, por defecto activa; fase `auto_validation` visible con progreso en Training y Validación) **y breadcrumb de "siguiente paso recomendado"** en la barra lateral de todas las páginas (`compute_next_step`: entrenar → ver en vivo → auto-validación → LOOCV → independiente → explotación → informe → completo, con enlace navegable). Pendientes del viaje: subida del `.fez` en Home con preflight automático (conexión + descubrimiento de materiales), editor de variables (matriz material×propiedad con checkboxes) y de distribuciones (PDF en vivo), estrategia de DoE recomendada por D con coste estimado del smoke test, informe auto al completar la validación, replay animado de `events.jsonl`.
4. Informe HTML/PDF de un clic (la página 8 ya descarga artefactos y zip).
5. Extracción de geometría del `.fez` para el visor de la página Modelo.
