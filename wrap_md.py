import sys

def wrap_text(text, width=100):
    lines = text.split('\n')
    wrapped_lines = []
    in_code_block = False
    
    for line in lines:
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            wrapped_lines.append(line)
            continue
            
        if in_code_block:
            wrapped_lines.append(line)
            continue
            
        # Ignore headers, list items, and blockquotes for strict wrapping if they are short,
        # but if they are long, we should wrap them carefully.
        # To be safe and simple, we wrap words
        if len(line) <= width:
            wrapped_lines.append(line)
        else:
            # Wrap long line
            words = line.split(' ')
            current_line = []
            current_length = 0
            
            for word in words:
                if current_length + len(word) + 1 > width and current_line:
                    # special case for bullet points to indent wrapped lines
                    if current_line[0].startswith('*') or current_line[0].startswith('-') or (current_line[0][0].isdigit() and current_line[0][1:] == '.'):
                        wrapped_lines.append(' '.join(current_line))
                        current_line = ['    ' + word]
                        current_length = 4 + len(word)
                    else:
                        wrapped_lines.append(' '.join(current_line))
                        current_line = [word]
                        current_length = len(word)
                else:
                    current_line.append(word)
                    current_length += len(word) + 1
                    
            if current_line:
                wrapped_lines.append(' '.join(current_line))

    return '\n'.join(wrapped_lines)

with open('Documentacion_Oficial_IA.md', 'r', encoding='utf-8') as f:
    content = f.read()

wrapped = wrap_text(content)

with open('Documentacion_Oficial_IA.md', 'w', encoding='utf-8') as f:
    f.write(wrapped)

print("Markdown reformateado para lectura (Word Wrap).")
