# ADR-0009: Claude, por la API de Anthropic, como LLM del motor

* **Estado:** accepted
* **Fecha:** 2026-10-20
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 02-design
* **Versión:** 0.1.0
* **ID:** ADR-0009
* **Supersede:** ADR-0004 (intención con un LLM autoalojado); ADR-0005 (rail de entrada con NeMo Guardrails), salvo su
  política fail-closed, que se mantiene; ADR-0007 (placement del serving del LLM)
* **OWASP:** A02 (la clave de la API), A04 (TLS hasta la API) · LLM01 (inyección de prompt), LLM02 (datos personales
  hacia un tercero), LLM05 (salida no confiable), LLM10 (consumo sin límite)

Aceptada el 2026-10-20 al fusionar la PR #65, con lo que proponía: el clasificador sustituye a NeMo y Ollama, y el de
respuesta lleva los *fallbacks* del servidor.

## Contexto

El motor necesita un LLM en tres workers: el clasificador (seguridad de la entrada e intención), el de respuesta y el
evaluador (ADR-0008). Hasta ahora era Ollama con `llama3.1` (ADR-0004), que hacía de juez de NeMo y de clasificador a
la vez (ADR-0005). Pero midgard no puede servir un modelo: es un i3-3240 sin AVX2 ni GPU. La alternativa de ADR-0007
era contratar una GPU en Hetzner.

Lo comprobado el 2026-10-20 en la documentación de Anthropic:

- **Retención:** la API borra de su backend las entradas y salidas en 30 días. Lo que marquen sus sistemas de
  seguridad se guarda hasta 2 años. Lo retenido no se usa para entrenar sin permiso expreso.
- **Retención cero (ZDR):** la API de mensajes es elegible, pero se pide a Anthropic, que la aprueba por
  organización.
- **Residencia:** en la API de Anthropic, `inference_geo` solo admite `us` o `global`. Para inferencia en la UE hace
  falta Vertex AI con región `eu`, y entonces el encargado del tratamiento es Google.

## Decisión

Decisiones de Jeremi del 2026-10-20: la API de Anthropic, sin pedir ZDR por ahora, Haiku 5.5 para clasificar y
Opus 5.5 para responder y evaluar.

1. **La API de Anthropic** (`api.anthropic.com`), con el SDK oficial de Python (`anthropic`). No hay serving propio
   ni GPU que mantener.
2. **Un modelo por worker, en su configuración:**

   | Worker | Modelo | Esfuerzo | Por qué |
   |---|---|---|---|
   | Clasificador | `claude-haiku-5-5` | `low` | Una tarea corta, en todos los mensajes |
   | Respuesta | `claude-opus-5-5` | `medium` (el suyo por defecto) | La calidad de lo que lee la persona |
   | Evaluador | `claude-opus-5-5` | `low` | Un veredicto corto sobre una respuesta ya escrita |

   Cambiar de modelo o de esfuerzo es cambiar la configuración, sin tocar código.
3. **El clasificador hace, en una sola llamada, lo que hacían NeMo y Ollama en dos:** decide si el mensaje se
   atiende y cuál es su intención.
   - La respuesta tiene un esquema fijo (`output_config.format`): `permitido`, `motivo`, `etiqueta`, `confianza`,
     `entidades`. Ningún texto libre llega más allá.
   - Se mantiene la política **fail-closed** de ADR-0005. Si falla la llamada, la respuesta no valida o Claude
     rechaza el mensaje (`stop_reason: "refusal"`), el mensaje queda `permitido=false`, con el motivo distinguido
     (error, rechazo o bloqueo).
   - **NeMo, Ollama y `annoy` salen del motor.** Con ellos se van la compilación de C++ en la imagen y la obligación
     de desarrollar en Linux.
4. **El de respuesta** recibe en el `system` la persona del bot y sus reglas, y en `messages` las últimas vueltas y
   el mensaje nuevo.
   - **El texto de la persona va siempre en un turno de usuario, nunca en el `system`.** Es la defensa básica contra
     la inyección de prompt (LLM01).
   - **El `system` es estable por bot y se cachea** (prompt caching).
   - **Lleva los *fallbacks* del lado del servidor** (`fallbacks: "default"`): si el modelo rechaza, la API reintenta
     con otro modelo dentro de la misma llamada. Si el rechazo persiste, el motor responde un texto fijo del bot y
     lo deja en el log.
5. **La salida de Claude no es de confianza (LLM05).**
   - El de respuesta no tiene herramientas: las acciones son del enlace, con los destinos validados (I7).
   - El evaluador revisa la respuesta antes de enviarla.
   - El notificador solo envía texto: nada de enlaces construidos por el modelo, ni plantillas, ni botones.
6. **Una clave de la API por worker que la usa**, guardada en Andvari, en `motor/data/anthropic/<worker>`. Cada rol
   `motor-<worker>` lee solo la suya.
   - Se revoca y se mide el gasto por worker.
   - La clave nunca está en un `.env`, en la imagen ni en el log.
7. **Límites, para que el gasto no se dispare (LLM10):**
   - un `max_tokens` por worker (256 para el clasificador y el evaluador, 1024 para el de respuesta);
   - un timeout del SDK por worker, con 2 reintentos;
   - el límite de gasto mensual de la organización en la consola de Anthropic.

   El coste estimado es de unos 3 céntimos de dólar por mensaje respondido: unos 0,02 céntimos el clasificador,
   1,8 el de respuesta y 1 el evaluador, con 1 500, 3 000 y 2 000 tokens de entrada respectivamente, a los precios
   del 2026-10-06. No cuenta el pensamiento de Opus 5.5, que no se puede desactivar y se cobra como salida: el
   esfuerzo bajo lo acota. Se mide en el esqueleto.
8. **Los datos que salen a Anthropic** son el texto del mensaje, las últimas vueltas de la conversación y las reglas
   del bot.
   - **No salen:** el número de teléfono, el nombre del contacto, el `clientId` ni los tokens de Meta. Los workers
     solo pasan a Claude el texto.
   - La clasificación de datos y el registro de tratamientos anotan a Anthropic como encargado del tratamiento,
     con su retención de 30 días y una transferencia internacional (EE. UU.).
   - **Pedir ZDR es condición antes del primer cliente real**, junto con el DPA de Anthropic.

## Alternativas consideradas

| Opción | Pros | Contras | Riesgo de seguridad |
|---|---|---|---|
| **API de Anthropic, Haiku 5.5 para clasificar y Opus 5.5 para responder** | Sin GPU ni serving propio. Calidad y salida estructurada. Mantenido por el proveedor | Coste por mensaje. Dependencia de un tercero. Inferencia fuera de la UE | Los mensajes salen a un encargado del tratamiento en EE. UU., con 30 días de retención mientras no haya ZDR |
| Claude por Vertex AI en la UE | Inferencia en la UE | Un proyecto de GCP y sus credenciales. Algunas funciones llegan más tarde | El encargado es Google; residencia en la UE |
| Ollama en una GPU de Hetzner (ADR-0007) | Datos en una máquina propia, en la UE | Una GPU que contratar, servir, actualizar y vigilar. Más calidad pide modelos más grandes | La superficie del servidor de inferencia y su red |
| NeMo Guardrails delante de Claude | Rails declarativos | Arrastra `annoy` y C++, otra llamada por mensaje y otra configuración que mantener | La misma: el juez es otro LLM |

## Consecuencias

- **Sale del motor:**
  - `nemoguardrails`, `ollama` y, con ellos, `annoy` y la compilación de C++;
  - los adaptadores `NeMoGuardrailsPolicy` y `OllamaIntentEngine`, sustituidos por adaptadores de Claude detrás
    de los mismos puertos (`GuardrailsPolicy` e `IntentEngine`).
- **ADR-0006 se revisa:** sin un modelo propio, el worker ya no tiene que vivir junto a él. Se despliega en midgard,
  junto a Bifröst y Andvari.
- **Las pruebas no llaman a la API:** usan un cliente falso con el contrato del SDK. Una batería de evaluación
  aparte, con mensajes reales anonimizados y con coste medido, mide la calidad del clasificador y del de respuesta
  antes de cerrar el Gate 3 del motor.
- **El threat model del motor se rehace:**
  - **T1** (inyección): con un modelo externo y la salida estructurada;
  - **T5** (TLS): la API es HTTPS;
  - **T7** (timeouts): fijados;
  - **T12** (secretos): la clave en Andvari.

## Condiciones de revisión

- Llega el primer cliente real: entonces, ZDR y el DPA firmados, o pasar a Vertex AI en la UE.
- El coste medido por mensaje supera lo que el producto puede pagar.
- La calidad medida del clasificador con Haiku 5.5 no basta para el rail de seguridad.
