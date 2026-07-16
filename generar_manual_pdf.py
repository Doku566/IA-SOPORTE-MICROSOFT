import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#333333"))
        
        # Encabezado (Header APA) en todas las páginas excepto la portada (página 1)
        if self._pageNumber > 1:
            self.drawString(2.54 * cm, 27.0 * cm, "MANUAL DE ARQUITECTURA E INGENIERÍA - SISTEMA AUTÓNOMO SOPORTE IA UTM (2026)")
            self.setStrokeColor(colors.HexColor("#CCCCCC"))
            self.setLineWidth(0.5)
            self.line(2.54 * cm, 26.8 * cm, letter[0] - 2.54 * cm, 26.8 * cm)
            
            # Pie de página (Footer APA con numeración)
            page_str = f"Página {self._pageNumber} de {page_count}"
            self.drawRightString(letter[0] - 2.54 * cm, 1.8 * cm, page_str)
            self.drawString(2.54 * cm, 1.8 * cm, "Universidad Tecnológica de Matamoros | Dirección de Sistemas (Módulo 3)")
            self.line(2.54 * cm, 2.2 * cm, letter[0] - 2.54 * cm, 2.2 * cm)
            
        self.restoreState()

def generar_pdf(md_filename, pdf_filename):
    if not os.path.exists(md_filename):
        print(f"Error: No se encontró el archivo {md_filename}")
        return

    with open(md_filename, "r", encoding="utf-8") as f:
        text = f.read()

    # Document template con márgenes APA (2.54 cm = 1 pulgada en los 4 lados)
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=letter,
        leftMargin=2.54 * cm,
        rightMargin=2.54 * cm,
        topMargin=2.54 * cm,
        bottomMargin=2.54 * cm
    )

    styles = getSampleStyleSheet()
    
    # Estilos APA Personalizados
    title_style = ParagraphStyle(
        'APATitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=24,
        alignment=1, # Centro
        textColor=colors.HexColor('#000000'),
        spaceAfter=20
    )
    
    subtitle_style = ParagraphStyle(
        'APASubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=18,
        alignment=1, # Centro
        textColor=colors.HexColor('#222222'),
        spaceAfter=35
    )
    
    h1_style = ParagraphStyle(
        'APAHeading1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#000000'),
        spaceBefore=18,
        spaceAfter=10,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'APAHeading2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#111111'),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    
    h3_style = ParagraphStyle(
        'APAHeading3',
        parent=styles['Heading3'],
        fontName='Helvetica-BoldOblique',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#222222'),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'APABody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        alignment=4, # Justificado
        textColor=colors.HexColor('#000000'),
        spaceAfter=8
    )

    bullet_style = ParagraphStyle(
        'APABullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        alignment=4,
        leftIndent=20,
        firstLineIndent=-10,
        textColor=colors.HexColor('#000000'),
        spaceAfter=5
    )

    code_style = ParagraphStyle(
        'APACode',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#000000'),
        backColor=colors.HexColor('#F5F5F5'),
        borderColor=colors.HexColor('#DDDDDD'),
        borderWidth=0.5,
        borderPadding=6,
        spaceBefore=6,
        spaceAfter=8
    )

    table_header_style = ParagraphStyle(
        'APATableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        alignment=1, # Centro
        textColor=colors.HexColor('#000000')
    )

    table_cell_style = ParagraphStyle(
        'APATableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        alignment=0, # Izquierda
        textColor=colors.HexColor('#000000')
    )

    story = []

    # Portada APA
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("Manual de Arquitectura, Ingeniería y Reconstrucción del Sistema Autónomo de Soporte Técnico Inteligente UTM (2026)", title_style))
    story.append(Spacer(1, 1 * cm))
    
    meta_text = """
    <b>Desarrollo y Arquitectura Principal:</b> Departamento de Sistemas e Infraestructura TI<br/><br/>
    <b>Afiliación:</b> Dirección de Tecnologías de la Información / Departamento de Sistemas (Módulo 3),<br/>
    Universidad Tecnológica de Matamoros (UTM)<br/><br/>
    <b>Fecha de Emisión:</b> 15 de Julio de 2026<br/><br/>
    <b>Clasificación:</b> Documento de Grado Doctoral & Guía de Reconstrucción Total (DRP)<br/><br/>
    <b>Estilo Normativo:</b> APA 7a Edición (Adaptado para Ciencias de la Computación)
    """
    story.append(Paragraph(meta_text, subtitle_style))
    story.append(PageBreak())

    # Procesar líneas del Markdown
    lines = text.split('\n')
    in_code_block = False
    code_buffer = []
    in_table = False
    table_rows = []

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return
        
        # Procesar datos de la tabla para ReportLab
        formatted_data = []
        for row_idx, row in enumerate(table_rows):
            # Limpiar filas divisorias (|---|---|)
            if all(cell.strip().replace('-', '').replace(':', '') == '' for cell in row):
                continue
            
            row_cells = []
            for cell in row:
                c_text = cell.strip()
                # Reemplazar markdown en celdas
                c_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', c_text)
                c_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', c_text)
                c_text = re.sub(r'`(.*?)`', r'<font name="Courier">\1</font>', c_text)
                
                if row_idx == 0:
                    row_cells.append(Paragraph(c_text, table_header_style))
                else:
                    row_cells.append(Paragraph(c_text, table_cell_style))
            formatted_data.append(row_cells)

        if formatted_data:
            # Calcular anchos de columna dinámicamente según la cantidad de columnas
            num_cols = len(formatted_data[0])
            total_width = letter[0] - 5.08 * cm
            
            if num_cols == 2:
                col_widths = [total_width * 0.35, total_width * 0.65]
            elif num_cols == 3:
                col_widths = [total_width * 0.25, total_width * 0.38, total_width * 0.37]
            elif num_cols == 4:
                col_widths = [total_width * 0.22, total_width * 0.26, total_width * 0.26, total_width * 0.26]
            else:
                col_widths = [total_width / num_cols] * num_cols

            t = Table(formatted_data, colWidths=col_widths, repeatRows=1)
            t.setStyle(TableStyle([
                ('LINEABOVE', (0, 0), (-1, 0), 1.5, colors.HexColor('#000000')),
                ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.HexColor('#000000')),
                ('LINEBELOW', (0, -1), (-1, -1), 1.5, colors.HexColor('#000000')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FAFAFA')])
            ]))
            story.append(Spacer(1, 4))
            story.append(t)
            story.append(Spacer(1, 10))
        table_rows = []

    for line in lines:
        line_str = line.rstrip()

        # Bloques de Código Fenced ```
        if line_str.startswith('```'):
            if in_code_block:
                in_code_block = False
                c_text = "\n".join(code_buffer)
                # Escapar HTML básico para que ReportLab no confunda etiquetas de Python/HTML
                c_text = c_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                c_text = c_text.replace('\n', '<br/>').replace('    ', '&nbsp;&nbsp;&nbsp;&nbsp;')
                story.append(Paragraph(c_text, code_style))
                code_buffer = []
            else:
                if in_table:
                    in_table = False
                    flush_table()
                in_code_block = True
            continue

        if in_code_block:
            code_buffer.append(line_str)
            continue

        # Detección de Tablas Markdown
        if line_str.startswith('|') and line_str.endswith('|'):
            if not in_table:
                in_table = True
            cells = [c for c in line_str.split('|')[1:-1]]
            table_rows.append(cells)
            continue
        else:
            if in_table:
                in_table = False
                flush_table()

        # Saltos o separadores horizontales ---
        if line_str == '---':
            story.append(Spacer(1, 8))
            story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor('#CCCCCC'), spaceAfter=14))
            continue

        # Encabezados
        if line_str.startswith('# '):
            t_text = line_str[2:].strip()
            # Omitir el primer título si es idéntico a la portada para no repetirlo
            if "Manual de Arquitectura" not in t_text:
                story.append(Paragraph(t_text, h1_style))
            continue
        elif line_str.startswith('## '):
            story.append(Paragraph(line_str[3:].strip(), h1_style))
            continue
        elif line_str.startswith('### '):
            story.append(Paragraph(line_str[4:].strip(), h2_style))
            continue
        elif line_str.startswith('#### '):
            story.append(Paragraph(line_str[5:].strip(), h3_style))
            continue

        # Viñetas y listas numéricas
        if re.match(r'^\s*[-*]\s+', line_str):
            b_text = re.sub(r'^\s*[-*]\s+', '• ', line_str)
            b_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', b_text)
            b_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', b_text)
            b_text = re.sub(r'`(.*?)`', r'<font name="Courier">\1</font>', b_text)
            story.append(Paragraph(b_text, bullet_style))
            continue
        elif re.match(r'^\s*\d+\.\s+', line_str):
            b_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line_str)
            b_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', b_text)
            b_text = re.sub(r'`(.*?)`', r'<font name="Courier">\1</font>', b_text)
            story.append(Paragraph(b_text, bullet_style))
            continue

        # Párrafos normales
        if line_str.strip() != "":
            p_text = line_str.strip()
            p_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', p_text)
            p_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', p_text)
            p_text = re.sub(r'`(.*?)`', r'<font name="Courier">\1</font>', p_text)
            story.append(Paragraph(p_text, body_style))
        else:
            story.append(Spacer(1, 4))

    # Asegurar volcado de tabla final si quedó pendiente
    if in_table:
        flush_table()

    # Compilar y construir el archivo PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"¡PDF generado exitosamente: {pdf_filename}!")

if __name__ == "__main__":
    md_file = "Guia_Arquitectura_e_Ingenieria_Soporte_IA_UTM.md"
    pdf_file = "Manual_Arquitectura_e_Ingenieria_Soporte_IA_UTM.pdf"
    print(f"Iniciando compilación a PDF APA 7a Edición desde {md_file}...")
    generar_pdf(md_file, pdf_file)
