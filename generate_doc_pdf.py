import markdown
import os
import subprocess

md_file = 'Documentacion_Oficial_IA.md'
html_file = 'temp_doc.html'
pdf_file = 'Documentacion_Oficial_Motor_Soporte_IA_UTM.pdf'

# Leer markdown
with open(md_file, 'r', encoding='utf-8') as f:
    text = f.read()

# Convertir a HTML
html_content = markdown.markdown(text, extensions=['tables', 'fenced_code'])

# Envolver en HTML con CSS para el PDF
full_html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<!-- Necesario para que MS Edge resuelva las imágenes relativas -->
<base href="file:///""" + os.path.abspath(html_file).replace('\\', '/') + """">
<style>
    @page { margin: 2cm; }
    body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: auto; }
    h1 { color: #004d40; border-bottom: 3px solid #004d40; padding-bottom: 10px; text-align: center; }
    h2 { color: #00695c; margin-top: 30px; border-bottom: 1px solid #ccc; padding-bottom: 5px; }
    h3 { color: #00796b; }
    code { background-color: #f4f4f4; padding: 2px 5px; border-radius: 4px; font-family: 'Courier New', monospace; color: #d32f2f; }
    pre { background-color: #263238; color: #eceff1; padding: 15px; border-radius: 5px; overflow-x: auto; }
    pre code { background-color: transparent; color: inherit; padding: 0; }
    img { max-width: 100%; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin: 20px 0; display: block; margin-left: auto; margin-right: auto; }
    blockquote { border-left: 4px solid #00695c; margin-left: 0; padding-left: 15px; color: #555; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background-color: #f2f2f2; color: #333; }
</style>
</head>
<body>
""" + html_content + """
</body>
</html>
"""

with open(html_file, 'w', encoding='utf-8') as f:
    f.write(full_html)

edge_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(edge_path):
    print('Edge no encontrado. Por favor instale Microsoft Edge.')
else:
    pdf_path = os.path.abspath(pdf_file)
    html_path = os.path.abspath(html_file)
    
    # Agregado --allow-file-access-from-files para asegurar que pueda leer las imágenes locales
    cmd = [
        edge_path, 
        '--headless', 
        '--disable-gpu', 
        '--allow-file-access-from-files',
        f'--print-to-pdf={pdf_path}', 
        '--no-margins', 
        html_path
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f'EXITO: PDF creado en {pdf_path}')
    except Exception as e:
        print(f'Error al crear PDF: {e}')
