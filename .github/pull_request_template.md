## Qué

<!-- Qué cambió, en una o dos oraciones. -->

<!-- Use `Part of #<issue>` or `Refs #<issue>` for a partial increment. Use
`Closes #<issue>` only for the final pull request that completes the story. -->

## Por qué

<!--
El razonamiento, no la repetición de lo de arriba. Qué opciones consideraste y por qué esta.
"Porque el enunciado lo pedía" no es una razón: el enunciado dice que necesitás la
capacidad, no cómo construirla.

Esta es la misma respuesta que vas a dar en voz alta en la reunión semanal. Si algo se
decidió por Slack, en una llamada o al lado de alguien, escribilo acá: esta es la copia que
sobrevive.
-->

## Cómo se probó

<!--
Qué tests agregaste y qué cubren. Si probaste a mano, decí exactamente qué hiciste, para que
otra persona pueda repetirlo.
-->

## Capturas o video

<!-- Obligatorio para cualquier cambio con interfaz. Borrá esta sección si el cambio es solo de backend. -->

---

- [ ] Se cumplen los criterios de aceptación que reclama este pull request; solo el PR final
  debe cumplir todos los criterios del issue
- [ ] Tests agregados, CI en verde, umbral de cobertura pasando
- [ ] Tests de integración agregados, si el cambio cruza el límite de un servicio
- [ ] `README.md` sigue levantando el servicio desde un clone limpio
- [ ] Variables de entorno nuevas agregadas a `.env.template`, sin secretos commiteados
- [ ] Si es un PR parcial, la tarjeta y el issue quedan abiertos; el PR final mueve la tarjeta a
  Done y cierra el issue
- [ ] Tutor agregado como reviewer
- [ ] Aprobado por alguien que no sea el autor
