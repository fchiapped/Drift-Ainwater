# Drift-Ainwater
Pipeline de detección de **drift univariado** para series de tiempo operacionales, desarrollado como parte del Proyecto de Grado de Ciencia de Datos UC en colaboración con Ainwater.

El objetivo es ofrecer un flujo **simple, modular y reproducible**, inspirado en la arquitectura del pipeline de **outliers** del proyecto Ainwater, pero especializado en **drift de distribución** para variables numéricas.

---

## 📌 1. Objetivo del Proyecto

Este pipeline permite:

- Procesar series de tiempo con una columna obligatoria `date_time`.
- Evaluar drift **univariado** para múltiples variables numéricas.
- Definir **métrica**, **estrategia de referencia**, **tamaño de ventana** y **umbrales** desde un archivo de configuración global.
- Generar un **CSV final por variable** con un flag booleano `has_drift` para cada timestamp.
- Registrar la **configuración exacta usada en cada corrida** (`config_used.json`) para trazabilidad y reproducibilidad.
- Mantener una estructura muy similar al pipeline de outliers, facilitando su adopción por parte del equipo de Ainwater.

---

## 📁 2. Estructura del Repositorio

Estructura mínima esperada:

```text
Drift-Ainwater/
├── data/                     ← CSV de entrada (ej: synthetic_plant.csv)
├── output/                   ← salidas del pipeline, organizadas por corrida
├── config/
│   └── config_drift.json     ← configuración global de drift
│
├── main.py                   ← punto de entrada (CLI)
├── pipeline_drift.py         ← lógica principal del pipeline
├── funciones_drift.py        ← métricas estadísticas + estrategias de referencia
├── drift_thresholds.py       ← lógica centralizada de umbrales
├── generar_config_drift.py   ← script para generar/actualizar config global
│
└── README.md
```

> Nota: el nombre del archivo CSV de entrada es libre, siempre que tenga una columna `date_time` y al menos una columna numérica.

---

## ⚙️ 3. Dependencias e Instalación

### 3.1. Versiones recomendadas

- Python **3.10+**
- Paquetes de Python:
  - `numpy`
  - `pandas`
  - `scipy` (opcional pero recomendado, necesario para KS y Wasserstein)

### 3.2. Instalación rápida con `pip`

Desde un entorno virtual (recomendado):

```bash
pip install numpy pandas scipy
```

Si no quieres usar KS ni Wasserstein puedes omitir `scipy`, pero el pipeline mostrará una advertencia y esas métricas devolverán `None`.

### 3.3. Chequeo automático del entorno

Al ejecutar `main.py`, el script realiza un **chequeo básico** del entorno:

- Verifica que `numpy` y `pandas` estén instalados (obligatorios).
- Verifica si `scipy` está disponible (recomendado).
- Si falta algún paquete, se imprime:
  - Una advertencia clara.
  - Un comando `pip install ...` listo para copiar y pegar.

El chequeo **no detiene la ejecución** a menos que falten paquetes obligatorios; en ese caso el pipeline se aborta con un mensaje explicativo.

---

## 🧩 4. Archivo de Configuración Global

El pipeline se controla a través de un archivo JSON global, por defecto `config/config_drift.json`.

Antes de la primera ejecución, puedes generar un config base con:

```bash
python generar_config_drift.py --output config/config_drift.json
```

Este archivo:

- **No depende del CSV** (no lista columnas).
- Es reutilizable para **cualquier planta o archivo**.
- Se puede modificar a mano o regenerar con parámetros desde CLI.

### 4.1. Ejemplo de config global

```json
{
  "global": {
    "metric": "wasserstein",
    "strategy": "decay",
    "window": "12h",
    "threshold": null,
    "min_points": 60,
    "hysteresis_windows": 1
  }
}
```

Donde:

- `metric`: métrica estadística de drift (`"psi"`, `"ks"`, `"wasserstein"`).
- `strategy`: estrategia de referencia (`"decay"`, `"golden"`, `"seasonal"`).
- `window`: tamaño de ventana deslizante (ej: `"12h"`, `"24h"`, `"6h"`).
- `threshold`: umbral explícito. Si es `null`, se usan los **defaults dinámicos** de `drift_thresholds.py` (por ejemplo, `c · std(ref)` para Wasserstein).
- `min_points`: mínimo de puntos por ventana para evaluar drift (por ejemplo, `60` si tienes datos minutales y quieres ~1h por ventana).
- `hysteresis_windows`: número de ventanas consecutivas sin drift para cerrar un episodio (por defecto `1` → un solo “no drift” ya termina el episodio).

### 4.2. Overrides por variable (opcional)

Aunque el config no requiere una sección de variables, el pipeline soporta overrides por variable:

```json
{
  "global": {
    "metric": "wasserstein",
    "strategy": "decay",
    "window": "12h",
    "threshold": null,
    "min_points": 60,
    "hysteresis_windows": 1
  },
  "variables": {
    "var_1": {
      "window": "24h",
      "metric": "ks"
    },
    "var_2": {
      "threshold": 0.3
    }
  }
}
```

Si existe `variables.<nombre_variable>`, esos campos sobreescriben los valores globales solo para esa variable.

---

## 🚀 5. Uso del Pipeline vía CLI

El punto de entrada es `main.py`, que expone una interfaz de línea de comandos.

### 5.1. Ejecución mínima

```bash
python main.py data/archivo.csv
```

- Usa `config/config_drift.json` como configuración global (si existe).
- Procesa **todas las columnas numéricas** del CSV de entrada.
- Guarda resultados en una nueva carpeta dentro de `output/`.

### 5.2. Especificar columnas

```bash
python main.py data/archivo.csv --columns var_1 var_2
```

Solo se procesan las columnas numéricas listadas en `--columns`.

### 5.3. Usar un config alternativo

```bash
python main.py data/archivo.csv --config config/otra_config.json
```

### 5.4. Cambiar directorio de salida

```bash
python main.py data/archivo.csv --output-dir resultados_drift
```

Los resultados se escribirán en `resultados_drift/<nombre_csv>_<timestamp>/`.

---

## 📤 6. Estructura de Salida

Cada corrida crea un subdirectorio único, basado en el nombre del CSV de entrada y un timestamp:

```text
output/
└── synthetic_plant_20251120_192536/
    ├── Windows/
    │   ├── var_1_windows.csv
    │   ├── var_2_windows.csv
    │   └── ...
    ├── Flags/
    │   ├── var_1.csv
    │   ├── var_2.csv
    │   └── ...
    └── config_used.json
```

### 6.1. Archivo `Flags/var_X.csv`

Estructura:

| date_time           | value   | has_drift |
|---------------------|---------|-----------|
| 2025-01-01 00:00:00 | 12.34   | false     |
| 2025-01-01 00:10:00 | 12.50   | false     |
| 2025-01-01 00:20:00 | 15.10   | true      |
| ...                 | ...     | ...       |

- `value`: serie original de la variable.
- `has_drift`: `true` si el timestamp cae dentro de alguna ventana marcada con drift para esa variable.

### 6.2. Archivo `Windows/var_X_windows.csv`

Ejemplo de columnas:

| t0                   | t1                   | drift_flag | episode_id | stat_value | threshold | state  |
|----------------------|----------------------|------------|------------|------------|-----------|--------|
| 2025-01-01 00:00:00  | 2025-01-01 12:00:00  | false      | NaN        | 0.12       | 0.30      | NORMAL |
| 2025-01-01 12:00:00  | 2025-01-02 00:00:00  | true       | 1          | 0.45       | 0.30      | DRIFT  |
| ...                  | ...                  | ...        | ...        | ...        | ...       | ...    |

- `t0`, `t1`: inicio y fin de la ventana.
- `drift_flag`: indicador de drift para la ventana.
- `episode_id`: identifica episodios contiguos de drift (1, 2, 3, …).
- `stat_value`: valor de la métrica (`psi`, `ks` o `wasserstein`).
- `threshold`: umbral efectivo usado en esa ventana.
- `state`: estado del detector después de esa ventana (`NORMAL` o `DRIFT`).

### 6.3. Archivo `config_used.json`

Ejemplo simplificado:

```json
{
  "input_csv": "data/synthetic_plant.csv",
  "run_dir": "output/synthetic_plant_20251120_192536",
  "generated_at": "2025-11-20T19:25:36.123456",
  "global": {
    "metric": "wasserstein",
    "strategy": "decay",
    "window": "12h",
    "threshold": null,
    "min_points": 60,
    "hysteresis_windows": 1
  },
  "variables": {
    "var_1": {
      "metric": "wasserstein",
      "strategy": "decay",
      "window": "12h",
      "threshold": null,
      "min_points": 60,
      "hysteresis_windows": 1
    },
    "...": {}
  }
}
```

Esto permite saber exactamente con qué parámetros se ejecutó cada corrida.

---

## 🔍 7. Lógica Interna (Resumen)

### 7.1. `funciones_drift.py`

Contiene:

- **Métricas de drift**:
  - `psi_numeric(ref, cur)`
  - `ks_numeric(ref, cur)`
  - `wasserstein_numeric(ref, cur)`
  - `score_numeric_series(a, b, metric)` – wrapper que elige la métrica correcta.

- **Estrategias de referencia**:
  - `ref_decay_prefix_mass(df_hist, now)` – pondera exponencialmente el pasado y se queda con el prefijo que concentra cierta masa de peso.
  - `ref_golden(df_hist, win, step, k)` – busca las `k` ventanas históricas más estables según una métrica robusta.
  - `ref_seasonal(df_hist, current_end, weeks_back)` – usa historial del mismo “slot horario” (día de semana + hora) para capturar estacionalidad.

### 7.2. `drift_thresholds.py`

Centraliza la lógica de umbrales:

- `DriftThresholdConfig` define defaults:
  - `psi`
  - `ks`
  - `wasserstein_factor` (multiplicador de `std(ref)`)
  - fallbacks para casos degenerados.
- `effective_threshold(metric, ref_series, cfg, thr_override)` decide:
  - usar umbral explícito (si se definió en config), o
  - calcular uno dinámico en función de la métrica y la referencia.

### 7.3. `pipeline_drift.py`

- Define el `@dataclass DriftConfig` con los parámetros por variable.
- Implementa `run_drift_univariate(series, cfg)`:
  - Genera ventanas deslizantes con tamaño `cfg.window`.
  - Construye la referencia según `cfg.strategy`.
  - Calcula `stat_value` con la métrica elegida.
  - Compara contra `threshold` (vía `effective_threshold`).
  - Implementa lógica **stateful** de episodios y histéresis (estado `NORMAL/DRIFT`).

- Implementa `windows_to_point_flags(windows_df, index)` para pasar de ventanas a flags por timestamp.

- Clase `DriftPipeline`:
  - Carga el CSV de entrada.
  - Valida y ordena la columna `date_time`.
  - Detecta columnas numéricas y aplica `DriftConfig` global + overrides por variable.
  - Ejecuta la detección por variable y genera los CSV en `Windows/` y `Flags/`.
  - Escribe `config_used.json` con la configuración efectiva usada.

### 7.4. `main.py`

- Parsea los argumentos de CLI (`input_csv`, `--config`, `--output-dir`, `--columns`, etc.).
- Invoca el chequeo de entorno (dependencias).
- Crea una instancia de `DriftPipeline` y llama a `run()`.

---

## 🧪 8. Validación y Buenas Prácticas

Para evaluar la calidad del detector de drift se recomienda (fuera de este repo):

- Usar series sintéticas como `synthetic_plant.csv` con **etiquetas manuales de episodios**.
- Comparar episodios detectados vs episodios etiquetados:
  - Cobertura temporal (`%` de tiempo de drift real cubierto).
  - Precisión temporal (`%` de tiempo flaggeado que corresponde realmente a drift).
  - Retraso medio de detección (horas desde el inicio real del episodio).
  - Tasa de falsas alarmas por día.
- Ajustar:
  - `window` (ventanas más largas para drift gradual, más cortas para cambios abruptos).
  - `metric` (Wasserstein vs KS vs PSI).
  - `threshold` (más alto → menos falsas alarmas, más bajo → más sensibilidad).

Este repo se centra en la **detección y serialización de flags**, dejando la evaluación cuantitativa para notebooks externos del proyecto de grado.

---

## 🧱 9. Extensibilidad

La arquitectura actual permite:

- Agregar nuevas métricas de drift (por ejemplo, Jensen–Shannon, Earth Mover con normalización, etc.).
- Incorporar nuevas estrategias de referencia (por ejemplo, ventanas móviles robustas, referencias por clúster, etc.).
- Extender a escenarios multivariados (combinando varias variables en un solo detector).
- Integrarse con orquestadores (Airflow, Prefect, etc.) envolviendo `main.py` o `DriftPipeline` en tareas programadas.

---

## 👥 10. Autores

Desarrollado como parte del Proyecto de Grado de la Licenciatura en Ingeniería en Ciencia de Datos – Pontificia Universidad Católica de Chile (2025), en colaboración con Ainwater.

- **Franco Chiappe**
- **Vicente Garay**
- **Ziyu Guo**