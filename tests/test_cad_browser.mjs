// Real Chromium/WebGL regression using a synthetic manifest. No private workbook.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve,dirname,extname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const deps=resolve(process.env.CAD_BROWSER_DEPS||root);
const require=createRequire(resolve(deps,'package.json'));
const {chromium}=require('playwright');
const threeRoot=resolve(deps,'node_modules','three');
const emu=9525;
const bounds=(x,y,w,h)=>({x:x*emu,y:y*emu,width:w*emu,height:h*emu});
function shape(name,kind,x,y,w,h,height,outline='#164070') {
  return {name,text:name,type:'shape',shape_kind:kind,bounds_emu:bounds(x,y,w,h),
    rotation_degrees:0,alt_text:{description:height||''},colors:{fill:'#e8d7ac',outline},outline_width_px:3};
}
function objects() {
  return [
    {type:'image',bounds_emu:bounds(0,0,420,240),rotation_degrees:0},
    {...shape('Cube A','rectangle',30,35,70,45,'z=0.5x','#000000'),outline_status:'color'},
    shape('Cube B','rectangle',155,35,70,45,'z=0.5x','#204060'),
    {...shape('Flat A','rectangle',30,135,70,45,'','#000000'),outline_status:'color'},
    {...shape('Flat B','rectangle',155,135,70,45,'','无/透明'),outline_status:'none',alt_text:undefined,
      rotation_degrees:12,outline_width_px:4},
    {...shape('Dot','ellipse',310,100,22,22,'','无/透明'),outline_status:'none'},
  ];
}
const manifest={workbook:'synthetic.xlsx',layers:[{available:true,sheet:'Fab',objects:objects()},
  {available:true,sheet:'Subfab',objects:objects()}],reference_svgs:{}};
const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json'};
async function startViewerServer(data) {
  const server=createServer(async(req,res)=>{
    try{
      const url=new URL(req.url,'http://localhost');
      if(url.pathname==='/viewer/cad-layout.json'){
        res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify(data));return;
      }
      let path;
      if(url.pathname.startsWith('/three/')) path=resolve(threeRoot,url.pathname.slice('/three/'.length));
      else if(url.pathname.startsWith('/viewer/')) path=resolve(root,url.pathname.slice('/viewer/'.length));
      else {res.writeHead(404);res.end();return;}
      let body=await readFile(path);
      if(path.endsWith('index.html')) body=body.toString().replaceAll('https://unpkg.com/three@0.160.0/','/three/');
      res.writeHead(200,{'content-type':types[extname(path)]||'application/octet-stream'});res.end(body);
    }catch(error){res.writeHead(404);res.end(String(error));}
  });
  await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
  return server;
}

test('Chromium renders every CAD outline and scales octave points around their centers', {timeout:90000}, async()=>{
  const server=await startViewerServer(manifest);
  let browser;
  try{
    browser=await chromium.launch({channel:'chrome',headless:true,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
    const page=await browser.newPage({viewport:{width:1400,height:950},deviceScaleFactor:1});
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('console',m=>{if(m.type()==='error' && /CAD layout failed|WebGLProgram/.test(m.text()))errors.push(m.text());});
    await page.goto('http://127.0.0.1:'+server.address().port+'/viewer/index.html');
    await page.waitForFunction(async()=>{
      const {layers}=await import('/viewer/cad_viewer.js');
      return layers.length===2 && layers.every(l=>l.clickable.length===5);
    },null,{timeout:25000});
    const rendered=await page.evaluate(async()=>{
      const {layers}=await import('/viewer/cad_viewer.js');
      const THREE=await import('three');
      const result=[];
      for(const layer of layers) {
        for(const tilted of [false,true]){
          const t=layer.controls.target;
          layer.camera.position.set(t.x+(tilted?90:0),t.y+(tilted?-150:0),t.z+1200);
          layer.controls.update();
          layer.renderer.render(layer.scene,layer.camera);
          const gl=layer.renderer.getContext(),W=gl.drawingBufferWidth,H=gl.drawingBufferHeight;
          for(const body of layer.clickable) {
            const item=body.userData.cadObject,group=body.parent;
            const edges=[];
            group.traverse(m=>{if(m.userData.isCadOutline) edges.push(m);});
            const foreground=edges[0];
            if(!foreground){result.push({name:item.name,missing:true});continue;}
            const spec=foreground.userData.outlineSegments;
            // Pick a horizontal/top edge (or a circumference segment), project
            // its center, and confirm the actual rendered outline RGB exists.
            const segment=item.shape_kind==='ellipse'?spec[0]:
              spec.filter(s=>Math.abs(s.direction[0])>.99).sort((a,b)=>b.center[2]-a.center[2]||b.center[1]-a.center[1])[0];
            const center=new THREE.Vector3(...segment.center);
            foreground.localToWorld(center);center.project(layer.camera);
            const x=Math.round((center.x+1)*W/2),y=Math.round((center.y+1)*H/2);
            const expectedColor=item.outline_status==='none'?item.colors.fill:item.colors.outline;
            const rgb=expectedColor.slice(1).match(/../g).map(h=>parseInt(h,16));
            let hit=false;
            for(let dy=-4;dy<=4&&!hit;dy++)for(let dx=-4;dx<=4&&!hit;dx++){
              if(x+dx<0||x+dx>=W||y+dy<0||y+dy>=H)continue;
              const p=new Uint8Array(4);gl.readPixels(x+dx,y+dy,1,1,gl.RGBA,gl.UNSIGNED_BYTE,p);
              hit=rgb.every((v,j)=>Math.abs(v-p[j])<=25);
            }
            result.push({name:item.name,tilted,hit,count:foreground.count,meshes:edges.length,
              culled:foreground.frustumCulled,allInstances:spec.length,
              flatGroup:foreground.parent.userData.isFlatRectangleOutline===true,
              outlineWidth:foreground.userData.outlineWidth,
              localZ:segment.center[2],expectedColor:expectedColor.toLowerCase(),
              actualColor:'#'+foreground.material.color.getHexString()});
          }
        }
      }
      return result;
    });
    assert.equal(rendered.length,20);
    for(const r of rendered){
      assert.equal(r.missing,undefined,JSON.stringify(r));
      assert.equal(r.meshes,1,JSON.stringify(r));
      assert.equal(r.actualColor,r.expectedColor,JSON.stringify(r));
      assert.equal(r.count,r.name.startsWith('Cube')?12:r.name.startsWith('Flat')?4:72,JSON.stringify(r));
      assert.equal(r.allInstances,r.count);
      assert.equal(r.culled,false);
      assert.equal(r.hit,true,'Missing rendered outline pixel '+JSON.stringify(r));
      assert.equal(r.flatGroup,r.name.startsWith('Flat'),JSON.stringify(r));
      assert.equal(r.outlineWidth,r.name==='Flat B'?4:3);
      if(r.name.startsWith('Flat')||r.name==='Dot') assert.equal(r.localZ,0.7);
    }
    const markers=await page.evaluate(async()=>{
      const {restyleSvgMarkup}=await import('/viewer/cad_ui.mjs');
      const source='<svg xmlns="http://www.w3.org/2000/svg" width="300" height="180" viewBox="0 0 300 180"><defs><circle id="glyph" r="3" fill="black"/></defs><path id="curve" stroke="black" stroke-width="2" fill="none" d="M20 90 L140 90 L270 90"/><circle id="pt" cx="50" cy="55" r="4" fill="black"/><use id="usePt" href="#glyph" x="130" y="55"/><path id="pathPt" d="M210 50 L215 55 L210 60 L205 55 Z" fill="black"/><g id="axis_1"><circle id="tick" cx="280" cy="55" r="3" fill="black"/></g></svg>';
      function measure(markup){
        const div=document.createElement('div');
        div.style.cssText='position:fixed;top:0;left:0;width:300px;height:180px;z-index:9999';
        div.innerHTML=markup;document.body.append(div);
        const values={};
        for(const id of ['pt','usePt','pathPt','tick']){
          const r=div.querySelector('#'+id).getBoundingClientRect();
          values[id]=[r.width,r.height,r.x+r.width/2,r.y+r.height/2];
        }
        div.remove();return values;
      }
      const original=measure(source);
      const widths=[2,2.5,3,3.5,4];
      const styled=Object.fromEntries(widths.map(lineWidth=>[lineWidth,
        measure(restyleSvgMarkup(source,{color:'#E41A1C',lineWidth},'octave'))]));
      const restored=measure(restyleSvgMarkup(source,{color:'#E41A1C'},'octave'));
      return {original,styled,restored};
    });
    for(const id of ['pt','usePt','pathPt','tick']){
      const before=markers.original[id],reset=markers.restored[id];
      assert.ok(before[0]>0,id);
      for(const width of [2,2.5,3,3.5,4]){
        const after=markers.styled[width][id],factor=id==='tick'?1:width/2;
        assert.ok(Math.abs(after[0]-before[0]*factor)<0.3,JSON.stringify({id,width,before,after}));
        assert.ok(Math.abs(after[1]-before[1]*factor)<0.3,JSON.stringify({id,width,before,after}));
        assert.ok(Math.abs(after[2]-before[2])<0.3 && Math.abs(after[3]-before[3])<0.3,'Point moved: '+id);
      }
      assert.deepEqual(reset,before);
    }
    assert.deepEqual(errors,[]);
  }finally{
    await browser?.close();
    await new Promise(ok=>server.close(ok));
  }
});


test('Chromium preserves XLSX anchor aspect, rotated corners, text and square projection with mismatched PNG pixels', {timeout:90000}, async()=>{
  const png=[
    'iVBORw0KGgoAAAANSUhEUgAAAFQAAAAgCAIAAAADushBAAAAQ0lEQVR4nO3PIQEAIADAMKB/UxQCTwzEvgT/3OcO1fod8FPzquZVzauaVzWval7VvKp5VfOq5lXNq5pXNa9qXtW86gElBwMRsCVbqQAAAABJRU5ErkJggg==',
    'iVBORw0KGgoAAAANSUhEUgAAACgAAAA8CAIAAACb22+3AAAAOklEQVR4nO3NIQEAMAgAsPP+TVEIPB0wmK3AIqvfhX+yisVisVgsFovFYrFYLBaLxWKxWCwWi8XipQGgZgNJgo88eAAAAABJRU5ErkJggg==',
  ];
  const anchorSizes=[[420,240],[280,200]];
  const data={workbook:'aspect-mismatch.xlsx',reference_svgs:{},
    layers:anchorSizes.map(([w,h],i)=>({
      available:true,sheet:i?'Subfab':'Fab',
      objects:[
        {type:'image',bounds_emu:bounds(0,0,w,h),rotation_degrees:0,
          image_url:'data:image/png;base64,'+png[i]},
        {...shape('Label','textbox',10,10,240,180,''),rotation_degrees:0,
          colors:{fill:'无/透明',outline:'无/透明'},outline_status:'none'},
        shape('Square','rectangle',30,35,40,40,''),
        {...shape('Rotated','rectangle',100,35,80,30,''),rotation_degrees:32},
        shape('Cube','rectangle',30,110,70,50,'z=0.5x'),
        shape('Inside','ellipse',55,125,12,12,''),
        shape('Partial','ellipse',94,125,12,12,''),
        shape('Outside','ellipse',220,125,12,12,''),
      ],
    }))};
  const server=await startViewerServer(data);
  let browser;
  try {
    browser=await chromium.launch({channel:'chrome',headless:true,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
    const page=await browser.newPage({viewport:{width:1400,height:950},deviceScaleFactor:1});
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('console',m=>{if(m.type()==='error'&&/CAD layout failed|embedded picture could not|WebGLProgram/.test(m.text())) errors.push(m.text());});
    await page.goto('http://127.0.0.1:'+server.address().port+'/viewer/index.html');
    await page.waitForFunction(async()=>{
      const {layers}=await import('/viewer/cad_viewer.js');
      return layers.length===2 && layers.every(l=>l.clickable.length===6 && l.hoverable.length===7);
    },null,{timeout:25000});
    const measured=await page.evaluate(async()=>{
      const {layers}=await import('/viewer/cad_viewer.js');
      const THREE=await import('three');
      return layers.map(layer=>{
        const raster=layer.scene.children.find(g=>g.renderOrder===0 && g.children.some(m=>m.material?.map))?.children.find(m=>m.material?.map);
        const target=layer.controls.target;
        layer.camera.position.set(target.x,target.y,target.z+1200);
        layer.controls.update();
        layer.renderer.render(layer.scene,layer.camera);
        const rect=layer.renderer.domElement.getBoundingClientRect();
        const project=p=>{
          const q=p.clone().project(layer.camera);
          return [q.x*rect.width/2,q.y*rect.height/2];
        };
        const shapes=layer.hoverable.map(mesh=>{
          const item=mesh.userData.cadObject;
          const {width,height,depth,radius}=mesh.geometry.parameters;
          const center=mesh.getWorldPosition(new THREE.Vector3());
          const text=mesh.parent.children.find(m=>m.userData.isTextboxText);
          const corners=width&&height?[
            [-width/2,height/2],[width/2,height/2],
            [width/2,-height/2],[-width/2,-height/2],
          ].map(([x,y])=>mesh.localToWorld(new THREE.Vector3(x,y,0))):[];
          return {name:item.name,width,height,depth,radius,center:center.toArray(),
            corners:corners.map(p=>p.toArray()),screen:corners.map(project),
            text:text?{width:text.geometry.parameters.width,height:text.geometry.parameters.height}:null};
        });
        return {sx:layer.scaleX,sy:layer.scaleY,zoom:layer.camera.zoom,
          raster:raster?{w:raster.geometry.parameters.width,h:raster.geometry.parameters.height,
            native:[raster.material.map.image.width,raster.material.map.image.height],
            center:raster.getWorldPosition(new THREE.Vector3()).toArray()}:null,shapes};
      });
    });
    function near(actual,expected,context){
      assert.ok(Number.isFinite(actual)&&Math.abs(actual-expected)<1e-5,
        context+': '+actual+' != '+expected);
    }
    assert.equal(measured.length,2);
    near(measured[0].zoom,measured[1].zoom,'linked camera zoom');
    for(let i=0;i<2;i++){
      const m=measured[i], [w,h]=anchorSizes[i],s=420/w;
      near(m.sx,s,'scaleX');near(m.sy,s,'scaleY');
      assert.ok(m.raster,'decoded background must be drawn');
      assert.deepEqual(m.raster.native,i?[40,60]:[84,32]);
      assert.notEqual(m.raster.native[0]/m.raster.native[1],w/h);
      near(m.raster.w,w*s,'background width');near(m.raster.h,h*s,'background height');
      near(m.raster.center[0],w*s/2,'background center X');
      near(m.raster.center[1],-h*s/2,'background center Y');
      for(const actual of m.shapes){
        const item=data.layers[i].objects.find(o=>o.name===actual.name), b=item.bounds_emu;
        const width=b.width/emu,height=b.height/emu, cx=(b.x/emu+width/2)*s,cy=-(b.y/emu+height/2)*s;
        near(actual.center[0],cx,actual.name+' center X');
        near(actual.center[1],cy,actual.name+' center Y');
        if(item.shape_kind==='ellipse'){
          near(actual.radius,Math.hypot(width,height)*s/2,actual.name+' circle radius');
          const z={Inside:35,Partial:17.5,Outside:0}[actual.name]*s+1.5;
          near(actual.center[2],z,actual.name+' elevation');
          continue;
        }
        near(actual.width,width*s,actual.name+' width');
        near(actual.height,height*s,actual.name+' height');
        const angle=-item.rotation_degrees*Math.PI/180;
        const raw=[[-width/2,height/2],[width/2,height/2],[width/2,-height/2],[-width/2,-height/2]];
        for(let j=0;j<4;j++){
          const [x,y]=raw[j],p=actual.corners[j];
          near(p[0],cx+s*(x*Math.cos(angle)-y*Math.sin(angle)),actual.name+' rotated X');
          near(p[1],cy+s*(x*Math.sin(angle)+y*Math.cos(angle)),actual.name+' rotated Y');
        }
        const edge=(a,b)=>Math.hypot(actual.screen[a][0]-actual.screen[b][0],actual.screen[a][1]-actual.screen[b][1]);
        near(edge(0,1)/edge(1,2),width/height,actual.name+' screen aspect');
        if(actual.name==='Cube') near(actual.depth,35*s,'cuboid height');
        if(actual.name==='Label'){
          assert.ok(actual.text,'textbox text texture exists');
          near(actual.text.width,width*s,'textbox texture plane width');
          near(actual.text.height,height*s,'textbox texture plane height');
        }
      }
    }
    assert.deepEqual(errors,[]);
  }finally{
    await browser?.close();
    await new Promise(ok=>server.close(ok));
  }
});
