import test from 'node:test';
import assert from 'node:assert/strict';
import {
  INITIAL_REFERENCE_SPLIT, shapeLabel, selectOnButton,
  containsShape, shapeAncestors, selectionPath, fitSvgPair,
  clampMainDivider, clampReferenceSplit, pictureLayerScales,
  requiredSvgRatio,svgPaintColors,legendForeground,legendPaint,canAddOverlay,
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

test('Fab selection breadcrumb uses workbook stem, exact sheet, parent textbox and child text',()=>{
  const body=shape('textbox',0,0,200,160,'BODYv2');
  const child=shape('rectangle',40,-35,70,55,'B1_x0.2');
  const peer=shape('rectangle',140,-35,35,40,'B2_x0.1');
  const items=[body,child,peer];
  assert.deepEqual(shapeAncestors(items,child,toRect),[body]);
  assert.equal(selectionPath('luoD.xlsx','FAB',items,child,toRect),
               'luoD·FAB·BODYv2·B1_x0.2');
  assert.equal(selectionPath('la.xlsx','Subfab',items,peer,toRect),
               'la·Subfab·BODYv2·B2_x0.1');
});

test('multiple ancestor levels are ordered outermost to innermost',()=>{
  const body=shape('textbox',0,0,300,300,'BODYv2');
  const area=shape('rectangle',30,-30,200,200,'Floor_A_x0.2');
  const dot=shape('ellipse',80,-80,10,10,'Sensor');
  assert.deepEqual(shapeAncestors([body,dot,area],dot,toRect),[body,area]);
  assert.equal(selectionPath('A.XLSX','Sheet2',[body,dot,area],dot,toRect),
               'A·Sheet2·BODYv2·Floor_A_x0.2·Sensor');
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


test('two embedded CAD pictures preserve native aspect and share exactly one width',()=>{
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


test('transparent SVG paint extraction uses explicit shapes and never invents white',()=>{
  assert.deepEqual(svgPaintColors('<svg><path stroke="#FF5733" fill="none"/></svg>'),['#FF5733']);
  const two='<svg><style>.a{fill:#0066cc;stroke:#00bbaa}</style>'+
    '<path class="a" fill="none" stroke="transparent"/></svg>';
  assert.deepEqual(svgPaintColors(two),['#0066cc','#00bbaa']);
  assert.deepEqual(svgPaintColors('<svg><path fill="url(#grad)" stroke="none"/></svg>'),[]);
  assert.equal(legendForeground(['#ffffff','#FF5733']),'#FF5733');
  assert.equal(legendPaint(['#ff0000']),'#ff0000');
  assert.match(legendPaint(['#ff0000','#0000ff']),/linear-gradient/);
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

test('oversize overlays influence fit without changing the base image ratio',()=>{
  assert.equal(requiredSvgRatio(0.4,[0.5,0.3]),0.5);
  assert.equal(requiredSvgRatio(0.4,[0.8,0.3]),0.8);
  const fit=fitSvgPair({width:800,height:250},{width:800,height:250},0.8,0.7);
  assert.ok(fit.heightA<=250 && fit.heightB<=250);
  assert.ok(fit.width>0);
});
