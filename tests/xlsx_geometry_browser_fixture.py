"""Real workbook/HTTP fixture for geometric fidelity; expected dimensions live in JS."""
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import base64
import sys

from tornado.ioloop import IOLoop
from tornado.netutil import bind_sockets
from tornado.httpserver import HTTPServer
from tornado.web import Application

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
sys.path.insert(0,str(ROOT))
app=import_module(f"{ROOT.name}.__main__")
spatial=import_module(f"{ROOT.name}.xlsx_spatial")
service=import_module(f"{ROOT.name}.cad_service")
from tests.test_xlsx_spatial import fixture, marker, image

EMU=9525
PNG=[
    "iVBORw0KGgoAAAANSUhEUgAAAFQAAAAgCAIAAAADushBAAAAQ0lEQVR4nO3PIQEAIADAMKB/UxQCTwzEvgT/3OcO1fod8FPzquZVzauaVzWval7VvKp5VfOq5lXNq5pXNa9qXtW86gElBwMRsCVbqQAAAABJRU5ErkJggg==",
    "iVBORw0KGgoAAAANSUhEUgAAACgAAAA8CAIAAACb22+3AAAAOklEQVR4nO3NIQEAMAgAsPP+TVEIPB0wmK3AIqvfhX+yisVisVgsFovFYrFYLBaLxWKxWCwWi8XipQGgZgNJgo88eAAAAABJRU5ErkJggg==",
]


def transform(x,y,w,h,rotation=0):
    # Nonzero common sheet origin tests actual relative-coordinate subtraction.
    return (f'<a:xfrm rot="{rotation*60000}"><a:off x="{(x+80)*EMU}" y="{(y+40)*EMU}"/>'
            f'<a:ext cx="{w*EMU}" cy="{h*EMU}"/></a:xfrm>')


def anchored(x,y,w,h,child):
    # Simulate a workbook saved with font-dependent columns that do not
    # match the 7px fallback MDW. Deliberately exaggerate horizontal marker
    # spacing; the saved DrawingML is the independent exact geometry.
    left=x+80
    top=y+40
    right=left+w
    bottom=top+h
    def mark(tag,px,py):
        col,dx=divmod(px,55)
        row,dy=divmod(py,20)
        return marker(tag,col,row,dx*EMU,dy*EMU)
    return (f'<xdr:twoCellAnchor editAs="oneCell">{mark("from",left,top)}'
            f'{mark("to",right,bottom)}{child}<xdr:clientData/></xdr:twoCellAnchor>')


def shape(name,kind,x,y,w,h,number,rotation=0,alt=""):
    tx=' txBox="1"' if kind=="textbox" else ""
    geom="ellipse" if kind=="ellipse" else "rect"
    return anchored(x,y,w,h,
        f'<xdr:sp><xdr:nvSpPr><xdr:cNvPr id="{number}" name="{name}" descr="{alt}"/>'
        f'<xdr:cNvSpPr{tx}/></xdr:nvSpPr><xdr:spPr>{transform(x,y,w,h,rotation)}'
        f'<a:prstGeom prst="{geom}"/><a:solidFill><a:srgbClr val="E8D7AC"/></a:solidFill>'
        '<a:ln><a:solidFill><a:srgbClr val="164070"/></a:solidFill></a:ln></xdr:spPr>'
        f'<xdr:txBody><a:bodyPr/><a:p><a:r><a:t>{name}</a:t></a:r></a:p></xdr:txBody></xdr:sp>')


def anchors(w,h):
    pic=image("Background").replace('<xdr:spPr/>',f'<xdr:spPr>{transform(0,0,w,h)}</xdr:spPr>')
    return "".join([
        anchored(0,0,w,h,pic),
        shape("Label","textbox",10,10,240,180,3),
        shape("Square","rectangle",30,35,40,40,4),
        shape("Rotated","rectangle",100,35,80,30,5,32),
        shape("Cube","rectangle",30,110,70,50,6,alt="z=0.5x"),
        shape("Inside","ellipse",55,125,12,12,7),
        shape("Partial","ellipse",94,125,12,12,8),
        shape("Outside","ellipse",220,125,12,12,9),
    ])


def main():
    with TemporaryDirectory() as tmp:
        base=Path(tmp)
        raw=fixture(base/"raw.xlsx",anchors(420,240),sheet_count=2,
                    second_anchors=anchors(280,200),media=True,
                    worksheet_xml='<sheetFormatPr defaultColWidth="10" defaultRowHeight="15"/><sheetData/>')
        book=base/"geometry.xlsx"
        # Replace fixture dummy raster with independently sized real PNGs.
        with ZipFile(raw) as src, ZipFile(book,"w") as dst:
            for name in src.namelist():
                if name=="xl/media/image1.png":
                    continue
                data=src.read(name)
                if name=="xl/drawings/_rels/drawing2.xml.rels":
                    data=data.replace(b"image1.png",b"image2.png")
                dst.writestr(name,data)
            for i,png in enumerate(PNG,1):
                dst.writestr(f"xl/media/image{i}.png",base64.b64decode(png))
        sheets=spatial.parse_xlsx(book)
        spatial.validate_two_layer_workbook(sheets)
        state={"workbook":book,"sheets":sheets,
               "manifest":service.build_cad_manifest(book,sheets,base)}
        application=Application([
            (r"/viewer/cad-layout\.json",app.CadManifestHandler,{"state":state}),
            (r"/viewer/cad-image/([0-9]+)/([0-9]+)",app.CadImageHandler,{"state":state}),
            (r"/viewer/(.*)",app.NoCacheIndexHandler,{"path":str(ROOT)}),
        ])
        sockets=bind_sockets(0,address="127.0.0.1")
        server=HTTPServer(application);server.add_sockets(sockets)
        print(f"GEOMETRY_PORT={sockets[0].getsockname()[1]}",flush=True)
        IOLoop.current().start()


if __name__=="__main__":
    main()
