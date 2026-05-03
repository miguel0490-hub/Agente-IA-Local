import os

def generate_tree(startpath):
    tree = []
    ignore_dirs = {'.git', 'venv', '__pycache__', '.vscode', 'generated_images', 'data'}
    for root, dirs, files in os.walk(startpath):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * level
        tree.append(f'{indent}{os.path.basename(root)}/')
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            if not f.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf', '.pyc', '.exe', '.zip', '.mp4', '.mov', '.avi')):
                tree.append(f'{subindent}{f}')
    return "\n".join(tree)

def export_project():
    output_file = "codigo_completo_para_gemini.txt"
    ignore_dirs = {'.git', 'venv', '__pycache__', '.vscode', 'generated_images', 'data'}
    ignore_extensions = {'.png', '.jpg', '.jpeg', '.pdf', '.pyc', '.exe', '.zip', '.mp4', '.mov', '.avi', '.docx', '.xlsx', '.pptx'}
    
    with open(output_file, "w", encoding="utf-8") as out:
        out.write("================================================================\n")
        out.write("ESTRUCTURA DEL PROYECTO\n")
        out.write("================================================================\n\n")
        out.write(generate_tree(os.getcwd()))
        out.write("\n\n")
        
        for root, dirs, files in os.walk(os.getcwd()):
            # Ignorar directorios prohibidos
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in ignore_extensions:
                    continue
                if file == ".env" or file == output_file or file == "export_project.py":
                    continue
                    
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, os.getcwd())
                
                out.write("================================================================\n")
                out.write(f"ARCHIVO: {rel_path}\n")
                out.write("================================================================\n")
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        out.write(f.read())
                except Exception as e:
                    out.write(f"Error al leer archivo: {e}")
                out.write("\n\n")

    print(f"✅ Proyecto exportado con éxito a: {output_file}")

if __name__ == "__main__":
    export_project()
