# ADR-0005: Perfil Argon2 canónico para login

- **Estado:** aceptado
- **Fecha:** 2026-08-24
- **Issue:** [#8 — E1S2 Login](https://github.com/software-development-workshop/udesa-x/issues/8)

## Contexto

ADR-0001 eligió Argon2id con `m=19456`, `t=2`, `p=1` y estableció que una suba futura de
parámetros no debe invalidar hashes existentes. E1S2 agrega la verificación de esos hashes y
trabajo Argon2 ficticio para que un identificador inexistente no tenga un camino barato.

Aceptar hoy cualquier perfil Argon2id dentro de un rango permitiría que una cuenta existente
consuma un costo distinto del hash ficticio. Esa diferencia se puede medir promediando
intentos y vuelve a revelar qué identificadores existen. Aceptar costos sin límites también
permitiría que un valor manipulado en la base imponga trabajo arbitrario al login.

## Decisión

Mientras Registration genere un único perfil, Login acepta un PHC completo Argon2id v19 con
exactamente `m=19456`, `t=2`, `p=1`, sal de 16 bytes y salida de 32 bytes. PostgreSQL y el
runtime aplican la misma regla. El hash ficticio usa ese mismo perfil, por lo que cuentas
existentes e identificadores desconocidos realizan una verificación con el mismo costo
Argon2.

Una suba futura de parámetros tiene que desplegar primero una estrategia que conserve la
verificación de hashes anteriores sin reintroducir el canal temporal. Recién después puede
Registration empezar a escribir el perfil nuevo. Ese cambio requiere su propia migración y
decisión; no se amplía preventivamente la lista de perfiles aceptados.

Este ADR no reemplaza la elección de Argon2id de ADR-0001: define la política operativa de
perfiles para el login incorporado por E1S2.

## Alternativas consideradas

### Aceptar una ventana de parámetros

Preservaría por adelantado varios perfiles válidos, pero cada uno tiene un costo observable
distinto. Un único hash ficticio no puede ocultar todas esas diferencias.

### Completar hasta un tiempo fijo con una espera

Una pausa de reloj depende del hardware, la carga y el scheduler. No garantiza igualdad,
bloquea el worker y convierte una propiedad de seguridad en un umbral difícil de probar.

### Ejecutar siempre un hash ficticio de costo máximo

Sumarlo a la verificación real duplica trabajo y todavía deja visible el costo variable de la
verificación real. No resuelve el canal temporal.

## Consecuencias

- Los hashes que Registration produce hoy siguen siendo los únicos aceptados y tienen el
  mismo perfil que el hash ficticio.
- La migración falla cerrada si encuentra un PHC malformado o un perfil que el login actual
  no sabe verificar sin filtrar información.
- Cambiar parámetros deja de ser sólo modificar `PasswordHasher`: exige preservar los hashes
  anteriores, la indistinguibilidad temporal y la restricción de base en un despliegue
  coordinado.
