import test from 'node:test';
import assert from 'node:assert/strict';
import {
  rectangleHeight, rectangleSpecs, rectangleOverlap,
  pointInsideRotatedRectangle, circleRectangleRelation, ellipseElevation,
} from '../cad_geometry.mjs';

const rect=(x,y,width,height,rotation=0)=>({x,y,width,height,rotation});
const item=(shape_kind,r,text='')=>({
  type:'shape',shape_kind,text,bounds_emu:r,
});
const identity=obj=>obj.bounds_emu;
const specs=(...items)=>rectangleSpecs(items,identity);
const circle=(x,y,w,h)=>item('ellipse',rect(x,y,w,h));

test('rectangle heights use width for x, height for y, never the diagonal',()=>{
  assert.equal(rectangleHeight('柱A_x0.2',100,50),20);
  assert.equal(rectangleHeight('柱B_y0.1',100,50),5);
  assert.equal(rectangleHeight('A_B_x.25',120,40),30);
  assert.equal(rectangleHeight('A_x0',100,40),0);
});
test('height suffix must be the last valid underscore-separated term',()=>{
  for(const text of ['x0.2','_x-1','_xabc','X_x.','X_z0.2',
    'X_x0.2_note','X_y1e2','X_x 0.2','X_xInfinity','']) {
    assert.equal(rectangleHeight(text,100,40),0,text);
  }
});
test('rectangleSpec includes only rectangles and computes roof heights',()=>{
  const found=specs(item('rectangle',rect(0,0,100,30),'one_x0.2'),
    circle(1,-1,20,20),item('rectangle',rect(120,0,50,20),'two_y0.5'));
  assert.deepEqual(found.map(x=>x.depth),[20,10]);
});
test('rotated footprint is correctly transformed',()=>{
  const a=specs(item('rectangle',rect(0,0,100,20,Math.PI/2),'A_x0.1'))[0];
  assert.equal(pointInsideRotatedRectangle(50,-10,a),true);
  assert.equal(pointInsideRotatedRectangle(50,30,a),true);
  assert.equal(pointInsideRotatedRectangle(50,60,a),false);
});
test('rebuilt circle wholly inside gives full roof height',()=>{
  const rectangle=specs(item('rectangle',rect(0,0,100,80),'A_x0.2'));
  assert.equal(circleRectangleRelation(circle(30,-20,10,10),identity,rectangle[0]),'inside');
  assert.equal(ellipseElevation(circle(30,-20,10,10),identity,rectangle),20);
});
test('rebuilt circle intersects one edge -> half roof height, even if its center is inside',()=>{
  const rectangle=specs(item('rectangle',rect(0,0,100,80),'A_x0.2'));
  assert.equal(circleRectangleRelation(circle(90,-20,16,16),identity,rectangle[0]),'partial');
  assert.equal(ellipseElevation(circle(90,-20,16,16),identity,rectangle),10);
  // Center OUTSIDE, circle crossing left border still intersects.
  assert.equal(ellipseElevation(circle(-14,-40,20,20),identity,rectangle),10);
});
test('entire reconstructed circle outside a rectangle -> zero height',()=>{
  const rectangle=specs(item('rectangle',rect(0,0,100,80),'A_x0.2'));
  assert.equal(circleRectangleRelation(circle(130,-20,10,10),identity,rectangle[0]),'outside');
  assert.equal(ellipseElevation(circle(130,-20,10,10),identity,rectangle),0);
});
test('external tangency counts as partial intersection',()=>{
  const rectSpec=specs(item('rectangle',rect(0,0,100,100),'A_x0.2'));
  // Center at x=-10, radius=10; use degenerate bbox (w=20,h=0).
  assert.equal(circleRectangleRelation(circle(-20,-50,20,0),identity,rectSpec[0]),'partial');
});
test('rotated rectangle uses its actual boundary not its AABB',()=>{
  const a=specs(item('rectangle',rect(0,0,80,40,Math.PI/4),'A_y0.5'));
  assert.equal(ellipseElevation(circle(36,-25,4,4),identity,a),20);
  assert.equal(ellipseElevation(circle(-15,-5,4,4),identity,a),0);
});
test('two nonoverlapping rectangles touching at edge are allowed',()=>{
  const [a,b]=specs(item('rectangle',rect(0,0,100,50)),
    item('rectangle',rect(100,0,100,50)));
  assert.equal(rectangleOverlap(a,b),false);
});
test('positive-area overlap between rotated rectangles is detected',()=>{
  const [a,b]=specs(item('rectangle',rect(0,0,100,50,Math.PI/6)),
    item('rectangle',rect(50,0,100,50,-Math.PI/6)));
  assert.equal(rectangleOverlap(a,b),true);
});
test('a circle intersecting two disjoint rectangles is an error',()=>{
  const rs=specs(item('rectangle',rect(0,0,100,80),'left_x0.2'),
    item('rectangle',rect(140,0,100,80),'right_x0.3'));
  assert.equal(rectangleOverlap(rs[0],rs[1]),false);
  assert.throws(()=>ellipseElevation(circle(100,-40,40,40),identity,rs),
    /multiple rectangles/);
});
