# 0001 - argon2id para el hashing de contraseñas

- **Estado:** aceptado
- **Fecha:** 2026-08-21
- **Historia:** [#1 E1S1 User Registration](https://github.com/software-development-workshop/udesa-x/issues/1)

## Contexto

El CA.4 de la E1S1 pide que la contraseña se guarde "encriptada". Encriptar es reversible:
quien tenga la clave recupera todas las contraseñas en texto plano. Lo que corresponde es
hashear con una función lenta y con sal, de modo que ni con la base entera robada se puedan
recuperar. Tomamos el CA.4 como "que no se pueda leer la contraseña desde la base", que es
lo que el criterio quiere decir.

Falta elegir la función y sus parámetros, y la elección es transversal: todo servicio que
verifique credenciales tiene que usar la misma, o el hash de un servicio no valida en otro.

Los requisitos del enunciado nombran los lineamientos de OWASP como referencia de seguridad.

## Decisión

**argon2id**, con `m=19456 KiB`, `t=2`, `p=1`, vía `argon2-cffi`.

Es la primera recomendación de la OWASP Password Storage Cheat Sheet, y esos parámetros son
una de las configuraciones mínimas que esa misma hoja publica. Alinearse con OWASP no es
preferencia nuestra: el enunciado lo cita como referencia, así que es un requisito con
nombre y apellido.

Lo que lo distingue técnicamente de las alternativas es que es *memory-hard*: cada intento
cuesta 19 MiB. Un atacante con GPUs o ASICs puede paralelizar cómputo barato, no memoria
barata, y ahí es donde bcrypt se queda corto.

## Alternativas consideradas

**bcrypt.** Veinticinco años de uso en producción, implementaciones auditadas en todos los
lenguajes y un solo parámetro que entender. OWASP lo sigue aceptando. Lo descartamos porque
no es memory-hard, y porque trunca silenciosamente a 72 bytes: una contraseña de 100
caracteres y sus primeros 72 abren la misma cuenta, y eso hay que taparlo a mano. Es lo que
usaba la implementación anterior de esta historia.

**scrypt.** También memory-hard y disponible en la stdlib, sin dependencia externa. OWASP lo
ubica por debajo de argon2id, y su espacio de parámetros (N, r, p) es más difícil de
justificar.

**PBKDF2.** Solo tiene sentido cuando hace falta cumplir FIPS-140. No es nuestro caso.

## Consecuencias

- Cada registro y cada login cuestan alrededor de 19 MiB de memoria y decenas de
  milisegundos. Es deliberado, pero define el techo de concurrencia del servicio: si el
  login se vuelve un cuello de botella, la causa es esta y está documentada.
- Los parámetros viajan dentro del hash. Subirlos más adelante no invalida ningún hash
  existente; los viejos siguen verificando con los suyos. Rehashear al validar el login es
  trabajo de la E1S2, no de acá.
- Se suma `argon2-cffi` como dependencia, que compila una extensión en C. Hay wheels para
  las plataformas que usamos, así que no agrega toolchain al build.
- Cualquier servicio futuro que verifique credenciales queda atado a esta elección. Si se
  escribe en otro lenguaje, tiene que usar argon2id con estos mismos parámetros.
