# ADR-0013: App mobile con Expo dentro del repositorio

- **Estado:** aceptado
- **Fecha:** 2026-09-13
- **Issue:** [#48 — Mobile foundation and authentication](https://github.com/software-development-workshop/udesa-x/issues/48)
- **Diseño aprobado:** [base compartida y entregas secuenciales](https://github.com/software-development-workshop/udesa-x/issues/48#issuecomment-5656189252)

## Contexto

La primera entrega mobile debe permitir iniciar y cerrar sesión con Accounts desde un
teléfono. La siguiente entrega reutiliza esa base para publicar. Necesitamos navegación,
controles nativos y una forma repetible de ejecutar la app, manteniendo el alcance acotado
para Iteration 5. El requisito de repositorio separado para backoffice no se extiende a
mobile, según la aclaración del equipo.

## Decisión

Usamos React Native, TypeScript y Expo SDK 57, con Expo Router. La app vive en `apps/mobile/`
y tiene su propio `package.json`, lockfile, pruebas y workflow. No se agrega un gestor de
monorepo ni código compartido entre el runtime Python y el cliente. Las integraciones
siguen siendo HTTP contra Accounts y Posts.

El SDK corresponde a la versión estable disponible para Expo Go al implementar esta
entrega. Las dependencias nativas se alinean con Expo y quedan fijadas por el lockfile.
La app utiliza componentes nativos y fuentes del sistema, sin un segundo framework visual.

Expo Router protege el grupo autenticado y retira su historial cuando deja de haber
sesión. El token vive en memoria; el contrato detallado, los estados de error y los
recortes de este incremento están en el comentario de diseño.

## Alternativas consideradas

- **React Native sin Expo:** permite controlar directamente los proyectos nativos, pero
  exige configurar y mantener Android e iOS antes de demostrar el primer flujo. No hay
  una dependencia nativa propia que justifique ese trabajo en este incremento.
- **Flutter o aplicaciones nativas separadas:** son opciones válidas para el producto,
  pero incorporan otro lenguaje o dos implementaciones de interfaz. TypeScript permite
  reutilizar conocimientos del equipo y mantener una implementación mobile.
- **Repositorio mobile separado:** ofrece permisos y ciclos de cambios independientes,
  a cambio de coordinar el contrato y las entregas entre más repositorios. El mismo equipo
  realiza estas dos entregas y no necesita un límite adicional de acceso al código.
- **Tooling de monorepo y paquetes compartidos:** facilita orquestar muchos paquetes,
  pero aquí cada servicio y la app ya se ejecutan por separado. No hay un paquete de
  código común que necesite esa infraestructura.

## Consecuencias

- La app puede probarse y empaquetarse con su toolchain sin instalar los servicios Python.
  El backend conserva sus contenedores y bases de datos independientes.
- Los cambios al contrato cliente/API pueden revisarse en la misma rama. Compartir Git
  no obliga a desplegar todos los componentes juntos.
- Hay que mantener la compatibilidad del SDK con el cliente nativo instalado. Expo Go
  sirve para esta demostración; distribución en tiendas y builds propios quedan fuera
  del #48.
- Reiniciar el proceso requiere iniciar sesión otra vez. No se implementan restauración
  de credenciales ni refresh sin un contrato de backend que lo soporte.
- #48 entrega login, inicio mínimo y logout. #49 se construye después sobre `develop`,
  reutilizando autenticación, HTTP y componentes visuales.

Referencias técnicas: [Expo Go](https://expo.dev/go) y
[rutas protegidas de Expo Router](https://docs.expo.dev/router/advanced/protected/).
