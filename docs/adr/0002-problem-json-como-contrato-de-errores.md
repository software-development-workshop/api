# 0002 - problem+json como contrato de errores

- **Estado:** aceptado
- **Fecha:** 2026-08-21
- **Historia:** [#1 E1S1 User Registration](https://github.com/software-development-workshop/udesa-x/issues/1)

## Contexto

El sistema va a tener varios microservicios, y el enunciado exige que el backend no sea una
sola tecnología. La app mobile y el backoffice pueden consumir más de uno. Si cada servicio
inventa su forma de reportar un error, el cliente termina con un parser por servicio y las
diferencias entre implementaciones se vuelven errores de integración.

Un contrato de error es una de las interfaces que tienen que coincidir entre servicios que
no comparten código. Decidirlo con un servicio existente es más barato que reconciliar varios
formatos cuando ya hay más clientes e implementaciones.

## Decisión

Usar **Problem Details** con el media type `application/problem+json` para los errores de
dominio y de validación de requests.

Este incremento aplica el contrato a esos errores. Las respuestas generadas directamente
por el framework para rutas o métodos inexistentes, como `404` y `405`, quedan fuera de este
alcance.

```json
{
  "type": "https://udesa-x.dev/problems/email-already-registered",
  "title": "Email already registered",
  "status": 409,
  "detail": "That email is already registered."
}
```

`type`, `title`, `status` y `detail` pertenecen al formato estándar. `errors` es una
extensión que aparece únicamente en las respuestas de validación `422` para devolver juntos
los errores de campos. `type` es un identificador estable; los clientes no deben depender de
que resuelva a una página web.

## Alternativas consideradas

**Un formato propio mínimo**, del tipo `{error, message, fields}`. Es menos ceremonioso y
más fácil de leer, pero obliga a documentarlo y reproducirlo en cada lenguaje y framework,
lo que aumenta la posibilidad de divergencias.

**El default de FastAPI.** No requiere trabajo inicial, pero cambia de forma según el tipo
de error: una validación de Pydantic y un `HTTPException` no tienen el mismo contrato. El
cliente tendría que manejar más de una forma antes de que exista el segundo servicio.

## Consecuencias

- Cada nuevo servicio HTTP debe implementar el mismo contrato para sus errores de dominio y
  validación, en el lenguaje y framework que use.
- La traducción HTTP vive en un módulo separado. Las excepciones de dominio actuales cargan
  el status, el slug, el título y el detalle público; el handler serializa esos metadatos sin
  transformarlos y sin que la capa de servicio importe FastAPI.
- Agregar un error público implica agregar un identificador estable. Renombrarlo puede
  romper clientes y requiere revisar el contrato.
- Los errores de validación incluyen `errors` con nombres de campos y mensajes generados por
  Pydantic. La respuesta omite los valores enviados.
