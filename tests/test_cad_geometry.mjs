import test from 'node:test';
import assert from 'node:assert/strict';
import {
  rectangleHeight, rectangleSpecs, rectangleOverlap,
  pointInsideRotatedRectangle, circleRectangleRelation, ellipseElevation,
  worldRectFromEmu, reconstructedCircleRadius,
} from '../cad_geometry.mjs';

const rect=(x,y,width,height,rotation=0)=>({x,y,width,height,rotation});
const item=(shape_kind,r,text='',alt='')=>({
  type:'shape',shape_kind,text,bounds_emu:r,alt_text:{description:alt},
});
const identity=obj=>obj.bounds_emu;
const specs=(...items)=>rectangleSpecs(items,identity);
const circle=(x,y,w,h)=>item('ellipse',rect(x,y,w,h));

test('alternative text z=0.5x / z=0.1y controls box height, not shape text',()=>{
  assert.equal(rectangleHeight({description:'z=0.5x'},100,50),50);
  assert.equal(rectangleHeight({description:'z=0.1y'},100,50),5);
  assert.equal(rectangleHeight({title:'z=.25x'},120,40),30);
  assert.equal(rectangleHeight({description:'',title:'z=0.75y'},100,40),30);
  assert.equal(rectangleHeight({description:'z=0x'},100,40),0);
  assert.equal(rectangleHeight({description:'_x000D_z=0.5x'},100,40),50);
});
test('visible suffix or empty/invalid alt text never produces cuboid height',()=>{
  for(const text of ['B1_x0.5','x0.2','_x-1','z=-1x','z=abcy',
    'z=0.5x_extra','z=1e2x','z=Infinityx','',' ']) {
    assert.equal(rectangleHeight({description:text},100,40),0,text);
  }
  assert.equal(rectangleHeight({description:''},100,40),0);
});
test('rectangleSpecs obtains roof only from alt_text and retains visible labels',()=>{
  const found=specs(item('rectangle',rect(0,0,100,30),'one_x0.2','z=0.2x'),
    circle(1,-1,20,20),item('rectangle',rect(120,0,50,20),'two_y0.5','z=0.5y'));
  assert.deepEqual(found.map(x=>x.depth),[20,10]);
  assert.equal(found[0].label,'one_x0.2');
  assert.equal(specs(item('rectangle',rect(0,0,100,30),'old_x0.9'))[0].depth,0);
});
test('rotated footprint is correctly transformed',()=>{
  const a=specs(item('rectangle',rect(0,0,100,20,Math.PI/2),'A_x0.1'))[0];
  assert.equal(pointInsideRotatedRectangle(50,-10,a),true);
  assert.equal(pointInsideRotatedRectangle(50,30,a),true);
  assert.equal(pointInsideRotatedRectangle(50,60,a),false);
});
test('rebuilt circle wholly inside gives full roof height',()=>{
  const rectangle=specs(item('rectangle',rect(0,0,100,80),'A_x0.2','z=0.2x'));
  assert.equal(circleRectangleRelation(circle(30,-20,10,10),identity,rectangle[0]),'inside');
  assert.equal(ellipseElevation(circle(30,-20,10,10),identity,rectangle),20);
});
test('rebuilt circle intersects one edge -> half roof height, even if its center is inside',()=>{
  const rectangle=specs(item('rectangle',rect(0,0,100,80),'A_x0.2','z=0.2x'));
  assert.equal(circleRectangleRelation(circle(90,-20,16,16),identity,rectangle[0]),'partial');
  assert.equal(ellipseElevation(circle(90,-20,16,16),identity,rectangle),10);
  // Center OUTSIDE, circle crossing left border still intersects.
  assert.equal(ellipseElevation(circle(-14,-40,20,20),identity,rectangle),10);
});
test('entire reconstructed circle outside a rectangle -> zero height',()=>{
  const rectangle=specs(item('rectangle',rect(0,0,100,80),'A_x0.2','z=0.2x'));
  assert.equal(circleRectangleRelation(circle(130,-20,10,10),identity,rectangle[0]),'outside');
  assert.equal(ellipseElevation(circle(130,-20,10,10),identity,rectangle),0);
});
test('external tangency counts as partial intersection',()=>{
  const rectSpec=specs(item('rectangle',rect(0,0,100,100),'A_x0.2','z=0.2x'));
  // Center at x=-10, radius=10; use degenerate bbox (w=20,h=0).
  assert.equal(circleRectangleRelation(circle(-20,-50,20,0),identity,rectSpec[0]),'partial');
});
test('rotated rectangle uses its actual boundary not its AABB',()=>{
  const a=specs(item('rectangle',rect(0,0,80,40,Math.PI/4),'A_y0.5','z=0.5y'));
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
  const rs=specs(item('rectangle',rect(0,0,100,80),'left_x0.2','z=0.2x'),
    item('rectangle',rect(140,0,100,80),'right_x0.3','z=0.3x'));
  assert.equal(rectangleOverlap(rs[0],rs[1]),false);
  assert.throws(()=>ellipseElevation(circle(100,-40,40,40),identity,rs),
    /multiple rectangles/);
});

test('all drawing kinds use the same exact EMU transform, including tiny dimensions',()=>{
  const bounds_emu={x:190500,y:285750,width:1,height:2};
  for(const shape_kind of ['textbox','rectangle','ellipse','image']){
    const r=worldRectFromEmu({shape_kind,bounds_emu,rotation_degrees:32},1.5);
    assert.equal(r.x,30);assert.equal(r.y,-45);
    assert.equal(r.width,1.5/9525);assert.equal(r.height,3/9525);
    assert.equal(r.rotation,-32*Math.PI/180);
    assert.equal(reconstructedCircleRadius(r.width,r.height),Math.hypot(r.width,r.height)/2);
  }
  assert.throws(()=>worldRectFromEmu({bounds_emu:{...bounds_emu,width:0}}),/Invalid saved XLSX geometry/);
});

test('explicit center is the single authoritative world position',()=>{
  const bounds_emu={x:999999,y:999999,width:95250,height:190500};
  const center_emu={x:95250.5,y:190500.5};
  const r=worldRectFromEmu({bounds_emu,center_emu,rotation_degrees:90},2);
  assert.equal(r.centerX,center_emu.x*2/9525);
  assert.equal(r.centerY,-center_emu.y*2/9525);
  assert.ok(Math.abs(r.x-(r.centerX-r.width/2))<1e-9);
  assert.ok(Math.abs(r.y-(r.centerY+r.height/2))<1e-9);
});
