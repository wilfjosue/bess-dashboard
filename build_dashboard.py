"""
BESS Project Control System — Módulo 1: Dashboard de Cronograma
Plantas: Majes y Repartición (Arequipa, Perú)
Genera: outputs/dashboard_bess.html
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json, os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR  = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

# Paleta
C = {
    "azul":      "#1a3a5c",
    "verde":     "#0d9e5c",
    "verde_l":   "#d4f5e3",
    "amarillo":  "#c97a0a",
    "amarillo_l":"#fdf0d0",
    "rojo":      "#c8263a",
    "rojo_l":    "#fde8ea",
    "celeste":   "#1a5fa8",
    "celeste_l": "#daeaf8",
    "bg":        "#f0f4f8",
    "white":     "#ffffff",
    "ink":       "#0d1b2a",
    "ink2":      "#1e3a5f",
    "muted":     "#607080",
    "faint":     "#dde4ed",
    "teal":      "#0b7a72",
}

HITO_PLAN     = datetime(2026, 6, 24)
HITO_OBJETIVO = datetime(2026, 5, 30)
FECHA_CORTE   = datetime(2026, 4, 10)   # ← EDITAR cada corte semanal
GENERADO_EL   = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
BUFFER_COES   = 13   # días entre fin respuesta COES y puesta en marcha

MACROFASES = [
    {"id":1,"nombre":"Ingeniería de Detalle",        "ids_min":3,  "ids_max":19,  "col_p":"#1a5fa8"},
    {"id":2,"nombre":"Permisos HSE y Arqueológicos", "ids_min":20, "ids_max":39,  "col_p":"#7c3aed"},
    {"id":3,"nombre":"Construcción Civil",           "ids_min":41, "ids_max":71,  "col_p":"#0b7a72"},
    {"id":4,"nombre":"Zanjas y Cableado",            "ids_min":72, "ids_max":95,  "col_p":"#c97a0a"},
    {"id":5,"nombre":"Suministro y Montaje",         "ids_min":96, "ids_max":127, "col_p":"#0d9e5c"},
    {"id":6,"nombre":"Estudio COES",                 "ids_min":128,"ids_max":143, "col_p":"#c8263a"},
    {"id":7,"nombre":"Puesta en Marcha",             "ids_min":144,"ids_max":154, "col_p":"#b45309"},
]

# Comentarios semanales — editar aquí cada semana
COMENTARIOS = {
    1: {"Majes":"Ingeniería civil y eléctrica aprobadas",
        "Repartición":"Ingeniería civil y eléctrica aprobadas"},
    2: {"Majes":"ITS aprobado, EIA en revisión final",
        "Repartición":"ITS en levantamiento observaciones"},
    3: {"Majes":"Civil completado — cimentaciones aceptadas",
        "Repartición":"Civil completado — cimentaciones aceptadas"},
    4: {"Majes":"Desencofrado zanjas +11d retraso (plan 30/03, pendiente)",
        "Repartición":"Desencofrado zanjas +11d retraso (plan 30/03, pendiente)"},
    5: {"Majes":"Izaje BESS 1,2,MV ✅ completados · Puesta a tierra sin iniciar",
        "Repartición":"Izaje BESS 1,2,MV ✅ completados · Puesta a tierra sin iniciar"},
    6: {"Majes":"🔴 BLOQUEADO — archivos DIgSILENT incorrectos de Itechene",
        "Repartición":"🔴 BLOQUEADO — archivos DIgSILENT incorrectos de Itechene"},
    7: {"Majes":"Pendiente aprobación COES",
        "Repartición":"Pendiente aprobación COES"},
}

# Novedades manuales del período — editar cada semana
# Se muestran en el panel "Alertas del Período" encima de las alertas automáticas
NOVEDADES = [
    {"tipo":"critico", "texto":"🔴 CRÍTICO — COES BLOQUEADO: Itechene no entrega archivos DIgSILENT correctos. Consultor sin insumos. Presentación 20/04 EN RIESGO. Objetivo 30/05 comprometido."},
    {"tipo":"atencion","texto":"⚠️ MAJES y REPARTICIÓN — Desencofrado zanjas con +11 días de retraso (plan 30/03, pendiente)."},
    {"tipo":"atencion","texto":"⚠️ AMBAS PLANTAS — Puesta a tierra sin iniciar. Materiales recién llegaron a obra."},
    {"tipo":"logro",   "texto":"✅ MAJES — Izaje BESS 1, BESS 2 y MV Station completados."},
    {"tipo":"logro",   "texto":"✅ REPARTICIÓN — Izaje BESS 1 (26/03), BESS 2 (27/03), MV Station (28/03) completados."},
]

# ─────────────────────────────────────────────────────────────────────────────
# 1. PARSEAR EXCELS
# ─────────────────────────────────────────────────────────────────────────────
_MESES_ES = {
    "enero":"01","febrero":"02","marzo":"03","abril":"04",
    "mayo":"05","junio":"06","julio":"07","agosto":"08",
    "septiembre":"09","octubre":"10","noviembre":"11","diciembre":"12"
}

def parse_date_es(s):
    if pd.isna(s): return pd.NaT
    s = str(s).strip()
    if s.upper() in ("NOD","NA",""): return pd.NaT
    sl = s.lower()
    for mes, num in _MESES_ES.items():
        if mes in sl:
            sl = sl.replace(mes, num); break
    parts = sl.split()
    dp = [p for p in parts if p.isdigit() or p in _MESES_ES.values()][:3]
    if len(dp) == 3:
        try: return pd.to_datetime(" ".join(dp), dayfirst=True, errors="coerce")
        except: pass
    return pd.to_datetime(sl, dayfirst=True, errors="coerce")

def load_cronograma(filepath, planta):
    df = pd.read_excel(filepath)
    df.columns = [c.strip() for c in df.columns]
    col_map = {}
    for c in df.columns:
        clean = (c.replace("ó","o").replace("ú","u").replace("é","e")
                  .replace("í","i").replace("á","a").replace("ñ","n")
                  .replace(" ","_").replace("-","_"))
        col_map[c] = clean
    df = df.rename(columns=col_map)
    for col in ["Comienzo","Fin"]:
        if col in df.columns:
            df[col] = df[col].apply(parse_date_es)
    df["planta"] = planta
    def get_macrofase(id_val):
        for mf in MACROFASES:
            if mf["ids_min"] <= id_val <= mf["ids_max"]: return mf["nombre"]
        return "Otro"
    df["macrofase"] = df["Id"].apply(get_macrofase)
    # Nombre de tarea — detectar columna
    df["_nombre"] = df[[c for c in df.columns if "Nombre" in c][0]] if any("Nombre" in c for c in df.columns) else ""
    return df

print("📂 Leyendo cronogramas...")
df_majes = load_cronograma(
    os.path.join(BASE_DIR,"Cronograma de Obra Actualizado BESS MAJES 19.03.2026.xlsx"), "Majes")
df_rep   = load_cronograma(
    os.path.join(BASE_DIR,"Cronograma de Obra Actualizado BESS REPARTICIÓN 19.3.26.xlsx"), "Repartición")
df_all = pd.concat([df_majes, df_rep], ignore_index=True)
print(f"   Majes: {len(df_majes)} | Repartición: {len(df_rep)} tareas")

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE CÁLCULO — deben estar antes de load_avance_semanal
# ─────────────────────────────────────────────────────────────────────────────
def pct_planeado_dinamico(inicio, fin, hoy=None):
    """% teórico planificado a FECHA_CORTE (no datetime.today)."""
    if hoy is None: hoy = FECHA_CORTE
    if pd.isna(inicio) or pd.isna(fin): return 0.0
    inicio, fin, hoy = pd.Timestamp(inicio), pd.Timestamp(fin), pd.Timestamp(hoy)
    if hoy <= inicio: return 0.0
    if hoy >= fin:    return 100.0
    dur = (fin - inicio).days
    return round(100.0 * (hoy - inicio).days / dur, 1) if dur else 100.0

def color_semaforo(pct_real, pct_plan, is_empty=False):
    """Verde si sin dato o real≥plan. Rojo si real<plan-10. Amarillo en medio."""
    if is_empty or pct_real >= pct_plan: return C["verde"]
    elif pct_real < pct_plan - 10:       return C["rojo"]
    else:                                return C["amarillo"]

def color_hex_light(hex_color):
    """Versión clara de un color hex para fondos."""
    mapping = {C["verde"]:C["verde_l"], C["rojo"]:C["rojo_l"], C["amarillo"]:C["amarillo_l"]}
    return mapping.get(hex_color, C["celeste_l"])

# ─────────────────────────────────────────────────────────────────────────────
# 2. CARGAR avance_semanal.xlsx → agregar a macrofase
# ─────────────────────────────────────────────────────────────────────────────
def load_avance_semanal():
    # Usar _new si existe (cuando el original está bloqueado por Excel)
    new_path = os.path.join(DATA_DIR, "avance_semanal_new.xlsx")
    path     = new_path if os.path.exists(new_path) else os.path.join(DATA_DIR, "avance_semanal.xlsx")
    df   = pd.read_excel(path)
    df["fecha_inicio_plan"] = pd.to_datetime(df["fecha_inicio_plan"], errors="coerce")
    df["fecha_fin_plan"]    = pd.to_datetime(df["fecha_fin_plan"],    errors="coerce")
    df["pct_plan_calc"]     = df.apply(
        lambda r: pct_planeado_dinamico(r["fecha_inicio_plan"], r["fecha_fin_plan"]), axis=1)
    df["pct_completado_num"] = pd.to_numeric(df.get("pct_completado"), errors="coerce")
    df["is_manual"]          = df["pct_completado_num"].notna()
    df["pct_real"]           = df.apply(
        lambda r: r["pct_completado_num"] if r["is_manual"] else r["pct_plan_calc"], axis=1)
    if "comentario" not in df.columns: df["comentario"] = ""
    df["comentario"] = df["comentario"].fillna("")

    rows = []
    for mf in MACROFASES:
        for planta in ["Majes","Repartición"]:
            sub = df[(df["planta"]==planta) & (df["macrofase"]==mf["nombre"])]
            if sub.empty: continue
            pct_plan  = round(sub["pct_plan_calc"].mean(), 1)
            all_empty = not sub["is_manual"].any()
            pct_real  = round(sub["pct_real"].mean(), 1)
            com = "; ".join(sub["comentario"][sub["comentario"]!=""].tolist()) \
                  or COMENTARIOS.get(mf["id"],{}).get(planta,"")
            col = color_semaforo(pct_real, pct_plan, is_empty=all_empty)
            if pct_real >= 99:                   estado = "Completado"
            elif pct_real == 0 and pct_plan == 0:estado = "No iniciado"
            elif col == C["rojo"]:               estado = "En riesgo"
            else:                                estado = "En curso"
            spi = round(pct_real/pct_plan,2) if pct_plan>0 else 1.0
            rows.append({"planta":planta,"id_tarea":mf["id"],"nombre_tarea":mf["nombre"],
                         "macrofase":mf["nombre"],"pct_plan":pct_plan,"pct_real":pct_real,
                         "all_empty":all_empty,"color":col,"estado":estado,
                         "spi":spi,"comentario":com})
    return pd.DataFrame(rows)

print("📊 Cargando avance_semanal.xlsx...")
df_avance = load_avance_semanal()
print(f"   ✅ {len(df_avance)} macrofases | FECHA_CORTE = {FECHA_CORTE.strftime('%d/%m/%Y')}")

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS ADICIONALES
# ─────────────────────────────────────────────────────────────────────────────
def dias_restantes(target):
    return (target - FECHA_CORTE).days

def fmt_fecha(dt):
    if pd.isna(dt): return "—"
    M = ["","Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
    return f"{dt.day:02d}/{M[dt.month]}/{dt.year}"

def kpi_avance_planta(planta):
    """% avance real promedio de todas las macrofases de una planta."""
    sub = df_avance[df_avance["planta"]==planta]
    return round(sub["pct_real"].mean(), 1) if not sub.empty else 0.0

def kpi_spi_global():
    return round(df_avance["spi"].mean(), 2)

# ─────────────────────────────────────────────────────────────────────────────
# DATOS CALCULADOS
# ─────────────────────────────────────────────────────────────────────────────
dias_obj    = dias_restantes(HITO_OBJETIVO)
dias_plan   = dias_restantes(HITO_PLAN)
brecha      = (HITO_PLAN - HITO_OBJETIVO).days
kpi_m       = kpi_avance_planta("Majes")
kpi_r       = kpi_avance_planta("Repartición")
kpi_spi     = kpi_spi_global()

# Semáforo global por planta: el peor color entre sus macrofases
def semaforo_global(planta):
    cols = df_avance[df_avance["planta"]==planta]["color"].tolist()
    if C["rojo"] in cols:      return C["rojo"]
    elif C["amarillo"] in cols: return C["amarillo"]
    return C["verde"]

sg_majes = semaforo_global("Majes")
sg_rep   = semaforo_global("Repartición")

# ── Actividades ejecutándose en FECHA_CORTE ──────────────────────────────────
def tareas_activas_hoy():
    sub = df_all[
        df_all["Comienzo"].notna() & df_all["Fin"].notna() &
        (df_all["Comienzo"] <= FECHA_CORTE) & (df_all["Fin"] >= FECHA_CORTE) &
        (df_all["Id"] >= 3)
    ].copy()
    rows = []
    for _, r in sub.iterrows():
        av = df_avance[(df_avance["planta"]==r["planta"]) &
                       (df_avance["macrofase"]==r["macrofase"])]
        pct_real = float(av["pct_real"].values[0]) if not av.empty else 0
        pct_plan = float(av["pct_plan"].values[0]) if not av.empty else 0
        col      = av["color"].values[0]           if not av.empty else C["celeste"]
        rows.append({"planta":r["planta"],"id":int(r["Id"]),"nombre":str(r["_nombre"])[:60],
                     "macrofase":r["macrofase"],"inicio":r["Comienzo"],"fin":r["Fin"],
                     "pct_plan":pct_plan,"pct_real":pct_real,"color":col})
    return sorted(rows, key=lambda x: (x["planta"],x["id"]))

# ── Actividades próximas 14 días desde FECHA_CORTE ───────────────────────────
def tareas_proximas():
    lim = FECHA_CORTE + timedelta(days=14)
    sub = df_all[
        df_all["Comienzo"].notna() &
        (df_all["Comienzo"] > FECHA_CORTE) & (df_all["Comienzo"] <= lim) &
        (df_all["Id"] >= 3)
    ].copy()
    rows = []
    for _, r in sub.iterrows():
        av = df_avance[(df_avance["planta"]==r["planta"]) &
                       (df_avance["macrofase"]==r["macrofase"])]
        col = av["color"].values[0] if not av.empty else C["celeste"]
        dias_para = (r["Comienzo"] - FECHA_CORTE).days
        rows.append({"planta":r["planta"],"id":int(r["Id"]),"nombre":str(r["_nombre"])[:60],
                     "macrofase":r["macrofase"],"inicio":r["Comienzo"],"fin":r["Fin"],
                     "dias_para":dias_para,"color":col})
    return sorted(rows, key=lambda x: x["dias_para"])

# ── Alertas automáticas (pct_real < pct_plan - 10%) ─────────────────────────
def build_alertas():
    alertas = []
    for _, r in df_avance.iterrows():
        if r["all_empty"]: continue   # sin dato manual, no hay alerta
        if r["pct_real"] < r["pct_plan"] - 10:
            desv = r["pct_real"] - r["pct_plan"]
            alertas.append({"planta":r["planta"],"macrofase":r["macrofase"],
                             "pct_real":r["pct_real"],"pct_plan":r["pct_plan"],
                             "desv":round(desv,1),"comentario":r["comentario"]})
    return alertas

# ── Hitos clave ──────────────────────────────────────────────────────────────
HITOS_CLAVE = [
    {"nombre":"✅ Izaje BESS 1 — Repartición",       "fecha":datetime(2026,3,26), "critico":False, "completado":True},
    {"nombre":"✅ Izaje BESS 2 — Repartición",       "fecha":datetime(2026,3,27), "critico":False, "completado":True},
    {"nombre":"✅ Izaje MV Station — Repartición",   "fecha":datetime(2026,3,28), "critico":False, "completado":True},
    {"nombre":"✅ Izaje BESS 1, 2 y MV — Majes",    "fecha":datetime(2026,3,30), "critico":False, "completado":True},
    {"nombre":"Desencofrado zanjas (en retraso)",    "fecha":datetime(2026,4,15), "critico":False},
    {"nombre":"Fin Puesta a Tierra (ambas plantas)", "fecha":datetime(2026,4,20), "critico":False},
    {"nombre":"🔴 Presentación COES — EN RIESGO",   "fecha":datetime(2026,4,20), "critico":True},
    {"nombre":"Fin Estudio COES",                    "fecha":datetime(2026,5,5),  "critico":False},
    {"nombre":"Fin Zanjas y Cableado",               "fecha":datetime(2026,5,10), "critico":False},
    {"nombre":"Aprobación COES",                     "fecha":datetime(2026,6,5),  "critico":True},
    {"nombre":"Puesta en marcha (obj.)",             "fecha":HITO_OBJETIVO,       "critico":True},
    {"nombre":"Puesta en marcha (plan)",             "fecha":HITO_PLAN,           "critico":False},
]

def build_hitos_table():
    rows = []
    for h in sorted(HITOS_CLAVE, key=lambda x: x["fecha"]):
        d = (h["fecha"] - FECHA_CORTE).days
        if h.get("completado"):         estado_h, cls = "Completado",  "completado"
        elif d < -30:                   estado_h, cls = "Completado",  "completado"
        elif d < 0:                     estado_h, cls = "Vencido",     "vencido"
        elif d <= 3:                    estado_h, cls = "HOY/Mañana",  "urgente"
        elif d <= 14:                   estado_h, cls = "Urgente",     "urgente"
        elif d <= 30:                   estado_h, cls = "Próximo",     "proximo"
        else:                           estado_h, cls = "Pendiente",   "pendiente"
        rows.append({"nombre":h["nombre"],"fecha":fmt_fecha(h["fecha"]),
                     "dias":d,"estado":estado_h,"cls":cls,
                     "critico":h.get("critico",False)})
    return rows

tareas_hoy    = tareas_activas_hoy()
tareas_prox   = tareas_proximas()
alertas       = build_alertas()
hitos_tabla   = build_hitos_table()

# ─────────────────────────────────────────────────────────────────────────────
# 3. FIGURAS PLOTLY — tema claro
# ─────────────────────────────────────────────────────────────────────────────
PLOT_LAYOUT = dict(
    paper_bgcolor=C["white"],
    plot_bgcolor="#f8fafc",
    font=dict(family="DM Sans,system-ui,sans-serif", color=C["ink"], size=12),
)

# ── Curva S ──────────────────────────────────────────────────────────────────
def build_curva_s_fig():
    fig = go.Figure()
    estilos = {
        "Majes":      {"plan":"#1a5fa8","real":"#0d9e5c"},
        "Repartición":{"plan":"#7c3aed","real":"#c97a0a"},
    }
    for planta in ["Majes","Repartición"]:
        sub = df_all[df_all["planta"]==planta].copy()
        sub = sub[sub["Comienzo"].notna() & sub["Fin"].notna() & (sub["Id"]>=3)]
        if sub.empty: continue
        weeks = pd.date_range(start=sub["Comienzo"].min(), end=sub["Fin"].max(), freq="W-MON")
        total = len(sub)
        plan  = [round(100*sub[sub["Fin"]<=w].shape[0]/total,1) for w in weeks]
        avmf  = df_avance[df_avance["planta"]==planta].set_index("id_tarea")["pct_real"].to_dict()
        real  = []
        for w in weeks:
            if w > FECHA_CORTE: real.append(None)
            else:
                cr = sum(len(sub[sub["Id"].between(mf["ids_min"],mf["ids_max"])])
                         * avmf.get(mf["id"],0)/100 for mf in MACROFASES)
                real.append(round(100*cr/total,1))
        e = estilos[planta]
        fig.add_trace(go.Scatter(x=weeks, y=plan, mode="lines",
            name=f"{planta} Plan", line=dict(color=e["plan"],width=2,dash="dot"),
            hovertemplate="%{y:.1f}%<extra>"+planta+" Plan</extra>"))
        fig.add_trace(go.Scatter(x=weeks, y=real, mode="lines+markers",
            name=f"{planta} Real", line=dict(color=e["real"],width=2.5),
            marker=dict(size=4), connectgaps=False,
            hovertemplate="%{y:.1f}%<extra>"+planta+" Real</extra>"))

    _corte_str = FECHA_CORTE.strftime("%Y-%m-%d")
    _corte_lbl = fmt_fecha(FECHA_CORTE)
    fig.add_shape(type="line", x0=_corte_str, x1=_corte_str, y0=0, y1=1,
                  yref="paper", line=dict(color=C["amarillo"], dash="dash", width=1.5))
    fig.add_annotation(x=_corte_str, y=1.02, yref="paper", text=f"Corte {_corte_lbl}",
                       showarrow=False, font=dict(color=C["amarillo"], size=10), xanchor="left")
    fig.update_layout(**PLOT_LAYOUT,
        xaxis=dict(title="", gridcolor=C["faint"], tickformat="%b %Y", showgrid=True),
        yaxis=dict(title="% Avance", gridcolor=C["faint"], range=[0,105], showgrid=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)", font_size=11),
        height=300, margin=dict(l=50, r=10, t=30, b=40))
    return fig

# ── SPI por macrofase ─────────────────────────────────────────────────────────
def build_spi_fig():
    fig = go.Figure()
    for planta in ["Majes","Repartición"]:
        sub = df_avance[df_avance["planta"]==planta].copy()
        cols = [C["verde"] if s>=0.95 else (C["amarillo"] if s>=0.80 else C["rojo"])
                for s in sub["spi"]]
        lbl = [f"{v:.2f}" for v in sub["spi"]]
        if planta == "Repartición":
            # Convertir hex a rgba con opacidad 0.55
            def hex2rgba(h, a=0.55):
                h=h.lstrip("#")
                return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{a})"
            cols = [hex2rgba(c) for c in cols]
        fig.add_trace(go.Bar(name=planta,
            x=sub["macrofase"].str.replace(" y "," &\n"),
            y=sub["spi"], text=lbl, textposition="outside",
            textfont=dict(size=10, color=C["ink"]),
            marker_color=cols, marker_line_width=0))
    fig.add_hline(y=1.0, line_color=C["verde"], line_dash="dash", line_width=1.5,
                  annotation_text="SPI 1.0", annotation_font_color=C["verde"])
    fig.add_hline(y=0.8, line_color=C["rojo"], line_dash="dot",  line_width=1,
                  annotation_text="Umbral 0.80", annotation_font_color=C["rojo"])
    fig.update_layout(**PLOT_LAYOUT, barmode="group",
        xaxis=dict(tickfont=dict(size=10), gridcolor=C["faint"]),
        yaxis=dict(title="SPI", range=[0,1.6], gridcolor=C["faint"], showgrid=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1,
                    font_size=11, bgcolor="rgba(0,0,0,0)"),
        height=300, margin=dict(l=50, r=10, t=30, b=80))
    return fig

# ── Gantt completo (macrofases agrupadas, tema claro) ─────────────────────────
def build_gantt_fig(planta):
    """Gantt con 1 barra por macrofase, coloreada por semáforo."""
    fig = go.Figure()
    y_labels, colors_list = [], []
    for mf in reversed(MACROFASES):
        tasks = df_all[(df_all["planta"]==planta) &
                       (df_all["Id"].between(mf["ids_min"],mf["ids_max"])) &
                       df_all["Comienzo"].notna() & df_all["Fin"].notna()]
        if tasks.empty: continue
        start  = tasks["Comienzo"].min()
        finish = tasks["Fin"].max()
        av = df_avance[(df_avance["planta"]==planta) & (df_avance["id_tarea"]==mf["id"])]
        color = av["color"].values[0]     if not av.empty else C["celeste"]
        pct   = av["pct_real"].values[0]  if not av.empty else 0
        plan  = av["pct_plan"].values[0]  if not av.empty else 0
        estado= av["estado"].values[0]    if not av.empty else "—"
        y_labels.append(mf["nombre"])
        colors_list.append(color)
        dur_ms    = (pd.Timestamp(finish) - pd.Timestamp(start)).total_seconds()*1000
        start_iso = pd.Timestamp(start).strftime("%Y-%m-%d")
        fig.add_trace(go.Bar(
            name=mf["nombre"], x=[dur_ms], y=[mf["nombre"]],
            base=[start_iso], orientation="h",
            marker_color=color, marker_line_color="rgba(0,0,0,0.1)",
            marker_line_width=1,
            text=f"  {pct:.0f}%", textposition="inside",
            insidetextanchor="start",
            textfont=dict(size=10, color=C["white"]),
            showlegend=False,
            hovertemplate=(f"<b>{mf['nombre']}</b><br>"
                           f"Inicio: {fmt_fecha(start)}<br>Fin: {fmt_fecha(finish)}<br>"
                           f"Planeado: {plan:.0f}% | Real: {pct:.0f}%<br>"
                           f"Estado: {estado}<extra></extra>")))
    # Líneas de referencia
    for date_str, col, label in [
        (FECHA_CORTE.strftime("%Y-%m-%d"), C["amarillo"], fmt_fecha(FECHA_CORTE)),
        ("2026-05-30", C["verde"],    "30/May obj."),
        ("2026-06-24", C["rojo"],     "24/Jun plan"),
    ]:
        fig.add_shape(type="line", x0=date_str, x1=date_str, y0=0, y1=1,
                      yref="paper", line=dict(color=col, dash="dash", width=1.5))
        fig.add_annotation(x=date_str, y=1.02, yref="paper", text=label,
                           showarrow=False, font=dict(color=col, size=9), xanchor="left")
    fig.update_layout(**PLOT_LAYOUT,
        barmode="overlay",
        xaxis=dict(type="date", tickformat="%b %Y", gridcolor=C["faint"],
                   showgrid=True, title=""),
        yaxis=dict(title="", gridcolor=C["faint"], autorange=True,
                   tickfont=dict(size=10)),
        height=320, margin=dict(l=180, r=20, t=30, b=40),
        title=dict(text=f"Gantt — {planta}", font=dict(size=13, color=C["ink2"]), x=0))
    return fig

# ── Gantt detallado (Tab 2 — 154 tareas) ─────────────────────────────────────
def build_gantt_detalle(planta):
    """Gantt con 1 fila por tarea individual, coloreada por semáforo de su macrofase."""
    sub = df_all[(df_all["planta"]==planta) &
                 df_all["Comienzo"].notna() & df_all["Fin"].notna() &
                 (df_all["Id"]>=3)].copy()
    sub = sub.sort_values("Id")

    rows = []
    for _, r in sub.iterrows():
        av = df_avance[(df_avance["planta"]==planta) & (df_avance["macrofase"]==r["macrofase"])]
        color  = av["color"].values[0]    if not av.empty else C["celeste"]
        pct_r  = av["pct_real"].values[0] if not av.empty else 0
        pct_p  = av["pct_plan"].values[0] if not av.empty else 0
        nombre_corto = str(r["_nombre"])[:45]
        rows.append({"y":nombre_corto,"start":r["Comienzo"],"fin":r["Fin"],
                     "color":color,"pct_r":pct_r,"pct_p":pct_p,
                     "macrofase":r["macrofase"],"id":int(r["Id"])})
    rows.reverse()  # para que ID 3 quede arriba en Plotly autorange

    fig = go.Figure()
    added_mf = set()
    for row in rows:
        show_leg = row["macrofase"] not in added_mf
        added_mf.add(row["macrofase"])
        mf_color = next((mf["col_p"] for mf in MACROFASES if mf["nombre"]==row["macrofase"]),
                        C["celeste"])
        dur_ms    = (pd.Timestamp(row["fin"]) - pd.Timestamp(row["start"])).total_seconds()*1000
        start_iso = pd.Timestamp(row["start"]).strftime("%Y-%m-%d")
        fig.add_trace(go.Bar(
            name=row["macrofase"], x=[dur_ms], y=[f"#{row['id']} {row['y']}"],
            base=[start_iso], orientation="h",
            marker_color=row["color"], marker_line_width=0,
            showlegend=show_leg, legendgroup=row["macrofase"],
            text=f" {row['pct_r']:.0f}%",
            textposition="inside", insidetextanchor="start",
            textfont=dict(size=8, color=C["white"]),
            hovertemplate=(f"<b>#{row['id']} {row['y']}</b><br>"
                           f"{row['macrofase']}<br>"
                           f"Inicio: {fmt_fecha(row['start'])}<br>"
                           f"Fin: {fmt_fecha(row['fin'])}<br>"
                           f"Real: {row['pct_r']:.0f}% | Plan: {row['pct_p']:.0f}%"
                           "<extra></extra>")))

    for date_str, col, label in [
        (FECHA_CORTE.strftime("%Y-%m-%d"), C["amarillo"], fmt_fecha(FECHA_CORTE)),
        ("2026-05-30", C["verde"],  "30/May"),
        ("2026-06-24", C["rojo"],   "24/Jun"),
    ]:
        fig.add_shape(type="line", x0=date_str, x1=date_str, y0=0, y1=1,
                      yref="paper", line=dict(color=col, dash="dash", width=1))
        fig.add_annotation(x=date_str, y=1.02, yref="paper", text=label,
                           showarrow=False, font=dict(color=col, size=8), xanchor="left")

    n_tasks = len(rows)
    height  = max(420, min(n_tasks * 22 + 60, 3000))
    fig.update_layout(**PLOT_LAYOUT,
        barmode="overlay",
        xaxis=dict(type="date", tickformat="%b %Y", gridcolor=C["faint"],
                   showgrid=True, title="", side="top"),
        yaxis=dict(title="", tickfont=dict(size=8), autorange=True, showgrid=False),
        legend=dict(orientation="v", x=1.01, y=1, font_size=10,
                    bgcolor="rgba(255,255,255,0.9)",
                    bordercolor=C["faint"], borderwidth=1),
        height=height, margin=dict(l=300, r=160, t=50, b=20),
        title=dict(text=f"Gantt Completo — {planta} ({n_tasks} tareas)",
                   font=dict(size=13, color=C["ink2"]), x=0))
    return fig

print("🏗️  Construyendo figuras...")
fig_curva_s     = build_curva_s_fig()
fig_spi         = build_spi_fig()
fig_gantt_m     = build_gantt_fig("Majes")
fig_gantt_r     = build_gantt_fig("Repartición")
fig_gantt_det_m = build_gantt_detalle("Majes")
fig_gantt_det_r = build_gantt_detalle("Repartición")

curva_s_json     = fig_curva_s.to_json()
spi_json         = fig_spi.to_json()
gantt_m_json     = fig_gantt_m.to_json()
gantt_r_json     = fig_gantt_r.to_json()
gantt_det_m_json = fig_gantt_det_m.to_json()
gantt_det_r_json = fig_gantt_det_r.to_json()

# ─────────────────────────────────────────────────────────────────────────────
# 4. HELPERS HTML
# ─────────────────────────────────────────────────────────────────────────────

def sem_color_css(col):
    m = {C["verde"]:"g", C["amarillo"]:"a", C["rojo"]:"r"}
    return m.get(col,"g")

def sem_estado_label(col):
    m = {C["verde"]:"En plan", C["amarillo"]:"Atención", C["rojo"]:"En riesgo"}
    return m.get(col,"—")

def pill_estado(estado):
    m = {"Completado":"pd","En curso":"pa","En riesgo":"pl","No iniciado":"pp","Atención":"pw"}
    cls = m.get(estado,"pp")
    return f'<span class="pill {cls}">{estado}</span>'

def pill_planta(planta):
    cls = "pla-m" if planta=="Majes" else "pla-r"
    return f'<span class="ppla {cls}">{planta}</span>'

# ── Semáforos por macrofase (Tab 1) ──────────────────────────────────────────
def render_semaforos(planta):
    html = ""
    for mf in MACROFASES:
        av = df_avance[(df_avance["planta"]==planta) & (df_avance["id_tarea"]==mf["id"])]
        if av.empty: continue
        col      = av["color"].values[0]
        pct_real = float(av["pct_real"].values[0])
        pct_plan = float(av["pct_plan"].values[0])
        is_empty = bool(av["all_empty"].values[0])
        estado   = av["estado"].values[0]
        com      = av["comentario"].values[0]
        sc       = sem_color_css(col)
        desv_html = ""
        if not is_empty:
            desv = pct_real - pct_plan
            sgn  = "+" if desv >= 0 else ""
            desv_html = f'<span class="desv desv-{sc}">{sgn}{desv:.0f} pp</span>'
        pct_bar  = min(pct_real, 100)
        bf_cls   = "bf-g" if col==C["verde"] else ("bf-a" if col==C["amarillo"] else "bf-r")
        html += f"""
        <div class="mf-row">
          <div class="mf-dot sd{sc}"></div>
          <div class="mf-body">
            <div class="mf-top">
              <span class="mf-nm">{mf['nombre']}</span>
              {pill_estado(estado)}
              {desv_html}
            </div>
            <div class="bar" style="height:5px;margin-top:5px;">
              <div class="bf {bf_cls}" style="width:{pct_bar:.0f}%;height:5px;"></div>
            </div>
            <div class="mf-com">{com}</div>
          </div>
          <div class="mf-pct-col">
            <div class="mf-pct" style="color:{col};">{pct_real:.0f}%</div>
            <div class="mf-plan">Plan {pct_plan:.0f}%</div>
          </div>
        </div>"""
    return html

# ── Tabla de hitos ────────────────────────────────────────────────────────────
def render_hitos():
    cls_map = {"completado":"pd","vencido":"pl","urgente":"pl","proximo":"pw","pendiente":"pp"}
    html = ""
    for h in hitos_tabla:
        cc     = cls_map[h["cls"]]
        d      = h["dias"]
        d_txt  = "Completado" if d<-30 else (f"{abs(d)}d pasados" if d<0 else f"en {d}d")
        crit   = "🔴 " if h["critico"] else ""
        html += f"""
        <tr>
          <td><span class="crit-ico">{crit}</span>{h['nombre']}</td>
          <td class="td-c">{h['fecha']}</td>
          <td class="td-c"><span class="pill {cc}">{d_txt}</span></td>
        </tr>"""
    return html

# ── Alertas del período (novedades manuales + automáticas SPI) ───────────────
def render_alertas():
    html = ""
    # — Novedades manuales del período —
    tipo_cfg = {
        "logro":    ("pd",  "✅"),
        "info":     ("pa",  "📅"),
        "atencion": ("pw",  "⚠️"),
        "critico":  ("pl",  "🔴"),
    }
    for n in NOVEDADES:
        pill_cls, ico = tipo_cfg.get(n["tipo"], ("pp","ℹ️"))
        al_cls = "al-r" if n["tipo"]=="critico" else ("al-a" if n["tipo"]=="atencion" else "al-b")
        html += f"""
        <div class="al {al_cls}">
          <div class="al-ico">{ico}</div>
          <div>
            <div class="al-bo">{n['texto']}</div>
          </div>
        </div>"""
    # — Alertas automáticas SPI —
    if alertas:
        html += '<div style="font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:10px 0 6px;">ALERTAS SPI AUTOMÁTICAS</div>'
        for a in alertas:
            html += f"""
            <div class="al al-r">
              <div class="al-ico">⚠️</div>
              <div>
                <div class="al-ti">{pill_planta(a['planta'])} {a['macrofase']}</div>
                <div class="al-bo">Real {a['pct_real']:.0f}% vs Plan {a['pct_plan']:.0f}%
                  — Desviación <b>{a['desv']:.0f} pp</b></div>
                <div class="al-bo">{a['comentario']}</div>
              </div>
            </div>"""
    if not html:
        html = '<div class="no-alert">✅ Sin alertas activas — todas las macrofases van según plan</div>'
    return html

# ── Actividades de hoy ────────────────────────────────────────────────────────
def render_tareas_hoy():
    if not tareas_hoy:
        return '<div class="no-alert">Sin actividades activas hoy</div>'
    rows = ""
    for t in tareas_hoy:
        sc = sem_color_css(t["color"])
        rows += f"""
        <tr>
          <td>{pill_planta(t['planta'])}</td>
          <td class="td-id">{t['id']}</td>
          <td>{t['nombre']}<br><small class="td-mf">{t['macrofase']}</small></td>
          <td class="td-c">{fmt_fecha(t['inicio'])}</td>
          <td class="td-c">{fmt_fecha(t['fin'])}</td>
          <td>
            <div class="bar" style="height:6px;">
              <div class="bf bf-plan" style="width:{min(t['pct_plan'],100):.0f}%;height:6px;opacity:.35;position:absolute;"></div>
              <div class="bf bf-sc{sc}" style="width:{min(t['pct_real'],100):.0f}%;height:6px;"></div>
            </div>
            <div style="font-size:9px;color:var(--muted);margin-top:2px;">{t['pct_real']:.0f}% / {t['pct_plan']:.0f}%</div>
          </td>
        </tr>"""
    return rows

def render_tareas_prox():
    if not tareas_prox:
        return '<div class="no-alert">Sin actividades que inicien en los próximos 14 días</div>'
    rows = ""
    for t in tareas_prox:
        urg = "⚡" if t["dias_para"] <= 3 else ""
        rows += f"""
        <tr>
          <td>{pill_planta(t['planta'])}</td>
          <td class="td-id">{t['id']}</td>
          <td>{t['nombre']}<br><small class="td-mf">{t['macrofase']}</small></td>
          <td class="td-c" style="font-weight:700;">{urg}{fmt_fecha(t['inicio'])}</td>
          <td class="td-c">{fmt_fecha(t['fin'])}</td>
          <td class="td-c" style="font-weight:700;color:var(--blue);">en {t['dias_para']}d</td>
        </tr>"""
    return rows

# ── Simulador COES ────────────────────────────────────────────────────────────
def coes_result(fecha_pres_str, dias_resp):
    try:    fp = datetime.strptime(fecha_pres_str, "%Y-%m-%d")
    except: fp = datetime(2026, 4, 20)
    fin_resp = fp + timedelta(days=int(dias_resp))
    pem      = fin_resp + timedelta(days=BUFFER_COES)
    delta    = (pem - HITO_OBJETIVO).days
    return pem.strftime("%d/%m/%Y"), delta

def delta_badge(d):
    if d <= 0:
        return f'<span class="pill pd">✅ {abs(d)}d antes del objetivo</span>'
    return f'<span class="pill pl">⚠ {d}d después del objetivo</span>'

pb_fecha, pb_delta = coes_result("2026-04-20", 45)
p1_fecha, p1_delta = coes_result("2026-04-07", 45)
p2_fecha, p2_delta = coes_result("2026-04-20", 20)
pc_fecha, pc_delta = coes_result("2026-04-07", 20)

# ── Banner de alerta ──────────────────────────────────────────────────────────
banner_cls = "banner-r" if dias_obj <= 45 else "banner-a"
banner_ico = "🔴" if dias_obj <= 45 else "🟡"

# ─────────────────────────────────────────────────────────────────────────────
# 5. GENERAR HTML
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# DIAGNÓSTICO — imprime antes de generar HTML
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "─"*60)
print(f"  DIAGNÓSTICO — Generado el {GENERADO_EL.strftime('%d/%m/%Y %H:%M')}")
print("─"*60)
print(f"  FECHA_CORTE (datos)     : {FECHA_CORTE.strftime('%d/%m/%Y')}  ← parámetro fijo")
print(f"  GENERADO_EL (hoy real)  : {GENERADO_EL.strftime('%d/%m/%Y')}")
print()
print(f"  {'Macrofase':<32} {'Plan M':>7} {'Real M':>7} {'Plan R':>7} {'Real R':>7}")
print(f"  {'─'*32} {'─'*7} {'─'*7} {'─'*7} {'─'*7}")
for mf in MACROFASES:
    row_m = df_avance[(df_avance["planta"]=="Majes")       & (df_avance["id_tarea"]==mf["id"])]
    row_r = df_avance[(df_avance["planta"]=="Repartición") & (df_avance["id_tarea"]==mf["id"])]
    pm = f"{float(row_m['pct_plan'].values[0]):.1f}%" if not row_m.empty else "—"
    rm = f"{float(row_m['pct_real'].values[0]):.1f}%" if not row_m.empty else "—"
    pr = f"{float(row_r['pct_plan'].values[0]):.1f}%" if not row_r.empty else "—"
    rr = f"{float(row_r['pct_real'].values[0]):.1f}%" if not row_r.empty else "—"
    print(f"  {mf['nombre']:<32} {pm:>7} {rm:>7} {pr:>7} {rr:>7}")
print()
print(f"  KPI GLOBAL Majes        : {kpi_m:.1f}%  (promedio pct_real 7 macrofases)")
print(f"  KPI GLOBAL Repartición  : {kpi_r:.1f}%  (promedio pct_real 7 macrofases)")
print(f"  SPI promedio global     : {kpi_spi:.2f}")
print(f"  pct_real = pct_plan_calc cuando pct_completado vacío en xlsx       ✓")
print(f"  pct_plan_calc = pct_planeado_dinamico(inicio, fin, FECHA_CORTE)  ✓")
print("─"*60 + "\n")

print("🎨 Generando HTML...")

HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BESS · Dashboard de Control · Majes &amp; Repartición</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
:root{{
  --bg:#f0f4f8;--white:#fff;--ink:{C["ink"]};--ink2:{C["ink2"]};
  --muted:{C["muted"]};--faint:{C["faint"]};--faint2:#bfcad6;
  --green:{C["verde"]};--greenl:{C["verde_l"]};
  --amber:{C["amarillo"]};--amberl:{C["amarillo_l"]};
  --red:{C["rojo"]};--redl:{C["rojo_l"]};
  --blue:{C["celeste"]};--bluel:{C["celeste_l"]};
  --teal:{C["teal"]};--azul:{C["azul"]};
  --head:'Playfair Display',Georgia,serif;
  --body:'DM Sans',system-ui,sans-serif;
}}
*,*::before,*::after{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:var(--bg);color:var(--ink);font-family:var(--body);font-size:14px;line-height:1.5;}}

/* ── HEADER ── */
.hdr{{background:var(--azul);color:#fff;height:58px;padding:0 28px;
      display:flex;align-items:center;justify-content:space-between;
      position:sticky;top:0;z-index:200;box-shadow:0 2px 16px rgba(0,0,0,.35);}}
.brand{{display:flex;align-items:center;gap:12px;}}
.brand-hex{{width:34px;height:34px;flex-shrink:0;
  background:linear-gradient(135deg,#38bdf8,#34d399);
  clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%);}}
.brand-name{{font-family:var(--head);font-size:18px;letter-spacing:-.01em;color:#fff;}}
.brand-sub{{font-size:9px;color:#8899aa;letter-spacing:.14em;text-transform:uppercase;margin-top:-1px;}}
.hdr-r{{display:flex;align-items:center;gap:18px;}}
.hdr-stat{{text-align:center;}}
.hdr-stat-v{{font-size:20px;font-weight:800;color:#fff;line-height:1;}}
.hdr-stat-l{{font-size:9px;color:#8899aa;letter-spacing:.1em;text-transform:uppercase;}}
.live{{display:flex;align-items:center;gap:5px;font-size:10px;color:#8899aa;}}
.dot{{width:6px;height:6px;border-radius:50%;background:#34d399;animation:blink 2s infinite;}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.2}}}}

/* ── TABS ── */
.tabs-bar{{background:var(--white);border-bottom:2px solid var(--faint);
           display:flex;align-items:stretch;padding:0 28px;
           position:sticky;top:58px;z-index:199;
           box-shadow:0 1px 6px rgba(0,0,0,.05);}}
.tab{{padding:0 22px;height:44px;display:flex;align-items:center;gap:7px;
      font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
      color:var(--muted);cursor:pointer;border-bottom:3px solid transparent;
      margin-bottom:-2px;transition:.18s;user-select:none;}}
.tab:hover{{color:var(--ink);}}
.tab.on{{color:var(--blue);border-color:var(--blue);}}
.tab-ico{{font-size:14px;}}

/* ── BANNER ── */
.banner{{display:flex;align-items:center;gap:12px;padding:11px 18px;
         margin-bottom:18px;border:1.5px solid;}}
.banner-r{{background:var(--redl);border-color:var(--red);}}
.banner-a{{background:var(--amberl);border-color:var(--amber);}}
.banner-ico{{font-size:20px;flex-shrink:0;}}
.banner-title{{font-size:13px;font-weight:700;color:var(--red);}}
.banner-a .banner-title{{color:var(--amber);}}
.banner-body{{font-size:12px;color:var(--ink);margin-top:1px;}}

/* ── PAGE ── */
.page{{padding:22px 28px;max-width:1440px;margin:0 auto;}}
.view{{display:none;}}.view.on{{display:block;}}

/* ── HERO KPIs ── */
.hero{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px;}}
.kpi{{background:var(--white);padding:20px 22px;
      box-shadow:0 1px 3px rgba(0,0,0,.06),0 4px 14px rgba(0,0,0,.05);
      position:relative;overflow:hidden;}}
.kpi::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:3px;background:var(--kc,var(--blue));}}
.kpi-l{{font-size:9px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:8px;}}
.kpi-v{{font-family:var(--head);font-size:38px;line-height:1;color:var(--kc,var(--ink));}}
.kpi-s{{font-size:11px;color:var(--muted);margin-top:6px;}}

/* ── CARDS ── */
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;}}
.g3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:16px;}}
.gcol{{display:flex;flex-direction:column;gap:16px;}}
.card{{background:var(--white);box-shadow:0 1px 3px rgba(0,0,0,.06),0 4px 14px rgba(0,0,0,.05);overflow:hidden;margin-bottom:16px;}}
.card:last-child{{margin-bottom:0;}}
.card-h{{padding:11px 18px;border-bottom:1px solid var(--faint);
         display:flex;align-items:center;justify-content:space-between;}}
.card-t{{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}}
.card-b{{padding:16px 18px;}}
.card-b.np{{padding:0;}}

/* ── SEMÁFORO MACROFASES ── */
.mf-row{{display:flex;align-items:flex-start;gap:12px;padding:10px 0;
         border-bottom:1px solid var(--faint);}}
.mf-row:last-child{{border-bottom:none;}}
.mf-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0;margin-top:4px;}}
.sdg{{background:var(--green);box-shadow:0 0 6px var(--green);}}
.sda{{background:var(--amber);box-shadow:0 0 6px var(--amber);}}
.sdr{{background:var(--red);box-shadow:0 0 6px var(--red);}}
.mf-body{{flex:1;}}
.mf-top{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}}
.mf-nm{{font-size:12px;font-weight:600;color:var(--ink);}}
.mf-com{{font-size:10px;color:var(--muted);margin-top:4px;}}
.mf-pct-col{{text-align:right;min-width:58px;}}
.mf-pct{{font-family:var(--head);font-size:20px;line-height:1;}}
.mf-plan{{font-size:9px;color:var(--muted);margin-top:2px;}}
.desv{{font-size:9px;font-weight:700;padding:1px 5px;border-radius:2px;}}
.desv-g{{background:var(--greenl);color:var(--green);}}
.desv-a{{background:var(--amberl);color:var(--amber);}}
.desv-r{{background:var(--redl);color:var(--red);}}

/* ── PILLS ── */
.pill{{display:inline-flex;padding:2px 7px;font-size:9px;font-weight:700;
       letter-spacing:.05em;text-transform:uppercase;}}
.pd{{background:var(--greenl);color:var(--green);}}
.pa{{background:var(--bluel);color:var(--blue);}}
.pw{{background:var(--amberl);color:var(--amber);}}
.pl{{background:var(--redl);color:var(--red);}}
.pp{{background:var(--faint);color:var(--muted);}}
.ppla{{display:inline-flex;padding:1px 6px;font-size:9px;font-weight:700;letter-spacing:.05em;}}
.pla-m{{background:#dbeafe;color:#1d4ed8;}}
.pla-r{{background:#f3e8ff;color:#6b21a8;}}

/* ── TABLA HITOS ── */
.tbl-w{{overflow-x:auto;}}
table.gt{{width:100%;border-collapse:collapse;}}
table.gt th{{font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
             color:var(--muted);padding:7px 10px;text-align:left;
             border-bottom:2px solid var(--faint);background:var(--bg);
             position:sticky;top:0;}}
table.gt td{{padding:6px 10px;border-bottom:1px solid var(--faint);
             vertical-align:middle;font-size:12px;}}
table.gt tr:hover td{{background:#f6f9fc;}}
.td-c{{text-align:center;}}
.td-id{{text-align:center;font-size:10px;color:var(--muted);width:36px;}}
.td-mf{{font-size:9px;color:var(--muted);font-weight:400;display:block;margin-top:1px;}}
.crit-ico{{font-size:10px;}}

/* ── ALERTAS ── */
.al{{display:flex;gap:11px;padding:11px 14px;border-left:3px solid;margin-bottom:6px;}}
.al:last-child{{margin-bottom:0;}}
.al-r{{border-color:var(--red);background:var(--redl);}}
.al-a{{border-color:var(--amber);background:var(--amberl);}}
.al-ico{{font-size:15px;flex-shrink:0;line-height:1.4;}}
.al-ti{{font-size:12px;font-weight:700;margin-bottom:3px;}}
.al-bo{{font-size:11px;color:var(--muted);line-height:1.45;}}
.no-alert{{font-size:12px;color:var(--green);padding:10px 4px;}}

/* ── BARRAS PROGRESS ── */
.bar{{background:var(--faint);overflow:hidden;position:relative;}}
.bf{{height:100%;transition:width .5s cubic-bezier(.4,0,.2,1);}}
.bf-g{{background:var(--green);}}.bf-a{{background:var(--amber);}}.bf-r{{background:var(--red);}}
.bf-plan{{background:var(--blue);}}
.bf-scg{{background:var(--green);}}.bf-sca{{background:var(--amber);}}.bf-scr{{background:var(--red);}}

/* ── COES (tab 3) ── */
.coes-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;}}
.coes-base{{background:var(--white);padding:18px 22px;
            box-shadow:0 1px 3px rgba(0,0,0,.06),0 4px 14px rgba(0,0,0,.05);
            border-left:4px solid var(--red);}}
.coes-alt{{background:var(--white);padding:18px 22px;
           box-shadow:0 1px 3px rgba(0,0,0,.06),0 4px 14px rgba(0,0,0,.05);
           border-left:4px solid var(--teal);}}
.coes-label{{font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
             color:var(--muted);margin-bottom:6px;}}
.coes-date{{font-family:var(--head);font-size:26px;color:var(--ink);line-height:1;}}
.coes-steps{{display:flex;align-items:center;gap:0;margin:14px 0;flex-wrap:wrap;}}
.coes-node{{background:var(--azul);color:#fff;padding:7px 12px;font-size:11px;font-weight:600;
            min-width:110px;text-align:center;}}
.coes-arrow{{color:var(--muted);font-size:18px;padding:0 4px;}}
.sim-row{{display:flex;align-items:center;gap:12px;margin-bottom:14px;}}
.sim-lbl{{font-size:11px;font-weight:600;color:var(--ink2);min-width:180px;}}
.sim-slider{{flex:1;accent-color:var(--blue);}}
.sim-val{{font-size:12px;font-weight:700;color:var(--blue);min-width:80px;text-align:right;}}
.sim-result{{background:var(--bluel);border:1px solid var(--blue);
             padding:14px 18px;margin-top:8px;}}
.sim-res-date{{font-family:var(--head);font-size:28px;color:var(--blue);}}
.sim-res-delta{{font-size:13px;margin-top:6px;}}

/* ── SECTION TITLE ── */
.sec-title{{font-family:var(--head);font-size:16px;color:var(--ink2);
            margin-bottom:12px;margin-top:4px;padding-bottom:6px;
            border-bottom:2px solid var(--faint);}}

/* ── BADGE GANTT PLANTA ── */
.gantt-tabs{{display:flex;gap:8px;margin-bottom:12px;}}
.gtab{{padding:6px 16px;font-size:11px;font-weight:700;cursor:pointer;
       border:1.5px solid var(--faint2);background:var(--bg);color:var(--muted);
       transition:.15s;letter-spacing:.05em;}}
.gtab.on{{background:var(--blue);color:#fff;border-color:var(--blue);}}
.gpanel{{display:none;}}.gpanel.on{{display:block;}}
</style>
</head>
<body>

<!-- ═══ HEADER ═══ -->
<header class="hdr">
  <div class="brand">
    <div class="brand-hex"></div>
    <div>
      <div class="brand-name">BESS · Control de Proyectos</div>
      <div class="brand-sub">Majes &amp; Repartición — Arequipa, Perú</div>
    </div>
  </div>
  <div class="hdr-r">
    <div class="hdr-stat">
      <div class="hdr-stat-v" style="color:#34d399;">{kpi_m:.0f}%</div>
      <div class="hdr-stat-l">Avance Majes</div>
    </div>
    <div class="hdr-stat">
      <div class="hdr-stat-v" style="color:#fbbf24;">{kpi_r:.0f}%</div>
      <div class="hdr-stat-l">Avance Repartición</div>
    </div>
    <div class="hdr-stat">
      <div class="hdr-stat-v" style="color:{'#c8263a' if dias_obj<=45 else '#f39c12'};">{dias_obj}d</div>
      <div class="hdr-stat-l">Al objetivo</div>
    </div>
    <div class="live">
      <div class="dot"></div>
      <span>Corte {FECHA_CORTE.strftime('%d/%m/%Y')}</span>
      <span style="font-size:9px;color:#8899aa;margin-left:8px;">gen. {GENERADO_EL.strftime('%d/%m/%Y')}</span>
    </div>
  </div>
</header>

<!-- ═══ TABS ═══ -->
<div class="tabs-bar">
  <div class="tab on" onclick="showTab(0)" id="tab0">
    <span class="tab-ico">📊</span> Vista Ejecutiva
  </div>
  <div class="tab" onclick="showTab(1)" id="tab1">
    <span class="tab-ico">🔧</span> Detalle Técnico
  </div>
  <div class="tab" onclick="showTab(2)" id="tab2">
    <span class="tab-ico">⚡</span> Ruta Crítica COES
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════
     TAB 0 — VISTA EJECUTIVA
════════════════════════════════════════════════════════════ -->
<div class="view on" id="view0">
<div class="page">

  <!-- Banner alerta -->
  <div class="banner {banner_cls}">
    <div class="banner-ico">{banner_ico}</div>
    <div>
      <div class="banner-title">OBJETIVO INTERNO: Puesta en marcha 30/05/26</div>
      <div class="banner-body">
        Quedan <b>{dias_obj} días</b> al objetivo · Plan original 24/06/26 (brecha de {brecha} días)
        · Corte de información: {FECHA_CORTE.strftime('%d/%m/%Y')} · Generado: {GENERADO_EL.strftime('%d/%m/%Y')}
      </div>
    </div>
  </div>

  <!-- KPIs -->
  <div class="hero">
    <div class="kpi" style="--kc:{C['celeste']};">
      <div class="kpi-l">Avance Real — Majes</div>
      <div class="kpi-v">{kpi_m:.0f}%</div>
      <div class="kpi-s">Promedio de 7 macrofases</div>
    </div>
    <div class="kpi" style="--kc:{C['teal']};">
      <div class="kpi-l">Avance Real — Repartición</div>
      <div class="kpi-v">{kpi_r:.0f}%</div>
      <div class="kpi-s">Promedio de 7 macrofases</div>
    </div>
    <div class="kpi" style="--kc:{'#c8263a' if dias_obj<=45 else '#c97a0a'};">
      <div class="kpi-l">Días al objetivo 30/May</div>
      <div class="kpi-v">{dias_obj}</div>
      <div class="kpi-s">Plan 24/Jun — brecha {brecha}d</div>
    </div>
    <div class="kpi" style="--kc:{'#0d9e5c' if kpi_spi>=0.95 else ('#c97a0a' if kpi_spi>=0.80 else '#c8263a')};">
      <div class="kpi-l">SPI Promedio (ambas plantas)</div>
      <div class="kpi-v">{kpi_spi:.2f}</div>
      <div class="kpi-s">{'✅ En plan' if kpi_spi>=0.95 else ('⚠ Atención' if kpi_spi>=0.80 else '🔴 Retraso')}</div>
    </div>
  </div>

  <!-- Semáforos + Hitos -->
  <div class="g2">
    <!-- Semáforos -->
    <div>
      <div class="sec-title">Estado por Macrofase</div>
      <div class="g2" style="margin-bottom:0;">
        <div class="card">
          <div class="card-h">
            <div class="card-t">🔵 Majes</div>
            <span class="pill {'pd' if sg_majes==C['verde'] else ('pw' if sg_majes==C['amarillo'] else 'pl')}">{sem_estado_label(sg_majes)}</span>
          </div>
          <div class="card-b">{render_semaforos('Majes')}</div>
        </div>
        <div class="card">
          <div class="card-h">
            <div class="card-t">🟣 Repartición</div>
            <span class="pill {'pd' if sg_rep==C['verde'] else ('pw' if sg_rep==C['amarillo'] else 'pl')}">{sem_estado_label(sg_rep)}</span>
          </div>
          <div class="card-b">{render_semaforos('Repartición')}</div>
        </div>
      </div>
    </div>

    <!-- Columna derecha: hitos + alertas -->
    <div class="gcol">
      <div class="card">
        <div class="card-h"><div class="card-t">🏁 Hitos Clave del Proyecto</div></div>
        <div class="card-b np">
          <div class="tbl-w">
            <table class="gt">
              <thead><tr>
                <th>Hito</th><th class="td-c">Fecha</th><th class="td-c">Estado</th>
              </tr></thead>
              <tbody>{render_hitos()}</tbody>
            </table>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-h"><div class="card-t">🚨 Alertas del Período — Corte {FECHA_CORTE.strftime('%d/%m/%Y')}</div>
          <span class="pill pa">{len(NOVEDADES)} novedad{'es' if len(NOVEDADES)!=1 else ''}</span>
          {'<span class="pill pl" style="margin-left:4px;">'+str(len(alertas))+' alerta SPI</span>' if alertas else ''}
        </div>
        <div class="card-b">{render_alertas()}</div>
      </div>
    </div>
  </div>

  <!-- Curva S -->
  <div class="card">
    <div class="card-h"><div class="card-t">📈 Curva S — Avance Planeado vs Real (ambas plantas)</div></div>
    <div class="card-b np">
      <div id="fig-curva-s" style="width:100%;"></div>
    </div>
  </div>

</div><!-- /page -->
</div><!-- /view0 -->

<!-- ═══════════════════════════════════════════════════════════
     TAB 1 — DETALLE TÉCNICO
════════════════════════════════════════════════════════════ -->
<div class="view" id="view1">
<div class="page">

  <!-- Actividades ejecutándose hoy -->
  <div class="card">
    <div class="card-h">
      <div class="card-t">▶ Actividades en Ejecución al {FECHA_CORTE.strftime('%d/%m/%Y')}</div>
      <span class="pill pa">{len(tareas_hoy)} activas</span>
    </div>
    <div class="card-b np">
      {'<div class="card-b">'+render_tareas_hoy()+'</div>' if not tareas_hoy else
       '''<div class="tbl-w" style="max-height:260px;">
         <table class="gt"><thead><tr>
           <th>Planta</th><th>ID</th><th>Nombre</th>
           <th class="td-c">Inicio</th><th class="td-c">Fin</th>
           <th style="min-width:140px;">Avance (real/plan)</th>
         </tr></thead><tbody>'''+render_tareas_hoy()+'''</tbody></table>
       </div>'''}
    </div>
  </div>

  <!-- Actividades próximas 14 días -->
  <div class="card">
    <div class="card-h">
      <div class="card-t">⏭ Actividades a Iniciar — Próximos 14 Días</div>
      <span class="pill pw">{len(tareas_prox)} tareas</span>
    </div>
    <div class="card-b np">
      {'<div class="card-b">'+render_tareas_prox()+'</div>' if not tareas_prox else
       '''<div class="tbl-w" style="max-height:260px;">
         <table class="gt"><thead><tr>
           <th>Planta</th><th>ID</th><th>Nombre</th>
           <th class="td-c">Inicio</th><th class="td-c">Fin</th>
           <th class="td-c">En</th>
         </tr></thead><tbody>'''+render_tareas_prox()+'''</tbody></table>
       </div>'''}
    </div>
  </div>

  <!-- Gantt completo -->
  <div class="sec-title">Gantt Completo por Planta</div>
  <div class="gantt-tabs">
    <div class="gtab on" onclick="switchGantt(0)">Majes</div>
    <div class="gtab" onclick="switchGantt(1)">Repartición</div>
  </div>
  <div class="card">
    <div class="card-b np">
      <div class="gpanel on" id="gp0">
        <div id="fig-gantt-det-m" style="width:100%;"></div>
      </div>
      <div class="gpanel" id="gp1">
        <div id="fig-gantt-det-r" style="width:100%;"></div>
      </div>
    </div>
  </div>

  <!-- SPI por macrofase -->
  <div class="card">
    <div class="card-h"><div class="card-t">📊 SPI por Macrofase — Ambas Plantas</div></div>
    <div class="card-b np">
      <div id="fig-spi" style="width:100%;"></div>
    </div>
  </div>

</div><!-- /page -->
</div><!-- /view1 -->

<!-- ═══════════════════════════════════════════════════════════
     TAB 2 — RUTA CRÍTICA COES
════════════════════════════════════════════════════════════ -->
<div class="view" id="view2">
<div class="page">

  <div class="sec-title">Cadena Crítica COES → Puesta en Marcha</div>

  <!-- Escenario base -->
  <div class="card" style="border-left:4px solid var(--red);margin-bottom:16px;">
    <div class="card-h"><div class="card-t">⚠ Escenario Base (sin palancas)</div></div>
    <div class="card-b">
      <div class="coes-steps">
        <div class="coes-node">Presentación COES<br><b>20/04/2026</b></div>
        <div class="coes-arrow">→</div>
        <div class="coes-node">Respuesta COES<br><b>45 días</b></div>
        <div class="coes-arrow">→</div>
        <div class="coes-node">Aprobación<br><b>{BUFFER_COES}d buffer</b></div>
        <div class="coes-arrow">→</div>
        <div class="coes-node" style="background:var(--red);">Puesta en marcha<br><b>{pb_fecha}</b></div>
      </div>
      {delta_badge(pb_delta)}
    </div>
  </div>

  <!-- Dos palancas -->
  <div class="coes-grid">
    <div class="card" style="border-left:4px solid var(--teal);">
      <div class="card-h"><div class="card-t">🔧 Palanca 1 — Adelantar presentación COES</div></div>
      <div class="card-b">
        <div class="coes-steps">
          <div class="coes-node" style="background:var(--teal);">Presentación<br><b>07/04/2026</b></div>
          <div class="coes-arrow">→</div>
          <div class="coes-node">Respuesta<br><b>45d</b></div>
          <div class="coes-arrow">→</div>
          <div class="coes-node" style="background:var(--teal);">PEM<br><b>{p1_fecha}</b></div>
        </div>
        <div class="coes-label">Resultado:</div>
        {delta_badge(p1_delta)}
        <p style="font-size:11px;color:var(--muted);margin-top:8px;">
          Adelantar presentación 13 días · Ganancia: {pb_delta-p1_delta} días
        </p>
      </div>
    </div>
    <div class="card" style="border-left:4px solid var(--blue);">
      <div class="card-h"><div class="card-t">🔧 Palanca 2 — Reducir tiempo respuesta COES</div></div>
      <div class="card-b">
        <div class="coes-steps">
          <div class="coes-node">Presentación<br><b>20/04/2026</b></div>
          <div class="coes-arrow">→</div>
          <div class="coes-node" style="background:var(--blue);">Respuesta<br><b>20d</b></div>
          <div class="coes-arrow">→</div>
          <div class="coes-node" style="background:var(--blue);">PEM<br><b>{p2_fecha}</b></div>
        </div>
        <div class="coes-label">Resultado:</div>
        {delta_badge(p2_delta)}
        <p style="font-size:11px;color:var(--muted);margin-top:8px;">
          Reducir respuesta 25 días · Ganancia: {pb_delta-p2_delta} días
        </p>
      </div>
    </div>
  </div>

  <!-- Combinado -->
  <div class="card" style="border-left:4px solid var(--green);margin-bottom:16px;">
    <div class="card-h"><div class="card-t">✅ Escenario Óptimo — Ambas Palancas Combinadas</div></div>
    <div class="card-b">
      <div class="coes-steps">
        <div class="coes-node" style="background:var(--teal);">Presentación<br><b>07/04/2026</b></div>
        <div class="coes-arrow">→</div>
        <div class="coes-node" style="background:var(--blue);">Respuesta<br><b>20d</b></div>
        <div class="coes-arrow">→</div>
        <div class="coes-node" style="background:var(--green);">Puesta en marcha<br><b>{pc_fecha}</b></div>
      </div>
      {delta_badge(pc_delta)}
    </div>
  </div>

  <!-- Simulador interactivo -->
  <div class="card">
    <div class="card-h"><div class="card-t">🎛 Simulador Interactivo</div></div>
    <div class="card-b">
      <div class="sim-row">
        <div class="sim-lbl">Fecha presentación COES</div>
        <input type="range" class="sim-slider" id="slider-dias-antes"
               min="0" max="30" value="0" oninput="updateSim()">
        <div class="sim-val" id="lbl-fecha-pres">20/04/2026</div>
      </div>
      <div class="sim-row">
        <div class="sim-lbl">Días respuesta COES</div>
        <input type="range" class="sim-slider" id="slider-resp"
               min="10" max="60" value="45" oninput="updateSim()">
        <div class="sim-val" id="lbl-resp">45 días</div>
      </div>
      <div class="sim-result" id="sim-result">
        <div class="coes-label">Fecha estimada de puesta en marcha</div>
        <div class="sim-res-date" id="sim-pem">{pb_fecha}</div>
        <div class="sim-res-delta" id="sim-delta">{delta_badge(pb_delta)}</div>
      </div>
    </div>
  </div>

</div><!-- /page -->
</div><!-- /view2 -->

<!-- ═══ SCRIPTS ═══ -->
<script>
// ── Plotly render ──────────────────────────────────────────
var CURVA_S_DATA     = {curva_s_json};
var SPI_DATA         = {spi_json};
var GANTT_M_DATA     = {gantt_m_json};
var GANTT_R_DATA     = {gantt_r_json};
var GANTT_DET_M_DATA = {gantt_det_m_json};
var GANTT_DET_R_DATA = {gantt_det_r_json};

var plotted = {{0:false, 1:false, 2:false}};
function renderTab(idx){{
  if(idx===0 && !plotted[0]){{
    Plotly.newPlot('fig-curva-s', CURVA_S_DATA.data, CURVA_S_DATA.layout, {{responsive:true, displayModeBar:false}});
    plotted[0]=true;
  }}
  if(idx===1 && !plotted[1]){{
    Plotly.newPlot('fig-gantt-det-m', GANTT_DET_M_DATA.data, GANTT_DET_M_DATA.layout, {{responsive:true, displayModeBar:false}});
    Plotly.newPlot('fig-spi', SPI_DATA.data, SPI_DATA.layout, {{responsive:true, displayModeBar:false}});
    // Repartición se renderiza al cambiar tab gantt
    plotted[1]=true;
  }}
}}

// ── Tabs ───────────────────────────────────────────────────
function showTab(idx){{
  ['view0','view1','view2'].forEach(function(id,i){{
    document.getElementById(id).classList.toggle('on', i===idx);
    document.getElementById('tab'+i).classList.toggle('on', i===idx);
  }});
  renderTab(idx);
}}

// ── Gantt tabs (Tab 1) ─────────────────────────────────────
var ganttDetRPlotted = false;
function switchGantt(idx){{
  document.querySelectorAll('.gtab').forEach(function(el,i){{
    el.classList.toggle('on', i===idx);
  }});
  document.getElementById('gp0').classList.toggle('on', idx===0);
  document.getElementById('gp1').classList.toggle('on', idx===1);
  if(idx===1 && !ganttDetRPlotted){{
    Plotly.newPlot('fig-gantt-det-r', GANTT_DET_R_DATA.data, GANTT_DET_R_DATA.layout, {{responsive:true, displayModeBar:false}});
    ganttDetRPlotted = true;
  }}
}}

// ── Simulador COES ─────────────────────────────────────────
var BASE_PRES = new Date('2026-04-20');
var BUFFER    = {BUFFER_COES};
var OBJ       = new Date('2026-05-30');

function fmtDate(d){{
  var dd=String(d.getDate()).padStart(2,'0');
  var mm=String(d.getMonth()+1).padStart(2,'0');
  return dd+'/'+mm+'/'+d.getFullYear();
}}
function updateSim(){{
  var diasAntes = parseInt(document.getElementById('slider-dias-antes').value);
  var diasResp  = parseInt(document.getElementById('slider-resp').value);

  var pres = new Date(BASE_PRES);
  pres.setDate(pres.getDate() - diasAntes);
  document.getElementById('lbl-fecha-pres').textContent = fmtDate(pres);
  document.getElementById('lbl-resp').textContent       = diasResp+' días';

  var finResp = new Date(pres);
  finResp.setDate(finResp.getDate() + diasResp);
  var pem = new Date(finResp);
  pem.setDate(pem.getDate() + BUFFER);

  document.getElementById('sim-pem').textContent = fmtDate(pem);

  var delta = Math.round((pem - OBJ) / 86400000);
  var deltaEl = document.getElementById('sim-delta');
  if(delta <= 0){{
    deltaEl.innerHTML = '<span class="pill pd">✅ '+Math.abs(delta)+'d antes del objetivo</span>';
    document.querySelector('.sim-result').style.background = '#d4f5e3';
    document.querySelector('.sim-result').style.borderColor = '#0d9e5c';
  }} else {{
    deltaEl.innerHTML = '<span class="pill pl">⚠ '+delta+'d después del objetivo</span>';
    document.querySelector('.sim-result').style.background = '#fde8ea';
    document.querySelector('.sim-result').style.borderColor = '#c8263a';
  }}
}}

// Render inicial Tab 0
renderTab(0);
</script>
</body>
</html>"""

out_path = os.path.join(OUT_DIR, "dashboard_bess.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(HTML)

size_kb = os.path.getsize(out_path) // 1024
print(f"\n✅ Dashboard generado: outputs/dashboard_bess.html ({size_kb} KB)")
print(f"   FECHA_CORTE = {FECHA_CORTE.strftime('%d/%m/%Y')}  |  Generado: {GENERADO_EL.strftime('%d/%m/%Y')}")
print(f"   KPI Majes = {kpi_m:.1f}% | Repartición = {kpi_r:.1f}% | SPI = {kpi_spi:.2f}")
print(f"   Días al objetivo 30/May: {dias_obj}")
print(f"   Alertas activas: {len(alertas)}")
print(f"   Tareas activas hoy: {len(tareas_hoy)}")
print(f"   Tareas próximas 14d: {len(tareas_prox)}")
print(f"\n   TAB 1 — Vista Ejecutiva: KPIs, semáforos, hitos, Curva S, alertas")
print(f"   TAB 2 — Detalle Técnico: actividades hoy/próximas, Gantt 154 tareas, SPI")
print(f"   TAB 3 — Ruta Crítica COES: palancas + simulador interactivo")
