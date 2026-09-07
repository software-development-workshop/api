# ADR-0011: Límite compartido de intentos de contraseña para Login y baja

- **Estado:** aceptado
- **Fecha:** 2026-09-07
- **Issue:** [#20 — E1S4 Account Deletion](https://github.com/software-development-workshop/udesa-x/issues/20)
- **Aprobación del diseño:** [review de Bruno de la versión 2](https://github.com/software-development-workshop/udesa-x/issues/20#issuecomment-5573549307)

## Contexto

La baja requiere un JWT vigente y confirmar la contraseña actual. Un atacante que obtenga
el JWT debe tener un límite de intentos; el límite de correos de #31 no protege esta ruta.
Login ya usa `failed_login_attempts` y `locked_until` en la fila de Accounts, con cinco
fallos consecutivos y un bloqueo de quince minutos.

## Decisión

Login y baja comparten ese contador y ese bloqueo por cuenta. Todos los JWT e identificadores
de la misma cuenta usan el mismo presupuesto. Las operaciones toman el bloqueo de fila y
leen el estado actualizado; la hora para el bloqueo se toma después de adquirirlo.

En la baja, el quinto fallo persiste el bloqueo y responde `401 invalid-credentials`.
Mientras el bloqueo esté activo, responde `423 account-temporarily-locked` sin verificar
contraseñas ni extender la ventana. El siguiente intento al vencer el bloqueo empieza
un presupuesto nuevo. El fallo se confirma en la base antes de devolver el error;
datos de perfil, hash, versión de sesión y tokens permanecen intactos.

Login conserva su contrato actual durante el bloqueo: `401` para contraseña incorrecta y
`423` para correcta. Un Login exitoso o una recuperación exitosa limpia el contador según
sus reglas existentes. La baja exitosa lo limpia junto con `deleted_at`, el incremento de
`session_version` y la invalidación de enlaces dentro de una sola transacción.

La baja identifica la fila por el UUID del JWT y no adquiere advisory locks después de
tomarla. Login mantiene su orden de advisory lock por identificador seguido del bloqueo
de fila. Las lecturas refrescan objetos previamente cargados en la sesión de SQLAlchemy.

## Alternativas

- **Contador exclusivo de baja:** evita que un fallo de una operación bloquee la otra,
  pero necesita nuevos campos y una migración, y ofrece dos presupuestos para adivinar
  la misma contraseña. El beneficio no compensa ese estado adicional en este alcance.
- **Límite por IP o JWT:** no requiere acoplar las operaciones, pero cambiar de IP o usar
  distintas sesiones permite acumular intentos sobre la misma cuenta. No reemplaza el
  límite por cuenta; podría complementarlo ante otros requisitos de disponibilidad.

## Consecuencias

- Fallar confirmaciones de baja puede bloquear Login, y fallar Login puede bloquear la baja.
  Un poseedor del JWT puede provocar ese bloqueo temporal; es un costo aceptado del diseño.
- No se agregan tablas, columnas, infraestructura, variables de entorno ni dependencias.
- Una cuenta suspendida, eliminada o con JWT obsoleto se rechaza como token inválido;
  una no verificada se rechaza con `403`, sin consumir intentos. No hay vía alternativa
  de baja para esos estados en este corte.
- El alcance sigue siendo `Part of #20`: conserva email, handle y hash. La política final
  de retención, anonimización y reutilización D-RET-01 requiere otra decisión y otro ADR.
