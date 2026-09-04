# 0010 - Resend, con su SDK, para todo el mail del servicio

- **Estado:** aceptado
- **Fecha:** 2026-08-31
- **Historia:** [#25 Enviar el mail de verificación con Resend](https://github.com/software-development-workshop/udesa-x/issues/25)

## Contexto

El servicio manda dos mails, el de verificación de cuenta y el de recuperación de contraseña, y
los dos salían por SMTP contra Mailpit: un buzón local que acepta cualquier remitente sin
credenciales y no deja salir nada de la máquina. Los dos flujos andaban de punta a punta en
desarrollo y no entregaban nada a nadie más.

Con `udesax.app` verificado en Resend, por fin hay una dirección desde la cual el servicio tiene
permiso de mandar.

## Decisión

**Todo el mail del servicio sale por Resend, usando su SDK oficial de Python.** Cualquier mail
que se agregue en adelante también.

El motivo es la simplicidad. Mandar es un `POST` con un header de autorización: no hay puertos,
ni negociación de cifrado, ni un servidor de correo que levantar en desarrollo. El mailer entero
son unas pocas líneas y los errores vienen tipados en vez de códigos que haya que interpretar a
mano.

## Alternativas consideradas

**SMTP, contra Resend o contra otro proveedor.** No agrega dependencias y `smtplib` es biblioteca
estándar. Se descarta porque para que desarrollo y producción compartan un solo camino de código
hay que levantar Mailpit con certificado TLS y flags de autenticación, o meter una rama en el
mailer que decida si negociar cifrado. Esa complejidad no desaparece, se muda al `compose.yaml`.

**Un cliente HTTP a mano.** Una dependencia en lugar de tres. Se descarta porque a cambio hay que
escribir y mantener el manejo de códigos de estado que el SDK ya trae resuelto.

## Consecuencias

- Ya no hay buzón local. Para registrar una cuenta en desarrollo hace falta una API key, una por
  persona, y se comparten los 100 envíos diarios del plan gratis. `delivered@resend.dev` está
  para no gastarlos.
- El servicio depende de un proveedor externo dentro del request. La llamada lleva un timeout
  explícito, más bajo que los 30 segundos que el SDK trae por defecto.
- No hay realimentación de entrega: saber si un mail llegó exige mirar el dashboard. El día que
  eso no alcance, la salida son los webhooks de Resend, y ese es el momento de un ADR nuevo.
- CI no manda mails ni guarda la credencial. Los secrets de Actions tampoco llegan a los
  workflows disparados desde un fork, así que guardarla ahí habría roto cualquier PR externo.
