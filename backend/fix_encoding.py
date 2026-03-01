"""
Fix file encoding issues
"""
import sys
import os

def fix_file_encoding(file_path):
    """Try to read file with different encodings and save as UTF-8"""
    encodings = ['gbk', 'gb2312', 'gb18030', 'utf-8', 'latin-1']

    content = None
    used_encoding = None

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            used_encoding = encoding
            print(f"Successfully read file with {encoding} encoding")
            break
        except (UnicodeDecodeError, UnicodeError) as e:
            print(f"Failed to read with {encoding}: {e}")
            continue

    if content is None:
        print("Failed to read file with any encoding!")
        return False

    # Write back as UTF-8
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Successfully wrote file as UTF-8")
        return True
    except Exception as e:
        print(f"Failed to write file: {e}")
        return False

if __name__ == "__main__":
    file_path = "offline/tencent_offline_asr.py"

    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)

    success = fix_file_encoding(file_path)
    sys.exit(0 if success else 1)
