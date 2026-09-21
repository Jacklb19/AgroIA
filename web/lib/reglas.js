/* Reglas orientativas de escenario (ENSO y régimen de lluvia).

   IMPORTANTE: NO son salidas del modelo XGBoost ni están calibradas con los datos del proyecto: son
   porcentajes fijos de referencia sobre el rendimiento. La interfaz las rotula como "regla orientativa"
   y las muestra por separado de la predicción del modelo.

   Son PROPORCIONALES al rendimiento del cultivo (antes eran una constante en t/ha igual para todos:
   -0,5 t/ha era un 2,5 % para la papa pero un 50 % para el café). Los porcentajes equivalen a los valores
   anteriores para un rendimiento de referencia de 5 t/ha. */

export const AJUSTE_ENSO_PCT = { "El Niño": -0.10, "La Niña": 0.06, Neutral: 0 };
export const AJUSTE_LLUVIA_PCT = { "Déficit": -0.08, Exceso: -0.04, Normal: 0 };

export function ajustePct(enso, lluvia) {
  return (AJUSTE_ENSO_PCT[enso] ?? 0) + (AJUSTE_LLUVIA_PCT[lluvia] ?? 0);
}

/* Ajuste en t/ha para un rendimiento `base` (t/ha). */
export function ajusteEscenario(enso, lluvia, base) {
  return Math.round(Number(base) * ajustePct(enso, lluvia) * 100) / 100;
}

export const NOTA_REGLAS =
  "El ajuste por escenario (ENSO y lluvia) es una regla orientativa fija, proporcional al rendimiento; no es una salida del modelo.";
