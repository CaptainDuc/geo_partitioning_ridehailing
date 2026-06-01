import zipfile
import xml.etree.ElementTree as ET
import os

def get_docx_text(path):
    """
    Extract text from docx without external dependencies.
    """
    try:
        with zipfile.ZipFile(path) as z:
            xml_content = z.read('word/document.xml')
        tree = ET.fromstring(xml_content)
        paragraphs = []
        # The text is in <w:t> tags within <w:p> tags
        for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
            texts = [t.text for t in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if t.text]
            if texts:
                paragraphs.append(''.join(texts))
        return '\n'.join(paragraphs)
    except Exception as e:
        return f"Error reading {path}: {str(e)}"

files = ["Design Document.docx", "Project proposal.docx"]
for f in files:
    print(f"--- {f} ---")
    print(get_docx_text(f))
    print("\n" + "="*50 + "\n")
