"""Private company seal assets and shared physical-size calculations."""
import base64
import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import HTTPException

MAX_BYTES = 3 * 1024 * 1024
MAX_PIXELS = 16_000_000


def normalize_seal(data: bytes) -> str:
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(400, "도장 이미지는 3MB 이하의 PNG 또는 JPEG 파일이어야 합니다.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in ('PNG', 'JPEG') or source.width * source.height > MAX_PIXELS:
                    raise ValueError('unsupported image')
                source.load()
                image = ImageOps.exif_transpose(source).convert('RGBA')
        bounds = image.getchannel('A').getbbox()
        if bounds is None:
            raise ValueError('empty image')
        image = image.crop(bounds)
        image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format='PNG')  # Re-encode; strip EXIF and other source metadata.
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(400, "올바른 PNG 또는 JPEG 도장 이미지를 선택하세요. 최대 1,600만 화소까지 지원합니다.")
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')


def company_seal(company):
    if not company or not company.seal_image:
        return None
    data = base64.b64decode(company.seal_image.split(',', 1)[1])
    with Image.open(BytesIO(data)) as image:
        scale = float(company.seal_size_mm) / max(image.size)
        return {'data': data, 'width_mm': image.width * scale, 'height_mm': image.height * scale}


def add_docx_seal(paragraph, seal, content_width_pt):
    """A non-reflowing drawing, behind the final '(인)' on its own signature line."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Mm, Pt

    width, height = Mm(seal['width_mm']), Mm(seal['height_mm'])
    marker_width = 17.5  # 10.5pt signature text, Korean character plus parentheses.
    paragraph.paragraph_format.right_indent = Pt(max(0, (width.pt - marker_width) / 2))
    paragraph.paragraph_format.space_before = Pt(max(0, (height.pt - 15.75) / 2) + 3)
    paragraph.paragraph_format.space_after = Pt(max(8, (height.pt - 15.75) / 2) + 3)
    shape = paragraph.add_run().add_picture(BytesIO(seal['data']), width=width, height=height)
    inline = shape._inline
    anchor = OxmlElement('wp:anchor')
    for key, value in {'distT': '0', 'distB': '0', 'distL': '0', 'distR': '0', 'simplePos': '0', 'relativeHeight': '0', 'behindDoc': '1', 'locked': '0', 'layoutInCell': '1', 'allowOverlap': '1'}.items():
        anchor.set(key, value)
    etree_child = OxmlElement('wp:simplePos')
    etree_child.set('x', '0'); etree_child.set('y', '0')
    anchor.append(etree_child)
    for tag, relative, offset in (('positionH', 'column', Pt(content_width_pt - width.pt)), ('positionV', 'line', Pt((15.75 - height.pt) / 2))):
        position = OxmlElement('wp:' + tag)
        position.set('relativeFrom', relative)
        value = OxmlElement('wp:posOffset'); value.text = str(int(offset))
        position.append(value); anchor.append(position)
    for tag in ('extent', 'effectExtent'):
        child = inline.find(qn('wp:' + tag))
        if child is not None:
            anchor.append(child)
    anchor.append(OxmlElement('wp:wrapNone'))
    for tag in ('docPr', 'cNvGraphicFramePr', 'a:graphic'):
        child = inline.find(qn(tag if ':' in tag else 'wp:' + tag))
        if child is not None:
            if tag == 'docPr':
                child.set('name', 'CompanySeal')
            anchor.append(child)
    inline.getparent().replace(inline, anchor)


def hwpx_picture(seal, content_width, identifier):
    from lxml import etree
    hp = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
    hc = 'http://www.hancom.co.kr/hwpml/2011/core'
    width, height = (round(seal[key] * 7200 / 25.4) for key in ('width_mm', 'height_mm'))
    picture = etree.Element(f'{{{hp}}}pic', id=str(identifier), zOrder='0', numberingType='PICTURE',
                            textWrap='BEHIND_TEXT', textFlow='BOTH_SIDES', lock='0', dropcapstyle='None',
                            href='', groupLevel='0', instid=str(identifier), reverse='0')

    def child(name, **attrs):
        ns, local = name.split(':') if ':' in name else ('hp', name)
        return etree.SubElement(picture, f'{{{hc if ns == "hc" else hp}}}{local}', {key: str(value) for key, value in attrs.items()})

    child('offset', x=0, y=0)
    child('orgSz', width=width, height=height)
    child('curSz', width=width, height=height)
    child('flip', horizontal=0, vertical=0)
    child('rotationInfo', angle=0, centerX=width//2, centerY=height//2, rotateimage=1)
    rendering = child('renderingInfo')
    for name in ('transMatrix', 'scaMatrix', 'rotMatrix'):
        etree.SubElement(rendering, f'{{{hc}}}{name}', e1='1', e2='0', e3='0', e4='0', e5='1', e6='0')
    child('hc:img', binaryItemIDRef='companySeal', bright=0, contrast=0, effect='REAL_PIC', alpha=0)
    rect = child('imgRect')
    for idx, (x, y) in enumerate(((0, 0), (width, 0), (width, height), (0, height))):
        etree.SubElement(rect, f'{{{hc}}}pt{idx}', x=str(x), y=str(y))
    child('imgClip', left=0, right=width, top=0, bottom=height)
    child('inMargin', left=0, right=0, top=0, bottom=0)
    child('imgDim', dimwidth=width, dimheight=height)
    child('effects')
    child('sz', width=width, widthRelTo='ABSOLUTE', height=height, heightRelTo='ABSOLUTE', protect=0)
    child('pos', treatAsChar=0, affectLSpacing=0, flowWithText=1, allowOverlap=1, holdAnchorAndSO=0,
          vertRelTo='PARA', horzRelTo='COLUMN', vertAlign='CENTER', horzAlign='LEFT', vertOffset=0,
          horzOffset=content_width-width)
    child('outMargin', left=0, right=0, top=0, bottom=0)
    child('shapeComment').text = '회사 날인'
    return picture


def quotation_seal_image(seal):
    """Excel drawings sit above cell text, so include the foreground marker."""
    import pymupdf
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from app.services.renderer import _register_font
    width, height = (seal[key] * 72 / 25.4 for key in ('width_mm', 'height_mm'))
    stream = BytesIO()
    page = canvas.Canvas(stream, pagesize=(width, height))
    page.drawImage(ImageReader(BytesIO(seal['data'])), 0, 0, width, height, mask='auto')
    page.setFont(_register_font(), 10.5)
    page.drawCentredString(width / 2, height / 2 - 3.5, '(인)')
    page.save()
    with pymupdf.open(stream=stream.getvalue(), filetype='pdf') as pdf:
        return pdf[0].get_pixmap(matrix=pymupdf.Matrix(4, 4), alpha=True).tobytes('png')
