# Drift-Ainwater  
### Pipeline Univariado de Detección de Drift para Series de Tiempo Operacionales

---

# 1. Introducción

Este repositorio implementa el **pipeline oficial de detección de drift univariado** utilizado en el proyecto Ainwater para monitorear sensores operacionales en plantas de tratamiento.

El sistema está diseñado para operar con series de tiempo reales, afectadas por:

- Ruido y variabilidad operativa  
- Comportamientos **cíclicos** (ej. caudal afluente)  
- Comportamientos con **mesetas extremas** (sensores ON/OFF, válvulas)  
- Cambios abruptos y graduales  
- Sensores con saturación, cortes o inactividad  

El pipeline:

- Construye referencias dinámicas  
- Compara ventanas usando **métodos estadísticos** (PSI, KS, Wasserstein)  
- Detecta episodios de drift y genera flags por timestamp  
- Es completamente reproducible y configurable vía JSON  
- Produce outputs en carpetas claras: `Flags/`, `Windows/`, `config_used.json`

---

# 2. Arquitectura General

## 2.1 Diagrama Tipo A — Flujo básico (ASCII)

```text
CSV → main.py → DriftPipeline → (loop por variable)
        ↓
   preprocesamiento (plateau / ciclos)
        ↓
   construcción de referencia
        ↓
   comparación estadística
        ↓
   detección de episodios
        ↓
   Flags/  y  Windows/
```

## 2.2 Estructura del Repositorio

```text
Drift-Ainwater/
├── config/
│   └── config_drift.json
├── data/
├── main.py
├── pipeline_drift.py
├── funciones_drift.py
├── drift_thresholds.py
├── generar_config_drift.py
└── output/
```

---

# 3. Arquitectura Completa del Pipeline

## 3.1 Diagrama Tipo B — Mermaid (detalle completo)

```mermaid
flowchart TD

A[CLI: main.py] --> B[Construir DriftPipeline]

B --> C[Pipeline.run()]
C --> D[Leer config_drift.json]
C --> E[Leer CSV y ordenar por date_time]

E --> F[Detectar variables numéricas]
F --> G{Loop por variable}

%% Preprocesamiento
G --> H1[¿Var ∈ plateau_vars?]
H1 -->|Sí| H2[Aplicar mask_plateau_extreme]
H1 -->|No| H3[Seguir]

%% Configuración
H2 --> I
H3 --> I
I[Construir cfg (global + overrides)] --> J{¿Var ∈ cyclical_vars?}

%% Ciclos
J -->|Sí| J1[Forzar strategy='seasonal']
J1 --> J2[Completar cycle_hours, cycles_back, band_frac]
J2 --> K[run_drift_univariate]
J -->|No| K

%% Drift univariado
K --> L[build_reference según strategy]
L --> M[Comparación estadística (PSI / KS / Wasserstein)]
M --> N[drift_flag + threshold]
N --> O[detect_episodes]

O --> P[windows_to_point_flags]
P --> Q[Guardar Flags/VAR.csv]
O --> R[Guardar Windows/VAR_windows.csv]

C --> S[Generar config_used.json]
```

---

# 4. Preprocesamiento Especializado

## 4.1 Variables con Mesetas (Plateau)

### ¿Qué son?

Variables cuyos valores quedan adheridos a un extremo:

- **Meseta baja** (ej. largos periodos en 0 → bombas apagadas)  
- **Meseta alta** (sensor saturado a máximo valor)

Comparar periodos en meseta vs periodos de operación normal produce **falsos positivos de drift**.

### ¿Cómo actúa `mask_plateau_extreme`?

1. Detecta si existe una meseta dominante (≥ `min_share`)
2. Determina el nivel de corte usando cuantiles (`low_quantile`, `high_quantile`)
3. Sustituye la meseta por `NaN`, dejando solo valores operativos reales
4. Los `NaN` simplemente **no participan** en el análisis de drift

### Parámetros (solo en config JSON)

```json
"plateau_defaults": {
  "abs_eps": 0.5,
  "rel_eps": 0.01,
  "min_share": 0.05,
  "low_quantile": 0.02,
  "high_quantile": 0.98
}
```

### Variables típicas plateau

- Nivel Pozo WAS  
- Flujo de lodos  
- Sensores ON/OFF  
- Bombas en estado activo/inactivo  

---

# 5. Variables Cíclicas (Ciclo Diario)

## 5.1 ¿Qué son?

Variables donde la forma temporal del día se repite con alta consistencia:

- Flujo afluente PTAR  
- Flujo cámaras de contacto  
- Aireación (1, 2, 3)  
- OD (1, 2)

Si se compara una ventana nocturna vs una de mediodía → da *falso drift*.

Por eso deben compararse **ventanas equivalentes dentro del ciclo diario**.

---

## 5.2 Diagrama Tipo A — Referencia estacional (ASCII)

```text
Ciclo -4   Ciclo -3   Ciclo -2   Ciclo -1
 [T-96h]   [T-72h]    [T-48h]    [T-24h]
     \        \          \                \________\__________\__________\__ → referencia estacional
```

---

## 5.3 Diagrama Tipo B — Mermaid (operación de estacionalidad)

```mermaid
flowchart LR

A[current_end] --> B[cycle_hours detectado o definido]
B --> C[Construcción de ciclos: current_end - k * cycle_hours]
C --> D[Filtro por banda horaria ± band_frac]
D --> E[Concatenación de ciclos equivalentes]
E --> F[Referencia final (df_ref)]
```

---

# 6. Construcción de la Configuración (cfg)

## 6.1 Proceso general (ASCII)

```text
global_cfg
    + overrides[var]
    + seasonal_defaults (si aplica)
→ cfg final por variable
```

## 6.2 ¿Qué incluye el cfg?

- `method`: psi / ks / wasserstein  
- `strategy`: decay / golden / seasonal  
- `window`: duración de ventana  
- `min_points`: puntos mínimos por ventana  
- (opcionales)  
  - `cycle_hours`  
  - `cycles_back`  
  - `band_frac`  

Los parámetros de plateau y estacionalidad vienen **solo desde config**, nunca hardcodeados.

---

# 7. Drift Univariado

## 7.1 Comparación Estadística

Los métodos permitidos:

- **PSI**: índice basado en bins  
- **KS**: estadístico de Kolmogorov–Smirnov  
- **Wasserstein**: distancia de transporte óptimo (recomendado)

Proceso:

1. Se construye una referencia según `strategy`
2. Se compara la ventana actual contra la referencia
3. Se calcula `stat_value`
4. Se obtiene un umbral dinámico vía `effective_threshold`
5. Se determina `drift_flag = stat_value >= threshold`

---

# 8. Detección de Episodios

Un episodio es una secuencia contigua de ventanas en drift.

```text
NORMAL NORMAL DRIFT DRIFT DRIFT NORMAL NORMAL
               └──── episodio 1 ────┘
```

El pipeline asigna:

- `episode_id`  
- `state` = NORMAL / DRIFT  

---

# 9. Outputs

Cada corrida genera un directorio con timestamp:

```text
output/<input_stem>_<timestamp>/
    ├── Flags/
    │     └── VAR.csv
    ├── Windows/
    │     └── VAR_windows.csv
    └── config_used.json
```

### `Flags/VAR.csv`

```text
date_time, value, has_drift
```

### `Windows/VAR_windows.csv`

```text
t0, t1, stat_value, threshold, drift_flag, episode_id, state
```

---

# 10. Ejecución Básica

```bash
python main.py data/planta.csv
```

Para variables cíclicas:

```bash
python main.py data/planta.csv     --cyclical_vars "Flujo Afluente PTAR" "Flujo Cámara de contacto 2"
```

Para aplicar máscara de plateau:

```bash
python main.py data/planta.csv     --plateau_vars "Nivel Pozo WAS"
```

Ambas cosas a la vez:

```bash
python main.py data/planta.csv     --cyclical_vars "Flujo Afluente PTAR"     --plateau_vars "Nivel Pozo WAS"
```

---

# 11. Archivo de Configuración – generar_config_drift.py

Se puede crear un config inicial con:

```bash
python generar_config_drift.py     --method wasserstein     --window 12h     --strategy decay
```

El archivo será guardado en:

```text
config/config_drift.json
```

Luego se puede editar a mano para:

- agregar `seasonal_defaults`  
- agregar `plateau_defaults`  
- definir overrides por variable en el bloque `"variables"`.

---

# 12. Conclusión

El pipeline es:

- Modular  
- Robusto a ruido, estacionalidad y sensores ON/OFF  
- Configurable mediante JSON  
- Reproducible y trazable  
- Adecuado para monitoreo operacional en tiempo real o análisis histórico  

Este repositorio constituye la referencia oficial para el análisis de drift univariado en Ainwater.
