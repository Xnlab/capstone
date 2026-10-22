"""Analyze and fill HWPX input locations without rebuilding the document."""
import re
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

from lxml import etree

HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
NS = {'hp': HP}
SECTIONS = re.compile(r'^Contents/section\d+\.xml$')
PLACEHOLDER = re.compile(r'\{\{\s*([^{}\n]{1,40}?)\s*\}\}')


def _read(source):
    with ZipFile(BytesIO(source) if isinstance(source, bytes) else source) as archive:
        entries = archive.infolist()
        if len(entries) > 3000 or sum(entry.file_size for entry in entries) > 100 * 1024 * 1024:
            raise ValueError('한글 양식의 압축 해제 크기가 너무 큽니다.')
        names = [entry.filename for entry in entries]
        if len(set(names)) != len(names):
            raise ValueError('중복 경로가 있는 HWPX 파일입니다.')
        if not any(SECTIONS.fullmatch(name) for name in names):
            raise ValueError('HWPX 본문이 없습니다. 암호화된 문서는 해제한 뒤 업로드하세요.')
        return entries, {entry.filename: archive.read(entry) for entry in entries}


def _roots(files):
    result = {}
    for name in sorted(files):
        if SECTIONS.fullmatch(name):
            xml = files[name]
            if b'<!DOCTYPE' in xml.upper():
                raise ValueError('외부 엔터티가 포함된 XML은 지원하지 않습니다.')
            root = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False))
            if root.getroottree().docinfo.doctype or etree.QName(root).localname != 'sec':
                raise ValueError('올바른 HWPX 본문 형식이 아닙니다.')
            result[name] = root
    return result


def paragraph_text(paragraph):
    return ''.join(''.join(node.itertext()) for node in paragraph.findall('hp:run/hp:t', NS))


def _cell_paragraphs(cell):
    return cell.findall('hp:subList/hp:p', NS)


def analyze(path: Path):
    from app.services.form_parser import _is_label, _BLANK, _PARA_FIELD
    from app.standard_fields import field_label, STANDARD_FIELDS
    _, files = _read(path)
    roots = _roots(files)
    items, titles = [], []
    table_count = para_count = 0
    for name, root in roots.items():
        cells = list(root.iter(f'{{{HP}}}tc'))
        cell_indices = {cell: index for index, cell in enumerate(cells)}
        for table in root.iter(f'{{{HP}}}tbl'):
            table_count += 1
            for row in table.findall('hp:tr', NS):
                row_cells = row.findall('hp:tc', NS)
                for left, right in zip(row_cells, row_cells[1:]):
                    label = '\n'.join(paragraph_text(p) for p in _cell_paragraphs(left)).strip()
                    value = '\n'.join(paragraph_text(p) for p in _cell_paragraphs(right))
                    clean_label = re.sub(r'^\s*(?:\d+[.)]|[①②③④⑤⑥⑦⑧⑨⑩])\s*', '', label).rstrip(' :：')
                    suffix_match = re.search(r'\((?:인|서명)\)\s*$', value)
                    blank_value = value[:suffix_match.start()] if suffix_match else value
                    skeleton = re.fullmatch(r'\s*\(?\s*(?:일금|금)?\s*(?:원정|원)?\s*\)?\s*|\s*년\s*월\s*일\s*', blank_value)
                    if _is_label(clean_label) and (_BLANK.fullmatch(blank_value) or skeleton):
                        location = {'type': 'hwpx_cell', 'section': name, 'index': cell_indices[right]}
                        if suffix_match:
                            location['suffix'] = suffix_match.group().strip()
                        items.append({'label': re.sub(r'\s+', ' ', clean_label), 'context': label, 'location': location})
        for index, paragraph in enumerate(root.iter(f'{{{HP}}}p')):
            para_count += 1
            text = paragraph_text(paragraph)
            if text.strip():
                titles.append(text.strip())
            markers = list(PLACEHOLDER.finditer(text))
            for marker in markers:
                key = marker.group(1).strip()
                items.append({'label': field_label(key) if key in STANDARD_FIELDS else key, 'context': text[:200],
                              'location': {'type': 'hwpx_placeholder', 'section': name, 'index': index, 'marker': marker.group()}})
            if markers:
                continue
            suffix_match = re.search(r'\((?:인|서명)\)\s*$', text)
            match = _PARA_FIELD.fullmatch(text[:suffix_match.start()] if suffix_match else text)
            if match:
                location = {'type': 'hwpx_para', 'section': name, 'index': index}
                if suffix_match:
                    location['suffix'] = suffix_match.group().strip()
                items.append({'label': match.group('label').strip(), 'context': text[:200],
                              'location': location})
    seen = set()
    unique = []
    for item in items:
        key = tuple(sorted(item['location'].items()))
        if key not in seen:
            unique.append(item); seen.add(key)
    return {'title': titles[0][:60] if titles else '', 'items': unique, 'paragraphs': para_count, 'tables': table_count}


def _set_text(node, value):
    for child in list(node):
        node.remove(child)
    lines = str(value).split('\n')
    node.text = lines[0]
    for line in lines[1:]:
        etree.SubElement(node, f'{{{HP}}}lineBreak').tail = line


def _write_paragraph(paragraph, value):
    nodes = paragraph.findall('hp:run/hp:t', NS)
    if not nodes:
        run = paragraph.find('hp:run', NS)
        if run is None:
            run = etree.SubElement(paragraph, f'{{{HP}}}run', charPrIDRef='0')
        nodes = [etree.SubElement(run, f'{{{HP}}}t')]
    _set_text(nodes[0], value)
    for node in nodes[1:]:
        _set_text(node, '')


def _replace_marker(paragraph, marker, value, start=None):
    nodes = paragraph.findall('hp:run/hp:t', NS)
    content = [''.join(node.itertext()) for node in nodes]
    start = ''.join(content).find(marker) if start is None else start
    if start < 0:
        raise ValueError('연결한 입력 위치의 표시자를 찾지 못했습니다. 양식을 다시 분석하세요.')
    end, offset, inserted = start + len(marker), 0, False
    for node, text in zip(nodes, content):
        next_offset = offset + len(text)
        if next_offset > start and offset < end:
            prefix = text[:max(0, start - offset)]
            suffix = text[max(0, end - offset):] if next_offset > end else ''
            _set_text(node, prefix + (value if not inserted else '') + suffix)
            inserted = True
        offset = next_offset


def fill(path: Path, fields: list, values: dict) -> bytes:
    entries, files = _read(path)
    roots = _roots(files)
    nodes = {name: {'hwpx_cell': list(root.iter(f'{{{HP}}}tc')), 'hwpx_para': list(root.iter(f'{{{HP}}}p'))} for name, root in roots.items()}
    modified = set()
    for field in fields:
        key = field.get('field_key')
        if not key or not str(values.get(key, '') or '').strip():
            continue
        value = str(values[key])
        location = field.get('location') or {}
        section, kind, index = location.get('section'), location.get('type'), location.get('index')
        node_kind = 'hwpx_para' if kind == 'hwpx_placeholder' else kind
        if section not in nodes or node_kind not in nodes[section] or type(index) is not int or not 0 <= index < len(nodes[section][node_kind]):
            raise ValueError('한글 양식의 입력 위치가 올바르지 않습니다. 매핑을 다시 확인하세요.')
        node = nodes[section][node_kind][index]
        suffix = location.get('suffix', '')
        if suffix not in ('', '(인)', '(서명)'):
            raise ValueError('한글 입력 위치의 서명 표시가 올바르지 않습니다.')
        if kind == 'hwpx_cell':
            paragraphs = _cell_paragraphs(node)
            if not paragraphs:
                raise ValueError('입력할 표 셀의 문단이 없습니다.')
            _write_paragraph(paragraphs[0], value + ('   ' + suffix if suffix else ''))
            for paragraph in paragraphs[1:]:
                _write_paragraph(paragraph, '')
        elif kind == 'hwpx_placeholder':
            marker = location.get('marker', '')
            if not isinstance(marker, str) or not PLACEHOLDER.fullmatch(marker):
                raise ValueError('한글 입력 표시자가 올바르지 않습니다.')
            positions = [match.start() for match in re.finditer(re.escape(marker), paragraph_text(node))]
            if not positions:
                raise ValueError('한글 입력 표시자를 찾지 못했습니다.')
            for position in reversed(positions):
                _replace_marker(node, marker, value, position)
        else:
            text = paragraph_text(node)
            pos = max(text.rfind(':'), text.rfind('：'))
            _write_paragraph(node, text[:pos + 1] + ' ' + value + ('   ' + suffix if suffix else ''))
        modified.add(section)
    for section in modified:
        root = roots[section]
        # Cached line positions describe the old blank contents; Hancom must lay out the new text.
        for cache in root.findall('.//hp:linesegarray', NS):
            cache.getparent().remove(cache)
        files[section] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    files['Preview/PrvText.txt'] = '\n'.join(paragraph_text(p) for root in roots.values() for p in root.iter(f'{{{HP}}}p')).encode('utf-8')
    output = BytesIO()
    with ZipFile(output, 'w') as archive:
        for entry in entries:
            if entry.filename == 'Preview/PrvImage.png':
                continue
            archive.writestr(entry, files[entry.filename])
        if 'Preview/PrvText.txt' not in [entry.filename for entry in entries]:
            archive.writestr('Preview/PrvText.txt', files['Preview/PrvText.txt'])
    return output.getvalue()


def editable_path(template):
    path = Path(template.source_path) if template.source_path else None
    if path and template.source_type == 'hwp':
        path = path.with_suffix('.hwpx')
    if not path or not path.is_file():
        from fastapi import HTTPException
        raise HTTPException(410, '보관된 한글 원본이 만료되었거나 없습니다. 원본 서식을 유지하려면 양식을 다시 업로드하세요.')
    return path


def project_docx(path, fields, values):
    """Text projection for legacy HTML/AI text review, not for native downloads or PDF."""
    from docx import Document
    doc = Document()
    _, files = _read(fill(path, fields, values))
    for root in _roots(files).values():
        for paragraph in root.iter(f'{{{HP}}}p'):
            text = paragraph_text(paragraph)
            if text.strip():
                doc.add_paragraph(text)
    return doc
