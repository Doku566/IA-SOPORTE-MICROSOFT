import os
import re

# Rango de emojis y símbolos decorativos
emoji_pattern = re.compile(
    "["
    "\U0001f300-\U0001f6ff"  # Miscellaneous Symbols and Pictographs
    "\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
    "\U0001f680-\U0001f6ff"  # Transport and Map Symbols
    "\U00002600-\U000026ff"  # Miscellaneous Symbols
    "\U00002700-\U000027bf"  # Dingbats
    "\U0001f1e6-\U0001f1ff"  # Regional Indicator Symbols (Flags)
    "]+", flags=re.UNICODE
)

def remove_emojis(text):
    return emoji_pattern.sub('', text)

def purge_folder(folder_path):
    for root, dirs, files in os.walk(folder_path):
        if '.git' in dirs:
            dirs.remove('.git')
        for file in files:
            if file.endswith(('.py', '.md', '.txt', '.env.example')):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    new_content = remove_emojis(content)
                    
                    if content != new_content:
                        print(f"Limpio: {file_path}")
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                except Exception as e:
                    print(f"Error procesando {file_path}: {e}")

if __name__ == "__main__":
    purge_folder("MICROSOFT")
    purge_folder(".") # Tambien la raiz por si acaso hay algo en el README principal
