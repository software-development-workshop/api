# 0002 - problem+json como contrato de errores

- **Estado:** aceptado
- **Fecha:** 2026-08-21
- **Historia:** [#1 E1S1 User Registration](https://github.com/software-development-workshop/udesa-x/issues/1)

## Contexto

El sistema va a tener varios microservicios, y el enunciado exige que el backend no sea una
sola tecnología. La app mobile y el backoffice consumen a todos. Si cada servicio inventa su
forma de reportar un error, el cliente termina con un parser por servicio, y el que se
escriba en otro lenguaje va a devolver una tercera forma sin que nadie lo note.

Un contrato de error es de las pocas cosas que tienen que coincidir entre servicios que no
comparten código. Cuando divergen, el bug aparece en un servicio que nadie tocó: el cliente
deja de reconocer un error que el backend viene devolviendo igual desde siempre.

Decidirlo con un servicio existiendo cuesta una tarde. Unificar cinco formatos en la semana
diez cuesta tocar cinco repos y el cliente.

## Decisión

**RFC 7807 `application/problem+json`** para toda respuesta de error.

```json
{
  "type": "https://udesa-x.dev/problems/email-already-registered",
  "title": "Email already registered",
  "status": 409,
  "detail": "That email is already registered.",
  "errors": [{ "field": "handle", "message": "..." }]
}
```

`type`, `title`, `status` y `detail` son del estándar. `errors` es una extensión, que el RFC
habilita explícitamente, y existe porque un formulario que rechaza de a un campo por vez son
seis viajes: los errores de validación se devuelven todos juntos.

`type` es un identificador, no una URL que alguien vaya a resolver. Que se vea como una URI
es lo que el estándar pide para que dos servicios no colisionen al elegir el mismo nombre.

## Alternativas consideradas

**Un formato propio mínimo**, del tipo `{error, message, fields}`. Menos ceremonia y más
fácil de leer. Lo descartamos porque es un contrato inventado: hay que documentarlo y
replicarlo a mano en cada servicio, y cada uno lo va a escribir un poco distinto. El
estándar ya viene documentado y tiene implementación en los frameworks de todos los
lenguajes que podríamos elegir.

**El default de FastAPI.** Cero trabajo hoy. Lo descartamos porque cambia de forma según el
tipo de error —un fallo de validación de Pydantic y un `HTTPException` no se parecen— así
que el cliente ya tendría que manejar dos formas antes de que exista el segundo servicio.

## Consecuencias

- Todo servicio nuevo arranca implementando esto, en el lenguaje que sea. Es la primera cosa
  que hay que portar y no es negociable, porque el valor del contrato es que sea uno solo.
- Los handlers de error viven en un módulo aparte (`errors.py`) y las excepciones de dominio
  cargan su status. El servicio las lanza sin saber que existe HTTP, que es lo que pide la
  separación de capas.
- Agregar un error nuevo es agregar una subclase y su slug. Los slugs son parte del contrato
  público: renombrarlos rompe clientes.
