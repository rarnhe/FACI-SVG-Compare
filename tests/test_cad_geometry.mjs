import test from 'node:test';
import assert from 'node:assert/strict';
import {rectangleHeight, rectangleSpecs, pointInsideRotatedRectangle, ellipseElevation} from '../cad_geometry.mjs';

const rect = (x, y, width, height, rotation=0) =>
  ({x,y,width,height,rotation});
const item = (shape_kind, r, text='') => ({
  type:'shape', shape_kind, text, bounds_emu:r,
});
const identity = obj=>obj.bounds_emu;

test('x suffix measures upper edge; y suffix measures left edge, never diagonal',()=>{
  assert.equal(rectangleHeight('柱A_x0.2',100,50),20);
  assert.equal(rectangleHeight('柱B_y0.1',100,50),5);
  assert.equal(rectangleHeight('名字_注释_x.25',120,40),30);
  assert.equal(rectangleHeight('标题_x0',90,70),0);
});
test('only a valid FINAL underscore directive counts',()=>{
  for(const text of ['_x','_x-0.2','_z0.2','x0.2','_x.','_xabc','_x0.2a','_y1e2','_x0.2_comment','','_xInfinity','_x 0.2']){
    assert.equal(rectangleHeight(text,100,40),0,text);
  }
  assert.equal(rectangleHeight('A_x0.2_bad',100,40),0);
  assert.equal(rectangleHeight('A_y.5',100,40),20);
});
test('rectangleSpecs filters shapes and preserves per-rectangle heights',()=>{
  const specs=rectangleSpecs([
    item('rectangle',rect(0,0,100,30),'one_x0.2'),
    item('ellipse',rect(1,1,20,20),'circle'),
    item('rectangle',rect(30,0,50,20),'two_y0.5'),
  ],identity);
  assert.deepEqual(specs.map(s=>s.depth),[20,10]);
});
test('rotated footprint point test respects angle and boundaries',()=>{
  const spec=rectangleSpecs([item('rectangle',rect(0,0,100,20,Math.PI/2),'a_x0.1')],identity)[0];
  assert.equal(pointInsideRotatedRectangle(50,-10,spec),true);
  assert.equal(pointInsideRotatedRectangle(50,30,spec),true);
  assert.equal(pointInsideRotatedRectangle(50,60,spec),false);
});
test('ellipse center over a rectangle gets its top height, otherwise zero',()=>{
  const specs=rectangleSpecs([item('rectangle',rect(0,0,100,40),'a_x0.2')],identity);
  assert.equal(ellipseElevation(item('ellipse',rect(10,-10,8,8)),identity,specs),20);
  assert.equal(ellipseElevation(item('ellipse',rect(110,-10,8,8)),identity,specs),0);
});
test('overlapping rectangles use the highest roof, including flat zero-height cases',()=>{
  const specs=rectangleSpecs([
    item('rectangle',rect(0,0,100,100),'floor_x0.1'),
    item('rectangle',rect(20,-20,50,50),'tower_y0.4'),
    item('rectangle',rect(20,-20,50,50),'none_wrong'),
  ],identity);
  assert.equal(ellipseElevation(item('ellipse',rect(30,-30,10,10)),identity,specs),20);
  assert.equal(ellipseElevation(item('ellipse',rect(2,-2,5,5)),identity,specs),10);
});
