# ADR-0011: Recuperación de cuenta después de responder

- **Estado:** aceptado
- **Fecha:** 2026-09-06
- **Issue:** [#33 — Prevent timing-based account enumeration in recovery endpoints](https://github.com/software-development-workshop/udesa-x/issues/33)
- **Reemplaza parcialmente:** ADR-0003 para el reenvío de verificación y la ejecución dentro
  del request de ADR-0010 para los dos endpoints genéricos de recuperación.

## Contexto

La recuperación de contraseña y el reenvío de verificación contestaban `202` sin contenido,
pero solamente las cuentas elegibles esperaban al proveedor. Una respuesta idéntica no evita
la enumeración si su tiempo permite distinguir una cuenta existente de una desconocida.

El registro tiene otro contrato: debe conservar la cuenta y devolver `502` Problem Details
si no puede enviar el primer link. Ese envío sigue siendo síncrono.

## Decisión

Los dos endpoints genéricos validan el cuerpo y programan siempre una tarea con
`BackgroundTasks`, sin consultar la cuenta antes de responder. La tarea ejecuta el flujo
completo de recuperación después de enviar el `202`, incluida la consulta de elegibilidad,
la emisión del token y el envío por Resend.

Los handlers, la construcción del mailer y las tareas que despachan el trabajo son
asíncronos. El trabajo bloqueante corre en un `ThreadPoolExecutor` propio de cuatro workers
por proceso. Compartir el pool de FastAPI permitía que una ráfaga de envíos a cuentas
elegibles bloqueara `/health` y revelara actividad por otra ruta. Cuatro workers limitan
también las sesiones ocupadas por recuperación por debajo de las cinco conexiones base
del pool actual de SQLAlchemy. La capacidad se revisará si cambia la configuración de base
o la carga; no se agrega otra variable de entorno para este alcance.

Responder no necesita conseguir un worker libre. Las tareas esperan al executor sin
bloquear el event loop y el SDK de correo sigue siendo síncrono. El executor vive durante
el proceso; el cierre normal del servidor espera las tareas y Python cierra sus threads.

Cada tarea crea y cierra su propia sesión de SQLAlchemy. Recibe únicamente el identificador
validado y un mailer sin estado por request, nunca la sesión ni objetos ORM del request.
La capa de servicio conserva las reglas y el repositorio las transacciones.

La elegibilidad se comprueba nuevamente bajo el bloqueo de la fila al emitir el token:
verificación requiere una cuenta sin verificar; reset requiere una cuenta verificada;
ambos excluyen cuentas suspendidas o eliminadas. El rate limit existente de recuperación
sigue contando pedidos por cuenta, sin importar si entraron por email o handle.

Si falla el envío de un reset, se invalida exclusivamente el token de ese intento. Una
respuesta tardía del proveedor no puede invalidar el link de un pedido posterior. El
registro conserva su flujo síncrono y su error explícito.

## Alternativas consideradas

- **Posponer solamente el envío:** todavía deja consultas, bloqueos y escrituras diferentes
  antes del `202`. Posponer todo el flujo mantiene el mismo trabajo previo a la respuesta
  para identidades conocidas y desconocidas.
- **Agregar una espera fija:** depende de la carga y de cuánto tarde el proveedor; no
  garantiza que desaparezca la diferencia y consume capacidad sin hacer trabajo útil.
- **Usar el pool compartido para el correo:** mantiene rápidos los `202` individuales,
  pero agotar sus workers bloquea otras rutas síncronas y permite observar la diferencia.
- **Cola durable o outbox:** permite recuperar pedidos tras una caída del proceso, pero
  requiere persistencia y un despachador. El issue permite la ejecución en proceso y el
  reintento explícito ya existe. La cola entre microservicios que pide la materia sigue
  pendiente para notificaciones, como establece ADR-0003.

## Consecuencias y límites

- `202` significa pedido aceptado para evaluación, no correo entregado. No revela si existe
  una cuenta elegible ni si el proveedor aceptó el envío.
- Las tareas viven en el proceso de la API: no hay persistencia de pedidos, reintentos
  automáticos ni garantía de entrega ante una terminación abrupta. Un usuario puede pedir
  otro link. La ventana de caída entre emitir un token y terminar el envío ya existía.
- Los fallos de proveedor manejados mantienen la respuesta genérica y la invalidación del
  reset. Fallos de infraestructura o terminación del proceso no adquieren garantías nuevas.
- El timeout del SDK sigue siendo de diez segundos; limita la ocupación del worker, no la
  respuesta de los endpoints genéricos.
- No se afirma tiempo constante bajo toda carga ni se resuelve el abuso volumétrico. El
  rate limiting de reenvío sigue en #31 y no se modifica en este arreglo.
- Las pruebas observan el último mensaje ASGI de respuesta mientras el proveedor está
  bloqueado. Medir solamente `TestClient.post` sería incorrecto: ese cliente espera también
  la finalización de las tareas en segundo plano.

Referencias: [Background Tasks de Starlette](https://starlette.dev/background/) y
[recursos propios en tareas de FastAPI](https://fastapi.tiangolo.com/advanced/advanced-dependencies/#background-tasks-and-dependencies-with-yield-technical-details).
