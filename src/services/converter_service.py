import os
import subprocess
from PIL import Image
import pypandoc

def get_file_type(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.ico']:
        return 'image'
    elif ext in ['.mp4', '.avi', '.mkv', '.mov', '.webm', '.mp3', '.wav', '.ogg', '.flac', '.aac']:
        return 'media'
    elif ext in ['.docx', '.md', '.rst', '.html', '.epub', '.odt', '.pdf']:
        return 'document'
    return 'unknown'

def convert_image(input_path: str, output_path: str) -> bool:
    try:
        with Image.open(input_path) as img:
            # Handle RGBA to RGB if converting to JPEG
            if output_path.lower().endswith(('.jpg', '.jpeg')) and img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(output_path)
        return True
    except Exception as e:
        print(f"Error converting image: {e}")
        return False

def convert_media(input_path: str, output_path: str) -> bool:
    try:
        # Calls local ffmpeg directly. Relies on FFmpeg being in PATH.
        command = [
            "ffmpeg", "-y", "-i", input_path, output_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"FFmpeg Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Error converting media: {e}")
        return False

def convert_document(input_path: str, output_path: str) -> bool:
    try:
        in_ext = os.path.splitext(input_path)[1].lower()
        out_ext = os.path.splitext(output_path)[1].lower()
        
        if in_ext == '.pdf' and out_ext == '.docx':
            from pdf2docx import parse
            parse(input_path, output_path)
            return True
            
        # pandoc input -o output
        pypandoc.convert_file(input_path, to=out_ext.replace('.', ''), outputfile=output_path)
        return True
    except Exception as e:
        print(f"Error converting document: {e}")
        return False

def run_conversion(input_path: str, output_path: str) -> bool:
    file_type = get_file_type(input_path)
    
    if file_type == 'image':
        return convert_image(input_path, output_path)
    elif file_type == 'media':
        return convert_media(input_path, output_path)
    elif file_type == 'document':
        return convert_document(input_path, output_path)
    else:
        # Fallback to FFmpeg which handles a lot of weird things just in case
        return convert_media(input_path, output_path)
