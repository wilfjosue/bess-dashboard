"""
Actualización de avance_semanal.xlsx — Corte 27/03/2026
"""
import pandas as pd
import os
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
XLSX     = os.path.join(BASE_DIR, "data", "avance_semanal.xlsx")

df = pd.read_excel(XLSX)
# Asegurar columnas de texto como object (pandas las lee como float64 si están en NaN)
for col in ["pct_completado", "estado", "comentario"]:
    if col not in df.columns:
        df[col] = None
    df[col] = df[col].astype(object)

# ── UPDATES ────────────────────────────────────────────────────────────────
UPDATES = [
    # (planta,  id,  pct,    estado,          comentario)
    # Repartición — Izajes
    ("Repartición", 107, 100.0, "Completado",  "Completado 26/03/26 ✅"),
    ("Repartición", 108, 100.0, "Completado",  "Completado 27/03/26 ✅"),
    ("Repartición", 109,   0.0, "En curso",    "Reprogramado 28/03/26"),
    ("Repartición", 110,   0.0, "No iniciado", "Pendiente aceptación"),
    # Majes — Desencofrado y curado (en curso, según plan — no poner pct para que calcule dinámico)
    # Solo ponemos comentario informativo
    ("Majes",        78,  None, "En curso",    "En ejecución — programado 27-30/03"),
    ("Majes",        87,  None, "En curso",    "En ejecución — programado 27-30/03"),
    ("Majes",        79,  None, "No iniciado", "Inicia 31/03 (curado y acabado BESS 1)"),
    ("Majes",        88,  None, "No iniciado", "Inicia 31/03 (curado y acabado BESS 2)"),
    # Majes — Izajes (detrás del plan)
    ("Majes",       107,   0.0, "No iniciado", "Pendiente domingo/lunes 29-30/03 — sujeto a condiciones climáticas"),
    ("Majes",       108,   0.0, "No iniciado", "Pendiente domingo/lunes 29-30/03 — sujeto a condiciones climáticas"),
    ("Majes",       109,   0.0, "No iniciado", "Pendiente semana 30/03"),
    ("Majes",       110,   0.0, "No iniciado", "Pendiente"),
]

cambios = []
for (planta, id_t, pct, estado, comentario) in UPDATES:
    mask = (df["planta"] == planta) & (df["id_tarea"] == id_t)
    n = mask.sum()
    if n == 0:
        print(f"  ⚠  No encontrado: {planta} ID {id_t}")
        continue
    if pct is not None:
        df.loc[mask, "pct_completado"] = pct
    df.loc[mask, "estado"]     = estado
    df.loc[mask, "comentario"] = comentario
    cambios.append(f"  ✓  {planta:12} ID {id_t:3}  pct={str(pct) if pct is not None else 'dinámica':6}  {estado}")

print("Actualizando avance_semanal.xlsx:")
for c in cambios: print(c)

# ── Guardar con estilo ─────────────────────────────────────────────────────
with pd.ExcelWriter(XLSX, engine="openpyxl", date_format="DD/MM/YYYY") as writer:
    df.to_excel(writer, index=False, sheet_name="Avance")
    ws = writer.sheets["Avance"]

    from openpyxl.utils import get_column_letter
    col_widths = {"A":14,"B":10,"C":50,"D":30,"E":18,"F":18,"G":14,"H":20,"I":18,"J":20,"K":50}
    for col, width in col_widths.items():
        ws.column_dimensions[col].width = width

    hdr_fill = PatternFill("solid", fgColor="1A3A5C")
    hdr_font = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
    for cell in ws[1]:
        cell.fill = hdr_fill
        cell.font = hdr_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    fill_m  = PatternFill("solid", fgColor="EBF5FB")
    fill_r  = PatternFill("solid", fgColor="EAFAF1")
    fill_up = PatternFill("solid", fgColor="FFF3CD")  # amarillo para filas actualizadas
    thin    = Side(style="thin", color="CCCCCC")
    border  = Border(left=thin, right=thin, top=thin, bottom=thin)

    updated_pairs = {(p, i) for (p, i, *_) in UPDATES}

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        planta_val  = row[0].value
        id_val      = row[1].value
        is_updated  = (planta_val, id_val) in updated_pairs
        fill = fill_up if is_updated else (fill_m if planta_val == "Majes" else fill_r)
        for cell in row:
            cell.fill   = fill
            cell.border = border
            cell.font   = Font(name="Calibri", size=10,
                               bold=True if is_updated else False)
            cell.alignment = Alignment(vertical="center")
        for ci in [1, 4, 5, 6, 7, 8]:
            row[ci].alignment = Alignment(horizontal="center", vertical="center")

    ws.freeze_panes = "A2"

print(f"\n  Guardado: data/avance_semanal.xlsx ({len(df)} filas)")
print(f"  Filas actualizadas: {len(cambios)}")
