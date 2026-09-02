import csv
import io
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.datavalidation import DataValidation
from database import db
from security import require_business, require_roles, new_id, now_iso

router = APIRouter(tags=["import-export"])
MANAGER = Depends(require_roles("propietario", "administrador"))

PRODUCT_COLUMNS = [
    ("nombre", "Nombre del producto", "Texto", "Ej. Harina P.A.N. blanca 1kg"),
    ("sku", "SKU / Código interno", "Texto", "P-0001"),
    ("codigo_barras", "Código de barras", "Texto", "7591234567890"),
    ("categoria", "Categoría", "Texto", "Alimentos"),
    ("marca", "Marca", "Texto", "P.A.N."),
    ("proveedor", "Proveedor", "Texto", "Proveedor Demo"),
    ("precio_compra", "Precio de compra", "Número", "1.25"),
    ("precio_venta", "Precio de venta", "Número", "1.80"),
    ("stock", "Stock inicial", "Número", "20"),
    ("stock_minimo", "Stock mínimo", "Número", "5"),
    ("stock_maximo", "Stock máximo", "Número", "50"),
    ("unidad", "Unidad", "Texto", "unidad"),
    ("imagen_url", "URL de imagen", "Texto", "https://..."),
]


def _styled_workbook(title, columns, example_rows=None):
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    thin = Side(style="thin", color="D9DEE7")
    header_fill = PatternFill("solid", fgColor="1F2937")
    example_fill = PatternFill("solid", fgColor="EFF6FF")
    header_font = Font(color="FFFFFF", bold=True)
    for idx, (key, label, *_rest) in enumerate(columns, 1):
        cell = ws.cell(1, idx, label)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = Border(bottom=thin)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}1"
    if example_rows:
        for r, row in enumerate(example_rows, 2):
            for c, value in enumerate(row, 1):
                cell = ws.cell(r, c, value)
                cell.fill = example_fill
                cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
    widths = [max(14, min(34, len(label) + 4)) for _, label, *_ in columns]
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.row_dimensions[1].height = 28
    return wb, ws


def _add_instructions(wb, columns, title):
    ws = wb.create_sheet("Instrucciones")
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 65
    ws.append(["PLANTILLA CUADRAAPP", title])
    ws.append(["Cómo usarla", "Completa la hoja de datos y conserva los nombres de las columnas. No elimines la fila de encabezados."])
    ws.append(["Obligatorios", "Los campos marcados como obligatorios deben estar completos."])
    ws.append(["Números", "Usa números sin símbolos de moneda. Ejemplo: 125.50"])
    ws.append(["Texto", "SKU y códigos de barras se tratan como texto para conservar ceros iniciales."])
    ws.append(["Importación", "CuadraApp validará el archivo antes de registrar los datos."])
    ws.append([])
    ws.append(["Columna", "Descripción"])
    for key, label, kind, example in columns:
        ws.append([label, f"Tipo: {kind}. Ejemplo: {example}"])
    for row in ws.iter_rows():
        for cell in row:
            cell.border = Border(bottom=Side(style="thin", color="E5E7EB"))
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    ws["A1"].font = Font(bold=True, size=14)
    ws["B1"].font = Font(bold=True, size=14)


def _xlsx_response(wb, filename):
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'})


def _num(value, default=0.0):
    try:
        return float(str(value or "").replace(",", ".").strip())
    except (TypeError, ValueError):
        return default


@router.get("/templates/products")
async def product_template(user: dict = MANAGER):
    columns = PRODUCT_COLUMNS
    examples = [[c[3] for c in columns]]
    wb, ws = _styled_workbook("Productos", columns, examples)
    _add_instructions(wb, columns, "Importación de productos")
    table = Table(displayName="ProductosPlantilla", ref=f"A1:{get_column_letter(len(columns))}2")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(table)
    return _xlsx_response(wb, "plantilla_productos")


@router.get("/templates/products/csv")
async def product_template_csv(user: dict = MANAGER):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([c[0] for c in PRODUCT_COLUMNS])
    writer.writerow([c[3] for c in PRODUCT_COLUMNS])
    return StreamingResponse(iter(["\ufeff" + buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="plantilla_productos.csv"'})


@router.post("/products/import/xlsx")
async def import_products_xlsx(file: UploadFile = File(...), user: dict = MANAGER):
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Sube una plantilla Excel .xlsx")
    from openpyxl import load_workbook
    raw = await file.read()
    try:
        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        ws = wb["Productos"] if "Productos" in wb.sheetnames else wb.active
        rows = list(ws.iter_rows(values_only=True))
    except Exception as exc:
        raise HTTPException(400, f"No pudimos leer el Excel: {exc}")
    if not rows:
        raise HTTPException(400, "El archivo está vacío")
    headers = [str(x or "").strip().lower() for x in rows[0]]
    expected = [c[0] for c in PRODUCT_COLUMNS]
    if "nombre" not in headers:
        raise HTTPException(400, "Falta la columna obligatoria: nombre")
    bid = user["business_id"]
    existing_skus = {p.get("sku") for p in await db.products.find({"business_id": bid}, {"sku": 1}).to_list(10000)}
    existing_barcodes = {p.get("barcode") for p in await db.products.find({"business_id": bid}, {"barcode": 1}).to_list(10000)}
    created = errors = 0
    issues = []
    for line_no, values in enumerate(rows[1:], 2):
        row = {headers[i]: values[i] if i < len(values) else None for i in range(len(headers))}
        name = str(row.get("nombre") or "").strip()
        if not name or name.startswith("Ej."):
            continue
        sku = str(row.get("sku") or "").strip() or None
        barcode = str(row.get("codigo_barras") or "").strip() or None
        if sku and sku in existing_skus:
            errors += 1; issues.append({"row": line_no, "field": "sku", "message": "SKU ya existe"}); continue
        if barcode and barcode in existing_barcodes:
            errors += 1; issues.append({"row": line_no, "field": "codigo_barras", "message": "Código de barras ya existe"}); continue
        product = {
            "id": new_id(), "business_id": bid, "name": name,
            "sku": sku or f"P-{await db.products.count_documents({'business_id': bid}) + created + 1:04d}",
            "barcode": barcode,
            "category": str(row.get("categoria") or "General").strip() or "General",
            "brand": str(row.get("marca") or "").strip() or None,
            "supplier": str(row.get("proveedor") or "").strip() or None,
            "purchase_price": _num(row.get("precio_compra")),
            "sale_price": _num(row.get("precio_venta")),
            "stock": _num(row.get("stock")),
            "min_stock": _num(row.get("stock_minimo"), 5),
            "max_stock": _num(row.get("stock_maximo")) or None,
            "unit": str(row.get("unidad") or "unidad").strip(),
            "image_url": str(row.get("imagen_url") or "").strip() or None,
            "status": "activo", "created_at": now_iso(), "updated_at": now_iso(),
        }
        await db.products.insert_one(product)
        existing_skus.add(product["sku"])
        if barcode: existing_barcodes.add(barcode)
        created += 1
        if product["stock"] > 0:
            await db.inventory_movements.insert_one({"id": new_id(), "business_id": bid, "product_id": product["id"], "product_name": name, "type": "entrada", "reason": "carga_inicial", "quantity": product["stock"], "stock_after": product["stock"], "user_email": user["email"], "notes": "Importado desde plantilla Excel", "created_at": now_iso()})
    return {"created": created, "errors": errors, "issues": issues, "processed": created + errors}
