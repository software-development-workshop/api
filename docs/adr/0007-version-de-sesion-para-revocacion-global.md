# ADR-0007: Versión de sesión para revocar todos los JWT de una cuenta

- **Estado:** aceptado
- **Fecha:** 2026-08-30
- **Issue:** [#19 — E1S5 Forgot My Password](https://github.com/software-development-workshop/udesa-x/issues/19)

## Contexto

El cambio exitoso de contraseña debe invalidar todos los JWT activos de la cuenta. El
mecanismo existente de Logout guarda el `jti` de un token y resuelve otro caso: cerrar una
sola sesión sin afectar las demás.

Los JWT ya emitidos no se pueden modificar. Por eso, Accounts necesita un dato actual de la
cuenta que permita distinguir los tokens anteriores al cambio de contraseña de los emitidos
después.

## Decisión

Cada cuenta tiene un entero `session_version`, inicialmente `0`. Accounts incluye ese valor
en cada nuevo JWT como el claim `session_version`.

El validador compara el valor del token con el valor actual de la cuenta. Si no coinciden, el
token se rechaza. Un cambio exitoso de contraseña incrementa `session_version` dentro de la
misma transacción que actualiza el hash; todos los JWT anteriores quedan inválidos a partir
de ese commit.

Los JWT emitidos antes de este cambio no contienen el claim. Para desplegar la migración sin
cerrar todas las sesiones existentes, el decodificador los interpreta como versión `0`. Una
vez que una cuenta cambia su contraseña y pasa a versión `1`, también quedan invalidados.

La revocación mediante `jti` se conserva para Logout. La versión de sesión no la reemplaza:
`jti` revoca un token concreto y `session_version` revoca todos los tokens anteriores de una
cuenta.

## Alternativas consideradas

### Persistir cada sesión emitida

Permitía marcar todas las sesiones de una cuenta como revocadas, pero requería registrar y
mantener una fila por cada Login. El requisito se resuelve con un solo número por cuenta y
sin cambiar el contrato actual de Logout.

### Comparar `iat` con la fecha del último cambio de contraseña

También separaba tokens viejos y nuevos, pero hacía depender la decisión de la precisión de
dos timestamps y de qué lado de un mismo segundo quedaba cada operación. El contador expresa
la regla de forma directa: igualdad significa sesión vigente.

## Consecuencias

- Un cambio exitoso de contraseña invalida todos los JWT emitidos con una versión anterior.
- Login debe copiar la versión actual de la cuenta al JWT.
- Cada validación consulta la versión actual y también conserva la comprobación individual de
  `jti`.
- Un token cuyo `sub` ya no corresponde a una cuenta se rechaza porque no existe una versión
  actual con la cual compararlo.
- Cualquier futuro componente que valide estos JWT deberá aplicar ambas comprobaciones.
