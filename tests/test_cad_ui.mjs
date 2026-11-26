import test from 'node:test';
import assert from 'node:assert/strict';
import {
  INITIAL_REFERENCE_SPLIT, shapeLabel, selectOnButton,
  containsShape, shapeAncestors, selectionPath, fitSvgPair,
  clampMainDivider, clampReferenceSplit,
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

test('split defaults to exactly 5.8:18.1, without adapting to SVG intrinsic size',()=>{
  assert.ok(Math.abs(INITIAL_REFERENCE_SPLIT-5.8/23.9)<1e-12);
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
