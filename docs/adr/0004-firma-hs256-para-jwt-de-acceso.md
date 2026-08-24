# ADR-0004: HS256 para firmar los JWT de acceso

- **Estado:** aceptado
- **Fecha:** 2026-08-23
- **Issue:** [#8 — E1S2 Login](https://github.com/software-development-workshop/udesa-x/issues/8)

## Contexto

El servicio de Accounts tiene que emitir un JWT cuando una cuenta verificada y habilitada
presenta credenciales válidas. El token lo consumirá primero el cliente móvil y, más adelante,
podría ser validado por otros servicios del sistema.

La historia exige un vencimiento definido, pero todavía no existen refresh tokens, sesiones
persistidas ni revocación del lado servidor. Esas capacidades pertenecen a E1S3 y a las
historias de cambio o recuperación de contraseña. Incorporarlas acá agrandaría el límite de
E1S2 sin entregar un comportamiento que esta historia pida.

La elección del algoritmo sí tiene consecuencias más allá de este sprint: con una firma
simétrica, cualquier componente que reciba la clave también puede emitir tokens válidos; con
una firma asimétrica, Accounts conserva la clave privada y distribuye solamente la pública.

## Decisión

Accounts firma los access tokens con HS256 y una clave obligatoria de al menos 32 bytes
provista por `JWT_SECRET`. La clave no tiene valor por defecto y nunca se versiona. Docker
Compose y CI usan únicamente valores explícitos para desarrollo y pruebas.

Cada token vence una hora después de su emisión e incluye:

- `sub`, con el UUID de la cuenta;
- `iat` y `exp`, con la emisión y el vencimiento;
- `jti`, único por token, para que una historia posterior pueda revocarlo sin cambiar el
  contrato emitido;
- `iss`, con `udesa-x-accounts`;
- `aud`, con `udesa-x`.

Antes de que un segundo servicio valide estos JWT de manera independiente, el equipo tiene que
revisar esta decisión y elegir explícitamente entre una firma asimétrica o un único punto de
validación. Compartir `JWT_SECRET` entre servicios por inercia no es una decisión aceptada por
este ADR.

## Alternativas consideradas

### RS256 desde esta historia

Mantiene la autoridad de firma dentro de Accounts y permite distribuir una clave pública. Es
la separación más segura para varios microservicios, pero requiere resolver ahora generación,
distribución, rotación y configuración local de pares de claves cuando todavía no existe otro
consumidor. Se difiere hasta que aparezca ese límite real.

### Sesiones opacas persistidas

Harían directa la revocación, pero no cumplen el requisito explícito de emitir un JWT. Una
tabla de sesiones acompañando al JWT también sería posible, aunque adelantaría el alcance de
E1S3 sin que E1S2 la necesite.

### JWT sin vencimiento

Reduciría el trabajo del cliente, pero contradice AC.1 y deja una credencial robada válida de
forma indefinida.

## Consecuencias

- El flujo actual necesita una sola variable secreta y sigue levantando con el Compose del
  repositorio.
- El token es autocontenido y no requiere una consulta de base para emitirse.
- La expiración limita a una hora la vida máxima de un token que todavía no puede revocarse.
- `jti` deja estable el contrato que E1S3 usará para revocación.
- HS256 no autoriza a copiar la clave a futuros servicios. Ese escenario obliga a revisar o
  reemplazar esta decisión antes de integrar el segundo validador.
