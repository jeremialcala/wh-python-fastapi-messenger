# ADR-0012: El aislamiento entre clientes se impone en la capa de datos

* **Estado:** accepted
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 02-design
* **Versión:** 0.1.0
* **ID:** ADR-0012
* **Supersede:** —
* **Controles OWASP afectados:** A01 (control de acceso), A06 (diseño inseguro)

Aceptada el 2026-10-12.

## Contexto

El requisito de mayor riesgo es que un cliente solo acceda a lo suyo (RS01). Hoy no existe la entidad cliente: los
bots no tienen dueño, y todo se busca por el UUID del propio objeto. Con ese esquema, autenticar a cada cliente
([ADR-0004](0004-firma-en-el-webhook-jwe-en-el-resto.md)) no basta: un cliente autenticado que conociera el UUID de
un bot ajeno podría leerlo.

El código actual accede a la base desde muchos sitios, con consultas escritas a mano en cada controlador. Añadir
una comprobación de dueño en cada una es fácil de olvidar en la siguiente.

## Decisión

1. **Existe la entidad cliente**, con su identificador, su clave pública de firma y su clave de datos envuelta.
2. **Todo documento con datos de un cliente lleva su `clientId`**: bots, números, contactos, reglas e intents.
3. **Ninguna consulta se hace sin el cliente autenticado.** El acceso a datos pasa por una capa de repositorio cuyas
   operaciones exigen el `clientId` y lo añaden al filtro. Los controladores no consultan la base directamente.
4. **Un objeto ajeno responde igual que uno inexistente**: `404`, sin distinguir.
5. **Dos papeles más, aparte del cliente.** El operador, que registra clientes y no usa las rutas de los clientes
   para leer sus datos. Y el cliente de servicio (el motor), con lectura de la configuración de cualquier bot y sin
   escritura. **Corregido el 2026-10-13 por [ADR-0016](0016-credencial-del-motor-por-cliente.md):** el motor tiene
   una clave por cliente y solo lee la configuración de los bots de ese cliente.
6. **El webhook no cambia.** Lo identifica el `bot_id` de la URL y lo autentica la firma; el `clientId` se toma del
   bot.

## Alternativas consideradas

| Opción | Pros | Contras | Riesgo de seguridad |
|---|---|---|---|
| **`clientId` en cada documento y capa de repositorio obligatoria** | Un solo sitio donde se impone; se puede probar de forma exhaustiva | Hay que reescribir el acceso a datos de los controladores | Bajo si no queda ninguna consulta fuera del repositorio |
| Comprobar el dueño en cada controlador | Cambio pequeño | Una consulta nueva sin comprobación es una fuga | Alto: falla abierto por olvido |
| Una base de datos por cliente | Aislamiento físico | Coste y operación por cliente; no encaja con el tamaño del servicio | El más fuerte |

## Consecuencias

- Positivas: el aislamiento deja de depender de la disciplina de cada cambio, y se puede verificar con una prueba
  que recorra todas las rutas con las credenciales de otro cliente.
- Negativas / deuda asumida: es la reescritura más amplia que abre el diseño. Los bots que ya existen hay que
  asignarlos a un cliente inicial, el del operador.
- Impacto en threat model: es el control del acceso cruzado entre clientes (T2), la amenaza de mayor puntuación.
