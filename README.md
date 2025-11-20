# Drift-Ainwater
Pipeline de detección de **drift univariado** para series de tiempo operacionales del proyecto Ainwater.

Este repositorio implementa un flujo modular y reproducible, inspirado en la arquitectura del pipeline de **outliers**, con el objetivo de mantener una línea coherente entre ambos módulos de calidad de datos, pero simplificando su uso y haciéndolo más general y escalable.

---

## 📌 1. Objetivo del Proyecto

El pipeline permite:

- Procesar series de tiempo con una columna obligatoria `date_time`.
- Evaluar drift **univariado** para múltiples variables numéricas.
- Definir estrategia, métrica, ventana y umbrales desde un **config global**.
- Generar un **CSV final por variable** con un flag `has_drift`.
- Registrar la **configuración exacta usada**, para máxima reproducibilidad.
- Mantener un flujo idéntico al pipeline de outliers, facilitando la adopción interna.

---

## 📁 2. Estructura del Repositorio

```
Drift-Ainwater/
├── data/                  ← archivos CSV de entrada (opc.)
├── output_drift/          ← salidas organizadas por corrida
├── config/
│   └── config_drift.json  ← configuración global
│
├── main.py                ← punto de entrada del pipeline
├── pipeline_drift.py      ← lógica principal de ejecución
├── detectors.py           ← detectores de drift (ventanas + métricas)
├── funciones_drift.py     ← funciones de referencia (decay, golden, seasonal)
├── generar_config_drift.py← genera config base
│
├── README.md
└── .gitignore
```

---

## ⚙️ 3. Instalación

Requisitos mínimos:

```
pip install numpy pandas scipy
```

Python recomendado: **3.10+**

---

## 🧩 4. Archivo de Configuración (Global)

Antes de ejecutar el pipeline por primera vez, genera un config base:

```
python generar_config_drift.py --output config/config_drift.json
```

Este archivo:

- **NO depende del CSV**
- Es **global para cualquier planta o archivo**
- Puedes editarlo manualmente para ajustar parámetros

### Ejemplo de config generado

```json
{
  "global": {
    "metric": "wasserstein",
    "strategy": "decay",
    "window": "12h",
    "threshold": 0.2,
    "min_points": 5
  }
}
```

### ¿Y las variables?

Ya no se incluyen variables explícitas en el config.  
Cada vez que ejecutes el pipeline sobre un CSV:

- se procesarán **todas las columnas numéricas**,  
- o solo las que especifiques con `--columns`.

Esto permite usar un **solo config** para múltiples plantas o archivos.

---

## 🚀 5. Ejecutar el Pipeline

La forma más simple:

```
python main.py data/archivo.csv
```

Si quieres limitarlo a algunas columnas:

```
python main.py data/archivo.csv --columns var_1 var_2
```

Si quieres cambiar el config:

```
python main.py data/archivo.csv --config otra_config.json
```

---

## 📤 6. Salida del Pipeline

Cada corrida crea una carpeta independiente:

```
output_drift/archivo_20251120_161044/
├── var_1_drift.csv
├── var_2_drift.csv
├── ...
└── config_used.json
```

### Formato de cada CSV

| date_time | value | has_drift |
|-----------|--------|-----------|

- `value` → valor original de la variable
- `has_drift` → booleano (`true` / `false`)

### Archivo `config_used.json`

Registra:

- Config global cargada
- Config efectiva usada
- Fecha/hora de corrida
- Columnas procesadas
- Ruta del CSV de entrada

Ideal para trazabilidad en producción.

---

## 🔍 7. Lógica Interna del Pipeline

### 7.1 `main.py`
- Parsea argumentos.
- Valida el CSV de entrada.
- Carga el config global.
- Invoca `DriftPipeline.run()`.

### 7.2 `pipeline_drift.py`
- Valida la columna `date_time`.
- Selecciona columnas numéricas.
- Combina config global + overrides de CLI.
- Ejecuta detección variable por variable.
- Genera outputs limpios y organizados.

### 7.3 `detectors.py`
Implementa todo el mecanismo de drift:

- Ventanas deslizantes (`window`)
- Estrategias de referencia:
  - **decay**
  - **golden**
  - **seasonal**
- Métrica (una sola, definida en config):
  - **psi**
  - **ks**
  - **wasserstein**
- Umbral (`threshold`)
- Histéresis de cierre (evita parpadeos)

### 7.4 `funciones_drift.py`
Define cómo se calcula la referencia:

- `ref_decay_prefix_mass()`
- `ref_golden()`
- `ref_seasonal()`

---

## 🧪 8. Validación y Buenas Prácticas

Para evaluar el rendimiento del pipeline recomendamos:

- Usar series sintéticas con etiquetas manuales  
- Medir métricas de cobertura/precisión fuera del pipeline
- Verificar que `threshold` produce resultados razonables
- Ajustar la ventana (`12h`, `24h`, etc.) según el tipo de drift

Este repositorio **no contiene métricas de evaluación**, solo la detección.

---

## 🧱 9. Extensibilidad

El diseño modular permite:

- Agregar nuevas métricas estadísticas
- Incluir nuevos baselines temporalmente dependientes
- Crear variantes multivariadas (futuro)
- Integración directa con Airflow u otros orquestadores

---

## 👥 10. Autores

Desarrollado como parte del Proyecto de Grado de Ciencia de Datos UC (2025) por:

- **Franco Chiappe**
- **Vicente Garay**
- **Ziyu Guo**