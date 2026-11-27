import test from 'node:test';
import assert from 'node:assert/strict';
import {
  INITIAL_REFERENCE_SPLIT, shapeLabel, selectOnButton,
  containsShape, shapeAncestors, selectionParts, fitSvgPair, fitSvgPane,
  clampMainDivider, clampReferenceSplit, pictureLayerScales, imageAspectRatio,
  requiredSvgRatio,canAddOverlay,SVG_COLORS,nextLegendColor,
  svgLegendName,svgSelectionKey,CUBOID_FACE_OPACITY,CUBOID_SELECTED_OPACITY,
  CAD_DRAW_ORDER,cadShapeRenderOrder,cadShapeZOffset,
  textboxFont,layoutTextboxText,
  recolorablePaint,recolorCssDeclarations,recolorSvgMarkup,
  SVG_COLOR_CHOICES,SVG_LINE_WIDTHS,SVG_LINE_TYPES,mergeSvgStyle,svgCurveNodes,restyleSvgMarkup,
  cadOutlineSpec,recolorOctaveGeometry,octavePointScale,octavePointNodes,octaveLineNodes,
  cadOutlineSegments,cadOutlineHaloColor,rectangleHasAltText,planarOutlineVertices,
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


test('seven named palette colors are unique, including rollover',()=>{
  assert.deepEqual(SVG_COLOR_CHOICES.map(c=>c.label),['红色','橙色','黄色','绿色','蓝色','紫色','灰色']);
  assert.equal(SVG_COLORS.length,7);
  assert.equal(new Set(SVG_COLORS).size,7);
  assert.equal(nextLegendColor(0),'#E41A1C');
  assert.equal(nextLegendColor(1),'#FF7F00');
  assert.equal(nextLegendColor(7),'#E41A1C');
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

test('cuboid uses 93% normal opacity and 100% selected opacity',()=>{
  assert.equal(CUBOID_FACE_OPACITY,0.93);
  assert.equal(CUBOID_SELECTED_OPACITY,1.00);
  assert.ok(CUBOID_SELECTED_OPACITY>CUBOID_FACE_OPACITY);
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


test('textbox font maps DrawingML point sizes and styles into canvas CSS',()=>{
  const font=textboxFont({
    font_family:'Aptos Display',east_asian_font:'Microsoft YaHei',
    font_size_pt:18,bold:true,italic:true,
  });
  assert.equal(font,'italic bold 24px "Aptos Display", "Microsoft YaHei", sans-serif');
  assert.ok(textboxFont({font_size_pt:11}).includes('14.667px'));
  // A malicious/unusual XLSX family string never breaks CSS font quoting.
  assert.ok(!textboxFont({font_family:'test"broken',font_size_pt:11})
    .includes('"broken'));
});

test('DrawingML text uses exact inset, vertical anchor, font runs and centering',()=>{
  const first={text:'AB',font_size_pt:12,color:'#FF0000'};
  const second={text:'测',font_size_pt:12,color:'#00AA00'};
  const layout={
    anchor:'middle',
    insets_px:{left:4,right:6,top:2,bottom:2},
    paragraphs:[{align:'center',runs:[first,second]}],
  };
  const output=layoutTextboxText(layout,100,70,()=>10);
  assert.deepEqual(output.map(({text,x,y,run})=>({text,x,y,color:run.color})),[
    {text:'AB',x:34,y:25,color:'#FF0000'},
    {text:'测',x:54,y:25,color:'#00AA00'},
  ]);
});

test('textbox line wraps within bounds and right-aligns second paragraph',()=>{
  const r1={text:'ABCDE',font_size_pt:12};
  const r2={text:'XY',font_size_pt:12};
  const result=layoutTextboxText({
    anchor:'top',insets_px:{left:2,right:2,top:3,bottom:3},
    paragraphs:[{align:'left',runs:[r1]},{align:'right',runs:[r2]}],
  },35,120,()=>10);
  assert.deepEqual(result.map(c=>[c.text,c.x,c.y]),[
    ['ABC',2,3],['DE',2,23],['XY',13,43],
  ]);
});

test('textbox explicit newline and bottom anchor preserve original position',()=>{
  const run={text:'A\nB',font_size_pt:12};
  const out=layoutTextboxText({
    anchor:'bottom',
    insets_px:{left:0,right:0,top:4,bottom:6},
    paragraphs:[{align:'left',runs:[run]}],
  },100,90,()=>10);
  assert.deepEqual(out.map(x=>[x.text,x.y]),[['A',44],['B',64]]);
});


test('SVG legend independent styles, original restoration and strict validation',()=>{
  const base=mergeSvgStyle({color:'#4F99CF'});
  assert.deepEqual(base,{color:'#4F99CF',lineWidth:null,lineStyle:null});
  const width=mergeSvgStyle(base,{lineWidth:3.5});
  const dash=mergeSvgStyle(width,{lineStyle:'8 5'});
  assert.deepEqual(mergeSvgStyle(dash,{color:'#E41A1C'}),
    {color:'#E41A1C',lineWidth:3.5,lineStyle:'8 5'});
  assert.deepEqual(mergeSvgStyle(dash,{lineWidth:null,lineStyle:null}),base);
  assert.deepEqual(SVG_LINE_WIDTHS,[2,2.5,3,3.5,4]);
  assert.equal(SVG_LINE_TYPES.length,4);
  assert.ok(!SVG_LINE_TYPES.some(t=>t.label==='原始线型'));
  assert.throws(()=>mergeSvgStyle(base,{lineWidth:6}),RangeError);
  assert.throws(()=>mergeSvgStyle(base,{lineWidth:7}),RangeError);
  assert.ok(!SVG_LINE_TYPES.some(t=>t.label==='点线'));
  for(const lineWidth of SVG_LINE_WIDTHS) assert.equal(mergeSvgStyle(base,{lineWidth}).lineWidth,lineWidth);
  assert.throws(()=>mergeSvgStyle(base,{lineWidth:5}),RangeError);
  assert.throws(()=>mergeSvgStyle(base,{lineWidth:1.5}),RangeError);
  assert.throws(()=>mergeSvgStyle(base,{lineStyle:'1 5'}),RangeError);
  assert.throws(()=>mergeSvgStyle(base,{lineWidth:-1}),RangeError);
  assert.throws(()=>mergeSvgStyle(base,{lineStyle:'bad'}),RangeError);
  assert.throws(()=>mergeSvgStyle(base,{color:'red'}),RangeError);
});

function svgFixture() {
  class Node {
    constructor(localName,attrs={},parentElement=null,textContent=''){
      Object.assign(this,{localName,attrs:{...attrs},parentElement,textContent});
    }
    getAttribute(key){return this.attrs[key]??null;}
    hasAttribute(key){return Object.hasOwn(this.attrs,key);}
    setAttribute(key,value){this.attrs[key]=value;}
    matches(selector){return selector.startsWith('.') &&
      (this.attrs.class||'').split(/\s+/).includes(selector.slice(1));}
  }
  const root=new Node('svg');
  const group=new Node('g',{id:'curve_1',stroke:'#111111'},root);
  const curve=new Node('path',{d:'M0 0 L5 8 L9 3',fill:'none',style:'stroke-width:1;stroke-dasharray:2 3'},group);
  const cssCurve=new Node('polyline',{class:'series',points:'0,0 1,2 3,1'},root);
  const none=new Node('path',{class:'series',stroke:'none',style:'stroke:none !important',d:'M0 0 L1 2 L3 4'},root);
  const axis=new Node('g',{id:'axis_1'},root);
  const axisPath=new Node('path',{class:'series',stroke:'#aaa',d:'M0 0 L1 2 L3 4'},axis);
  const defs=new Node('defs',{},root);
  const protectedPath=new Node('path',{class:'series',stroke:'#aaa'},defs);
  const css=new Node('style',{},root,'.series { stroke: #123456 !important; stroke-width: 4; }');
  const nodes=[root,group,curve,cssCurve,none,axis,axisPath,defs,protectedPath,css];
  return {curve,cssCurve,none,axisPath,protectedPath,xml:{
    documentElement:root,
    getElementsByTagName:name=>name==='*'?nodes:name==='style'?[css]:[],
  }};
}
test('curve detection supports inherited and CSS strokes; excludes axes and definitions',()=>{
  const {xml,curve,cssCurve}=svgFixture();
  assert.deepEqual(svgCurveNodes(xml),[curve,cssCurve]);
});
test('restyle sets inline overrides on curves, preserves auxiliary geometry and restores originals',()=>{
  const previousParser=globalThis.DOMParser,previousSerializer=globalThis.XMLSerializer;
  let fixture;
  globalThis.DOMParser=class {parseFromString(){fixture=svgFixture();return fixture.xml;}};
  globalThis.XMLSerializer=class {serializeToString(){return JSON.stringify(
    Object.fromEntries(['curve','cssCurve','none','axisPath','protectedPath'].map(key=>[key,fixture[key].attrs])));}};
  try {
    const style=mergeSvgStyle({color:'#4F99CF'},{lineWidth:4,lineStyle:'8 5'});
    const out=JSON.parse(restyleSvgMarkup('<svg/>',style));
    assert.match(out.curve.style,/stroke-width:4 !important/);
    assert.match(out.cssCurve.style,/stroke-dasharray:32 20 !important/);
    assert.equal(out.curve.d,'M0 0 L5 8 L9 3');
    assert.equal(out.curve.fill,'none');
    assert.equal(out.axisPath.style,undefined);
    assert.equal(out.protectedPath.style,undefined);
    assert.equal(out.none.style,'stroke:none !important');
    const original=JSON.parse(restyleSvgMarkup('<svg/>',mergeSvgStyle(style,{lineWidth:null,lineStyle:null})));
    assert.equal(original.curve.style,'stroke-width:1;stroke-dasharray:2 3;stroke:#4F99CF !important');
    assert.equal(original.cssCurve.style,'stroke:#4F99CF !important');
    const solid=JSON.parse(restyleSvgMarkup('<svg/>',mergeSvgStyle(style,{lineStyle:'none'})));
    assert.match(solid.curve.style,/stroke-dasharray:none !important/);
  } finally {
    if(previousParser===undefined) delete globalThis.DOMParser; else globalThis.DOMParser=previousParser;
    if(previousSerializer===undefined) delete globalThis.XMLSerializer; else globalThis.XMLSerializer=previousSerializer;
  }
});
test('unmarked open polyline/path fallback avoids single segments and closed paths',()=>{
  const nodes=['M0 0 L1 2 L3 4','M0 0 L1 2','M0 0 L1 2 L3 4 Z'].map(d=>({
    localName:'path',getAttribute:key=>key==='d'?d:key==='stroke'?'red':null,
    hasAttribute:key=>key==='stroke',
  }));
  const xml={getElementsByTagName:name=>name==='*'?nodes:[]};
  assert.deepEqual(svgCurveNodes(xml),[nodes[0]]);
});


test('octave recolors all separate lines and filled points without changing unpainted channels',()=>{
  const {xml,curve,cssCurve,axisPath,protectedPath}=svgFixture();
  class Node {
    constructor(localName,attrs={},parentElement=null){Object.assign(this,{localName,attrs:{...attrs},parentElement});}
    getAttribute(key){return this.attrs[key]??null;}
    hasAttribute(key){return Object.hasOwn(this.attrs,key);}
    setAttribute(key,value){this.attrs[key]=value;}
    matches(selector){return selector==='.dot' && this.attrs.class==='dot';}
  }
  const root=xml.documentElement, defs=new Node('defs',{},root);
  const glyph=new Node('path',{id:'dotshape',d:'M0 0 L1 0 L1 1 Z',fill:'black'},defs);
  const point=new Node('circle',{fill:'#123456',stroke:'none'},root);
  const ellipse=new Node('ellipse',{},root);
  const poly=new Node('polygon',{fill:'none',stroke:'black'},root);
  const separate=new Node('line',{stroke:'black'},root);
  const use=new Node('use',{'xlink:href':'#dotshape',fill:'black'},root);
  const background=new Node('rect',{fill:'white'},root);
  const text=new Node('g',{id:'text_1'},root);
  const textUse=new Node('use',{fill:'black'},text);
  const clip=new Node('clipPath',{},defs);
  const clipPath=new Node('path',{fill:'black',d:'M0 0 L2 2 Z'},clip);
  const css=new Node('style',{},root);css.textContent='.dot {fill:#222222; stroke:none}';
  const cssPoint=new Node('circle',{class:'dot'},root);
  const base=xml.getElementsByTagName;
  xml.getElementsByTagName=name=>name==='*'?[...base(name),defs,glyph,point,ellipse,poly,separate,use,background,text,textUse,clip,clipPath,cssPoint,css]:name==='style'?[...base(name),css]:[];
  recolorOctaveGeometry(xml,'#E41A1C');
  for(const n of [curve,cssCurve,axisPath,separate,poly]) assert.match(n.attrs.style,/stroke:#E41A1C !important/);
  for(const n of [point,ellipse,use,glyph,cssPoint]) assert.match(n.attrs.style,/fill:#E41A1C !important/);
  assert.doesNotMatch(point.attrs.style,/stroke:/);
  assert.doesNotMatch(poly.attrs.style,/fill:/);
  for(const n of [background,textUse,clipPath,protectedPath]) assert.equal(n.attrs.style,undefined);
});

test('outline uses Excel color and width; equipment without border still has a visible contrast outline',()=>{
  assert.deepEqual(cadOutlineSpec({shape_kind:'rectangle',colors:{outline:'#5B9BD5'},outline_width_px:3}),{color:'#5B9BD5',width:3});
  assert.deepEqual(cadOutlineSpec({shape_kind:'ellipse',colors:{outline:'#123456'},outline_width_px:0.5}),{color:'#123456',width:2});
  assert.deepEqual(cadOutlineSpec({shape_kind:'rectangle',colors:{outline:'无/透明',fill:'#FFFFFF'}}),{color:'#7a7a7a',width:2});
  assert.equal(cadOutlineSpec({shape_kind:'textbox',colors:{outline:'无/透明'}}),null);
  assert.equal(cadOutlineSpec({shape_kind:'rectangle',colors:{outline:'#123456'},outline_width_px:10}).width,5);
});


test('octave point size is proportional to original line width and resets without accumulation',()=>{
  const {xml,curve,cssCurve}=svgFixture();
  curve.attrs.style='stroke-width:2';
  cssCurve.attrs.style='stroke-width:2';
  const lines=octaveLineNodes(xml);
  assert.deepEqual(lines,[curve,cssCurve]);
  assert.equal(octavePointScale(xml,lines,3),1.5);
  assert.equal(octavePointScale(xml,lines,4),2);
  assert.equal(octavePointScale(xml,lines,5),2.5);
  assert.equal(octavePointScale(xml,lines,null),1);
  assert.equal(octavePointScale(xml,[],4),4);
});

test('all independent CAD segment buffers preserve centers, directions and lengths',()=>{
  const a=new Float32Array([0,0,0,10,0,0,10,0,0,10,20,0,10,20,0,10,20,5]);
  const b=new Float32Array([20,30,0,30,30,0,30,30,0,30,40,0,30,40,0,20,40,0,20,40,0,20,30,0]);
  const cube=cadOutlineSegments(a),flat=cadOutlineSegments(b);
  assert.equal(cube.length,3);
  assert.equal(flat.length,4);
  assert.deepEqual(cube[2],{center:[10,20,2.5],direction:[0,0,1],length:5});
  assert.deepEqual(flat[0],{center:[25,30,0],direction:[1,0,0],length:10});
  assert.notEqual(cube[0],flat[0]);
  assert.deepEqual(cadOutlineSegments([0,0,0,0,0,0]),[]);
  assert.equal(cadOutlineHaloColor('#FFFFFF'),'#202020');
  assert.equal(cadOutlineHaloColor('#000000'),'#f5f5f5');
});


test('empty alternative text uses same planar outline coordinates as sensor geometry',()=>{
  for(const value of [null,undefined,'','  ',{}, {description:'',title:''},{description:'_x000D_ ',title:' '}])
    assert.equal(rectangleHasAltText(value),false);
  for(const value of ['z=0.5x',{title:'z=0x'},{description:'invalid'}])
    assert.equal(rectangleHasAltText(value),true);
  const vertices=planarOutlineVertices('rectangle',80,40);
  assert.deepEqual(vertices,[[-40,20,0.7],[40,20,0.7],[40,-20,0.7],[-40,-20,0.7]]);
  const circle=planarOutlineVertices('ellipse',80,40);
  assert.equal(circle.length,72);
  assert.equal(circle[0][2],vertices[0][2]);
  assert.equal(circle[0][0],Math.hypot(80,40)/2);
});
