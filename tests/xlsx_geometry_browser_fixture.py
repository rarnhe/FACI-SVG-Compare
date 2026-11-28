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
    # Independent vertical anchors must work even without a parseable off@y.
    # Picture lacks Y, shapes have stale or malformed Y values.
    y_attr='' if x==0 and y==0 else (' y="invalid"' if x==30 else f' y="{(y+49+x%17)*EMU}"')
    return (f'<a:xfrm rot="{rotation*60000}"><a:off x="{(x+80)*EMU}"{y_attr}/>'
            f'<a:ext cx="{w*EMU}" cy="{h*EMU}"/></a:xfrm>')


def anchored(x,y,w,h,child,anchor_scale=1):
    # Column markers intentionally disagree. Row anchors are exact,
    # including the first hidden row; only Y is reconciled.
    left=x+80
    top=40+y*anchor_scale
    right=left+w
    # Picture endpoints independently establish scale; other spans conflict.
    bottom=top+(h if x==0 and y==0 else h+7)*anchor_scale
    def mark(tag,px,py):
        col,dx=divmod(px,55)
        row,dy=divmod(round(py*EMU),20*EMU)
        return marker(tag,col,row+1,dx*EMU,dy)
    return (f'<xdr:twoCellAnchor editAs="oneCell">{mark("from",left,top)}'
            f'{mark("to",right,bottom)}{child}<xdr:clientData/></xdr:twoCellAnchor>')


def shape(name,kind,x,y,w,h,number,rotation=0,alt="",anchor_scale=1):
    tx=' txBox="1"' if kind=="textbox" else ""
    geom="ellipse" if kind=="ellipse" else "rect"
    text={"Label":"BODYv2","Cube":"R_Cube"}.get(name,name)
    fill='<a:solidFill><a:srgbClr val="E8D7AC"/></a:solidFill>'
    return anchored(x,y,w,h,
        f'<xdr:sp><xdr:nvSpPr><xdr:cNvPr id="{number}" name="{name}" descr="{alt}"/>'
        f'<xdr:cNvSpPr{tx}/></xdr:nvSpPr><xdr:spPr>{transform(x,y,w,h,rotation)}'
        f'<a:prstGeom prst="{geom}"/>{fill}'
        '<a:ln><a:solidFill><a:srgbClr val="164070"/></a:solidFill></a:ln></xdr:spPr>'
        f'<xdr:txBody><a:bodyPr/><a:p><a:r><a:t>{text}</a:t></a:r></a:p></xdr:txBody></xdr:sp>',anchor_scale)


def anchors(w,h):
    pic=image("Background").replace('<xdr:spPr/>',f'<xdr:spPr>{transform(0,0,w,h)}</xdr:spPr>')
    a=0.8 if w==420 else 1.25
    return "".join([
        anchored(0,0,w,h,pic,a),
        shape("Label","textbox",10,10,240,180,3,anchor_scale=a),
        shape("Square","rectangle",30,35,40,40,4,anchor_scale=a),
        shape("Rotated","rectangle",100,35,80,30,5,32,anchor_scale=a),
        shape("Cube","rectangle",30,110,70,50,6,alt="z=0.5x",anchor_scale=a),
        shape("Inside","ellipse",55,125,12,12,7,anchor_scale=a),
        shape("Partial","ellipse",94,125,12,12,8,anchor_scale=a),
        shape("Outside","ellipse",220,125,12,12,9,anchor_scale=a),
    ])


def main():
    with TemporaryDirectory() as tmp:
        base=Path(tmp)
        raw=fixture(base/"raw.xlsx",anchors(420,240),sheet_count=2,
                    second_anchors=anchors(280,200),media=True,
                    worksheet_xml='<sheetFormatPr defaultColWidth="50" defaultRowHeight="15"/>'
                                  '<cols><col min="1" max="5" hidden="1"/></cols>'
                                  '<sheetData><row r="1" hidden="1"/></sheetData>')
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
        # Use production catalog and static handlers with private fixture assets.
        assets=base/"assets";folder=assets/"BODYv2";folder.mkdir(parents=True)
        svg='<svg xmlns="http://www.w3.org/2000/svg" width="300" height="180" viewBox="0 0 300 180"><path id="curve" d="M10 60 L100 40 L200 90" stroke="#123456" stroke-width="2" fill="none"/><circle cx="100" cy="40" r="3" fill="#123456"/></svg>'
        for label,date,axis in [
            ("R_Cube","20260704101627","X"),("R_Cube","20260706101627","Z"),
            ("BODYv2","20260705101627","Y"),("Partial","20260707101627","Y"),
            ("R_Cube10","20260708101627","X"),("Cube","20260709101627","X"),
        ]:
            for suffix in ("PSD","1-3-Octave"):
                (folder/f"{label}_{date}_+{axis}_{suffix}.svg").write_text(svg,encoding="utf-8")
        for name in ("R_Cube_20260704101627_+X_PSD.csv","R_Cube_20260704101528_+X_Time.csv",
                     "R_Cube_20260704101626_+X_extra_Time.csv",
                     "R_Cube10_20260704101627_+X_wrong.csv","R_Cube_20260704101627_+Y_wrong.csv"):
            (folder/name).write_text("frequency,value\n1,2\n",encoding="utf-8")
        app.STATIC_DIR=base
        state={"workbook":book,"sheets":sheets,
               "manifest":service.build_cad_manifest(book,sheets,assets)}
        application=Application([
            (r"/viewer/cad-svg-catalog/([0-9]+)/([0-9]+)",app.EllipseSvgCatalogHandler,{"state":state}),
            (r"/viewer/assets/(.*)",app.NoCacheIndexHandler,{"path":str(assets)}),
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
