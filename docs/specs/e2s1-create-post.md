# E2S1 Create a Post — diseño aprobado

Fecha de aprobación: 2026-08-30  
Issue: [#21](https://github.com/software-development-workshop/udesa-x/issues/21)

## Objetivo

Permitir que una persona autenticada publique un mensaje de hasta 280 caracteres, seguro
frente a contenido HTML/script, persistido con su autor, fecha y contadores iniciales, con un
límite de 30 publicaciones por hora.

## Arquitectura

Se crea `services/posts` como microservicio independiente con Python 3.13, FastAPI,
SQLAlchemy, Alembic y PostgreSQL. Posts posee su contenedor, configuración, migraciones, CI y
base `posts-db`; no comparte tablas, credenciales, foreign keys ni imports de runtime con
Accounts.

Accounts sigue siendo la única autoridad de sesiones. Expone
`POST /api/v1/sessions/introspect`, que recibe el Bearer token, valida firma, expiración,
`jti`, `session_version` y que la cuenta continúe activa, y devuelve `account_id`. Posts llama
sincrónicamente a ese endpoint con un timeout corto antes de persistir. Un token inválido
produce `401`; una caída, timeout o respuesta inválida de Accounts produce `503`; ninguna de
esas respuestas crea una publicación.

La introspección se apoya sobre E1S5 y su `session_version`, actualmente entregada por el PR
#22. El trabajo de Accounts se prepara como una rama apilada sobre ese PR.

## Contrato HTTP

`POST /api/v1/posts` recibe:

```json
{
  "content": "Mi primera publicación"
}
```

Requiere `Authorization: Bearer <token>` y responde `201`:

```json
{
  "id": "c6438fd1-432f-4f65-9d46-700b33da2086",
  "author_id": "c6a8f8cf-9f92-48e9-a391-2c2deff8e32f",
  "content": "Mi primera publicación",
  "created_at": "2026-08-30T21:00:00Z",
  "like_count": 0,
  "repost_count": 0,
  "reply_count": 0
}
```

Todos los errores usan `application/problem+json`:

- `401` para un Bearer token ausente o inválido.
- `422` para contenido inválido.
- `429` cuando el autor ya publicó 30 veces durante los últimos 60 minutos.
- `503` cuando Accounts no puede confirmar la identidad.

## Persistencia

La tabla `posts` contiene:

- `id`: UUID, clave primaria.
- `author_id`: UUID indexado, sin foreign key entre servicios.
- `content`: texto de 1 a 280 caracteres.
- `created_at`: timestamp con zona horaria generado por PostgreSQL.
- `like_count`, `repost_count`, `reply_count`: enteros no negativos con default `0`.

Un índice compuesto por `author_id, created_at` sostiene el conteo de la ventana anti-spam.

## Contenido

El backend normaliza CRLF a LF, quita whitespace exterior, rechaza un valor vacío, comprueba
el máximo de 280 caracteres, elimina etiquetas HTML/script mediante `nh3`, vuelve a quitar
whitespace y repite las comprobaciones de vacío y longitud antes de persistir. La base agrega
restricciones defensivas de longitud, contenido no vacío y contadores no negativos.

## Límite anti-spam

El repositorio toma un advisory lock transaccional derivado de `author_id`, cuenta las
publicaciones confirmadas de ese autor durante los últimos 60 minutos y realiza la inserción
en la misma transacción. Las primeras 30 se aceptan y la número 31 se rechaza. Sólo las
publicaciones persistidas consumen cupo, y dos solicitudes concurrentes no pueden superar el
límite.

## Entrega

1. `feat/access-token-introspection`: endpoint ejercitable de Accounts, con pruebas de
   sesión válida, vencida, revocada, obsoleta, suspendida y eliminada. Referencia `Part of
   #21`.
2. `feat/create-post`: Posts completo, PostgreSQL, Docker/Compose, CI, documentación y pruebas
   unitarias, de integración y end-to-end. Usa `Closes #21` sólo cuando se hayan verificado
   los cinco criterios.

Se registra un ADR para la validación centralizada de sesiones y otro para la propiedad y
tecnología de Posts. Quedan fuera la aplicación móvil, feed/listado, edición, borrado,
respuestas, likes, reposts, multimedia, notificaciones y la segunda tecnología de backend y
segundo tipo de base requeridos a nivel sistema.
