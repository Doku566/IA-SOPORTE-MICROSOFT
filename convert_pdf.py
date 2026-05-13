import markdown
import os
import subprocess

html_content = markdown.markdown(open('README.md', encoding='utf-8').read(), extensions=['tables', 'fenced_code'])
full_html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; padding: 40px; line-height: 1.6; color: #333; }
    h1 { color: #003366; border-bottom: 2px solid #eee; padding-bottom: 10px; }
    h2 { color: #004080; }
    code { background-color: #f4f4f4; padding: 2px 5px; border-radius: 4px; font-family: monospace; }
    pre { background-color: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }
    img { max-width: 100%; }
</style>
</head>
<body>
""" + html_content + """
</body>
</html>
"""

with open('temp_readme.html', 'w', encoding='utf-8') as f:
    f.write(full_html)

edge_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(edge_path):
    print('Edge no encontrado en ruta predeterminada.')
else:
    pdf_path = os.path.abspath('README_Motor_Soporte_IA.pdf')
    html_path = os.path.abspath('temp_readme.html')
    cmd = [edge_path, '--headless', '--disable-gpu', f'--print-to-pdf={pdf_path}', html_path]
    subprocess.run(cmd)
    print(f'PDF creado en: {pdf_path}')
