/* Glosario único de la app: cada término se explica igual en todas las pantallas (componente <Term>). */
export const GLOSARIO = {
  "t/ha": {
    termino: "t/ha",
    definicion: "Toneladas por hectárea: cuánto se cosecha en cada hectárea sembrada. Es la medida de rendimiento.",
  },
  "p10-p90": {
    termino: "p10–p90",
    definicion:
      "Rango en el que suele caer el valor real. Se calculó con los errores reales del modelo en años anteriores: en las pruebas, ~8 de cada 10 valores reales quedaron dentro.",
  },
  ENSO: {
    termino: "ENSO",
    definicion:
      "El Niño–Oscilación del Sur: ciclo de calentamiento (El Niño) y enfriamiento (La Niña) del Pacífico que cambia las lluvias en Colombia. El Niño suele traer menos lluvia; La Niña, más.",
  },
  ONI: {
    termino: "ONI",
    definicion: "Índice Oceánico de El Niño (NOAA): anomalía de temperatura del mar en el Pacífico. Valores ≥ 0,5 sostenidos indican El Niño; ≤ −0,5, La Niña.",
  },
  SPI: {
    termino: "SPI",
    definicion:
      "Índice estandarizado de precipitación: cuántas desviaciones típicas se aleja la lluvia de lo normal. Aquí se calcula con pocos años de datos, así que es orientativo.",
  },
  MAE: {
    termino: "MAE",
    definicion: "Error absoluto medio: cuántas t/ha se equivoca el modelo, en promedio, sin importar el signo. Menor es mejor.",
  },
  "R2": {
    termino: "R²",
    definicion:
      "Qué parte de la variación de los rendimientos explica el modelo (0 a 1). Ojo: es alto porque los cultivos rinden muy distinto entre sí; para juzgar el modelo compáralo con la línea base.",
  },
  "linea-base": {
    termino: "línea base",
    definicion: "Predicción ingenua contra la que se compara el modelo: el promedio histórico de ese municipio y cultivo. Un modelo útil debe superarla.",
  },
  "fuera-de-muestra": {
    termino: "fuera de muestra",
    definicion: "Predicción hecha para un año que el modelo no vio al entrenarse. Es la única forma honesta de medir qué tan bien predice.",
  },
  mayorista: {
    termino: "precio mayorista",
    definicion: "Precio al que se vende por volumen en las centrales de abasto. No es el precio que paga el consumidor en tienda o plaza.",
  },
  SIPSA: {
    termino: "SIPSA",
    definicion: "Sistema de Información de Precios y Abastecimiento del Sector Agropecuario del DANE: fuente oficial de los precios mayoristas.",
  },
  "dia-habil": {
    termino: "día hábil",
    definicion: "Lunes a viernes. DANE publica los precios una vez por día hábil; fines de semana y festivos se muestra el último dato.",
  },
  eta2: {
    termino: "η² (eta cuadrado)",
    definicion: "Tamaño del efecto: qué fracción de la variación se explica por el grupo. ~0,01 pequeño, ~0,06 mediano, ~0,14 grande.",
  },
};
