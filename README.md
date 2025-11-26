# 📘 Drift-Ainwater

**Pipeline Univariado de Detección de Drift para Series de Tiempo Operacionales**

Desarrollado como parte del Proyecto de Grado de la Licenciatura en Ingeniería en Ciencia de Datos – Pontificia Universidad Católica de Chile (2025), en colaboración con Ainwater.

---

## 📋 Tabla de Contenidos

1. [Propósito del Proyecto](#-propósito-del-proyecto)  
2. [Arquitectura General](#-arquitectura-general)  
3. [Instalación y Requisitos](#-instalación-y-requisitos)  
4. [Configuración del Pipeline](#-configuración-del-pipeline)  
5. [Uso por CLI](#-uso-por-cli)  
6. [Outputs Generados](#-outputs-generados)  
7. [Flujo Detallado por Variable](#-flujo-detallado-por-variable)  
8. [Estrategias de Referencia](#-estrategias-de-referencia)  
9. [Variables Especiales](#-variables-especiales)  
10. [Estructura del Proyecto](#-estructura-del-proyecto)  
11. [Ejemplos de Uso](#-ejemplos-de-uso)  
12. [Evaluación y Métricas](#-evaluación-y-métricas)  
13. [Extensibilidad](#-extensibilidad)  

---

## 🎯 Propósito del Proyecto

Este repositorio implementa el pipeline oficial de Ainwater para **detectar drift univariado** en sensores operacionales de plantas de tratamiento de agua (caudales, niveles, oxígeno disuelto, aireación, etc.).

### Objetivos principales

✅ **Monitoreo continuo** de calidad de datos en sensores operacionales.  
✅ **Trazabilidad total** – la configuración efectiva queda registrada en los outputs.  
✅ **Modularidad** – referencia, métricas, umbrales y lógica de pipeline están desacopladas.  
✅ **Reproducibilidad** – `config_used.json` permite recrear cualquier corrida.  
✅ **Manejo de casos reales**:

- Sensores con mesetas extremas (variables ON/OFF).  
- Sensores con ciclos fuertes (diarios, horarios, semanales).  
- Sensores con tendencia suave o ruido natural.  

### ¿Qué NO es este proyecto?

- ❌ No es un detector multivariado (cada variable se evalúa de forma independiente).  
- ❌ No incluye modelos de predicción o forecasting.  
- ❌ No reemplaza ni corrige sensores; solo identifica **cambios de comportamiento** en las series.

---

## 🧱 Arquitectura General

El pipeline sigue una arquitectura modular con **separación estricta de responsabilidades**:

```text
┌─────────────────────────────────────────────────────────────┐
│                    CSV de Entrada                           │
│            (date_time + variables numéricas)                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      main.py (CLI)                          │
│  - Define qué columnas procesar (--columns)                 │
│  - Marca variables especiales:                              │
│    • --plateau_vars  → aplicar máscara de mesetas           │
│    • --cyclical_vars → usar referencia seasonal             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              DriftPipeline (pipeline_drift.py)              │
│                                                             │
│  1. Carga configuración JSON (global + defaults)            │
│  2. Loop por cada variable numérica:                        │
│     a) Preprocesamiento (si aplica máscara plateau)         │
│     b) Fusión de configuración (global + overrides)         │
│     c) Construcción de ventanas temporales                  │
│     d) Construcción de referencia según estrategia          │
│     e) Evaluación de drift (PSI, KS, Wasserstein)           │
│     f) Detección de episodios (episode_id)                  │
│     g) Proyección a timestamps (flags)                      │
│  3. Guardado de resultados:                                 │
│     - Windows/var_X_windows.csv                             │
│     - Flags/var_X.csv                                       │
│     - config_used.json                                      │
└─────────────────────────────────────────────────────────────┘
```

### Principio de diseño fundamental

**La CLI define que variables son especiales, el JSON define como tratarlas.**

- `--plateau_vars` marca variables como ON/OFF → el JSON define los parámetros numéricos (`abs_eps`, `rel_eps`, `min_share`, etc.).  
- `--cyclical_vars` marca variables como cíclicas → el JSON define los parámetros de ciclo (`cycle_hours`, `cycles_back`).  

---

## 💻 Instalación y Requisitos

### Requisitos del Sistema

- **Python 3.10+**
- Paquetes obligatorios: `numpy`, `pandas`
- Paquete recomendado: `scipy` (para métodos KS y Wasserstein)

### Instalación

```bash
# Clonar el repositorio
git clone https://github.com/fchiapped/Drift-Ainwater.git
cd Drift-Ainwater

# Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install numpy pandas scipy
```

### Verificación de Entorno

El pipeline realiza un **chequeo automático** al ejecutarse:

```bash
python main.py data/ejemplo.csv
```

Si falta alguna dependencia, verás por ejemplo:

```text
⚠️  ADVERTENCIA: scipy no está instalado
   Los métodos 'ks' y 'wasserstein' no estarán disponibles

   Ejecuta: pip install scipy
```

Si faltan `numpy` o `pandas`, el pipeline se detiene con un mensaje explícito.

---

## ⚙️ Configuración del Pipeline

### Archivo de Configuración Global

El pipeline se controla mediante un **archivo JSON centralizado** (por defecto: `config/config_drift.json`). Este archivo no depende de un CSV particular y puede reutilizarse entre plantas y datasets.

#### Generar configuración inicial

```bash
python generar_config_drift.py --output config/config_drift.json
```

#### Estructura del JSON

```json
{
  "global": {
    "method": "wasserstein",
    "strategy": "decay",
    "window": "12h",
    "threshold": null,
    "min_points": 60
  },

  "seasonal_defaults": {
    "cycle_hours": 24.0,
    "cycles_back": 10,
    "band_frac": 0.15
  },

  "plateau_defaults": {
    "abs_eps": 0.5,
    "rel_eps": 0.01,
    "min_share": 0.05,
    "low_quantile": 0.02,
    "high_quantile": 0.98
  },

  "variables": {
    "Flujo Afluente PTAR": {
      "strategy": "seasonal"
    },
    "Nivel Pozo WAS": {
      "window": "24h"
    }
  }
}
```

### Parámetros Globales

| Parámetro   | Descripción                        | Valores posibles                     | Default      |
|------------|------------------------------------|--------------------------------------|--------------|
| `method`   | Métrica estadística de drift       | `"psi"`, `"ks"`, `"wasserstein"`     | `"wasserstein"` |
| `strategy` | Estrategia de referencia           | `"decay"`, `"golden"`, `"seasonal"`  | `"decay"`    |
| `window`   | Tamaño de ventana                  | `"6h"`, `"12h"`, `"24h"`, etc.       | `"12h"`      |
| `threshold`| Umbral explícito de la métrica     | número o `null`                      | `null` (dinámico) |
| `min_points` | Mínimo de puntos por ventana     | entero positivo                      | `60`         |

Si `threshold` es `null`, se utiliza la lógica dinámica definida en `drift_thresholds.py` (por ejemplo, `factor · std(ref)` en Wasserstein).

### Parámetros Estacionales (`seasonal_defaults`)

Usados **solo** cuando `strategy = "seasonal"` o cuando la variable está en `--cyclical_vars`:

| Parámetro      | Descripción                               | Ejemplo                      |
|----------------|-------------------------------------------|------------------------------|
| `cycle_hours`  | Duración del ciclo completo (horas)       | `24.0` (diario), `168.0` (semanal) |
| `cycles_back`  | Número de ciclos históricos usados        | `10` (últimos 10 días)         |
| `band_frac`    | Fracción de banda (reservado / avanzado)  | `0.15`                       |

### Parámetros de Meseta (`plateau_defaults`)

Usados **solo** cuando la variable está en `--plateau_vars`:

| Parámetro      | Descripción                                        | Rango típico      |
|----------------|----------------------------------------------------|-------------------|
| `abs_eps`      | Tolerancia absoluta para detectar meseta           | `0.1–1.0`         |
| `rel_eps`      | Tolerancia relativa (fracción del rango)          | `0.01–0.05`       |
| `min_share`    | Fracción mínima de puntos en meseta                | `0.05–0.20`       |
| `low_quantile` | Cuantil inferior para definir extremo bajo         | `0.01–0.05`       |
| `high_quantile`| Cuantil superior para definir extremo alto         | `0.95–0.99`       |

### Overrides por Variable

Puedes sobreescribir parámetros globales para variables específicas:

```json
{
  "variables": {
    "Flujo Afluente PTAR": {
      "strategy": "seasonal",
      "window": "24h"
    },
    "OD Reactor 1": {
      "threshold": 0.5,
      "method": "ks"
    }
  }
}
```

**Orden de precedencia**:

1. `global`  
2. `seasonal_defaults` / `plateau_defaults` (según estrategia / tipo de variable)  
3. `variables[nombre]` (override específico)  

---

## 🖥️ Uso por CLI

### Sintaxis Básica

```bash
python main.py <input_csv> [opciones]
```

### Ejemplos de Uso

#### 1. Ejecución mínima

```bash
python main.py data/planta.csv
```

- Usa `config/config_drift.json` como configuración global.  
- Procesa **todas** las columnas numéricas del CSV de entrada.  
- Guarda resultados en `output/planta_<timestamp>/`.

#### 2. Procesar columnas específicas

```bash
python main.py data/planta.csv --columns "Flujo Afluente PTAR" "OD Reactor 1"
```

#### 3. Variables cíclicas (estacionalidad diaria/semanal)

```bash
python main.py data/planta.csv   --cyclical_vars "Flujo Afluente PTAR" "Flujo Cámara de contacto 1"
```

**Efecto**:

- Fuerza `strategy = "seasonal"` para esas variables.  
- Aplica parámetros de `seasonal_defaults` del JSON.  
- Ajusta `window = cycle_hours` automáticamente.

#### 4. Variables con mesetas extremas (ON/OFF)

```bash
python main.py data/planta.csv   --plateau_vars "Nivel Pozo WAS" "Bomba Recirculación"
```

**Efecto**:

- Aplica `mask_plateau_extreme()` antes de la detección.  
- Usa parámetros de `plateau_defaults` del JSON.  
- Elimina mesetas extremas (períodos prolongados en valores mínimo/máximo).

#### 5. Combinación completa

```bash
python main.py data/planta.csv   --config config/config_custom.json   --output-dir resultados_drift   --columns "Flujo PTAR" "OD Reactor 1" "Nivel WAS"   --cyclical_vars "Flujo PTAR"   --plateau_vars "Nivel WAS"
```

### Opciones CLI Disponibles

| Opción         | Descripción                           | Default                     |
|----------------|---------------------------------------|-----------------------------|
| `input_csv`    | Ruta al CSV de entrada (obligatorio)  | -                           |
| `--config`     | Ruta al JSON de configuración         | `config/config_drift.json`  |
| `--output-dir` | Directorio raíz de salida             | `output/`                   |
| `--columns`    | Lista de columnas a procesar          | Todas las numéricas         |
| `--cyclical_vars` | Variables con estacionalidad fuerte| Ninguna                     |
| `--plateau_vars`  | Variables tipo ON/OFF con mesetas   | Ninguna                     |

---

## 📤 Outputs Generados

Cada corrida crea un subdirectorio único con timestamp:

```text
output/
└── planta_20251119_143300/
    ├── Windows/
    │   ├── Flujo_Afluente_PTAR_windows.csv
    │   ├── OD_Reactor_1_windows.csv
    │   └── ...
    ├── Flags/
    │   ├── Flujo_Afluente_PTAR.csv
    │   ├── OD_Reactor_1.csv
    │   └── ...
    └── config_used.json
```

### 1. Flags por Timestamp (`Flags/`)

Un flag booleano por cada timestamp original de la variable:

| date_time           | value | has_drift |
|---------------------|-------|-----------|
| 2025-01-01 00:00:00 | 12.34 | false     |
| 2025-01-01 00:10:00 | 12.50 | false     |
| 2025-01-01 00:20:00 | 15.10 | true      |
| 2025-01-01 00:30:00 | 18.23 | true      |

- `value`: serie original de la variable.  
- `has_drift`: `true` si el timestamp cae dentro de una ventana marcada con drift para esa variable.

Uso típico: visualización de zonas en drift y filtrado de datos anómalos.

### 2. Detalle por Ventana (`Windows/`)

Una fila por ventana evaluada:

| t0                    | t1                    | drift_flag | stat_value | threshold | episode_id | state  |
|-----------------------|----------------------|-----------:|-----------:|----------:|-----------:|--------|
| 2025-01-01 00:00:00   | 2025-01-01 12:00:00  | false      | 0.12       | 0.30      | NaN        | NORMAL |
| 2025-01-01 12:00:00   | 2025-01-02 00:00:00  | true       | 0.45       | 0.30      | 1.0        | DRIFT  |
| 2025-01-02 00:00:00   | 2025-01-02 12:00:00  | true       | 0.52       | 0.30      | 1.0        | DRIFT  |

- `t0`, `t1`: inicio y fin de la ventana.  
- `drift_flag`: `true` si se detectó drift en esa ventana.  
- `stat_value`: valor de la métrica de drift (PSI, KS o Wasserstein).  
- `threshold`: umbral efectivo usado.  
- `episode_id`: ID del episodio de drift al que pertenece la ventana (NaN si NORMAL).  
- `state`: estado del detector después de esa ventana (`NORMAL` o `DRIFT`).  

Uso típico: análisis detallado, debugging del pipeline y ajuste fino de umbrales.

### 3. Configuración Usada (`config_used.json`)

```json
{
  "input_csv": "data/planta.csv",
  "run_dir": "output/planta_20251119_143300",
  "generated_at": "2025-11-19T14:33:00.123456",
  
  "global": {
    "method": "wasserstein",
    "strategy": "decay",
    "window": "12h",
    "threshold": null,
    "min_points": 60
  },
  
  "seasonal_defaults": { ... },
  "plateau_defaults": { ... },
  
  "variables": {
    "Flujo Afluente PTAR": {
      "strategy": "seasonal",
      "window": "24h",
      "cycle_hours": 24.0
    }
  },
  
  "cyclical_vars": ["Flujo Afluente PTAR"],
  "plateau_vars": ["Nivel Pozo WAS"]
}
```

Permite trazabilidad total: saber con qué parámetros se ejecutó cada corrida.

---

## 🔄 Flujo Detallado por Variable

### Diagrama de Flujo Completo

```text
┌────────────────────────────────────────┐
│   Variable VAR seleccionada            │
│   series = df_raw[VAR]                 │
└──────────────┬─────────────────────────┘
               │
               ▼
    ┌──────────────────────────┐
    │ ¿VAR ∈ plateau_vars?     │
    └──────────┬───────────────┘
               │ Sí
               ▼
    ┌────────────────────────────────────┐
    │ Preprocesamiento Plateau           │
    │ mask_plateau_extreme(series,       │
    │   abs_eps, rel_eps, min_share,     │
    │   low_quantile, high_quantile)     │
    │                                    │
    │ → Elimina mesetas extremas         │
    │ → Retorna serie con NaN en mesetas │
    └──────────┬─────────────────────────┘
               │
               ▼
    ┌────────────────────────────────────┐
    │ Construcción de cfg para VAR       │
    │ _build_cfg_for_var(VAR)            │
    │                                    │
    │ Fusión:                            │
    │  global                            │
    │  + seasonal_defaults (si seasonal) │
    │  + variables[VAR] (overrides)      │
    └──────────┬─────────────────────────┘
               │
               ▼
    ┌──────────────────────────┐
    │ ¿VAR ∈ cyclical_vars?    │
    └──────────┬───────────────┘
               │ Sí
               ▼
    ┌────────────────────────────────────┐
    │ Ajuste para Variables Cíclicas     │
    │ - Forzar strategy = "seasonal"     │
    │ - Completar con seasonal_defaults  │
    │ - Ajustar window = cycle_hours h   │
    └──────────┬─────────────────────────┘
               │
               ▼
    ┌────────────────────────────────────┐
    │ run_drift_univariate(series, cfg)  │
    │                                    │
    │ 1. Construir ventanas [t0, t1]     │
    │ 2. Para cada ventana:              │
    │    - Separar historial (< t0)      │
    │    - Separar ventana actual        │
    │    - build_reference(strategy)     │
    │    - score_numeric_series(method)  │
    │    - effective_threshold()         │
    │    - drift_flag = (stat >= thr)    │
    │ 3. Retornar windows_df             │
    └──────────┬─────────────────────────┘
               │
               ▼
    ┌────────────────────────────────────┐
    │ detect_episodes(windows_df)        │
    │ - Asigna episode_id a tramos       │
    │   contiguos de drift_flag=True     │
    │ - Etiqueta state (NORMAL/DRIFT)    │
    └──────────┬─────────────────────────┘
               │
               ▼
    ┌────────────────────────────────────┐
    │ windows_to_point_flags()           │
    │ - Proyecta ventanas → timestamps   │
    │ - Crea columna has_drift           │
    └──────────┬─────────────────────────┘
               │
               ▼
    ┌────────────────────────────────────┐
    │ Guardar CSVs:                      │
    │ - Windows/VAR_windows.csv          │
    │ - Flags/VAR.csv                    │
    └────────────────────────────────────┘
```

También puede verse en forma resumida como:

```text
┌─────────────── Variable VAR ─────────────────┐
│ series = df_raw[VAR]                         │
└─────────────────────────┬────────────────────┘
                          ▼
           ¿VAR está en plateau_vars?
                      │
           Sí → aplicar mask_plateau_extreme()
           No → continuar
                          ▼
              Config efectiva para VAR
        (_build_cfg_for_var en pipeline_drift.py)
                          ▼
           ¿VAR está en cyclical_vars?
                │
   Sí → forzar strategy="seasonal"
        ajustar window = cycle_hours
                          ▼
              run_drift_univariate()
                          │
                          ├─ dividir en ventanas
                          ├─ construir referencia (según estrategia)
                          ├─ medir stat_value (PSI/KS/W)
                          ├─ threshold dinámico (effective_threshold)
                          └─ drift_flag
                          ▼
                detect_episodes()
                          ▼
          windows_to_point_flags()
                          ▼
       Guardado: Windows/*.csv y Flags/*.csv
```

---

## 🌀 Estrategias de Referencia

La **estrategia** define cómo se construye la distribución de referencia contra la cual se compara cada ventana.

### 1. Estrategia `decay` (default)

**Ideal para**: variables sin estacionalidad clara, con posibles tendencias graduales.

**Funcionamiento**:

- Asigna **pesos exponencialmente decrecientes** al historial.  
- Los puntos más recientes tienen mayor peso.  
- La función `ref_decay_prefix_mass()` elige el prefijo de la historia que acumula una cierta masa de peso y construye la referencia con esos puntos.

**Cuándo usar**: sensores con comportamiento generalmente estable, en los que interesa priorizar lo más reciente.

---

### 2. Estrategia `golden`

**Ideal para**: variables de bajo ruido y comportamiento muy estable, donde es posible identificar “ventanas ejemplo” representativas de operación normal.

**Funcionamiento**:

- Divide el historial en ventanas.  
- Calcula una métrica de estabilidad (ej. IQR/mediana).  
- Selecciona las `k` ventanas **más estables** como referencia “dorada”.  
- La función `ref_golden()` implementa esta lógica.

**Cuándo usar**: sensores bien calibrados, procesos altamente controlados, niveles de pozo con variación lenta y acotada.

---

### 3. Estrategia `seasonal`

**Ideal para**: variables con **ciclos fuertes y repetitivos** (diarios, semanales, etc.).

**Funcionamiento**:

- Se define un ciclo de duración `cycle_hours` (ej: 24h).  
- Para una ventana actual que termina en `t1`, se buscan ciclos equivalentes en el pasado: `t1 - cycle_hours`, `t1 - 2·cycle_hours`, … hasta `cycles_back`.  
- La referencia se construye con esos ciclos históricos alineados.

**Cuándo usar**: caudales influenciados por horarios, aireación con patrones diarios, variables con rutinas operacionales marcadas.

---

## 🌟 Variables Especiales

El pipeline incluye soporte explícito para dos tipos de variables problemáticas en datos operacionales reales:

- Variables tipo **plateau** (ON/OFF, colgadas en extremos).  
- Variables **cíclicas** (con estacionalidad fuerte).  

### 1. Variables `plateau_vars`

Marcadas vía CLI con `--plateau_vars` y parametrizadas en `plateau_defaults`.

Se procesan con la función `mask_plateau_extreme()` que:

1. Detecta si la serie pasa una fracción significativa del tiempo en valores muy cercanos al mínimo o máximo (según `low_quantile`, `high_quantile`, `abs_eps`, `rel_eps`).  
2. Si existe una meseta dominante, **elimina esos puntos** (los reemplaza por `NaN`).  
3. Devuelve una serie “limpia” donde el pipeline de drift sólo observa el comportamiento **operativo** (cuando la variable no está pegada en 0 o en el máximo).  

**Motivación**:

Muchas variables de planta pasan largos períodos en 0 (bomba apagada) o en un valor extremo (válvula completamente abierta).  
Comparar distribuciones dominadas por esos estados puede esconder drift relevante cuando el sensor está “activo”.

### 2. Variables `cyclical_vars`

Marcadas vía CLI con `--cyclical_vars` y parametrizadas en `seasonal_defaults`.

Efectos principales:

- Fuerza `strategy = "seasonal"` para esas variables.  
- Completa los parámetros de ciclo (`cycle_hours`, `cycles_back`, etc.) desde el JSON.  
- Ajusta `window` para que coincida con la duración de un ciclo (`window = f"{cycle_hours}h"`).  

**Motivación**:

Si una variable tiene comportamiento fuertemente cíclico (ej: caudal horario), comparar ventanas arbitrarias (ej: 12h que mezclan mitad día y mitad noche) induce muchos falsos positivos.  
Usar ciclos completos alineados reduce drásticamente ese problema.

---

## 🧱 Estructura del Proyecto

Estructura mínima esperada del repositorio:

```text
Drift-Ainwater/
├── data/                     # CSV de entrada (ej: synthetic_plant.csv)
├── output/                   # Salidas del pipeline, organizadas por corrida
├── config/
│   └── config_drift.json     # Configuración global de drift
│
├── main.py                   # Punto de entrada (CLI)
├── pipeline_drift.py         # Lógica principal del pipeline
├── funciones_drift.py        # Estrategias de referencia + métodos estadísticos
├── drift_thresholds.py       # Lógica centralizada de umbrales
├── generar_config_drift.py   # Script para generar/actualizar config global
│
└── README.md
```

> Nota: el nombre del archivo CSV de entrada es libre, siempre que tenga una columna `date_time` y al menos una columna numérica.

---

## 🧪 Ejemplos de Uso

### 1. Detección básica en todas las variables

```bash
python main.py data/planta.csv
```

- Usa configuración por defecto.  
- Evalúa drift en todas las columnas numéricas.  
- Genera `Windows/` y `Flags/` por variable.

### 2. Caudal cíclico + nivel con mesetas

```bash
python main.py data/planta.csv   --columns "Flujo Afluente PTAR" "Nivel Pozo WAS"   --cyclical_vars "Flujo Afluente PTAR"   --plateau_vars "Nivel Pozo WAS"
```

- `Flujo Afluente PTAR` se trata como variable con ciclo → `seasonal`.  
- `Nivel Pozo WAS` aplica máscara de meseta antes de calcular drift.

### 3. Uso con configuración alternativa y salida custom

```bash
python main.py data/planta.csv   --config config/config_drift_alt.json   --output-dir drift_results_v2
```

---

## 📈 Evaluación y Métricas

Aunque este repositorio se centra en la **detección y serialización de flags**, es importante saber cómo afectan los parámetros al comportamiento del detector.

### 1. Tamaño de ventana (`window`)

- Ventanas **más grandes** (ej: 24h):  
  - Mayor estabilidad, menos ruido.  
  - Detectan drift gradual, pero pueden retrasar la detección.  
- Ventanas **más pequeñas** (ej: 3–6h):  
  - Más sensibilidad a cambios rápidos.  
  - Mayor riesgo de falsos positivos por ruido.

### 2. Umbrales (`threshold` y factores dinámicos)

- Umbral **más alto** → menos detecciones, solo drift “grande”.  
- Umbral **más bajo** → más sensibilidad, pero más falsas alarmas.

### 3. Estrategias vs tipo de variable

- `decay`: buena opción por defecto para sensores sin ciclos claros.  
- `golden`: recomendable en sensores muy estables, con poco ruido, donde es posible identificar “operación ideal”.  
- `seasonal`: imprescindible para caudales y variables fuertemente cíclicas (diario, semanal).

### 4. Efecto de `min_points`

- Si es muy alto: se descartan muchas ventanas (no se evalúa drift).  
- Si es muy bajo: se evalúan ventanas con pocos datos, lo que aumenta la variabilidad de las métricas.

---

## 🧱 Extensibilidad

La arquitectura actual permite:

- Agregar nuevos métodos estadísticos de drift (por ejemplo, Jensen–Shannon, otras distancias de distribución) implementándolos en `funciones_drift.py`.  
- Incorporar nuevas estrategias de referencia (por ejemplo, referencias por clúster o ventanas móviles robustas) extendiendo `pipeline_drift.py`.  
- Integrarse con orquestadores (Airflow, Prefect, etc.) envolviendo `main.py` o `DriftPipeline` en tareas programadas.  
- Sentar la base para futuros detectores **multivariados**, reusando la estructura de ventanas y referencias.

---

Desarrollado como parte del Proyecto de Grado de la Licenciatura en Ingeniería en Ciencia de Datos – Pontificia Universidad Católica de Chile (2025), en colaboración con Ainwater.

- **Franco Chiappe**  
- **Vicente Garay**  
- **Ziyu Guo**
