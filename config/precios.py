"""
precios.py — Constantes de la sección de precios mayoristas diarios (SIPSA - DANE).

Los nombres de mercado llegan con variantes entre fuentes y en el tiempo; los
alias viven aquí (y no en un CSV) porque `*.csv` está ignorado por git.
"""

# ── Fuentes DANE ─────────────────────────────────────────────────────────
# Servicio SOAP: solo responde a SOAP 1.2 (application/soap+xml). SOAP 1.1 da 415
# y http:// redirige (301) a https://.
SIPSA_SOAP_URL = "https://appweb.dane.gov.co/sipsaWS/SrvSipsaUpraBeanService"
SIPSA_SOAP_NS = "http://servicios.sipsa.co.gov.dane/"

# Excel diario (resumen: ~16 mercados x 36 productos, solo precio promedio).
SIPSA_EXCEL_URL = "https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSADiario-{token}.xlsx"
MESES_ABREV = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Precio mayorista máximo creíble (COP/kg). Fuera de rango se descarta la fila.
PRECIO_MAX_KG = 200_000

# ── Mercados ─────────────────────────────────────────────────────────────
# clave: nombre tal como llega (SOAP o Excel) -> nombre canónico.
MERCADO_ALIAS = {
    # SOAP
    "Bogotá, D.C., Corabastos": "Bogotá, Corabastos",
    "Cali, Santa Helena": "Cali, Santa Elena",
    "Pereira, La 41-Impala": "Pereira, La 41",
    "Santa Marta (Magdalena)": "Santa Marta",
    "Ibagué, Plaza La 21": "Ibagué, La 21",
    "Medellín, Central Mayorista de Antioquia": "Medellín, CMA",
    "Popayán, Plaza de mercado del barrio Bolívar": "Popayán, Plaza del barrio Bolívar",
    # Excel diario (columnas de ciudad sin nombre de plaza)
    "Popayán": "Popayán, Plaza del barrio Bolívar",
    "Tunja": "Tunja, Complejo de Servicios del Sur",
}

# El Excel diario reporta estas ciudades como PROMEDIO simple de sus mercados en
# el SOAP (verificado 2026-09-18: Valledupar 23/23 y Barranquilla igual a la media
# de Barranquillita y Granabastos). No son mercados: se excluyen del feed horario.
MERCADOS_EXCEL_AGREGADOS = {"Barranquilla", "Valledupar"}

# ── Producto SIPSA -> cultivo de la EVA (dim_cultivo.nombre_normalizado) ──
# Vínculo explícito y revisado a mano (no por coincidencia de texto: 'TOMATE DE ARBOL' no es 'TOMATE',
# 'PAPAYA' no es 'PAPA'). Varios productos pueden apuntar al mismo cultivo (se promedian).
# Sin vínculo (None): CHOCOLO MAZORCA (maíz tierno) se deja fuera para no mezclarlo con el maíz de grano.
PRODUCTO_A_CULTIVO = {
    "AGUACATE": "AGUACATE", "AHUYAMA": "AHUYAMA", "ARRACACHA": "ARRACACHA",
    "ARVEJA VERDE EN VAINA": "ARVEJA", "BANANO": "BANANO",
    "CEBOLLA CABEZONA BLANCA": "CEBOLLA DE BULBO", "CEBOLLA JUNCA": "CEBOLLA DE RAMA",
    "COCO": "COCO", "FRIJOL VERDE": "FRIJOL", "GRANADILLA": "GRANADILLA", "GUAYABA": "GUAYABA",
    "HABICHUELA": "HABICHUELA", "LECHUGA BATAVIA": "LECHUGA", "LIMON COMUN": "LIMON", "LIMON TAHITI": "LIMON",
    "LULO": "LULO", "MANDARINA": "MANDARINA", "MANGO TOMMY": "MANGO", "MANZANA ROYAL GALA": "MANZANA",
    "MARACUYA": "MARACUYA", "MORA DE CASTILLA": "MORA", "NARANJA": "NARANJA",
    "PAPA CRIOLLA": "PAPA", "PAPA NEGRA": "PAPA", "PAPAYA MARADOL": "PAPAYA",
    "PEPINO COHOMBRO": "PEPINO COHOMBRO", "PIMENTON": "PIMENTON", "PINA": "PINA",
    "PLATANO GUINEO": "PLATANO", "PLATANO HARTON VERDE": "PLATANO", "REMOLACHA": "REMOLACHA",
    "TOMATE": "TOMATE", "TOMATE DE ARBOL": "TOMATE DE ARBOL", "YUCA": "YUCA", "ZANAHORIA": "ZANAHORIA",
}

# ── Departamentos ────────────────────────────────────────────────────────
DEPARTAMENTO_ALIAS = {
    "BOGOTÁ, D. C.": "Bogotá D.C.",
    "BOGOTÁ, D.C.": "Bogotá D.C.",
}
PALABRAS_MENORES = {"de", "del", "la", "las", "los", "y"}

# ── Grupos de producto ───────────────────────────────────────────────────
GRUPO_ALIAS = {
    "FRUTAS": "Frutas",
    "VERDURAS Y HORTALIZAS": "Verduras y hortalizas",
    "TUBERCULOS, RAICES Y PLATANOS": "Tubérculos, raíces y plátanos",
    "TUBÉRCULOS, RAÍCES Y PLÁTANOS": "Tubérculos, raíces y plátanos",
}
