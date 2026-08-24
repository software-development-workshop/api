# ADR-0006: Revocación de JWT de acceso mediante `jti`

- **Estado:** aceptado
- **Fecha:** 2026-08-24
- **Issue:** [#9 — E1S3 Logout](https://github.com/software-development-workshop/udesa-x/issues/9)

## Contexto

El logout debe invalidar el access token en el backend, aunque todavía no existen sesiones
persistidas ni endpoints protegidos en el repositorio. El contrato actual emite JWT con un
`jti` único por token y un vencimiento de una hora.

La revocación debe afectar al token que se cerró, conservar el contrato JWT del login y no
guardar credenciales reutilizables en la base de datos.

## Decisión

Accounts persiste los `jti` revocados en `revoked_access_tokens`, junto con `expires_at` y
`revoked_at`. El endpoint `POST /api/v1/sessions/logout` exige un Bearer token válido,
verifica firma, emisor, audiencia, claims requeridos y vencimiento, y registra su `jti`.

La operación es idempotente: cerrar sesión dos veces con el mismo token devuelve `204` y no
duplica la fila. Los futuros endpoints protegidos deben usar el validador compartido, que
rechaza un token cuyo `jti` figure en la tabla además de aplicar las validaciones normales del
JWT.

La tabla conserva la fila hasta el vencimiento del token. Una tarea posterior podrá eliminar
filas expiradas sin cambiar el contrato del endpoint.

## Alternativas consideradas

### Sesiones opacas persistidas

Simplificarían la revocación, pero cambiarían el contrato actual basado en JWT y agregarían una
decisión de gestión de sesiones fuera del alcance de esta issue.

### Marca de logout por cuenta

Sería más simple, pero invalidaría todas las sesiones de la cuenta y no permitiría revocar un
token individual.

### No persistir revocaciones

Mantendría los JWT completamente autocontenidos, pero no cumpliría AC.1: un token seguiría
siendo válido en el backend después del logout.

## Consecuencias

- Logout invalida el token en el backend sin almacenar su valor ni su firma completa.
- Cada endpoint protegido deberá consultar la tabla de revocaciones, además de validar el JWT.
- La retención queda acotada por `exp`; la limpieza automática se puede agregar después.
- El borrado seguro del token y de la sesión local en el cliente móvil queda pendiente del
  cliente, que no está incluido en este repositorio.
