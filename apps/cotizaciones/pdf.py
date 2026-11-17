"""Generación del PDF de una cotización (S4-J2).

Módulo aislado: solo depende de ReportLab y de los datos de la cotización. Si algún día hay que
sacrificarlo, basta con borrar este archivo, la ruta/vista `descargar_pdf` y el botón de la plantilla.
Usa fuentes estándar del PDF (Helvetica): no requiere archivos de fuentes en el servidor.
"""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

AZUL = colors.HexColor("#0b3d6b")
GRIS = colors.HexColor("#5b6670")
LINEA = colors.HexColor("#c9d1d9")
FONDO = colors.HexColor("#eef3f8")


def _clp(valor):
    try:
        return "$" + f"{int(valor):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "$0"


def _fecha(valor):
    return valor.strftime("%d-%m-%Y") if valor else ""


def _t(valor):
    """Texto seguro para ReportLab: escapa XML y reemplaza lo que Helvetica (WinAnsi) no puede dibujar."""
    texto = "" if valor is None else str(valor)
    texto = texto.encode("cp1252", "replace").decode("cp1252")
    return escape(texto).replace("\n", "<br/>")


def _estilos():
    base = getSampleStyleSheet()["Normal"]
    return {
        "n": ParagraphStyle("n", parent=base, fontName="Helvetica", fontSize=9.5, leading=13),
        "peq": ParagraphStyle("peq", parent=base, fontName="Helvetica", fontSize=8.5, leading=11, textColor=GRIS),
        "h1": ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=AZUL),
        "h3": ParagraphStyle("h3", parent=base, fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=AZUL),
        "der": ParagraphStyle("der", parent=base, fontName="Helvetica", fontSize=9.5, leading=13, alignment=TA_RIGHT),
        "th": ParagraphStyle("th", parent=base, fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.white),
        "thd": ParagraphStyle("thd", parent=base, fontName="Helvetica-Bold", fontSize=9, leading=12,
                              textColor=colors.white, alignment=TA_RIGHT),
    }


def _pie(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRIS)
    canvas.drawString(doc.leftMargin, 10 * mm, doc.titulo_pie)
    canvas.drawRightString(A4[0] - doc.rightMargin, 10 * mm, f"Página {canvas.getPageNumber()}")
    canvas.restoreState()


def generar_pdf(cot, empresa=None, iva_porcentaje=None):
    """Devuelve los bytes del PDF de la cotización `cot` (con sus líneas y solicitud ya cargadas)."""
    if empresa is None or iva_porcentaje is None:
        from django.conf import settings

        empresa = empresa if empresa is not None else settings.EMPRESA
        iva_porcentaje = iva_porcentaje if iva_porcentaje is not None else settings.IVA_PORCENTAJE
    e = _estilos()
    sol = cot.solicitud
    historia = []

    # Encabezado: empresa a la izquierda, código y estado a la derecha.
    izq = [Paragraph(_t(empresa["nombre"]), e["h3"]), Paragraph(_t(empresa.get("eslogan", "")), e["peq"]),
           Paragraph(_t(" · ".join(x for x in (empresa.get("email"), empresa.get("telefono")) if x)), e["peq"]),
           Paragraph(_t(empresa.get("direccion", "")), e["peq"])]
    der = [Paragraph(f"Cotización {_t(cot.codigo)}", ParagraphStyle("h1d", parent=e["h1"], alignment=TA_RIGHT)),
           Paragraph(f"Emitida el {_fecha(cot.creada)}", e["der"]),
           Paragraph(f"Estado: {_t(cot.get_estado_display())}", e["der"])]
    cab = Table([[izq, der]], colWidths=[85 * mm, 85 * mm])
    cab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("LINEBELOW", (0, 0), (-1, 0), 1, AZUL),
                             ("BOTTOMPADDING", (0, 0), (-1, 0), 8)]))
    historia += [cab, Spacer(1, 6 * mm)]

    # Datos de la solicitud.
    lugar = ", ".join(x for x in (sol.direccion, sol.comuna) if x)
    filas = [("Cliente", sol.nombre_contacto), ("Solicitud", f"{sol.codigo} · {sol.asunto}"), ("Lugar", lugar)]
    if cot.validez_hasta:
        filas.append(("Válida hasta", _fecha(cot.validez_hasta)))
    datos = Table([[Paragraph(f"<b>{_t(k)}</b>", e["n"]), Paragraph(_t(v), e["n"])] for k, v in filas],
                  colWidths=[30 * mm, 140 * mm])
    datos.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, -1), FONDO),
                               ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 3),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    historia += [datos, Spacer(1, 6 * mm)]

    # Detalle: la fila de títulos se repite si la tabla pasa a otra página.
    filas = [[Paragraph("Descripción", e["th"]), Paragraph("Cant.", e["thd"]),
              Paragraph("P. unitario", e["thd"]), Paragraph("Subtotal", e["thd"])]]
    for l in cot.lineas.all():
        filas.append([Paragraph(_t(l.descripcion), e["n"]), Paragraph(str(l.cantidad), e["der"]),
                      Paragraph(_clp(l.precio_unitario), e["der"]), Paragraph(_clp(l.subtotal), e["der"])])
    detalle = Table(filas, colWidths=[88 * mm, 18 * mm, 30 * mm, 34 * mm], repeatRows=1)
    detalle.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), AZUL), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("LINEBELOW", (0, 1), (-1, -1), 0.5, LINEA), ("TOPPADDING", (0, 0), (-1, -1), 4),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    historia += [detalle, Spacer(1, 4 * mm)]

    # Totales (alineados a la derecha, no se parten entre páginas).
    totales = Table(
        [[Paragraph("Neto", e["der"]), Paragraph(_clp(cot.neto), e["der"])],
         [Paragraph(f"IVA ({iva_porcentaje}%)", e["der"]), Paragraph(_clp(cot.iva), e["der"])],
         [Paragraph("<b>Total</b>", e["der"]), Paragraph(f"<b>{_clp(cot.total)}</b>", e["der"])]],
        colWidths=[40 * mm, 34 * mm], hAlign="RIGHT")
    totales.setStyle(TableStyle([("LINEABOVE", (0, 2), (-1, 2), 1, AZUL), ("BACKGROUND", (0, 2), (-1, 2), FONDO)]))
    historia.append(totales)

    if cot.observaciones:
        historia += [Spacer(1, 6 * mm), Paragraph("Observaciones", e["h3"]), Paragraph(_t(cot.observaciones), e["n"])]
    historia += [Spacer(1, 6 * mm),
                 Paragraph("Montos en pesos chilenos. Los precios unitarios son netos; el IVA se detalla arriba.", e["peq"])]

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                            bottomMargin=20 * mm, title=f"Cotización {cot.codigo}", author=empresa["nombre"])
    doc.titulo_pie = f"{empresa['nombre']} · {cot.codigo}"
    doc.build(historia, onFirstPage=_pie, onLaterPages=_pie)
    return buffer.getvalue()
