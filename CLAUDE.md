# CLAUDE.md — geosurrogate

Lee este archivo completo al iniciar cada sesión en esta carpeta. El estado
detallado del proyecto (qué se hizo, resultados verificados, bugs cazados y
pendientes) está en **ESTADO.md**; el diseño completo en **ARQUITECTURA.md**.
Los tres archivos son la memoria del proyecto: mantenlos al día al cerrar
cada bloque de trabajo.

## 1. Qué es este proyecto

**geosurrogate**: plataforma de análisis de fiabilidad para estabilidad de
taludes. Construye un *surrogate model* de Procesos Gaussianos (librería
`deepgp` de R, inferencia MCMC) mediante *active learning* (función de
adquisición ALC) sobre un modelo de elementos finitos (RS2 de Rocscience en
v1), lo valida (LOOCV, validación masiva, curva K-S) y lo explota (Monte
Carlo masivo → probabilidad de fallo PoF). Dashboard Streamlit + CLI.

- **Autor/dueño:** Geovanny Benavides (Máster Ingeniería Geológica, UPM).
  Responde SIEMPRE en español. Le gusta probar la UI a fondo y reportar
  fricciones: tómalas como QA de primera y corrígelas con test de regresión.
- **Origen:** prototipo comercial derivado de su TFM (defensa junio 2026).
  El material del TFM vive en `G:\TFM_GeovannyBenavides\RS2Scripting_VSC`
  — **NUNCA modifiques ese directorio** (solo lectura; de ahí se copiaron
  los datos de los casos demo).
- **Visión:** repo privado en GitHub → escaparate en LinkedIn → herramienta
  comercial; núcleo agnóstico al solver (RS2 hoy; PLAXIS/FLAC en el futuro
  vía la interfaz `FEMSolver`).

## 2. Estado en tres líneas

Fases F1 (núcleo) + F2 (dashboard 8 páginas) + F3 (validación/explotación)
+ F4 (adaptador RS2 real) **completas y verificadas** (46 tests, incluido
e2e con deepgp real), más el flujo guiado (auto-LOOCV al converger,
breadcrumbs) y el viaje desde cero (subida de `.fez`, descubrimiento de
materiales, editor de variables, preflight en UI). Tres casos demo
empaquetados con resultados FEM reales. **Falta:** F5 (publicación GitHub)
y el backlog de ARQUITECTURA §15. Detalle y números en ESTADO.md.

## 3. Cómo trabajar aquí

- **Entorno:** `.venv` local (Python 3.11.4). Instalación editable ya hecha
  (`pip install -e .[ui,dev]` + `RS2Scripting==11.28.0`).
- **Tests:** `.venv\Scripts\python -m pytest -q` → 46 deben pasar. El e2e
  (`test_e2e_demo`) entrena con deepgp real (~100 s); los de UI usan
  AppTest de Streamlit (sin navegador).
- **CLI:** `geosurrogate demo list|run`, `new`, `check [--simulate]`,
  `run`, `testset`, `validate [--loocv --massive --ks --use-pool
  --test-xlsx]`, `exploit`, `report`, `ui`.
- **Dashboard:** `geosurrogate ui` → localhost:8501. Si tocas módulos de
  `src/` hay que **reiniciar el servidor** (Python cachea imports); si solo
  tocas `app/` (páginas), basta refrescar el navegador.
- **R obligatorio** para entrenar/validar/explotar: R 4.5.3 +
  `deepgp` (ruta de Rscript en el config de cada proyecto). **RS2
  licenciado** solo para modo real (esta máquina lo tiene).
- `runs/` es zona de pruebas (gitignored): crea y borra proyectos ahí sin
  miedo. `runs/embankment_3d` es el caso real 3D completo — no lo borres.

### Reglas operativas (aprendidas a base de incidentes)

- **Una sola tarea RS2 a la vez** (entrenamiento real, testset, preflight,
  detect): comparten los puertos 60054/60055. Si un proceso se aborta con
  Ctrl+C pueden quedar `RS2`/`Interpret` huérfanos ocupando puertos —
  cerrarlos por PID (nunca `taskkill /im` global: mataría sesiones del
  usuario).
- Las corridas son **reanudables**: `geosurrogate run <dir>` retoma del
  `dataset.csv`; `testset` retoma de su CSV parcial.
- `--fast` (MCMC reducido) es solo para comprobar mecánica: su ruido de
  muestreo posterior (~0,002) impide converger con tolerancias finas. Las
  métricas presentables salen del modo completo.

### Convenciones de código

- Código y commits en inglés; commits con
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. OJO PowerShell
  5.1: sin comillas dobles dentro de `git commit -m @'...'@` (rompe los
  argumentos).
- UI bilingüe EN/ES: todo texto pasa por `t(clave)` con diccionarios en
  `app/i18n/{en,es}.json` (añade SIEMPRE ambas lenguas).
- **Todo `st.button`/`st.download_button` lleva `key=` único** — hay un
  test AST que lo exige (las pestañas renderizan todo a la vez y las
  etiquetas traducidas pueden colisionar).
- Rigor estadístico innegociable (herencia del TFM): el K-S nunca
  "demuestra igualdad" — la formulación es *"H0 not rejected at α = 0.05"*
  y la convergencia se argumenta con D (independiente del tamaño muestral),
  no con el p-value. Con 0 fallos en MCS, la cota de PoF es la regla del
  tres (3/n), no la aproximación normal.
- Figuras de validación **sin títulos** (las etiquetas viven en las
  tarjetas del dashboard y en las secciones del informe HTML).
- Operaciones largas en la UI: proceso desacoplado (`launch_cli`) + archivo
  de progreso + fragmento auto-refrescante + botón deshabilitado mientras
  corre. Análisis con bucle de refits → progreso contado
  (`*_progress.json` por refit); llamada única larga a R → progreso por
  etapas (`running_stage`/`stage_progress_bar` en `ui.common`).
- Directorios de trabajo R únicos por proceso (`work_*_{pid}`) — dos
  análisis concurrentes no deben compartir CSVs.

## 4. Mapa del repo

- `src/geosurrogate/` — núcleo (nunca importa Streamlit):
  `config.py` (pydantic, `project.yaml` = única fuente de verdad),
  `project.py` (proyecto-carpeta: estado atómico, eventos, dataset),
  `solvers/` (interfaz `FEMSolver`; `rs2.py` real con materiales POR
  NOMBRE + `discover_materials`; `demo.py` pool-based: cada SRF servido es
  un resultado RS2 real), `doe/` (LHS/Maximin/PEM/híbrido/factorial_3),
  `surrogate/` (puente R: UN script N-dimensional, escalado en Python),
  `activelearning/` (bucle reanudable + runner), `validation/` (LOOCV, K-S,
  masiva, testset), `exploitation/` (muestreo truncadas + MCS/PoF),
  `reporting/` (figuras + informe HTML autocontenido), `ui/` (helpers
  comunes + wizard del viaje desde cero).
- `app/` — dashboard Streamlit: `Home.py` (abrir / nuevo desde demo /
  nuevo desde `.fez`) + `pages/1..8` (Model, Variables, Distributions,
  DoE, Training, Validation, Exploitation, Report) + `i18n/`.
- `demo_cases/` — datos, no código: `registry.yaml` + por caso `case.yaml`
  + `lookup.csv` (pool de resultados RS2 reales; sin ningún `.fez`).
- `examples/embankment_3d.yaml` — proyecto real de ejemplo; `models/` —
  `.fez` base (gitignored); `tools/build_demo_cases.py` — empaqueta los
  demos desde el TFM y desde `runs/embankment_3d` (re-ejecutable).
- `tests/` — 46: unidad (config, doe, sampling, wizard, next_step),
  humo de UI por AppTest, e2e demo con R real.

## 5. Lo que falta (orden sugerido)

1. **F5 — publicación:** ANTES del primer push, configurar la identidad
   git real del autor y amendar (la actual es provisional:
   `geovanny.benavides@example.com`); crear repo **privado** en GitHub
   (autenticación pendiente: el autor no quiso conectar `gh` aún); README
   escaparate con capturas/GIF; CI (GitHub Actions con R, sin RS2 — el
   DemoSolver permite el e2e completo).
2. **Backlog ARQUITECTURA §15:** informe autogenerado al completar la
   validación; replay animado de `events.jsonl`; visor de geometría del
   `.fez`; análisis de sensibilidad (tornado) en exploitation; familia
   triangular en el editor del wizard; casos demo 6D/8D (pendiente
   decisión de procedencia: usan el modelo del acantilado real del TFM).
3. Menores: PoF ilustrativa en demo 3D si el dueño quiere (subir
   `failure_threshold` a ~1,40 daría PoF ≈ 0,20); n recomendado del
   testset en la UI (regla 2–3 × n_train).

## 6. Decisiones cerradas (no re-litigar; detalle en ARQUITECTURA §13)

Nombre `geosurrogate` · UI conmutable EN/ES (defecto EN) · repo privado ·
umbral de PoF configurable por proyecto · DoE por dimensionalidad:
`factorial_3` para D ≤ 3 (reproduce la malla 3^D del TFM; converge mejor
que el híbrido en baja D), `hybrid_lhs_pem` para D ≥ 4 · candidatos del AL
refrescados por iteración (corrige efecto colateral del TFM) · demos solo
con modelos publicables (tutoriales Rocscience); el acantilado real (6D/8D)
aplazado · RS2 se localiza por registro de Windows automáticamente; el
acoplamiento es versión del paquete pip ↔ generación de RS2 instalada.
