# ADR-0008: Introspección sincrónica como punto único de validación de sesiones

- **Estado:** aceptado
- **Fecha:** 2026-08-30
- **Issue:** [#21 — E2S1 Create a Post](https://github.com/software-development-workshop/udesa-x/issues/21)

## Contexto

Posts es el primer servicio distinto de Accounts que necesita asociar una acción a la
identidad contenida en un access token. Accounts firma los JWT con HS256, registra las
revocaciones individuales por `jti` y mantiene una `session_version` por cuenta para invalidar
todas las sesiones anteriores a un cambio de contraseña.

Validar sólo la firma y el vencimiento dentro de Posts no alcanza: una copia local del secreto
no puede observar un Logout, una versión de sesión obsoleta, una suspensión ni una eliminación
de cuenta. Además, compartir `JWT_SECRET` permitiría que Posts emitiera tokens indistinguibles
de los de Accounts, riesgo que ADR-0004 prohíbe aceptar por inercia.

## Decisión

Accounts es el único punto que valida access tokens. Expone
`POST /api/v1/sessions/introspect`, recibe el token mediante `Authorization: Bearer`, y aplica
en conjunto:

- firma, issuer, audience y vencimiento;
- revocación individual por `jti`;
- igualdad con la `session_version` actual;
- existencia de la cuenta y ausencia de suspensión o eliminación.

Una sesión válida responde solamente el `account_id`. Cualquier credencial ausente, malformada,
vencida, revocada, obsoleta o perteneciente a una cuenta inutilizable produce el mismo Problem
Details `401 invalid-access-token`.

Posts consulta la introspección antes de persistir. Usa un timeout corto y falla cerrado: una
caída, timeout, status inesperado o cuerpo inválido de Accounts se convierte en `503` y no crea
la publicación.

## Alternativas consideradas

### Compartir HS256 con Posts

Evitaría un salto de red para firma y vencimiento, pero repartiría una credencial capaz de
firmar JWT y todavía necesitaría consultar Accounts para `jti`, `session_version` y estado de
cuenta. Aumenta el riesgo sin eliminar la dependencia sincrónica.

### Migrar inmediatamente a firma asimétrica

Una clave pública permitiría validar firma y vencimiento sin entregar capacidad de emisión a
Posts. Sigue sin resolver por sí sola las revocaciones y el estado actual, y obligaría a sumar
ahora generación, distribución y rotación de claves a E2S1. Puede revisarse cuando el sistema
tenga requisitos de disponibilidad o volumen que justifiquen validación distribuida.

### Copiar el estado de sesión a Posts

Replicar revocaciones y cuentas mediante eventos quitaría el salto sincrónico, pero introduce
consistencia eventual, una cola y reglas de reconciliación antes de que exista otra necesidad
de ese mecanismo. Una ventana de propagación permitiría publicar con una sesión ya revocada.

## Consecuencias

- Accounts conserva el secreto y toda la autoridad de sesión.
- Logout, cambios de contraseña, suspensiones y eliminaciones se reflejan en Posts en la
  siguiente solicitud, sin demora de propagación.
- Crear un post agrega una llamada de red y deja de estar disponible mientras Accounts no
  pueda validar la sesión.
- Posts debe distinguir credencial inválida (`401`) de indisponibilidad del validador (`503`)
  y nunca persistir antes de conocer la identidad.
- Otros servicios pueden reutilizar el contrato HTTP, pero no código ni secretos de Accounts.
- Si latencia o disponibilidad vuelven inaceptable este acoplamiento, una decisión posterior
  deberá reemplazar este ADR y resolver conjuntamente firma asimétrica y revocación distribuida.
