import test from 'node:test';
import assert from 'node:assert/strict';
import {
  INITIAL_REFERENCE_SPLIT, shapeLabel, selectOnButton,
  containsShape, shapeAncestors, selectionParts, fitSvgPair, fitSvgPane,
  clampMainDivider, clampReferenceSplit, pictureLayerScales, imageAspectRatio,
  requiredSvgRatio,canAddOverlay,SVG_COLORS,nextLegendColor,
  svgLegendName,svgSelectionKey,CUBOID_FACE_OPACITY,CUBOID_SELECTED_OPACITY,
  CAD_DRAW_ORDER,cadShapeRenderOrder,cadShapeZOffset,
  recolorablePaint,recolorCssDeclarations,recolorSvgMarkup,
} from '../cad_ui.mjs';

const shape=(kind,x,y,width,height,text,rotation=0)=>({
  type:'shape',shape_kind:kind,text,
  bounds_emu:{x,y,width,height,rotation},
});
const toRect=item=>item.bounds_emu;

test('operation menu selection: textbox never, ellipse right only, other shapes left',()=>{
  assert.equal(selectOnButton(shape('textbox',0,0,10,10,'BODYv2'),0),false);
  assert.equal(selectOnButton(shape('textbox',0,0,10,10,'BODYv2'),2),false);
  assert.equal(selectOnButton(shape('ellipse',0,0,10,10,'X'),0),false);
  assert.equal(selectOnButton(shape('ellipse',0,0,10,10,'X'),2),true);
  assert.equal(selectOnButton(shape('rectangle',0,0,10,10,'A'),0),true);
  assert.equal(selectOnButton(shape('rectangle',0,0,10,10,'A'),2),false);
  assert.equal(selectOnButton({type:'image'},0),false);
});

test('hover breadcrumb excludes workbook and sheet and bolds textbox',()=>{
  const body=shape('textbox',0,0,300,300,'BODYv2');
  const rectangle=shape('rectangle',30,-30,200,200,'20260704_SCN_B1');
  const dot=shape('ellipse',80,-80,10,10,'测点名称');
  const parts=selectionParts([body,rectangle,dot],dot,toRect);
  assert.deepEqual(parts,[
    {kind:'textbox',text:'BODYv2'},
    {kind:'rectangle',text:'20260704_SCN_B1'},
    {kind:'ellipse',text:'测点名称'},
  ]);
  assert.equal(parts.map(p=>p.text).join('·'),'BODYv2·20260704_SCN_B1·测点名称');
  assert.deepEqual(selectionParts([body,rectangle,dot],body,toRect),
    [{kind:'textbox',text:'BODYv2'}]);
  assert.deepEqual(selectionParts([body,rectangle,dot],rectangle,toRect),[
    {kind:'textbox',text:'BODYv2'},
    {kind:'rectangle',text:'20260704_SCN_B1'},
  ]);
});

test('no sibling, unrelated, ellipse parent, or equal-size duplicate enters the hierarchy',()=>{
  const body=shape('textbox',0,0,300,300,'BODYv2');
  const sibling=shape('rectangle',350,0,30,30,'SIBLING');
  const child=shape('rectangle',50,-50,40,40,'CHILD');
  const same=shape('rectangle',50,-50,40,40,'DUPLICATE');
  const ellipse=shape('ellipse',45,-45,50,50,'ELLIPSE');
  assert.equal(containsShape(sibling,child,toRect),false);
  assert.equal(containsShape(same,child,toRect),false);
  assert.equal(containsShape(ellipse,child,toRect),false);
  assert.deepEqual(shapeAncestors([body,sibling,child,same,ellipse],child,toRect),[body]);
});

test('rotated textbox containment uses rotated corners rather than axis-aligned bounding box',()=>{
  const outer=shape('textbox',0,0,100,50,'Rotated',Math.PI/4);
  const centered=shape('rectangle',47,-21,6,6,'inside');
  const outside=shape('rectangle',0,0,12,12,'outside');
  assert.equal(containsShape(outer,centered,toRect),true);
  assert.equal(containsShape(outer,outside,toRect),false);
});

test('circle containment accounts for reconstructed diagonal radius',()=>{
  const body=shape('textbox',0,0,100,100,'BODY');
  assert.equal(containsShape(body,shape('ellipse',44,-44,8,8,'inside'),toRect),true);
  assert.equal(containsShape(body,shape('ellipse',0,0,60,60,'edge'),toRect),false);
});

test('format label uses visible text with name fallback and safe whitespace',()=>{
  assert.equal(shapeLabel({text:'BODYv2\nSecond line'}),'BODYv2 Second line');
  assert.equal(shapeLabel({name:'Rectangle 4'}),'Rectangle 4');
  assert.equal(shapeLabel(null),'');
});

test('SVGs have equal widths, intrinsic aspect ratios, and fit inside BOTH panes',()=>{
  for (const [a,b,r1,r2] of [
    [{width:700,height:200},{width:700,height:650},0.5,1.4],
    [{width:260,height:65},{width:260,height:300},0.8,2.3],
    [{width:1100,height:580},{width:1100,height:250},0.2,1.5],
  ]) {
    const fit=fitSvgPair(a,b,r1,r2);
    assert.ok(fit.width<=a.width+1e-8 && fit.width<=b.width+1e-8);
    assert.ok(fit.heightA<=a.height+1e-8 && fit.heightB<=b.height+1e-8);
    assert.equal(fit.heightA,fit.width*r1);
    assert.equal(fit.heightB,fit.width*r2);
  }
});

test('right SVG split initially aligns with the fixed CAD center divider',()=>{
  assert.equal(INITIAL_REFERENCE_SPLIT,0.5);
});

test('both splitter clamps keep each area visible, including narrow displays',()=>{
  for (const width of [400,600,1600]) {
    const left=clampMainDivider(-100,width);
    const right=clampMainDivider(width+200,width);
    assert.ok(left>0 && right<width-8);
    assert.ok(right>left);
  }
  for (const height of [180,500,1200]) {
    const min=clampReferenceSplit(-100,height);
    const max=clampReferenceSplit(height+100,height);
    assert.ok(min>0 && max<1);
    assert.ok(max>min);
  }
});


test('two XLSX images preserve native ratios and share one CAD world width',()=>{
  const sizes=pictureLayerScales(
    [{width:1400,height:500},{width:900,height:900}],
    [0.5,0.75],
  );
  assert.equal(sizes[0].width,1400);
  assert.equal(sizes[1].width,1400);
  assert.equal(sizes[0].height,700);
  assert.equal(sizes[1].height,1050);
  assert.equal(sizes[0].x,1);
  assert.ok(Math.abs(sizes[1].x-1400/900)<1e-10);
  assert.ok(Math.abs(sizes[0].y-700/500)<1e-10);
  assert.ok(Math.abs(sizes[1].y-1050/900)<1e-10);
});

test('divider clamps stop before any displayed SVG would need horizontal scrolling',()=>{
  const rightWidth=485;
  const x=clampMainDivider(9999,1500,8,rightWidth);
  assert.ok(1500-8-x>=rightWidth);
  const topHeight=120,bottomHeight=300;
  const min=clampReferenceSplit(-100,700,8,topHeight,bottomHeight);
  const max=clampReferenceSplit(9999,700,8,topHeight,bottomHeight);
  assert.ok(min*(700-8)+1e-8>=topHeight);
  assert.ok((1-max)*(700-8)+1e-8>=bottomHeight);
});


test('all seventeen palette colors are unique, including rollover',()=>{
  assert.equal(SVG_COLORS.length,17);
  assert.equal(new Set(SVG_COLORS).size,17);
  assert.equal(nextLegendColor(0),'#4F99CF');
  assert.equal(nextLegendColor(1),'#E41A1C');
  assert.equal(nextLegendColor(17),'#4F99CF');
});

test('legend deduplicates before SVG loads and also during pending loads',()=>{
  const active=new Map(),pending=new Set();
  assert.equal(canAddOverlay(active,pending,'B1_20260704101627_+X'),true);
  pending.add('B1_20260704101627_+X');
  assert.equal(canAddOverlay(active,pending,'B1_20260704101627_+X'),false);
  pending.clear();
  active.set('B1_20260704101627_+X',{});
  assert.equal(canAddOverlay(active,pending,'B1_20260704101627_+X'),false);
  active.delete('B1_20260704101627_+X');
  assert.equal(canAddOverlay(active,pending,'B1_20260704101627_+X'),true);
});

test('each SVG pane maximizes width or height independently without overflow',()=>{
  assert.equal(requiredSvgRatio(0.4,[0.5,0.3]),0.5);
  assert.equal(requiredSvgRatio(0.4,[0.8,0.3]),0.8);
  const a=fitSvgPane(800,250,0.8);
  assert.equal(a.width,312.5);
  assert.equal(a.height,250);
  const b=fitSvgPane(800,650,0.5);
  assert.equal(b.width,800);
  assert.equal(b.height,400);
  assert.notEqual(a.width,b.width);
  for(const [width,height,ratio] of [[100,30,2],[800,400,0.1],[550,150,0.8]]) {
    const fit=fitSvgPane(width,height,ratio);
    assert.ok(fit.width<=width && fit.height<=height);
    assert.ok(Math.abs(fit.height/fit.width-ratio)<1e-9);
  }
});


test('SVG CSS recoloring preserves transparent regions and existing line geometry',()=>{
  assert.equal(recolorablePaint('#2C3E50'),true);
  assert.equal(recolorablePaint('currentColor'),true);
  assert.equal(recolorablePaint('none'),false);
  assert.equal(recolorablePaint('transparent'),false);
  assert.equal(recolorablePaint('url(#gradient)'),false);
  const initial='.plot{fill:none;stroke:#123456;stroke-width:2;stroke-dasharray:3 2}';
  const colored=recolorCssDeclarations(initial,'#E41A1C');
  assert.equal(colored,'.plot{fill:none;stroke:#E41A1C;stroke-width:2;stroke-dasharray:3 2}');
  assert.equal(recolorCssDeclarations('fill:url(#p);stroke:transparent', '#4F99CF'),
    'fill:url(#p);stroke:transparent');
  assert.throws(()=>recolorCssDeclarations('stroke:red','red'),RangeError);
});

test('SVG markup recolor runs on browser XML nodes without creating painted backgrounds',()=>{
  const beforeParser=globalThis.DOMParser,beforeSerializer=globalThis.XMLSerializer;
  class MockNode {
    constructor(localName,attributes={},textContent='') {
      this.localName=localName;
      this.attributes={...attributes};
      this.textContent=textContent;
    }
    hasAttribute(key){return Object.hasOwn(this.attributes,key);}
    getAttribute(key){return this.attributes[key]??null;}
    setAttribute(key,value){this.attributes[key]=value;}
  }
  const root=new MockNode('svg',{viewBox:'0 0 40 20'});
  const plot=new MockNode('path',{
    stroke:'#123456',fill:'none',style:'stroke:#212121;stroke-width:1.5',
  });
  const blank=new MockNode('rect',{fill:'none',stroke:'none'});
  const gradient=new MockNode('path',{fill:'url(#gradient)',stroke:'transparent'});
  const css=new MockNode('style',{},'.line{stroke:#555555;fill:none}');
  const nodes=[root,plot,blank,gradient,css];
  globalThis.DOMParser=class {
    parseFromString(){return {
      documentElement:root,
      getElementsByTagName:name=>{
        if(name==='*')return nodes;
        if(name==='style')return [css];
        return [];
      },
    };}
  };
  globalThis.XMLSerializer=class {
    serializeToString(){
      return JSON.stringify({root:root.attributes,plot:plot.attributes,
        blank:blank.attributes,gradient:gradient.attributes,css:css.textContent});
    }
  };
  try {
    const result=JSON.parse(recolorSvgMarkup('<svg/>','#4F99CF'));
    assert.equal(result.plot.stroke,'#4F99CF');
    assert.equal(result.plot.fill,'none');
    assert.equal(result.plot.style,'stroke:#4F99CF;stroke-width:1.5');
    assert.equal(result.blank.fill,'none');
    assert.equal(result.blank.stroke,'none');
    assert.equal(result.gradient.fill,'url(#gradient)');
    assert.equal(result.gradient.stroke,'transparent');
    assert.equal(result.css,'.line{stroke:#4F99CF;fill:none}');
    assert.equal(result.root.fill,undefined);
  } finally {
    if(beforeParser===undefined)delete globalThis.DOMParser;
    else globalThis.DOMParser=beforeParser;
    if(beforeSerializer===undefined)delete globalThis.XMLSerializer;
    else globalThis.XMLSerializer=beforeSerializer;
  }
});


test('SVG legend shows folder_sheet_rectangle-or-sensor_axis, never date',()=>{
  const inside={folder:'BODYv2',sheet:'fab',target_kind:'rectangle',
    identifier:'20260704_SCN_B1',ellipse:'测点名称'};
  assert.equal(svgLegendName(inside,'Y'),'BODYv2_fab_20260704_SCN_B1_+Y');
  const outside={folder:'BODYv2',sheet:'subfab',target_kind:'ellipse',
    identifier:'测点名称'};
  assert.equal(svgLegendName(outside,'Z'),'BODYv2_subfab_测点名称_+Z');
  const key1=svgSelectionKey(inside,'20260704101627','Y');
  const key2=svgSelectionKey(inside,'20260705101627','Y');
  assert.notEqual(key1,key2);
  assert.equal(svgSelectionKey(inside,'20260704101627','Y'),key1);
  const map=new Map([[key1,{}]]);
  assert.equal(canAddOverlay(map,new Set(),key2),true);
  assert.equal(canAddOverlay(map,new Set(),key1),false);
});

test('cuboid uses 43% normal opacity and 50% selected opacity',()=>{
  assert.equal(CUBOID_FACE_OPACITY,0.43);
  assert.equal(CUBOID_SELECTED_OPACITY,0.50);
  assert.ok(CUBOID_SELECTED_OPACITY>CUBOID_FACE_OPACITY);
  assert.ok(CUBOID_SELECTED_OPACITY<1);
});


test('CAD shape Z offsets keep textbox behind flat rectangles and ellipses',()=>{
  assert.equal(cadShapeZOffset('textbox'),-1);
  assert.equal(cadShapeZOffset('rectangle'),0);
  assert.equal(cadShapeZOffset('ellipse'),1);
  assert.equal(cadShapeZOffset('other'),0);
  // Existing local heights remain valid, including lifted sensors.
  assert.ok(cadShapeZOffset('textbox')+0.5 < cadShapeZOffset('rectangle'));
  assert.ok(cadShapeZOffset('ellipse')+0.5 > cadShapeZOffset('rectangle'));
});

test('CAD transparent render order is stable for any XLSX enumeration order',()=>{
  assert.ok(CAD_DRAW_ORDER.image<CAD_DRAW_ORDER.textbox);
  assert.ok(CAD_DRAW_ORDER.textbox<CAD_DRAW_ORDER.rectangle);
  assert.ok(CAD_DRAW_ORDER.rectangle<CAD_DRAW_ORDER.ellipse);
  assert.ok(CAD_DRAW_ORDER.textbox<CAD_DRAW_ORDER.other);
  const names=['ellipse','textbox','rectangle','textbox','ellipse','other'];
  assert.deepEqual(names.slice().sort((a,b)=>cadShapeRenderOrder(a)-cadShapeRenderOrder(b)),
    ['textbox','textbox','other','rectangle','ellipse','ellipse']);
  assert.equal(cadShapeRenderOrder('shape-unknown'),CAD_DRAW_ORDER.other);
});


test('embedded PNG/JPEG backgrounds and XLSX shapes use identical x/y scale factors',()=>{
  // XLSX image anchors define the local origin; decoded raster dimensions
  // determine the picture's display aspect ratio.
  const bounds=[{width:1200,height:480},{width:600,height:300}];
  const decodedImages=[{naturalWidth:2000,naturalHeight:1200},
    {naturalWidth:600,naturalHeight:900}];
  const aspects=decodedImages.map((image,i)=>imageAspectRatio(image,bounds[i]));
  assert.deepEqual(aspects,[0.6,1.5]); // NOT the XLSX anchors' ratios.
  const scales=pictureLayerScales(bounds,aspects);
  assert.deepEqual(scales.map(s=>s.width),[1200,1200]);
  assert.deepEqual(scales.map(s=>s.height),[720,1800]);
  for(let i=0;i<2;i++){
    const pic=bounds[i],display=scales[i];
    // Any shape's local offset transforms in exactly the same coordinate
    // system as its SVG background, so relative placements never drift.
    const x=pic.width/4,y=pic.height/3;
    const shape={x:x*display.x,y:y*display.y,
                 width:pic.width/8*display.x,height:pic.height/8*display.y};
    assert.ok(Math.abs(shape.x/display.width-0.25)<1e-9);
    assert.ok(Math.abs(shape.y/display.height-1/3)<1e-9);
    assert.ok(Math.abs(shape.width/display.width-1/8)<1e-9);
    assert.ok(Math.abs(shape.height/display.height-1/8)<1e-9);
    assert.ok(Math.abs(display.height/display.width-aspects[i])<1e-9);
  }
});


test('imageAspectRatio selects decoded XLSX picture rather than drawing anchor size',()=>{
  const anchor={width:1400,height:700}; // anchor ratio=0.5
  assert.equal(imageAspectRatio({naturalWidth:1920,naturalHeight:1080},anchor),1080/1920);
  assert.equal(imageAspectRatio({width:640,height:480},anchor),480/640);
  assert.equal(imageAspectRatio({naturalWidth:0,naturalHeight:0},anchor),0.5);
  assert.equal(imageAspectRatio(null,anchor),0.5);
  assert.equal(imageAspectRatio(null,{width:0,height:100}),1);
  assert.equal(imageAspectRatio({naturalWidth:NaN,naturalHeight:20},anchor),0.5);
});

test('shape and raster background share exact corner alignment at different aspect ratios',()=>{
  const anchors=[{width:1600,height:900},{width:800,height:800}];
  const decoded=[{naturalWidth:1600,naturalHeight:600},
                 {naturalWidth:1200,naturalHeight:1800}];
  const scales=pictureLayerScales(anchors,
    decoded.map((im,i)=>imageAspectRatio(im,anchors[i])));
  // Two pictures maintain a common displayed width without squashing pixels.
  assert.equal(scales[0].width,1600);
  assert.equal(scales[1].width,1600);
  assert.equal(scales[0].height,600);
  assert.equal(scales[1].height,2400);
  for(let i=0;i<2;i++){
    const {width:w,height:h}=anchors[i],factor=scales[i];
    // A rectangle exactly matching the XLSX picture anchor must match
    // all four displayed raster corners, not just its top-left.
    const corners=[[0,0],[w,0],[w,h],[0,h]];
    const scaled=corners.map(([x,y])=>[x*factor.x,y*factor.y]);
    assert.deepEqual(scaled,[[0,0],[factor.width,0],
      [factor.width,factor.height],[0,factor.height]]);
    const point={x:0.6*w,y:0.4*h};
    const aligned=[point.x*factor.x,point.y*factor.y];
    assert.ok(Math.abs(aligned[0]/factor.width-0.6)<1e-9);
    assert.ok(Math.abs(aligned[1]/factor.height-0.4)<1e-9);
  }
});
