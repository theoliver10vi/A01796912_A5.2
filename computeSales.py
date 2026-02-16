#!/usr/bin/env python3
# pylint: disable=invalid-name

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Iterable


RESULTS_DIR = "results"
RESULTS_FILENAME = "SalesResults.txt"
SEPARATOR_LEN = 72


@dataclass
class ErrorRegistro:
    """Representa un error detectado en un registro, sin detener el programa."""
    indice: int
    mensaje: str
    registro: dict[str, Any]


def cargar_json(ruta: str) -> Any:
    with open(ruta, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def construir_catalogo_precios(catalogo: Any) -> tuple[dict[str, float], list[str]]:
    advertencias: list[str] = []
    precios: dict[str, float] = {}

    if not isinstance(catalogo, list):
        advertencias.append(
            "El catálogo no es una lista. Se esperaba una lista de productos."
        )
        return precios, advertencias

    for i, item in enumerate(catalogo, start=1):
        if not isinstance(item, dict):
            advertencias.append(f"Catálogo: elemento #{i} no es objeto JSON.")
            continue

        titulo = item.get("title")
        precio = item.get("price")

        if not isinstance(titulo, str) or not titulo.strip():
            advertencias.append(
                f"Catálogo: elemento #{i} no tiene 'title' válido (string)."
            )
            continue

        if not isinstance(precio, (int, float)):
            advertencias.append(
                f"Catálogo: '{titulo}' no tiene 'price' numérico válido."
            )
            continue

        precios[titulo.strip()] = float(precio)

    return precios, advertencias


def obtener_str(registro: dict[str, Any], clave: str) -> str | None:
    """Obtiene un campo string no vacío."""
    valor = registro.get(clave)
    if isinstance(valor, str) and valor.strip():
        return valor.strip()
    return None


def obtener_int(registro: dict[str, Any], clave: str) -> int | None:
    """Obtiene un campo entero (o convertible razonablemente a entero)."""
    valor = registro.get(clave)

    # Evitamos que True/False pasen como int
    if isinstance(valor, bool):
        return None

    if isinstance(valor, int):
        return valor

    if isinstance(valor, str):
        texto = valor.strip()
        if texto.isdigit():
            return int(texto)

    return None


def asegurar_carpeta_resultados() -> None:
    """Crea la carpeta results/ si no existe."""
    os.makedirs(RESULTS_DIR, exist_ok=True)


def ruta_salida_resultados() -> str:
    """Devuelve la ruta completa del archivo de salida en results/."""
    return os.path.join(RESULTS_DIR, RESULTS_FILENAME)


def formatear_moneda(valor: float) -> str:
    """Formatea un número como moneda con 2 decimales."""
    return f"{valor:,.2f}"


def construir_encabezado_tabla() -> list[str]:
    """Crea el encabezado de la tabla en texto."""
    header = (
        "SALE_ID | SALE_Date | Product | Quantity | "
        "Unit Price | Line Total"
    )
    return [header, "-" * SEPARATOR_LEN]


def registrar_error(
    errores: list[ErrorRegistro],
    indice: int,
    mensaje: str,
    registro: dict[str, Any],
) -> None:
    """Agrega un error a la lista de errores."""
    errores.append(ErrorRegistro(indice=indice, mensaje=mensaje, registro=registro))


def validar_venta(
    registro: Any,
    precios: dict[str, float],
    indice: int,
    errores: list[ErrorRegistro],
) -> tuple[int, str, str, int] | None:
    if not isinstance(registro, dict):
        registrar_error(
            errores,
            indice,
            "Registro no es un objeto JSON (dict).",
            {"raw": registro},
        )
        return None

    sale_id = obtener_int(registro, "SALE_ID")
    sale_date = obtener_str(registro, "SALE_Date")
    producto = obtener_str(registro, "Product")
    cantidad = obtener_int(registro, "Quantity")

    problemas: list[str] = []
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
        registrar_error(errores, indice, "; ".join(problemas), registro)
        return None

    # A este punto ya están validados y no son None
    assert sale_id is not None
    assert sale_date is not None
    assert producto is not None
    assert cantidad is not None

    return sale_id, sale_date, producto, cantidad


def calcular_linea(
    sale_id: int,
    sale_date: str,
    producto: str,
    cantidad: int,
    precios: dict[str, float],
) -> tuple[str, float]:
    precio_unitario = precios[producto]
    total_linea = precio_unitario * cantidad

    linea = (
        f"{sale_id} | {sale_date} | {producto} | {cantidad} | "
        f"{formatear_moneda(precio_unitario)} | {formatear_moneda(total_linea)}"
    )
    return linea, total_linea


def construir_resumen(validos: int, invalidos: int, total: float) -> list[str]:
    """Construye el bloque de resumen al final del reporte."""
    return [
        "",
        "-" * SEPARATOR_LEN,
        f"Valid records: {validos}",
        f"Invalid records: {invalidos}",
        f"Total cost: {formatear_moneda(total)}",
        "",
    ]


def construir_bloque_errores(errores: Iterable[ErrorRegistro]) -> list[str]:
    """Construye el bloque de errores (si existen)."""
    errores_list = list(errores)
    if not errores_list:
        return []

    lineas: list[str] = [
        "Errores detectados (la ejecución continuó):",
        "-" * SEPARATOR_LEN,
    ]
    for err in errores_list:
        lineas.append(f"[#{err.indice}] {err.mensaje}")
    lineas.append("")
    return lineas


def procesar_ventas(
    precios: dict[str, float],
    ventas: Any,
) -> tuple[str, float, int, int]:
    if not isinstance(ventas, list):
        encabezado = (
            "ERROR: El archivo de ventas no contiene una lista de registros.\n"
            "No se puede procesar.\n"
        )
        return encabezado, 0.0, 0, 0

    errores: list[ErrorRegistro] = []
    lineas: list[str] = [
        "Compute Sales - Results",
        "",
        (
            "Detalle de ventas (se omiten registros inválidos, "
            "pero se reportan):"
        ),
        "",
    ]
    lineas.extend(construir_encabezado_tabla())

    total_general = 0.0
    validos = 0
    invalidos = 0

    for idx, raw in enumerate(ventas, start=1):
        normalizado = validar_venta(raw, precios, idx, errores)
        if normalizado is None:
            invalidos += 1
            continue

        sale_id, sale_date, producto, cantidad = normalizado
        linea, total_linea = calcular_linea(
            sale_id=sale_id,
            sale_date=sale_date,
            producto=producto,
            cantidad=cantidad,
            precios=precios,
        )
        lineas.append(linea)
        total_general += total_linea
        validos += 1

    lineas.extend(construir_resumen(validos, invalidos, total_general))
    lineas.extend(construir_bloque_errores(errores))

    reporte = "\n".join(lineas)
    return reporte, total_general, validos, invalidos


def construir_bloque_advertencias(advertencias: list[str]) -> str:
    """Construye el bloque de advertencias del catálogo."""
    if not advertencias:
        return ""

    lineas: list[str] = [
        "Advertencias del catálogo (no fatales):",
        "-" * SEPARATOR_LEN,
    ]
    lineas.extend(f"- {adv}" for adv in advertencias)
    lineas.append("")
    return "\n".join(lineas)


def parsear_argumentos(argv: list[str]) -> tuple[str, str] | None:
    """Valida argumentos de línea de comandos y devuelve rutas."""
    if len(argv) != 3:
        print("Uso:")
        print("  python computeSales.py priceCatalogue.json salesRecord.json")
        return None
    return argv[1], argv[2]


def cargar_archivo_con_mensaje(ruta: str, tipo: str) -> Any | None:
    """
    Carga un JSON y muestra un error amigable si falla.

    Args:
        ruta: ruta del archivo
        tipo: texto para el mensaje (por ejemplo: 'catálogo' o 'ventas')
    """
    try:
        return cargar_json(ruta)
    except FileNotFoundError:
        print(f"ERROR: No se encontró el archivo de {tipo}: {ruta}")
        return None
    except json.JSONDecodeError as exc:
        print(f"ERROR: El archivo de {tipo} no es JSON válido: {ruta}")
        print(f"Detalle: {exc}")
        return None


def escribir_reporte(salida: str, contenido: str) -> bool:
    """Escribe el reporte en disco. Devuelve True si se pudo, si no False."""
    try:
        with open(salida, "w", encoding="utf-8") as archivo:
            archivo.write(contenido)
        return True
    except OSError as exc:
        print(f"ERROR: No se pudo escribir el archivo de resultados: {salida}")
        print(f"Detalle: {exc}")
        return False


def main() -> int:
    """Punto de entrada del programa."""
    inicio = time.perf_counter()

    rutas = parsear_argumentos(sys.argv)
    if rutas is None:
        return 1

    ruta_catalogo, ruta_ventas = rutas

    catalogo_json = cargar_archivo_con_mensaje(ruta_catalogo, "catálogo")
    if catalogo_json is None:
        return 1

    ventas_json = cargar_archivo_con_mensaje(ruta_ventas, "ventas")
    if ventas_json is None:
        return 1

    precios, advertencias = construir_catalogo_precios(catalogo_json)

    asegurar_carpeta_resultados()
    reporte, _, _, _ = procesar_ventas(precios, ventas_json)

    bloque_adv = construir_bloque_advertencias(advertencias)
    if bloque_adv:
        reporte = bloque_adv + reporte

    tiempo_transcurrido = time.perf_counter() - inicio
    reporte += f"\nElapsed time (s): {tiempo_transcurrido}\n"

    # Imprimir en pantalla
    print(reporte)

    # Guardar en archivo
    salida = ruta_salida_resultados()
    if not escribir_reporte(salida, reporte):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
