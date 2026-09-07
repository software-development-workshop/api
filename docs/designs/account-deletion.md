# E1S4 Account Deletion: propuesta de alcance y diseño

Estado: **revisión 2 aprobada por Bruno para implementar el primer corte**.

Aprobación: https://github.com/software-development-workshop/udesa-x/issues/20#issuecomment-5573549307.

Esta revisión atiende los tres puntos de la
[review de Bruno](https://github.com/software-development-workshop/udesa-x/issues/20#issuecomment-5570948597).
Publicar o corregir el diseño no constituye aprobación para implementar.

Issue: [#20](https://github.com/software-development-workshop/udesa-x/issues/20).
Base inspeccionada el 2026-09-07: `origin/develop` en
`e09c86e5112b444f007a60f36c486f5af0b8d69b`.
La tarjeta sigue en Tasks, estado Ready, asignada a Joacocade. El diseño y su revisión
están publicados en el issue. El worktree de esta propuesta está basado en el SHA indicado.
La PR #40 de edición de perfil está abierta y todavía no forma parte de esa base;
antes de implementar se revisará si cambió el modelo o los flujos de Accounts.

## Criterios originales y cobertura prevista

Se conservan literalmente y por separado. Ninguno se marca como completado por este documento.

- [ ] AC.1: A "soft-delete" must be implemented in the database, preserving referential integrity, but the user must not be able to log in again.
- [ ] AC.2: All follow relationships of the deleted user must be automatically removed and disappear from the followers/following lists.
- [ ] AC.3: To confirm permanent deletion, the mobile app must require the user to re-enter their current password (to avoid accidental or malicious deletions if the phone was left unlocked).
- [ ] AC.4: All posts from the deleted user must immediately stop appearing in the feed and timeline of other users.
- [ ] AC.5: Replies and retweets from the deleted user must show a "[Deleted user]" state so existing conversation threads are not broken.

| Criterio | Estado observado | Entrega propuesta |
|---|---|---|
| AC.1 | Existe `deleted_at`, pero no una operación de baja. Login e introspección ya rechazan cuentas eliminadas. | Primer corte en Accounts: baja autenticada y transaccional, sin borrar el UUID. |
| AC.2 | No existe un servicio ni modelo de follows. | Pendiente de la capacidad de relaciones y sus listas. |
| AC.3 | No existe app móvil en este repositorio. | El primer corte exige contraseña en el servidor; el criterio sigue pendiente hasta probar la pantalla móvil. |
| AC.4 | Posts sólo expone creación; no hay feed ni timeline. | Pendiente de las lecturas y su filtro de autores eliminados. |
| AC.5 | No hay modelos ni endpoints de replies o retweets; sólo contadores en Post. | Pendiente de esas capacidades y de la representación del autor eliminado. |

## Alternativas y recomendación

1. **Recomendado: primer corte vertical en Accounts.** Entrega una baja que se puede ejercer
   por HTTP y verificar en PostgreSQL. Completa AC.1 y la parte de servidor de AC.3; mantiene
   #20 abierto. El costo es una entrega parcial explícita, hasta que existan las demás superficies.
2. Construir ahora app móvil, relaciones, lecturas de publicaciones y respuestas/reposts.
   Permitiría abordar los cinco criterios, pero introduce varios subsistemas y requiere leer
   y aprobar las tarjetas correspondientes del board antes de diseñarlos.
3. Introducir ahora una cola y réplicas del estado de eliminación. Facilitaría la limpieza
   futura, pero agrega infraestructura sin consumidores actuales y la propagación eventual
   por sí sola no garantiza la desaparición inmediata de AC.4.

Bruno aprobó sólo el primer corte. Las otras capacidades no se simulan
ni se dan por terminadas mediante tests con modelos inexistentes.

## Primer corte: baja de la cuenta autenticada

Propuesta de contrato: `POST /api/v1/account-deletions`, con JWT Bearer y cuerpo
`{"password": "contraseña actual"}`. El UUID se obtiene del token, nunca de un identificador
elegido por el cliente. Una baja confirmada devuelve `204` sin cuerpo.

La API valida el cuerpo con los mismos límites de contraseña de Login y sin recortar
espacios; traduce errores al contrato Problem Details existente. El servicio valida el
token y coordina las reglas. El repositorio obtiene la cuenta por UUID con `SELECT FOR UPDATE`,
refrescando el estado previamente cargado. Una vez adquirido el bloqueo se toma la hora
actual y se vuelven a comprobar vencimiento del JWT, revocación por `jti`, estado de cuenta
y versión de sesión. No se usa una hora anterior a la espera para calcular el lockout.
El servicio aplica la matriz siguiente y verifica la contraseña sólo si el intento está
permitido; el repositorio persiste el resultado antes de liberar el bloqueo.

Con contraseña correcta, una transacción asigna `deleted_at`, incrementa `session_version`,
invalida los tokens pendientes de verificación y recuperación y limpia el contador y bloqueo
compartidos de intentos fallidos. Conserva la fila y su UUID. Un intento incorrecto sólo
actualiza los campos de protección contra intentos fallidos: no cambia datos de perfil,
hash, `deleted_at`, `session_version` ni tokens. No se registran cuerpos, contraseñas ni tokens.

### P1: límite de confirmaciones fallidas por cuenta

Se propone reutilizar `failed_login_attempts` y `locked_until`, con los valores existentes
de Login: **5 fallos consecutivos y bloqueo de 15 minutos**. El presupuesto se comparte entre
Login y baja, y entre todos los JWT de la cuenta; rotar token, IP o proceso no lo reinicia.
La alternativa es un contador exclusivo de baja: aislaría ambos flujos, pero exige una
migración y dos presupuestos de comprobación de la misma contraseña. Se elige el estado
compartido y se acepta explícitamente que fallar la baja puede bloquear Login y viceversa.

- Con un bloqueo activo (`locked_until > now`), la baja devuelve `423` antes de comprobar
  la contraseña, aunque ésta fuera correcta. No incrementa el contador, no extiende el
  bloqueo y no revela si la contraseña presentada coincide.
- Sin bloqueo activo, cada contraseña incorrecta incrementa el contador bajo el bloqueo
  de fila. El quinto fallo persiste `locked_until = now + 15 minutos`. Los fallos primero
  a quinto devuelven `401 invalid-credentials`; las solicitudes siguientes reciben `423`.
- Cuando `locked_until <= now`, el siguiente intento permitido reinicia el contador y
  limpia el bloqueo vencido antes de evaluar su resultado. Un nuevo fallo queda en 1.
  La igualdad exacta con el vencimiento permite intentar nuevamente.
- El commit del contador y del eventual bloqueo ocurre **antes** de devolver el error.
  Lanzar una excepción no debe provocar un rollback de ese registro.
- Un Login correcto fuera del bloqueo reinicia el contador, como hoy; recuperar la contraseña
  correctamente también lo limpia e incrementa `session_version`, invalidando el JWT robado.
  Una baja correcta limpia el contador junto con la baja. Obtener otro JWT sin una
  comprobación correcta de contraseña no concede intentos adicionales.
- Login conserva su contrato actual: durante el bloqueo responde `401` para contraseña
  incorrecta y `423` para correcta. La baja, ya autenticada, responde siempre `423` durante
  el bloqueo y no evalúa la contraseña. No se llama a `authenticate` como atajo para la baja.

Login y baja deben serializar las escrituras de estos campos sobre la misma fila, con
lecturas frescas para evitar incrementos perdidos. Login ya toma primero su advisory lock
por identificador y después la fila. La baja toma sólo la fila por UUID y no intenta tomar
después un advisory lock; así no introduce un orden inverso de bloqueos.

Este límite pertenece al primer corte de #20. #31 limita correos y no cubre esta operación.
El costo aceptado es que un poseedor del JWT puede provocar un bloqueo temporal de la cuenta;
el límite reduce intentos de contraseña, no evita por sí solo toda denegación de servicio.

### P2: matriz de estados y respuestas

Todas las respuestas de error usan `application/problem+json` y el `type` existente
`https://udesa-x.dev/problems/<slug>`. La tabla asume un cuerpo válido; un cuerpo inválido
produce `422 validation-error` y no consume intentos. Para solicitudes válidas, las filas
se evalúan en este orden: credencial, estado de cuenta, verificación, bloqueo, contraseña.
Si se combinan estados, gana la primera condición aplicable.

| Condición | ¿Permite la baja? | HTTP / slug | Cambios persistidos |
|---|---|---|---|
| JWT ausente, malformado, firma inválida, vencido o `jti` revocado | No | `401 invalid-access-token` | Ninguno. |
| Cuenta inexistente, ya eliminada o `session_version` obsoleta | No | `401 invalid-access-token` | Ninguno; incluye reintentos tras una baja exitosa. |
| Cuenta suspendida | No | `401 invalid-access-token` | Ninguno; mantiene el contrato actual de introspección. |
| Cuenta no verificada, con JWT por lo demás válido | No | `403 unverified-account` | Ninguno; se cubre defensivamente aunque Login no emita ese JWT hoy. |
| Cuenta verificada y utilizable, bloqueo activo | No, con cualquier contraseña | `423 account-temporarily-locked` | Ninguno; no comprueba contraseña ni prolonga el bloqueo. |
| Cuenta verificada y utilizable, sin bloqueo activo, contraseña incorrecta | No | `401 invalid-credentials` | Sólo contador y eventual bloqueo; el quinto fallo inicia 15 minutos. |
| Cuenta verificada y utilizable, bloqueo ausente o vencido, contraseña correcta | Sí | `204` sin cuerpo | Baja, versión de sesión, invalidación de enlaces y limpieza del contador/bloqueo en una transacción. |

Una suspensión impide esta baja por JWT en el primer corte: **no se crea una excepción al
validador de sesiones**. Permitir baja de suspendidos o no verificados mediante otra prueba
de identidad requeriría un flujo y un diseño separados. Esto limita el autoservicio de este
corte y debe quedar visible al aprobarlo; no se presenta como una vía universal de borrado.

La serialización por cuenta resuelve la carrera con cambio de contraseña: si éste gana,
el token viejo no puede eliminarla; si la baja gana, la recuperación no puede modificarla.
La emisión y el consumo de enlaces deben volver a comprobar `deleted_at` bajo el mismo
bloqueo, incluyendo solicitudes que empezaron antes de la baja. Una verificación vieja
tampoco puede devolver datos del perfil eliminado.

Los reintentos con el JWT anterior a la baja responden `401`; no vuelven a modificar la
fila. No se promete `204` para un token que ya quedó invalidado. Solicitudes de publicación
que comiencen después del commit serán rechazadas por la introspección existente.
Una publicación que ya superó introspección puede terminar concurrentemente: la baja de
Accounts no equivale a una transacción distribuida con Posts. El filtro futuro de AC.4
debe cubrir también esas publicaciones, no sólo las que existían al iniciar la baja.

## Inventario de decisiones aprobado para el primer corte

| Decisión | Propuesta y razón | Registro |
|---|---|---|
| Soft-delete y conservación del UUID | Usar `deleted_at` existente para conservar referencias. | Deriva de AC.1. |
| Identidad de la baja | Sólo la cuenta del JWT; no permitir elegir otra cuenta. | Inventario. |
| Confirmación | Verificar contraseña actual con el helper Argon2 existente. | Servidor de AC.3; hashing ya decidido en ADR-0001/0005. |
| HTTP | POST a `account-deletions` admite un cuerpo de confirmación; DELETE a `accounts/me` es la alternativa, con la dependencia de soporte de cuerpo DELETE en clientes e intermediarios. | Inventario de contrato. |
| Sesiones | Incrementar `session_version` y conservar la comprobación de `deleted_at`; sin lista nueva de sesiones. | Reutiliza ADR-0007/0008. |
| Concurrencia | Bloqueo de fila, hora posterior a la espera y revalidación dentro de la transacción; sin invertir el orden de bloqueo de Login, recuperación o verificación. | Inventario. |
| Credenciales incorrectas | Contador compartido con Login, 5 fallos y 15 minutos; commit del fallo antes del error. Sólo cambian contador/bloqueo. | Merece ADR por compartir el presupuesto entre dos operaciones frente a contadores separados; protección incluida en #20, independiente de #31 y #33. |
| Estados admitidos | Sólo verificada, no suspendida, no eliminada, sesión vigente y sin bloqueo activo. Matriz P2 con precedencia explícita. | Inventario; no cambia el validador compartido ni agrega una vía alternativa de baja. |
| Reintentos | JWT invalidado devuelve 401; el estado de la baja permanece estable. | Inventario de contrato. |
| Datos personales y reutilización | El primer corte conserva email, handle y hash, y los índices únicos siguen reservándolos. No equivale a anonimización ni borrado de toda la información. | Límite propuesto; la política final queda como decisión separada D-RET-01, pendiente. |
| Posts y otras bases | Accounts no escribe en las bases de otros servicios. | Reutiliza separación de servicios y ADR-0009. |
| Visibilidad inmediata futura | Las lecturas deberán comprobar el estado actual del autor, sin una caché que exponga eliminados; una caída del verificador debe impedir esa exposición. | Contrato pendiente para el corte de AC.4/AC.5; merece ADR frente a replicación eventual cuando se diseñe ese corte. |

### P3 / D-RET-01: política final de retención y reutilización, pendiente

La historia dice que el usuario quiere toda su información borrada, mientras AC.1 exige
soft-delete y AC.5 exige conservar hilos. La propuesta no interpreta silenciosamente esa
tensión: este primer corte sólo da de baja el acceso. No certifica borrado integral ni define
todavía la retención final de datos. Antes de cerrar #20 se necesita aprobar esa política y
la forma de conservar hilos sin exponer el perfil eliminado.

D-RET-01 queda registrada aquí como decisión separada del mecanismo de baja. Debe definir
qué datos se anonimizan o conservan y por cuánto tiempo, el destino del hash y de la actividad,
si email y handle vuelven a estar disponibles y cómo se conserva la atribución de hilos sin
reidentificar al usuario. Requiere aprobación humana y un ADR con alternativas y consecuencias;
no se deduce de la aprobación del endpoint. Hasta entonces siguen reservados email y handle.

La entrega será `Part of #20`, nunca `Closes #20`. No se cierra el issue ni se mueve a Done
por este corte. El cierre requiere resolver D-RET-01 y comprobar individualmente los cinco
criterios, incluidas las superficies pendientes. La descripción será «baja de acceso mediante
soft-delete con confirmación de contraseña», sin prometer borrado completo.

## Archivos previstos y división de entrega

Un único corte funcional en Accounts, eventualmente una PR `Part of #20`:

- `services/accounts/src/accounts/api.py`: contrato de solicitud y ruta.
- `services/accounts/src/accounts/service.py`: baja, límite compartido con Login, matriz de estados y rechazo de recuperación/verificación de cuentas eliminadas.
- `services/accounts/src/accounts/repository.py`: transacción de baja y comprobaciones bajo bloqueo en los flujos existentes.
- `services/accounts/tests/unit/`: casos de servicio, API y repositorio; actualizar los fakes que utilicen esos tests.
- `services/accounts/tests/integration/`: persistencia, integridad referencial, contador compartido y carreras con Login, recuperación y verificación.
- `services/posts/tests/integration/test_accounts_client.py`: comprobar rechazo del token eliminado a través del contrato existente, si el fixture permite ejercer Accounts real.
- `README.md`: ejemplo reproducible de baja y respuesta esperada.
- `docs/adr/`: registrar, con la implementación aprobada, el límite compartido de Login y baja, su alternativa de contadores separados y el costo de bloqueo entre operaciones. D-RET-01 tendrá su propio ADR cuando se resuelva esa política.

No se prevé una migración para este alcance: `deleted_at` y `session_version` ya existen.
La implementación deberá confirmar esa premisa con la base migrada. No se modifica la
política de índices ni el formato del hash. Las futuras entregas de relaciones, móvil,
feed/timeline y replies/reposts requieren sus diseños y pruebas cuando esas capacidades
existan; no son PRs artificiales que sólo añaden capas sin comportamiento utilizable.

## Verificación requerida al implementar

1. Formato, lint y suite unitaria de Accounts con cobertura mínima de 85%; regresión de Posts.
2. Integración en PostgreSQL: UUID y referencias conservados, timestamp persistido, versión
   incrementada y todos los enlaces pendientes invalidados. Ante contraseña incorrecta,
   comprobar en una sesión nueva que sólo cambiaron contador/bloqueo; perfil, hash, baja,
   versión y tokens deben permanecer iguales, incluso en el quinto fallo.
3. Límite secuencial: primeros cinco fallos `401`, contador en 5 y bloqueo de 15 minutos;
   sexto intento y contraseña correcta durante bloqueo `423`, sin verificación del hash ni
   extensión. Probar antes del vencimiento y exactamente al vencer; nuevo fallo queda en 1.
   Repetir con varios JWT de la misma cuenta y comprobar que comparten el presupuesto.
4. Límite concurrente: lanzar más de cinco fallos con sesiones de base independientes sobre
   una cuenta en cero; esperar exactamente cinco `401`, restantes `423`, contador 5 y una
   sola ventana de bloqueo. Mezclar cuatro fallos de Login con uno de baja y viceversa;
   comprobar el estado compartido y ausencia de incrementos perdidos. Retener la fila para
   verificar que los 15 minutos se calculan después de adquirirla, no al iniciar la petición.
5. Cubrir cada fila de la matriz y combinaciones de precedencia (suspendida y bloqueada,
   no verificada y bloqueada, JWT obsoleto y contraseña correcta). Tokens inválidos y cuentas
   no elegibles no consumen intentos. Verificar status, `type`, `title`, `detail` y media type
   contra el contrato existente; éxito sin cuerpo.
6. Carreras controladas, forzando ambos órdenes: dos bajas; baja contra cambio de contraseña,
   verificación, recuperación y emisión de enlaces. Después de confirmar la baja ningún JWT
   ni enlace debe dejar la cuenta utilizable. Si la recuperación gana, el JWT anterior no
   puede confirmar la baja. Si la baja gana, recuperación/verificación no alteran ni exponen
   la cuenta. Si la emisión gana, la baja invalida su enlace; si pierde, no emite uno usable.
7. Flujo real con dos servicios y una cuenta local preparada sin envío de correos: emitir
   dos sesiones, publicar, intentar baja con contraseña incorrecta, confirmar la baja,
   consultar la fila y probar ambos JWT, Login, introspección y creación de otro post.
8. Documentar por separado AC.1 y el soporte de servidor de AC.3. AC.2, la pantalla de AC.3,
   AC.4 y AC.5 no pueden verificarse con las superficies actuales y quedan pendientes.

## Verificación de la implementación del primer corte

Verificación local del 2026-09-07, con las dependencias de `uv sync --locked`:

| Servicio | Formato y lint | Unitarios | Cobertura unitaria | Integración con PostgreSQL 17 |
|---|---|---|---|---|
| Accounts | Aprobados | 210 aprobados | 86,05% | 125 aprobados |
| Posts | Aprobados | 37 aprobados | 96,73% | 14 aprobados |

Se comprobó primero que el endpoint ausente producía `404` y que las regresiones de enlaces
de cuentas eliminadas y del contador precargado fallaban; luego pasaron con la implementación.
Los tests de carreras usan sesiones independientes y observan la espera real de PostgreSQL
antes de liberar el bloqueo. Los cinco criterios originales se conservaron literalmente.
Las suites que usan TestClient reportan una advertencia de deprecación de Starlette sobre httpx.

La revisión final con `agy-worker`, en modo de lectura, no encontró hallazgos accionables
en seguridad/concurrencia ni en cumplimiento del diseño. Repitió los gates unitarios,
formato y lint de ambos servicios; la integración y el flujo real se verificaron por separado.

También se ejecutaron ambas APIs con Uvicorn en puertos locales libres y bases desechables
dedicadas, sin enviar correos. Se preparó una cuenta verificada con dos enlaces de cada tipo:

| Paso | Resultado observado |
|---|---|
| Emitir dos sesiones y publicar | `200`, `200`, `201` |
| Confirmar con contraseña incorrecta | `401`; sólo contador incrementado |
| Confirmar con contraseña correcta | `204`, cuerpo vacío |
| Introspección y publicación con cada JWT anterior | `401` en las cuatro solicitudes |
| Login posterior a la baja | `403`, sin sesión nueva |
| Consumir los dos enlaces de verificación y los dos de recuperación | Cuatro respuestas `400` |
| Inspeccionar las bases | UUID, email, handle y hash conservados; `deleted_at` informado, versión 1, cuatro enlaces usados; un único post, el anterior a la baja |

Estos resultados prueban AC.1 y el contrato de servidor que soporta AC.3. No prueban feed,
follows, móvil ni atribución de respuestas: no se implementan en este corte. La publicación
anterior permanece en la base de Posts; su ocultamiento pertenece a AC.4.

Bruno aprobó el diseño y el usuario autorizó implementación, commit y push en un worktree y
rama nuevos. No se abre una PR ni se cierra #20. D-RET-01 y los criterios excluidos siguen
pendientes. La futura PR debe referenciar `Part of #20`.
