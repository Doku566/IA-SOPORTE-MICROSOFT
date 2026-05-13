import markdown
import os
import base64
import re

md_file = 'Documentacion_Oficial_IA.md'
html_file = 'Documentacion_Oficial_Motor_Soporte_IA_UTM.html'

def get_base64_image(image_path):
    if not os.path.exists(image_path):
        return ""
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    ext = os.path.splitext(image_path)[1][1:]
    return f"data:image/{ext};base64,{encoded_string}"

with open(md_file, 'r', encoding='utf-8') as f:
    text = f.read()

# Convertir Markdown a HTML usando extensión extra para bloques de código
html_content = markdown.markdown(text, extensions=['tables', 'fenced_code'])

# Transformar los bloques pre code class="language-mermaid" a divs para mermaid
html_content = html_content.replace('<pre><code class="language-mermaid">', '<div class="mermaid">')
html_content = html_content.replace('</code></pre>', '</div>')

full_html = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Documentación IA UTM</title>
<!-- Mermaid JS -->
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
  mermaid.initialize({ startOnLoad: true, theme: 'default' });
</script>
<style>
    @page { margin: 2.54cm; }
    body { background-color: #ffffff; font-family: "Times New Roman", Times, serif; font-size: 12pt; line-height: 2; color: #000000; text-align: left; max-width: 8.5in; margin: auto; padding: 40px; }
    p { text-indent: 1.27cm; margin-top: 0; margin-bottom: 0; }
    h1 { color: #000000; text-align: center; font-size: 14pt; font-weight: bold; margin-top: 24pt; margin-bottom: 24pt; }
    h2 { color: #000000; text-align: left; font-size: 12pt; font-weight: bold; margin-top: 18pt; margin-bottom: 18pt; }
    h3 { color: #000000; text-align: left; font-size: 12pt; font-style: italic; font-weight: bold; margin-top: 12pt; margin-bottom: 12pt; }
    ul, ol { margin-top: 0; margin-bottom: 0; }
    li { margin-bottom: 0; text-indent: 0; }
    code { font-family: "Courier New", Courier, monospace; font-size: 10pt; color: #000000; }
    pre { background-color: #ffffff; color: #000000; padding: 10px; overflow-x: auto; border: 1px solid #cccccc; }
    pre code { background-color: transparent; color: inherit; padding: 0; border: 0; }
    img { max-width: 100%; height: auto; margin: 20px auto; display: block; }
    blockquote { margin-left: 1.27cm; color: #000000; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th, td { border: 1px solid #000000; padding: 8px; text-align: left; }
    th { font-weight: bold; }
    .mermaid { display: flex; justify-content: center; margin: 20px 0; }
    
    @media print {
        body { padding: 0; max-width: 100%; }
        pre, blockquote { page-break-inside: avoid; }
        img { page-break-inside: avoid; max-height: 800px; }
        h2, h3 { page-break-after: avoid; }
    }
</style>
</head>
<body>
""" + html_content + """
</body>
</html>
"""

with open(html_file, 'w', encoding='utf-8') as f:
    f.write(full_html)
print(f"HTML generado exitosamente con imágenes incrustadas en: {os.path.abspath(html_file)}")
