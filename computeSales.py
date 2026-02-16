#!/usr/bin/env python3
# pylint: disable=invalid-name
"""
Actividad 5.2 - Compute sales (A5.2)

Este programa:
- Se ejecuta desde línea de comandos.
- Recibe 2 archivos JSON:
  1) Un catálogo de precios (priceCatalogue.json)
  2) Un registro de ventas (salesRecord.json)
- Calcula el costo total de las ventas (sumando cantidad * precio unitario).
- Muestra resultados en consola y los guarda en results/SalesResultsN.txt
  (N se incrementa automáticamente: 1, 2, 3, ...).
- Maneja datos inválidos sin detener la ejecución (registra errores y continúa).
- Reporta el tiempo transcurrido.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Optional


RESULTS_DIR = "results"
BASE_RESULT_NAME = "SalesResults"
RESULT_EXTENSION = ".txt"
SEPARATOR_LINE = "-" * 72
TABLE_HEADER = "SALE_ID | SALE_Date | Product | Quantity | Unit Price | Line Total"


@dataclass(frozen=True)
class ErrorRegistro:
    """Representa un error detectado en un registro, sin detener el programa."""
    indice: int
    mensaje: str


def cargar_json(ruta: str) -> Any:
    """Carga y parsea un archivo JSON."""
    with open(ruta, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def asegurar_carpeta_resultados() -> None:
    """Crea la carpeta de resultados si no existe."""
    os.makedirs(RESULTS_DIR, exist_ok=True)


def formatear_moneda(valor: float) -> str:
    """Formatea un número como moneda con 2 decimales."""
    return f"{valor:,.2f}"


def construir_catalogo_precios(catalogo: Any) -> tuple[dict[str, float], list[str]]:
    """
    Construye un diccionario {nombre_producto: precio} a partir del catálogo.

    Se espera típicamente una lista de objetos con:
    - "title" (nombre del producto)
    - "price" (precio)
    """
    advertencias: list[str] = []
    precios: dict[str, float] = {}

    if not isinstance(catalogo, list):
        advertencias.append(
            "El catálogo no es una lista. Se esperaba una lista de productos."
        )
        return precios, advertencias

    for idx, item in enumerate(catalogo, start=1):
        if not isinstance(item, dict):
            advertencias.append(f"Catálogo: elemento #{idx} no es un objeto JSON.")
            continue

        titulo = item.get("title")
        precio = item.get("price")

        if not isinstance(titulo, str) or not titulo.strip():
            advertencias.append(
                f"Catálogo: elemento #{idx} no tiene 'title' válido (string)."
            )
            continue

        if not isinstance(precio, (int, float)):
            advertencias.append(
                f"Catálogo: '{titulo}' no tiene 'price' numérico válido."
            )
            continue

        precios[titulo.strip()] = float(precio)

    return precios, advertencias


def obtener_str(registro: dict[str, Any], clave: str) -> Optional[str]:
    """Obtiene un campo string no vacío."""
    valor = registro.get(clave)
    if isinstance(valor, str) and valor.strip():
        return valor.strip()
    return None


def obtener_int(registro: dict[str, Any], clave: str) -> Optional[int]:
    """
    Obtiene un campo entero (o convertible a entero).

    Nota: evita aceptar bool (True/False) como int.
    """
    valor = registro.get(clave)

    if isinstance(valor, bool):
        return None

    if isinstance(valor, int):
        return valor

    if isinstance(valor, str):
        texto = valor.strip()
        if texto.isdigit():
            return int(texto)

    return None


def validar_registro_venta(
    indice: int,
    raw: Any,
    precios: dict[str, float],
) -> tuple[Optional[dict[str, Any]], list[str]]:
    """
    Valida un registro de venta.

    Returns:
        (registro_normalizado, problemas)
        - registro_normalizado: dict si es válido estructuralmente, si no None.
        - problemas: lista de problemas encontrados (vacía si todo está bien).
    """
    problemas: list[str] = []

    if not isinstance(raw, dict):
        problemas.append("Registro no es un objeto JSON (dict).")
        return None, problemas

    sale_id = obtener_int(raw, "SALE_ID")
    sale_date = obtener_str(raw, "SALE_Date")
    producto = obtener_str(raw, "Product")
    cantidad = obtener_int(raw, "Quantity")

    if sale_id is None:
        problemas.append("SALE_ID inválido o faltante")
    if sale_date is None:
        problemas.append("SALE_Date inválido o faltante")
    if producto is None:
        problemas.append("Product inválido o faltante")
    if cantidad is None:
        problemas.append("Quantity inválido o faltante")
    elif cantidad < 0:
        problemas.append("Quantity no puede ser negativa")

    if producto is not None and producto not in precios:
        problemas.append(f"Producto no existe en catálogo: '{producto}'")

    if problemas:
        return raw, problemas

    return raw, []


def crear_linea_tabla(
    sale_id: int,
    sale_date: str,
    producto: str,
    cantidad: int,
    precio_unitario: float,
) -> tuple[str, float]:
    """Crea una línea humana/legible para la tabla y devuelve también el total de línea."""
    total_linea = precio_unitario * cantidad
    linea = (
        f"{sale_id} | {sale_date} | {producto} | {cantidad} | "
        f"{formatear_moneda(precio_unitario)} | {formatear_moneda(total_linea)}"
    )
    return linea, total_linea


def procesar_ventas(
    precios: dict[str, float],
    ventas: Any,
) -> tuple[str, float, int, int]:
    """
    Procesa ventas y genera un reporte en texto.

    Returns:
        (reporte, total, registros_validos, registros_invalidos)
    """
    errores: list[ErrorRegistro] = []
    lineas: list[str] = []
    total_general = 0.0
    validos = 0
    invalidos = 0

    if not isinstance(ventas, list):
        reporte_error = (
            "ERROR: El archivo de ventas no contiene una lista de registros.\n"
            "No se puede procesar.\n"
        )
        return reporte_error, 0.0, 0, 0

    lineas.extend(
        [
            "Compute Sales - Results",
            "",
            "Detalle de ventas (se omiten registros inválidos, pero se reportan):",
            "",
            TABLE_HEADER,
            SEPARATOR_LINE,
        ]
    )

    for idx, raw in enumerate(ventas, start=1):
        registro, problemas = validar_registro_venta(idx, raw, precios)
        if problemas:
            invalidos += 1
            mensaje = "; ".join(problemas)
            errores.append(ErrorRegistro(indice=idx, mensaje=mensaje))
            continue

        # Ya validado: existe y tiene campos correctos
        assert registro is not None
        sale_id = int(registro["SALE_ID"])
        sale_date = str(registro["SALE_Date"])
        producto = str(registro["Product"])
        cantidad = int(registro["Quantity"])

        precio_unitario = precios[producto]
        linea, total_linea = crear_linea_tabla(
            sale_id=sale_id,
            sale_date=sale_date,
            producto=producto,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
        )

        lineas.append(linea)
        total_general += total_linea
        validos += 1

    lineas.extend(
        [
            "",
            SEPARATOR_LINE,
            f"Valid records: {validos}",
            f"Invalid records: {invalidos}",
            f"Total cost: {formatear_moneda(total_general)}",
            "",
        ]
    )

    if errores:
        lineas.extend(
            [
                "Errores detectados (la ejecución continuó):",
                SEPARATOR_LINE,
            ]
        )
        for err in errores:
            lineas.append(f"[#{err.indice}] {err.mensaje}")
        lineas.append("")

    reporte = "\n".join(lineas)
    return reporte, total_general, validos, invalidos


def nombre_siguiente_resultado() -> str:
    """
    Genera un nombre tipo SalesResultsN.txt (N incremental) dentro de results/.

    Ejemplos:
      - results/SalesResults1.txt
      - results/SalesResults2.txt
    """
    patron = re.compile(rf"^{re.escape(BASE_RESULT_NAME)}(\d+){re.escape(RESULT_EXTENSION)}$")
    max_num = 0

    try:
        archivos = os.listdir(RESULTS_DIR)
    except FileNotFoundError:
        archivos = []

    for nombre in archivos:
        match = patron.match(nombre)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num

    siguiente = max_num + 1
    return f"{BASE_RESULT_NAME}{siguiente}{RESULT_EXTENSION}"


def escribir_reporte(ruta_salida: str, reporte: str) -> None:
    """Escribe el reporte en disco."""
    with open(ruta_salida, "w", encoding="utf-8") as archivo:
        archivo.write(reporte)


def construir_bloque_advertencias(advertencias: list[str]) -> str:
    """Construye un bloque de advertencias del catálogo para anteponer al reporte."""
    if not advertencias:
        return ""
    lineas = ["Advertencias del catálogo (no fatales):", SEPARATOR_LINE]
    lineas.extend(f"- {a}" for a in advertencias)
    lineas.append("")
    return "\n".join(lineas)


def ejecutar(argv: list[str]) -> int:
    """
    Ejecuta el flujo principal.

    Returns:
        0 si todo sale bien, 1 si hay error fatal.
    """
    if len(argv) != 3:
        print("Uso:")
        print("  python computeSales.py priceCatalogue.json salesRecord.json")
        return 1

    ruta_catalogo = argv[1]
    ruta_ventas = argv[2]

    try:
        catalogo_json = cargar_json(ruta_catalogo)
        ventas_json = cargar_json(ruta_ventas)
    except FileNotFoundError as exc:
        print(f"ERROR: No se encontró el archivo: {exc.filename}")
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: JSON inválido en: {exc.msg}")
        return 1

    precios, advertencias = construir_catalogo_precios(catalogo_json)

    asegurar_carpeta_resultados()
    reporte, _, _, _ = procesar_ventas(precios, ventas_json)

    bloque_adv = construir_bloque_advertencias(advertencias)
    if bloque_adv:
        reporte = bloque_adv + reporte

    # Guardar con nombre incremental
    nombre_salida = nombre_siguiente_resultado()
    ruta_salida = os.path.join(RESULTS_DIR, nombre_salida)

    try:
        escribir_reporte(ruta_salida, reporte)
    except OSError as exc:
        print(f"ERROR: No se pudo escribir el archivo de resultados: {ruta_salida}")
        print(f"Detalle: {exc}")
        return 1

    # También mostrar en consola
    print(reporte)
    print(f"\nArchivo de salida: {ruta_salida}")

    return 0


def main() -> int:
    """Punto de entrada principal con medición de tiempo."""
    inicio = time.perf_counter()
    codigo = ejecutar(sys.argv)
    fin = time.perf_counter()

    # Nota: se imprime siempre, incluso si hubo error (así queda evidencia).
    print(f"\nElapsed time (s): {fin - inicio}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())