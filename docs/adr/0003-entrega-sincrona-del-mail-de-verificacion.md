# 0003 - Entrega síncrona del mail de verificación

- **Estado:** aceptado
- **Fecha:** 2026-08-21
- **Historia:** [#1 E1S1 User Registration](https://github.com/software-development-workshop/udesa-x/issues/1)

## Contexto

El CA.1 de la E1S1 exige que una cuenta no se pueda usar hasta validarse con un token
enviado por mail, y el CA.6 que ese token venza y se pueda pedir de nuevo desde la pantalla
de login.

Mandar un mail es una llamada a un sistema externo dentro del request que crea la cuenta. Si
el servidor SMTP está caído o lento, o el request se corta después de escribir en la base
pero antes de enviar, queda una cuenta sin su link. La pregunta es cuánta maquinaria poner
para que eso no pase.

Los requisitos del enunciado piden además al menos una cola que comunique dos microservicios
de forma asincrónica.

## Decisión

**Se manda por SMTP dentro del request**, sin cola ni outbox.

El argumento que decide no es que sea más simple, sino que **la recuperación ya está en los
requisitos**: el CA.6 obliga a un botón de reenvío en el login. Si un envío falla, el camino
de salida ya existe y hay que construirlo igual. Un outbox construiría una segunda
recuperación para el mismo problema, y la primera seguiría siendo obligatoria.

La cola que pide el enunciado va a vivir en notificaciones (E.4), donde hay dos servicios que
realmente necesitan hablarse de forma asincrónica. Acá habría un solo servicio publicando y
consumiendo su propio mensaje, que es una cola de adorno.

## Alternativas consideradas

**Outbox transaccional con un worker.** El envío se persiste en la misma transacción que el
alta y un proceso aparte lo despacha con reintentos. Garantiza que ningún mail se pierda.
Cuesta una tabla, un worker, su ciclo de vida, y tests de integración para el despacho.
Vale la pena cuando perder el mensaje es caro y no hay otra forma de recuperarlo; acá el
usuario aprieta "reenviar" y sigue.

Si aparece evidencia de que los envíos fallan seguido, la respuesta es un ADR nuevo que
supersede a este, no volver a discutir la misma decisión en cada review.

**Cola desde el día uno.** accounts publica un evento y un consumidor manda el mail. Cubriría
el requisito de cola ya mismo y desacoplaría a accounts del proveedor de correo. Se descarta
por lo mismo: un broker, un consumidor y sus tests en la primera historia de un servicio que
todavía no tiene con quién comunicarse.

## Consecuencias

- El request de registro tarda lo que tarde el SMTP. Es el techo de latencia del endpoint y
  está a la vista.
- Si el envío falla, el usuario queda registrado sin poder entrar hasta que pida el reenvío.
  El mensaje de error tiene que decirle eso; no alcanza con fallar.
- No hay reintento automático. Es deliberado: el reintento lo pide la persona.
- Rate limiting del reenvío queda pendiente. El CA.8 de la E1S5 lo pide para el reset de
  contraseña, y cuando se implemente ahí conviene aplicar lo mismo acá.
- El requisito de cola del enunciado sigue sin cumplirse después de esta historia. Es
  intencional y su lugar es E.4.
