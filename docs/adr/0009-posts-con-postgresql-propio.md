# ADR-0009: PostgreSQL propio para el servicio de Posts

- **Estado:** aceptado
- **Fecha:** 2026-08-30
- **Issue:** [#21 — E2S1 Create a Post](https://github.com/software-development-workshop/udesa-x/issues/21)

## Contexto

E2S1 incorpora el primer dominio fuera de Accounts. La asignación exige microservicios
independientemente desplegables, al menos dos tecnologías de backend y al menos dos tipos de
base de datos a nivel sistema. Esos requisitos no obligan a que Posts introduzca ambas
variantes, pero sí a que el equipo decida quién posee los datos de publicaciones y evite que
la comodidad inicial convierta Accounts en una base compartida.

Posts necesita persistencia transaccional para crear una publicación y hacer atómico el límite
de 30 por hora frente a solicitudes concurrentes. El equipo ya puede operar PostgreSQL,
SQLAlchemy, Alembic y sus pruebas de integración durante esta iteración.

## Decisión

Posts usa Python 3.13, FastAPI y una instancia PostgreSQL 17 propia llamada `posts-db`. El
servicio posee esquema, migraciones, credenciales, contenedor y workflow. Guarda `author_id`
como UUID sin foreign key hacia Accounts; la existencia y vigencia del autor se confirma por
el contrato HTTP de introspección definido en ADR-0008.

El límite horario se resuelve dentro de `posts-db`: un advisory lock transaccional por UUID de
autor serializa el conteo de la ventana móvil y la inserción. No se agrega Redis ni un contador
en memoria para esta historia.

La segunda tecnología de backend y el segundo tipo de base exigidos para el sistema se
asignarán a otro servicio mediante una decisión separada. E2S1 no afirma que esos requisitos
globales estén cumplidos.

## Alternativas consideradas

### Guardar publicaciones en la base de Accounts

Reutilizaba infraestructura sin otro contenedor, pero compartía propiedad de tablas y ciclo de
migraciones. Accounts y Posts dejarían de poder evolucionar o desplegarse de forma
independiente, contradiciendo el límite de microservicio del repositorio.

### Introducir ahora un segundo tipo de base

MongoDB u otra base documental podían cumplir anticipadamente el requisito global. La forma
actual de una publicación y el rate limit concurrente encajan de manera directa en PostgreSQL;
cambiar tecnología en E2S1 agregaría aprendizaje, operación y otro patrón de pruebas sin una
ventaja específica para sus cinco criterios.

### Compartir una instancia PostgreSQL con esquemas separados

Separaba nombres de tabla, pero conservaba credenciales, disponibilidad y operación comunes.
Una migración o incidente de una capacidad seguiría afectando a la otra, y la separación sería
lógica pero no desplegable.

### Redis para el límite horario

Puede dar conteos de baja latencia, pero suma un almacén y reglas de consistencia entre el
contador y la publicación. PostgreSQL ya participa en la operación; el lock y conteo en la
misma transacción evitan divergencias con menos componentes.

## Consecuencias

- Accounts y Posts pueden migrar, probar y desplegar sus datos por separado.
- No existen joins ni foreign keys entre servicios; las integraciones usan contratos HTTP.
- El equipo opera dos PostgreSQL en desarrollo y despliegue, con puertos y credenciales
  distintos.
- El índice por `author_id, created_at` y el advisory lock sostienen el límite sin estado local
  del proceso.
- El requisito global de diversidad tecnológica y de base sigue pendiente y debe aterrizar en
  otro servicio, no darse por cumplido por tener dos instancias PostgreSQL.
