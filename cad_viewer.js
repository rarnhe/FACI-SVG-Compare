// Linked Fab/Subfab Excel CAD viewer. Each picture starts at (0,0) in local XY.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { rectangleHeight, rectangleSpecs, ellipseElevation } from './cad_geometry.mjs';
import {
  INITIAL_REFERENCE_SPLIT, selectOnButton, selectionPath, fitSvgPair,
  clampMainDivider, clampReferenceSplit,
} from './cad_ui.mjs';

const EMU_TO_PX = 1 / 9525;
const layers = [];
const pointerStart = new WeakMap();
let workbookName = '';
let syncing = false;
let hasGeometry = false;
let sceneBounds = {minX:0,maxX:500,minY:0,maxY:400};
let lastCadSize = null;
let rightSplitRatio = INITIAL_REFERENCE_SPLIT;
const referenceImages = new Map();

function createLayer(stageId) {
  const stage = document.getElementById(stageId);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xffffff);
  const renderer = new THREE.WebGLRenderer({antialias:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  const camera = new THREE.OrthographicCamera(-200,200,150,-150,0.1,200000);
  camera.position.set(0,0,3000);
  camera.up.set(0,1,0);
  const controls = new OrbitControls(camera,renderer.domElement);
  controls.enableDamping = false;
  controls.screenSpacePanning = true;
  controls.enableRotate = true;
  controls.mouseButtons = {
    LEFT:THREE.MOUSE.ROTATE,
    MIDDLE:THREE.MOUSE.DOLLY,
    RIGHT:THREE.MOUSE.PAN,
  };
  controls.minZoom = 0.01;
  controls.maxZoom = 100;
  controls.target.set(0,0,0);
  controls.update();
  stage.prepend(renderer.domElement);
  const layer = {
    stage,scene,renderer,camera,controls,clickable:[],objects:[],
    sheetName:'',selectedMesh:null,
    selectedInfo:document.getElementById(
      stageId==='fab-stage'?'fab-selected-info':'subfab-selected-info'),
  };
  layer.menu = createContextMenu(layer);
  controls.addEventListener('change',()=>synchronizeFrom(layer));
  renderer.domElement.addEventListener('contextmenu',e=>e.preventDefault());
  installPicking(layer);
  layers.push(layer);
  return layer;
}

function synchronizeFrom(source) {
  if(syncing) return;
  syncing=true;
  try {
    for(const layer of layers) {
      if(layer===source) continue;
      layer.camera.position.copy(source.camera.position);
      layer.camera.quaternion.copy(source.camera.quaternion);
      layer.camera.zoom=source.camera.zoom;
      layer.camera.updateProjectionMatrix();
      layer.controls.target.copy(source.controls.target);
      layer.controls.update();
    }
  } finally {syncing=false;}
}

function toWorldRect(item) {
  const b=item.bounds_emu;
  return {
    x:b.x*EMU_TO_PX,
    y:-b.y*EMU_TO_PX,
    width:Math.max(0.1,b.width*EMU_TO_PX),
    height:Math.max(0.1,b.height*EMU_TO_PX),
    rotation:-(item.rotation_degrees || 0)*Math.PI/180,
  };
}

function colorValue(value,fallback) {
  return typeof value==='string' && /^#[0-9a-f]{6}$/i.test(value)
    ? parseInt(value.slice(1),16) : fallback;
}

// Text is a natural-aspect texture anchored to the upper-left of its shape.
// Never stretch a 1024x256 text canvas to an arbitrary shape rectangle.
function drawTopLeftText(group,label,width,height,foreground,frontZ) {
  if(!label?.trim()) return;
  const lines=label.split(/\r?\n/).slice(0,6);
  const unitFont=48, pad=6, lineHeight=58;
  const canvas=document.createElement('canvas');
  const measure=canvas.getContext('2d');
  measure.font='500 48px "Microsoft YaHei","Segoe UI",sans-serif';
  const measured=Math.max(...lines.map(line=>measure.measureText(line).width),16);
  canvas.width=Math.ceil(Math.min(4096,measured+pad*2));
  canvas.height=Math.ceil(lines.length*lineHeight+pad*2);
  const ctx=canvas.getContext('2d');
  ctx.font='500 48px "Microsoft YaHei","Segoe UI",sans-serif';
  ctx.textBaseline='top';
  ctx.textAlign='left';
  ctx.fillStyle=/^#[0-9a-f]{6}$/i.test(foreground||'') ? foreground : '#f4f9fd';
  lines.forEach((line,index)=>ctx.fillText(line,pad,pad+index*lineHeight,canvas.width-pad*2));
  const texture=new THREE.CanvasTexture(canvas);
  texture.colorSpace=THREE.SRGBColorSpace;
  const margin=Math.max(1,Math.min(width,height)*0.04);
  const scale=Math.max(0.0001,Math.min(
    0.35,
    Math.max(0.1,width-2*margin)/canvas.width,
    Math.max(0.1,height-2*margin)/canvas.height,
  ));
  const textWidth=canvas.width*scale, textHeight=canvas.height*scale;
  const text=new THREE.Mesh(
    new THREE.PlaneGeometry(textWidth,textHeight),
    new THREE.MeshBasicMaterial({
      map:texture,transparent:true,depthWrite:false,side:THREE.DoubleSide,
      polygonOffset:true,polygonOffsetFactor:-1,
    }),
  );
  text.position.set(-width/2+margin+textWidth/2,
                    height/2-margin-textHeight/2,frontZ);
  group.add(text);
}

function makeOutline(points,color) {
  return new THREE.LineLoop(
    new THREE.BufferGeometry().setFromPoints(points),
    new THREE.LineBasicMaterial({color,transparent:true,opacity:0.95,depthTest:false}),
  );
}

function kindForElevation(item, rect, rectangles) {
  return item.shape_kind==='ellipse' ? ellipseElevation(item,toWorldRect,rectangles) : 0;
}

function drawShape(layer,item,rectangles=[]) {
  const r=toWorldRect(item);
  const w=r.width,h=r.height;
  const group=new THREE.Group();
  // The XLSX image is at Z=0; all drawing geometry starts at that plane.
  const raisedZ=kindForElevation(item, r, rectangles);
  group.position.set(r.x+w/2,r.y-h/2,raisedZ);
  group.rotation.z=r.rotation;
  const colors=item.colors || {};
  const kind=item.shape_kind || 'other';
  const fillColor=kind==='textbox' ? 0x828b96 : colorValue(colors.fill,0x3599c3);
  const borderColor=colorValue(colors.outline,0x67dcfc);
  const opacity=kind==='textbox' ? 0.82 : colors.fill==='无/透明' ? 0.13 : 0.68;
  const mat=new THREE.MeshBasicMaterial({
    color:fillColor,transparent:true,opacity,
    side:THREE.DoubleSide,depthWrite:false,
  });
  let frontZ=1.0;
  let clickTarget;
  if(kind==='ellipse') {
    // Per drawing requirement: the diagonals meet at the center, and
    // upper-left -> lower-right is the diameter (not the minor axis).
    const radius=Math.hypot(w,h)/2;
    clickTarget=new THREE.Mesh(new THREE.CircleGeometry(radius,72),mat);
    clickTarget.position.z=0.5;
    frontZ=1.2;
    group.add(clickTarget);
    const circumference=[];
    for(let i=0;i<72;i++) {
      const t=2*Math.PI*i/72;
      circumference.push(new THREE.Vector3(radius*Math.cos(t),radius*Math.sin(t),0.7));
    }
    group.add(makeOutline(circumference,borderColor));
  } else if(kind==='rectangle') {
    // A CAD rectangle is a cuboid with actual +Z thickness.
    const depth=rectangleHeight(item.text,w,h);
    if (depth>0) {
      const cube=new THREE.BoxGeometry(w,h,depth);
      clickTarget=new THREE.Mesh(cube,mat);
      clickTarget.position.z=depth/2;
      frontZ=depth+1;
      group.add(clickTarget);
      const edges=new THREE.LineSegments(
        new THREE.EdgesGeometry(cube),
        new THREE.LineBasicMaterial({color:borderColor,transparent:true,opacity:0.85}),
      );
      edges.position.copy(clickTarget.position);
      group.add(edges);
    } else {
      // Missing/invalid directive: zero height, no artificial thickness.
      clickTarget=new THREE.Mesh(new THREE.PlaneGeometry(w,h),mat);
      clickTarget.position.z=0;
      frontZ=0.7;
      group.add(clickTarget);
      const hw=w/2,hh=h/2;
      group.add(makeOutline([
        new THREE.Vector3(-hw,hh,0.2),new THREE.Vector3(hw,hh,0.2),
        new THREE.Vector3(hw,-hh,0.2),new THREE.Vector3(-hw,-hh,0.2),
      ],borderColor));
    }
  } else {
    // A textbox always has gray background; unrecognized shapes stay flat.
    clickTarget=new THREE.Mesh(new THREE.PlaneGeometry(w,h),mat);
    clickTarget.position.z=0.5;
    frontZ=1.2;
    group.add(clickTarget);
    const hw=w/2,hh=h/2;
    const vertices=[
      new THREE.Vector3(-hw,hh,0.8),new THREE.Vector3(hw,hh,0.8),
      new THREE.Vector3(hw,-hh,0.8),new THREE.Vector3(-hw,-hh,0.8),
    ];
    group.add(makeOutline(vertices,borderColor));
  }
  clickTarget.userData.cadObject=item;
  if (kind !== 'textbox') layer.clickable.push(clickTarget);
  drawTopLeftText(group,item.text||'',w,h,colors.text,frontZ);
  layer.scene.add(group);
}

function drawImage(layer,item) {
  if(!item.image_url) return;
  const r=toWorldRect(item);
  const group=new THREE.Group();
  group.position.set(r.x+r.width/2,r.y-r.height/2,0);
  group.rotation.z=r.rotation;
  new THREE.TextureLoader().load(item.image_url,texture=>{
    texture.colorSpace=THREE.SRGBColorSpace;
    texture.anisotropy=Math.min(8,layer.renderer.capabilities.getMaxAnisotropy());
    const image=new THREE.Mesh(
      new THREE.PlaneGeometry(r.width,r.height),
      new THREE.MeshBasicMaterial({
        map:texture,side:THREE.DoubleSide,transparent:true,depthWrite:false,
      }),
    );
    group.add(image);
    layer.scene.add(group);
  },undefined,error=>console.error('XLSX image could not be loaded:',error));
}

function createContextMenu(layer) {
  const menu=document.createElement('div');
  menu.className='cad-context-menu';
  menu.hidden=true;
  menu.setAttribute('role','menu');
  menu.setAttribute('aria-label','椭圆形状操作');
  const year2025=document.createElement('button');
  year2025.type='button';
  year2025.setAttribute('role','menuitem');
  const yearLabel=document.createElement('span');
  yearLabel.textContent='2025';
  const arrow=document.createElement('span');
  arrow.className='cad-menu-arrow';
  arrow.textContent='›';
  year2025.append(yearLabel,arrow);
  const submenu=document.createElement('div');
  submenu.className='cad-submenu';
  submenu.hidden=true;
  submenu.setAttribute('role','group');
  for (const entry of ['X','Y','Z']) {
    const button=document.createElement('button');
    button.type='button';
    button.textContent=entry;
    button.setAttribute('role','menuitem');
    button.addEventListener('click',()=>{menu.hidden=true;});
    submenu.append(button);
  }
  year2025.setAttribute('aria-haspopup','true');
  year2025.setAttribute('aria-expanded','false');
  year2025.addEventListener('click',()=>{
    submenu.hidden=!submenu.hidden;
    year2025.setAttribute('aria-expanded',String(!submenu.hidden));
    keepMenuInStage(layer);
  });
  const year2026=document.createElement('button');
  year2026.type='button';
  year2026.textContent='2026';
  year2026.setAttribute('role','menuitem');
  year2026.addEventListener('click',()=>{menu.hidden=true;});
  menu.addEventListener('pointerdown',event=>event.stopPropagation());
  menu.append(year2025,submenu,year2026);
  layer.stage.append(menu);
  return {element:menu,submenu,year2025};
}

function keepMenuInStage(layer) {
  const menu=layer.menu.element;
  const left=Math.max(4,Math.min(
    Number.parseFloat(menu.style.left)||4,Math.max(4,layer.stage.clientWidth-menu.offsetWidth-4)));
  const top=Math.max(4,Math.min(
    Number.parseFloat(menu.style.top)||4,Math.max(4,layer.stage.clientHeight-menu.offsetHeight-4)));
  menu.style.left=left+'px';
  menu.style.top=top+'px';
}

function closeContextMenus() {
  for (const layer of layers) {
    layer.menu.element.hidden=true;
    layer.menu.submenu.hidden=true;
    layer.menu.year2025.setAttribute('aria-expanded','false');
  }
}

function openContextMenu(layer,clientX,clientY) {
  closeContextMenus();
  const bounds=layer.stage.getBoundingClientRect();
  layer.menu.element.style.left=(clientX-bounds.left)+'px';
  layer.menu.element.style.top=(clientY-bounds.top)+'px';
  layer.menu.element.hidden=false;
  keepMenuInStage(layer);
}

function installPicking(layer) {
  const canvas=layer.renderer.domElement;
  const raycaster=new THREE.Raycaster(), mouse=new THREE.Vector2();
  canvas.addEventListener('pointerdown',event=>{
    closeContextMenus();
    pointerStart.set(canvas,{x:event.clientX,y:event.clientY,button:event.button});
  });
  canvas.addEventListener('pointercancel',()=>pointerStart.delete(canvas));
  canvas.addEventListener('pointerup',event=>{
    const start=pointerStart.get(canvas);
    pointerStart.delete(canvas);
    // OrbitControls owns rotation and right-drag panning. Short clicks
    // alone select: left for regular shapes, right for ellipses.
    if (!start || start.button!==event.button ||
        Math.hypot(event.clientX-start.x,event.clientY-start.y)>5) return;
    if(event.button!==0 && event.button!==2) return;
    const rect=canvas.getBoundingClientRect();
    mouse.set((event.clientX-rect.left)/rect.width*2-1,
              1-(event.clientY-rect.top)/rect.height*2);
    raycaster.setFromCamera(mouse,layer.camera);
    const pickable=layer.clickable.filter(mesh=>
      selectOnButton(mesh.userData.cadObject,event.button));
    const hit=raycaster.intersectObjects(pickable,false)[0];
    if(!hit) return;
    if(layer.selectedMesh)
      layer.selectedMesh.material.opacity=layer.selectedMesh.userData.originalOpacity;
    const mesh=hit.object;
    if(mesh.userData.originalOpacity===undefined)
      mesh.userData.originalOpacity=mesh.material.opacity;
    mesh.material.opacity=0.95;
    layer.selectedMesh=mesh;
    layer.selectedInfo.textContent=selectionPath(
      workbookName,layer.sheetName,layer.objects,
      mesh.userData.cadObject,toWorldRect);
    if(event.button===2) openContextMenu(layer,event.clientX,event.clientY);
  });
}
document.addEventListener('pointerdown',event=>{
  if(!event.target.closest?.('.cad-context-menu')) closeContextMenus();
});
document.addEventListener('keydown',event=>{
  if(event.key==='Escape') closeContextMenus();
});

function fitScale(width,height) {
  const dw=Math.max(20,sceneBounds.maxX-sceneBounds.minX);
  const dh=Math.max(20,sceneBounds.maxY-sceneBounds.minY);
  return Math.min(width/(dw*1.1),height/(dh*1.1));
}

function resizeCadLayers() {
  const stage=layers[0].stage;
  const w=Math.max(1,stage.clientWidth),h=Math.max(1,stage.clientHeight);
  const nextScale=fitScale(w,h);
  const previousScale=lastCadSize ? fitScale(lastCadSize.w,lastCadSize.h) : nextScale;
  const factor=hasGeometry && previousScale>0 ? nextScale/previousScale : 1;
  syncing=true;
  try {
    for(const layer of layers) {
      const width=Math.max(1,layer.stage.clientWidth);
      const height=Math.max(1,layer.stage.clientHeight);
      layer.renderer.setSize(width,height,false);
      layer.camera.left=-width/2;layer.camera.right=width/2;
      layer.camera.top=height/2;layer.camera.bottom=-height/2;
      layer.camera.zoom=Math.max(0.01,Math.min(100,layer.camera.zoom*factor));
      layer.camera.updateProjectionMatrix();
      layer.controls.update();
    }
  } finally {syncing=false;}
  lastCadSize={w,h};
}

function initialFit() {
  if(!hasGeometry) return;
  const minX=sceneBounds.minX,maxX=sceneBounds.maxX;
  const minY=sceneBounds.minY,maxY=sceneBounds.maxY;
  const target=new THREE.Vector3((minX+maxX)/2,-(minY+maxY)/2,0);
  const distance=Math.max(1000,Math.max(maxX-minX,maxY-minY)*4);
  const zoom=Math.min(100,Math.max(0.01,
    fitScale(layers[0].stage.clientWidth,layers[0].stage.clientHeight)));
  syncing=true;
  try {
    for(const layer of layers) {
      layer.camera.position.set(target.x,target.y,distance);
      layer.camera.zoom=zoom;
      layer.camera.updateProjectionMatrix();
      layer.controls.target.copy(target);
      layer.controls.update();
    }
  } finally {syncing=false;}
  lastCadSize={
    w:Math.max(1,layers[0].stage.clientWidth),
    h:Math.max(1,layers[0].stage.clientHeight),
  };
}

function resetTopView() {
  // Preserve current target (pan), distance, and zoom; ONLY remove tilt/rotation.
  const source=layers[0];
  const target=source.controls.target.clone();
  const distance=Math.max(0.1,source.camera.position.distanceTo(target));
  syncing=true;
  try {
    for(const layer of layers) {
      layer.camera.position.set(target.x,target.y,target.z+distance);
      layer.camera.up.set(0,1,0);
      layer.camera.lookAt(target);
      layer.camera.updateProjectionMatrix(); // zoom intentionally untouched
      layer.controls.target.copy(target);
      layer.controls.update();
    }
  } finally {syncing=false;}
}

function collectPictureBounds(manifest) {
  const boxes=manifest.layers.flatMap(layer=>layer.objects
    .filter(item=>item.type==='image').map(item=>item.bounds_emu));
  if(!boxes.length) return;
  sceneBounds={
    minX:Math.min(...boxes.map(b=>b.x))*EMU_TO_PX,
    maxX:Math.max(...boxes.map(b=>b.x+b.width))*EMU_TO_PX,
    minY:Math.min(...boxes.map(b=>b.y))*EMU_TO_PX,
    maxY:Math.max(...boxes.map(b=>b.y+b.height))*EMU_TO_PX,
  };
  hasGeometry=true;
}

function applySvgSplitRatio() {
  const panel=document.getElementById('reference-frames');
  const ratio=Math.max(0.05,Math.min(0.95,rightSplitRatio));
  panel.style.gridTemplateRows=
    'minmax(0,'+ratio+'fr) 8px minmax(0,'+(1-ratio)+'fr)';
}

function fitSvgHeightToPane() {
  const psd=document.getElementById('psd-frame');
  const octave=document.getElementById('octave-frame');
  const a=referenceImages.get('psd');
  const b=referenceImages.get('octave');
  if(a && b) {
    const sizes=fitSvgPair(
      {width:psd.clientWidth,height:psd.clientHeight},
      {width:octave.clientWidth,height:octave.clientHeight},
      a.ratio,b.ratio);
    a.element.style.width=sizes.width+'px';
    a.element.style.height=sizes.heightA+'px';
    b.element.style.width=sizes.width+'px';
    b.element.style.height=sizes.heightB+'px';
  } else {
    for (const [key,entry] of referenceImages) {
      const frame=document.getElementById(key+'-frame');
      const width=Math.max(0,Math.min(
        frame.clientWidth,frame.clientHeight/entry.ratio));
      entry.element.style.width=width+'px';
      entry.element.style.height=(width*entry.ratio)+'px';
    }
  }
}

function referenceImage(key,info) {
  const image=document.getElementById(key+'-reference');
  const placeholder=document.getElementById(key+'-placeholder');
  if(!info?.available) return;
  image.onload=()=>{
    const width=Math.max(1,image.naturalWidth),height=Math.max(1,image.naturalHeight);
    referenceImages.set(key,{element:image,ratio:height/width});
    image.style.display='block';
    placeholder.hidden=true;
    // Keep the requested initial height split of 5.8:18.1,
    // regardless of the intrinsic SVG dimensions.
    fitSvgHeightToPane();
  };
  image.onerror=()=>{placeholder.textContent='SVG 资源加载失败';};
  image.src=info.url;
}

function installSplitter(id,direction,callback) {
  const bar=document.getElementById(id);
  let pointer=null;
  bar.addEventListener('pointerdown',event=>{
    if(event.button!==0 || getComputedStyle(bar).display==='none') return;
    pointer=event.pointerId;
    bar.setPointerCapture(pointer);
    document.body.classList.add('dragging-divider');
    document.body.classList.toggle('vertical',direction==='horizontal');
    event.preventDefault();
  });
  bar.addEventListener('pointermove',event=>{
    if(pointer!==event.pointerId) return;
    callback(event);
    event.preventDefault();
  });
  const end=()=>{
    pointer=null;
    document.body.classList.remove('dragging-divider','vertical');
  };
  bar.addEventListener('pointerup',end);
  bar.addEventListener('pointercancel',end);
  bar.addEventListener('lostpointercapture',end);
  bar.addEventListener('keydown',event=>{
    if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)) return;
    const current=bar.getBoundingClientRect();
    const x=current.left+current.width/2 +
      (event.key==='ArrowRight'?20:event.key==='ArrowLeft'?-20:0);
    const y=current.top+current.height/2 +
      (event.key==='ArrowDown'?20:event.key==='ArrowUp'?-20:0);
    callback({clientX:x,clientY:y});
    event.preventDefault();
  });
}

installSplitter('main-splitter','vertical',event=>{
  const layout=document.getElementById('layout');
  const bounds=layout.getBoundingClientRect();
  const left=clampMainDivider(event.clientX-bounds.left,bounds.width);
  layout.style.gridTemplateColumns='minmax(0,'+left+'px) 8px minmax(0,1fr)';
  resizeCadLayers();
  fitSvgHeightToPane();
});

installSplitter('reference-splitter','horizontal',event=>{
  const panel=document.getElementById('reference-frames');
  const bounds=panel.getBoundingClientRect();
  rightSplitRatio=clampReferenceSplit(event.clientY-bounds.top,bounds.height);
  applySvgSplitRatio();
  fitSvgHeightToPane();
});

const fab=createLayer('fab-stage');
const subfab=createLayer('subfab-stage');
applySvgSplitRatio();
document.getElementById('reset-view').addEventListener('click',resetTopView);
new ResizeObserver(()=>resizeCadLayers()).observe(document.getElementById('cad-layers'));
new ResizeObserver(()=>fitSvgHeightToPane()).observe(document.getElementById('reference-frames'));
for(const layer of layers) {
  new ResizeObserver(()=>resizeCadLayers()).observe(layer.stage);
}
resizeCadLayers();

async function initialize() {
  try {
    const response=await fetch('./cad-layout.json',{cache:'no-store'});
    if(!response.ok) throw new Error('CAD layout HTTP '+response.status);
    const data=await response.json();
    workbookName=data.workbook || '';
    const targets=[fab,subfab];
    for(let i=0;i<2;i++) {
      const layerData=data.layers[i], layer=targets[i];
      if(!layerData?.available) continue;
      layer.objects=layerData.objects;
      layer.sheetName=layerData.sheet || '';
      const rectangles=rectangleSpecs(layerData.objects,toWorldRect);
      for(const item of layerData.objects) {
        if(item.type==='image') drawImage(layer,item);
        if(item.type==='shape') drawShape(layer,item,rectangles);
      }
    }
    collectPictureBounds(data);
    initialFit();
    referenceImage('psd',data.reference_svgs?.psd);
    referenceImage('octave',data.reference_svgs?.octave);
  } catch(error) {
    console.error('CAD layout failed:',error);
  }
}
initialize();
function animate() {
  requestAnimationFrame(animate);
  for(const layer of layers) layer.renderer.render(layer.scene,layer.camera);
}
animate();
