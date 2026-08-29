# Documentación del challenge

## Bugs corregidos al trasladar el notebook a `model.py`

El notebook fue un buen punto de partida para entender los datos y probar modelos, pero no estaba pensado para ejecutarse como parte de un servicio. Al llevar esa lógica a `challenge/model.py` aparecieron algunos casos que en una ejecución interactiva pasan desapercibidos, pero que en producción podían producir resultados incorrectos o hacer fallar una predicción.

### Las horas límite quedaban sin periodo del día

La función `get_period_day()` del notebook usaba comparaciones estrictas (`>` y `<`). Esto dejaba fuera horas válidas como las 05:00, 12:00 o 19:00 y devolvía `None` para ellas. Además de ser incorrecto según la definición del challenge, podía introducir valores vacíos durante el preprocesamiento.

En `model.py` los intervalos quedaron expresados sin huecos:

- mañana: desde las 05:00 hasta antes de las 12:00;
- tarde: desde las 12:00 hasta antes de las 19:00;
- noche: cualquier otra hora.

La implementación compara la hora numérica (`5 <= hour < 12` y `12 <= hour < 19`), por lo que también evita depender del formato textual de la fecha.

### Las columnas dummy cambiaban según el lote recibido

En el notebook, `pd.get_dummies()` se ejecutaba sobre todo el dataset. Como allí estaban presentes todas las aerolíneas, meses y tipos de vuelo, el problema no era visible. En la API, en cambio, una petición puede contener un solo vuelo. Si se copiaba la lógica literalmente, solo se generaban las columnas presentes en ese lote y el modelo recibía un esquema diferente al utilizado durante el entrenamiento.

Para evitarlo, `preprocess()` reindexa el resultado contra `FEATURES_COLS`, crea con cero las columnas ausentes y conserva siempre el mismo orden. De esta manera, entrenamiento e inferencia usan exactamente las mismas diez variables, aunque una categoría no aparezca en la petición.

### La carga del dataset dependía del directorio de ejecución

El notebook carga el CSV mediante una ruta relativa porque normalmente se abre desde la carpeta `challenge`. Esa misma ruta deja de funcionar cuando el modelo se ejecuta desde la raíz del repositorio, desde pytest, dentro de un contenedor o mediante un servidor ASGI.

El entrenamiento automático ahora construye la ruta a partir de la ubicación real de `model.py` usando `Path(__file__).resolve()`. Así, encontrar `data/data.csv` no depende de dónde se haya lanzado el proceso.

### El preprocesamiento modificaba el DataFrame original

En el notebook se agregaban `min_diff`, `delay`, `high_season` y `period_day` directamente sobre el DataFrame global. Ese comportamiento es cómodo durante la exploración, pero dentro de una clase introduce estado implícito: llamar dos veces al preprocesamiento puede trabajar sobre datos que ya fueron alterados por la primera llamada.

`DelayModel` hace una copia antes de crear variables derivadas y solo calcula una columna cuando todavía no existe y están disponibles sus datos de origen. El objeto entregado por quien llama permanece intacto y el método se puede reutilizar tanto para entrenamiento como para predicción.

### La tasa de retrasos estaba invertida

El notebook calculaba la tasa de cada grupo como `total / retrasos`. Por ejemplo, con 100 vuelos y 20 retrasos devolvía `5`, cuando la tasa correcta es `20 %` (`retrasos / total * 100`). Este error afecta los gráficos y las conclusiones del análisis exploratorio.

Esa función no se trasladó a `model.py` porque no participa en el preprocesamiento ni en la inferencia. Aun así, el error se tuvo en cuenta al revisar las conclusiones del notebook: los gráficos construidos con esas tasas se descartaron y no se utilizaron como criterio para elegir el modelo.

## Decisión de implementación

Se mantuvieron las diez features seleccionadas en el notebook y se eligió una regresión logística con `class_weight="balanced"`. En la única partición evaluada ofrece un recall y un F1 para vuelos retrasados muy similares a XGBoost balanceado, con una implementación más sencilla y sin agregar otra dependencia al proyecto.

El objetivo del traslado no fue reescribir el experimento, sino conservar su intención y eliminar los supuestos propios del notebook que no eran seguros al servir predicciones reales.

## Estado de la Parte I

La primera parte queda terminada. El modelo puede preprocesar datos tanto para entrenamiento como para inferencia, entrenarse y devolver predicciones binarias. La validación final se hizo con `make model-test`: las cuatro pruebas pasaron y `challenge/model.py` alcanzó un 100 % de cobertura. Solo quedan advertencias informativas de pandas por columnas con tipos mixtos en el CSV; no afectan el resultado de las pruebas.

## Parte II: API

El modelo se expuso con FastAPI mediante `POST /predict`. La API acepta uno o varios vuelos, valida la aerolínea, el tipo de vuelo y el mes, y devuelve las predicciones en una lista. Cuando alguno de esos datos no es válido, responde con estado HTTP 400. También se dejó disponible `GET /health` para comprobar que el servicio está activo.

La validación se ejecutó con `make api-test`. Las cuatro pruebas pasaron: una petición válida devolvió HTTP 200 con la predicción esperada y las tres peticiones con datos inválidos devolvieron HTTP 400. No se presentaron errores ni advertencias; `challenge/api.py` alcanzó 97 % de cobertura y la cobertura total fue 94 %. La suite proporcionada se concentra en `/predict`, por lo que `/health` queda implementado, aunque no está cubierto por esas cuatro pruebas.

## Parte III: productización

La API se empaquetó en una imagen Docker basada en Python 3.10 y configurada para ejecutar Uvicorn en el puerto 8080. Después de validar el contenedor localmente, se desplegó en Cloud Run y se comprobó que el endpoint `/health` respondiera correctamente desde su URL pública.

La prueba de estrés final se ejecutó contra el servicio desplegado con 100 usuarios y una tasa de creación de 10 usuarios por segundo. Se completaron 17 842 solicitudes a `/predict` sin fallos, con un promedio de 285 ms, un percentil 95 de 370 ms y cerca de 301 solicitudes por segundo. Locust advirtió un uso alto de CPU en la máquina que generó la carga, por lo que el rendimiento máximo podría estar limitado por el cliente de prueba y no por la API.

Con la URL pública configurada en el `Makefile` y el servicio disponible en Cloud Run, la parte III queda terminada.

## Parte IV: CI/CD

Se prepararon dos workflows de GitHub Actions. El de integración continua instala las dependencias y ejecuta las pruebas del modelo y de la API en cada cambio dirigido a `develop` o `main`. El de entrega continua queda listo para desplegar en Cloud Run después de una ejecución exitosa de CI.

El despliegue automático requiere configurar `WIF_PROVIDER` y `WIF_SERVICE_ACCOUNT` en GitHub. Como no fue posible completar esos permisos de IAM en el proyecto, el workflow omite el despliegue cuando las variables no existen, en lugar de generar un fallo engañoso. La imagen, el despliegue manual y el servicio publicado ya fueron validados durante la parte III.

## Persistencia y ciclo de vida del modelo

Hasta la parte III el modelo se re-entrenaba en cada arranque del servicio. Eso funcionaba, pero tenía tres problemas: el cold start leía y procesaba todo el CSV antes de poder responder, el resultado dependía de que `data.csv` estuviera disponible dentro de la imagen y dos despliegues distintos podían terminar sirviendo modelos diferentes si los datos cambiaban.

La solución fue separar el entrenamiento de la inferencia. El script `challenge/train.py` entrena el modelo a partir de `data/data.csv` y lo persiste como `challenge/model.joblib` usando joblib, ejecutable con `python -m challenge.train`. La imagen Docker corre ese script durante el build, por lo que el artefacto queda empaquetado y el arranque en Cloud Run solo lo carga en memoria. El artefacto no se versiona en git: se regenera en cada build, como cualquier otro producto de compilación.

Para esto `DelayModel` ganó dos métodos, `save()` y `load()`, con la misma idea que el resto de la clase: una sola ruta por defecto (`MODEL_PATH`, junto a `model.py`) y sin depender del directorio de ejecución.

La API mantiene una contingencia: si el artefacto no existe al primer request, entrena desde el CSV, guarda el artefacto para la siguiente ejecución y registra un warning en el log. Es un respaldo para desarrollo local y para los tests, no el camino normal — en producción el artefacto siempre viene en la imagen. Si el modelo no puede entrenarse ni cargarse, el error se propaga en lugar de devolver una predicción inventada.

El ciclo de vida queda así: entrenar con `python -m challenge.train` cuando cambien los datos o el modelo, construir la imagen, desplegar. El test `test_model_save_and_load` verifica que un modelo guardado y cargado produce predicciones idénticas al original.
