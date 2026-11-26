// Linked Fab/Subfab Excel CAD viewer. Each picture starts at (0,0) in local XY.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { rectangleHeight, rectangleSpecs, ellipseElevation } from './cad_geometry.mjs';
import {
  INITIAL_REFERENCE_SPLIT, selectOnButton, selectionParts, shapeAncestors, shapeLabel,
  pictureLayerScales, fitSvgPane, clampMainDivider, clampReferenceSplit,
  requiredSvgRatio, canAddOverlay, SVG_COLORS, SVG_LINE_WIDTHS, SVG_LINE_TYPES,
  nextLegendColor,
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
const svgHistory = document.getElementById('reference-log');
const legendMenu = document.getElementById('legend-context-menu');
const overlaySelections = new Map();
const overlayLoads = new Set();
let colorCursor=0;
let lastLegendIndex=-1;
let displayedSvgWidth = 0;

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
    stage,scene,renderer,camera,controls,clickable:[],hoverable:[],objects:[],images:[],
    sheetName:'',selectedMesh:null,scaleX:1,scaleY:1,layerIndex:stageId==='fab-stage'?0:1,
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

function toWorldRect(item,layer=null) {
  const b=item.bounds_emu;
  const sx=layer?.scaleX || 1, sy=layer?.scaleY || 1;
  return {
    x:b.x*EMU_TO_PX*sx,
    y:-b.y*EMU_TO_PX*sy,
    width:Math.max(0.1,b.width*EMU_TO_PX*sx),
    height:Math.max(0.1,b.height*EMU_TO_PX*sy),
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

function kindForElevation(item, rect, rectangles,layer) {
  return item.shape_kind==='ellipse'
    ? ellipseElevation(item,x=>toWorldRect(x,layer),rectangles) : 0;
}

function drawShape(layer,item,rectangles=[]) {
  const r=toWorldRect(item,layer);
  const w=r.width,h=r.height;
  const group=new THREE.Group();
  // The XLSX image is at Z=0; all drawing geometry starts at that plane.
  const raisedZ=kindForElevation(item, r, rectangles,layer);
  group.position.set(r.x+w/2,r.y-h/2,raisedZ);
  group.rotation.z=r.rotation;
  const colors=item.colors || {};
  const kind=item.shape_kind || 'other';
  const fillColor=colorValue(colors.fill,kind==='textbox'?0xffffff:0x3599c3);
  const borderColor=colorValue(colors.outline,0x67dcfc);
  const opacity=kind==='textbox'
    ? (colors.fill==='无/透明'?0:1)
    : colors.fill==='无/透明' ? 0.13 : 0.68;
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
    const depth=rectangleHeight(item.alt_text,w,h);
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
    // Textboxes follow XLSX fill/outline colors; unrecognized shapes stay flat.
    clickTarget=new THREE.Mesh(new THREE.PlaneGeometry(w,h),mat);
    clickTarget.position.z=0.5;
    frontZ=1.2;
    group.add(clickTarget);
    const hw=w/2,hh=h/2;
    const vertices=[
      new THREE.Vector3(-hw,hh,0.8),new THREE.Vector3(hw,hh,0.8),
      new THREE.Vector3(hw,-hh,0.8),new THREE.Vector3(-hw,-hh,0.8),
    ];
    if(kind!=='textbox' || colors.outline!=='无/透明')
      group.add(makeOutline(vertices,borderColor));
  }
  clickTarget.userData.cadObject=item;
  layer.hoverable.push(clickTarget);
  if (kind !== 'textbox') layer.clickable.push(clickTarget);
  drawTopLeftText(group,item.text||'',w,h,colors.text,frontZ);
  layer.scene.add(group);
}

function drawImage(layer,item,texture) {
  if(!texture) return;
  const r=toWorldRect(item,layer);
  const group=new THREE.Group();
  group.position.set(r.x+r.width/2,r.y-r.height/2,0);
  group.rotation.z=r.rotation;
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
}

function loadCadTexture(url) {
  if (!url) return Promise.resolve(null);
  return new Promise(resolve=>{
    new THREE.TextureLoader().load(url,texture=>resolve(texture),undefined,error=>{
      console.error('XLSX image could not be loaded:',url,error);
      resolve(null);
    });
  });
}

function createContextMenu(layer) {
  const menu=document.createElement('div');
  menu.className='cad-context-menu';
  menu.hidden=true;
  menu.setAttribute('role','menu');
  menu.setAttribute('aria-label','椭圆图表时间菜单');
  menu.addEventListener('pointerdown',e=>e.stopPropagation());
  const submenu=document.createElement('div');
  submenu.className='cad-submenu';
  submenu.hidden=true;
  submenu.setAttribute('role','menu');
  submenu.addEventListener('pointerdown',e=>e.stopPropagation());
  layer.stage.append(menu,submenu);
  return {element:menu,submenu,requestId:0};
}

function keepMenuInStage(layer) {
  const menu=layer.menu.element;
  menu.style.left=Math.max(4,Math.min(parseFloat(menu.style.left)||4,
    Math.max(4,layer.stage.clientWidth-menu.offsetWidth-4)))+'px';
  menu.style.top=Math.max(4,Math.min(parseFloat(menu.style.top)||4,
    Math.max(4,layer.stage.clientHeight-menu.offsetHeight-4)))+'px';
}

function closeContextMenus() {
  for(const layer of layers) {
    layer.menu.requestId++;
    layer.menu.element.hidden=true;
    layer.menu.submenu.hidden=true;
  }
}

function showAxisSubmenu(layer,button,date,catalog) {
  const pane=layer.menu.submenu;
  pane.replaceChildren();
  for(const axis of ['X','Y','Z']) {
    const item=document.createElement('button');
    item.type='button';
    item.setAttribute('role','menuitem');
    item.textContent=axis;
    item.addEventListener('click',async()=>{
      const pair=catalog.pairs?.[date]?.[axis];
      if(!pair) {
        item.title='没有匹配此矩形、时间及方向的成对 SVG 文件';
        return;
      }
      try {
        const line=[catalog.rectangle,date,'+'+axis].join('_');
        const selection={layer:layer.layerIndex,
          object_index:layer.objects.indexOf(layer.menu.selectedObject),date,axis};
        await switchReferencePair(pair,line,selection);
        closeContextMenus();
      } catch(error) {
        console.error('Unable to switch SVG pair:',error);
        item.title='SVG 图片载入失败，原图保持不变';
      }
    });
    if(!catalog.pairs?.[date]?.[axis]) {
      item.title='当前没有匹配的 PSD 与 1-3-Octave 两张 SVG';
    }
    pane.append(item);
  }
  pane.hidden=false;
  const stageBounds=layer.stage.getBoundingClientRect();
  const bounds=button.getBoundingClientRect();
  // Submenu is an independent sibling, not nested below the date. It opens
  // to the right, with left-side fallback when close to a viewport edge.
  const menuWidth=layer.menu.element.offsetWidth;
  const popupWidth=Math.max(94,pane.offsetWidth);
  const right=bounds.right-stageBounds.left+2;
  pane.style.left=(right+popupWidth<=layer.stage.clientWidth
    ? right : Math.max(4,bounds.left-stageBounds.left-popupWidth-2))+'px';
  pane.style.top=Math.max(4,Math.min(bounds.top-stageBounds.top,
    layer.stage.clientHeight-pane.offsetHeight-4))+'px';
}

async function openContextMenu(layer,clientX,clientY,selectedObject) {
  closeContextMenus();
  layer.menu.selectedObject=selectedObject;
  const id=layer.menu.requestId;
  const menu=layer.menu.element;
  const bounds=layer.stage.getBoundingClientRect();
  menu.style.left=(clientX-bounds.left)+'px';
  menu.style.top=(clientY-bounds.top)+'px';
  menu.replaceChildren();
  menu.hidden=false;
  const placeholder=document.createElement('div');
  placeholder.textContent='查找 SVG 日期…';
  placeholder.style.padding='7px 10px';
  menu.append(placeholder);
  keepMenuInStage(layer);
  try {
    const index=layer.objects.indexOf(selectedObject);
    const response=await fetch('./cad-svg-catalog/'+layer.layerIndex+'/'+index,
                               {cache:'no-store'});
    if(!response.ok) throw new Error('SVG catalog HTTP '+response.status);
    const catalog=await response.json();
    if(layer.menu.requestId!==id) return;
    menu.replaceChildren();
    if(!catalog.dates?.length) {
      const empty=document.createElement('div');
      empty.textContent='无可用时间标签';
      empty.style.padding='7px 10px';
      menu.append(empty);
    } else {
      for(const date of catalog.dates) {
        const button=document.createElement('button');
        button.type='button';
        button.setAttribute('role','menuitem');
        button.setAttribute('aria-haspopup','true');
        button.setAttribute('aria-expanded','false');
        const caption=document.createElement('span');
        caption.textContent=date;
        const arrow=document.createElement('span');
        arrow.className='cad-menu-arrow';
        arrow.textContent='›';
        button.append(caption,arrow);
        button.addEventListener('click',()=>{
          for(const btn of menu.querySelectorAll('button')) {
            btn.setAttribute('aria-expanded','false');
          }
          button.setAttribute('aria-expanded','true');
          showAxisSubmenu(layer,button,date,catalog);
        });
        menu.append(button);
      }
    }
    keepMenuInStage(layer);
  } catch(error) {
    if(layer.menu.requestId!==id) return;
    console.error('SVG catalog lookup failed:',error);
    placeholder.textContent='SVG 日期查询失败';
  }
}

function installPicking(layer) {
  const canvas=layer.renderer.domElement;
  const raycaster=new THREE.Raycaster(), mouse=new THREE.Vector2();
  function pick(clientX,clientY,button=null) {
    const rect=canvas.getBoundingClientRect();
    if(!rect.width || !rect.height) return null;
    mouse.set((clientX-rect.left)/rect.width*2-1,
              1-(clientY-rect.top)/rect.height*2);
    raycaster.setFromCamera(mouse,layer.camera);
    const targets=button===null ? layer.hoverable : layer.clickable.filter(mesh=>
      selectOnButton(mesh.userData.cadObject,button));
    return raycaster.intersectObjects(targets,false)[0]?.object || null;
  }
  canvas.addEventListener('pointermove',event=>{
    // Hover breadcrumbs are independent per pane; a drag must never select.
    if(event.buttons!==0) return;
    const mesh=pick(event.clientX,event.clientY);
    const parts=mesh
      ? selectionParts(layer.objects,mesh.userData.cadObject,
                       obj=>toWorldRect(obj,layer)) : [];
    layer.selectedInfo.replaceChildren();
    parts.forEach((part,i)=>{
      if(i) layer.selectedInfo.append(document.createTextNode('·'));
      const node=document.createElement(part.kind==='textbox'?'strong':'span');
      node.textContent=part.text;
      layer.selectedInfo.append(node);
    });
  });
  canvas.addEventListener('pointerleave',()=>{layer.selectedInfo.textContent='';});
  canvas.addEventListener('pointerdown',event=>{
    closeContextMenus();
    pointerStart.set(canvas,{x:event.clientX,y:event.clientY,button:event.button});
  });
  canvas.addEventListener('pointercancel',()=>pointerStart.delete(canvas));
  canvas.addEventListener('pointerup',event=>{
    const start=pointerStart.get(canvas);
    pointerStart.delete(canvas);
    if(!start || start.button!==event.button ||
       Math.hypot(event.clientX-start.x,event.clientY-start.y)>5) return;
    if(event.button!==0 && event.button!==2) return;
    const mesh=pick(event.clientX,event.clientY,event.button);
    if(!mesh) return;
    if(layer.selectedMesh)
      layer.selectedMesh.material.opacity=layer.selectedMesh.userData.originalOpacity;
    if(mesh.userData.originalOpacity===undefined)
      mesh.userData.originalOpacity=mesh.material.opacity;
    mesh.material.opacity=0.95;
    layer.selectedMesh=mesh;
    if(event.button===2) void openContextMenu(layer,event.clientX,event.clientY,
                                            mesh.userData.cadObject);
  });
}

document.addEventListener('pointerdown',event=>{
  if(!event.target.closest?.('.cad-context-menu,.cad-submenu')) closeContextMenus();
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

function collectPictureBounds() {
  const imageRects=layers.flatMap(layer=>layer.images.map(item=>toWorldRect(item,layer)));
  if(!imageRects.length) return;
  sceneBounds={
    minX:Math.min(...imageRects.map(b=>b.x)),
    maxX:Math.max(...imageRects.map(b=>b.x+b.width)),
    minY:Math.min(...imageRects.map(b=>-b.y)),
    maxY:Math.max(...imageRects.map(b=>-b.y+b.height)),
  };
  hasGeometry=true;
}

function applySvgSplitRatio() {
  const panel=document.getElementById('reference-frames');
  panel.style.gridTemplateRows=
    'minmax(0,'+rightSplitRatio+'fr) 8px minmax(0,'+(1-rightSplitRatio)+'fr)';
}

function displayedRatio(key) {
  const base=referenceImages.get(key);
  return requiredSvgRatio(base?.ratio||1,
    [...overlaySelections.values()].map(entry=>entry[key].ratio));
}

function fitSvgHeightToPane() {
  // Each pane uses its own available width and height. An oversized image is
  // scaled down by whichever dimension would otherwise exceed its pane.
  let widest=0;
  for(const key of ['psd','octave']) {
    const frame=document.getElementById(key+'-frame');
    const base=referenceImages.get(key);
    const {width}=fitSvgPane(frame.clientWidth,frame.clientHeight,displayedRatio(key));
    widest=Math.max(widest,width);
    if(base) {
      base.element.style.width=width+'px';
      base.element.style.height=(width*base.ratio)+'px';
    }
    for(const entry of overlaySelections.values()) {
      const layer=entry[key];
      layer.element.style.width=width+'px';
      layer.element.style.height=(width*layer.ratio)+'px';
    }
  }
  displayedSvgWidth=widest;
}

function applyReferenceImage(key,url,width,height) {
  const image=document.getElementById(key+'-reference');
  const placeholder=document.getElementById(key+'-placeholder');
  image.src=url;
  image.style.display='block';
  placeholder.hidden=true;
  referenceImages.set(key,{element:image,ratio:height/width});
}

function prefetchSvg(url) {
  return new Promise((resolve,reject)=>{
    const probe=new Image();
    probe.onload=()=>resolve({
      url,width:Math.max(1,probe.naturalWidth),height:Math.max(1,probe.naturalHeight),
    });
    probe.onerror=()=>reject(new Error('SVG image failed: '+url));
    probe.src=url;
  });
}

function styleUrl(url) {
  return url+(url.includes('?')?'&':'?')+'v='+Date.now();
}

async function persistSvgStyle(selection,operation,value) {
  const response=await fetch('./cad-svg-style',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({...selection,operation,value}),
  });
  if(!response.ok) throw new Error('SVG 修改未保存 (HTTP '+response.status+')');
  const result=await response.json();
  if(!result.saved || !result.pair?.psd || !result.pair?.octave)
    throw new Error('SVG 修改未得到本地写入确认');
  return result.pair;
}

async function switchReferencePair(pair,label,selection) {
  if(!canAddOverlay(overlaySelections,overlayLoads,label)) return false;
  overlayLoads.add(label);
  try {
    // The same palette entry is saved in BOTH SVG files before displaying
    // either one. It cycles per successfully requested new legend item.
    const color=nextLegendColor(colorCursor++);
    const urls=await persistSvgStyle(selection,'color',color);
    const [psd,octave]=await Promise.all([
      prefetchSvg(styleUrl(urls.psd)),prefetchSvg(styleUrl(urls.octave)),
    ]);
    if(overlaySelections.has(label)) return false;
    const entry={selection,color,width:'1.5',dash:'--',saving:false};
    for(const [key,image] of [['psd',psd],['octave',octave]]) {
      const element=document.createElement('img');
      element.alt='';
      element.className='reference-overlay-image';
      element.decoding='async';
      element.style.background='transparent';
      element.src=image.url;
      entry[key]={element,ratio:image.height/image.width,url:urls[key]};
    }
    overlaySelections.set(label,entry);
    document.getElementById('psd-overlays').append(entry.psd.element);
    document.getElementById('octave-overlays').append(entry.octave.element);
    appendReferenceHistory(label,entry);
    fitSvgHeightToPane();
    return true;
  } finally {
    overlayLoads.delete(label);
  }
}

function referenceImage(key,info) {
  const placeholder=document.getElementById(key+'-placeholder');
  if(!info?.available) return;
  prefetchSvg(info.url).then(image=>{
    applyReferenceImage(key,image.url,image.width,image.height);
    fitSvgHeightToPane();
  }).catch(error=>{
    placeholder.textContent='SVG 资源加载失败';
    console.error(error);
  });
}

function appendReferenceHistory(label,entry) {
  svgHistory.style.display='block';
  const line=document.createElement('span');
  line.className='reference-log-line';
  line.dataset.legend=label;
  line.textContent=label;
  line.style.color=entry.color;
  line.addEventListener('contextmenu',event=>{
    event.preventDefault();
    event.stopPropagation();
    showLegendMenu(label,event.clientX,event.clientY);
  });
  entry.legend=line;
  svgHistory.append(line);
  clampFloatingLog();
}

function removeReferenceOverlay(label) {
  const entry=overlaySelections.get(label);
  if(!entry) return;
  entry.psd.element.remove();
  entry.octave.element.remove();
  entry.legend.remove();
  overlaySelections.delete(label);
  legendMenu.hidden=true;
  if(!overlaySelections.size) svgHistory.style.display='none';
  fitSvgHeightToPane();
  clampFloatingLog();
}

async function changeLegendStyle(label,operation,value) {
  const entry=overlaySelections.get(label);
  if(!entry || entry.saving) return;
  entry.saving=true;
  try {
    const urls=await persistSvgStyle(entry.selection,operation,value);
    const [psd,octave]=await Promise.all([
      prefetchSvg(styleUrl(urls.psd)),prefetchSvg(styleUrl(urls.octave)),
    ]);
    if(!overlaySelections.has(label)) return;
    for(const [key,image] of [['psd',psd],['octave',octave]]) {
      entry[key].element.src=image.url;
      entry[key].ratio=image.height/image.width;
      entry[key].url=urls[key];
    }
    if(operation==='color') {
      entry.color=value;
      entry.legend.style.color=value;
    }
    if(operation==='width') entry.width=value;
    if(operation==='dash') entry.dash=value;
    fitSvgHeightToPane();
    legendMenu.hidden=true;
  } catch(error) {
    console.error('Cannot save local SVG styling:',error);
    legendMenu.title='修改失败：'+error.message;
  } finally {
    entry.saving=false;
  }
}

function showLegendMenu(label,x,y) {
  if(!overlaySelections.has(label)) return;
  const pane=document.getElementById('reference-pane');
  const bounds=pane.getBoundingClientRect();
  legendMenu.replaceChildren();
  const primary=document.createElement('div');
  primary.className='legend-menu-primary';
  const secondary=document.createElement('div');
  secondary.className='legend-menu-secondary';
  secondary.hidden=true;
  legendMenu.append(primary,secondary);
  for(const [title,kind,options] of [
    ['颜色','color',SVG_COLORS],
    ['线宽','width',SVG_LINE_WIDTHS],
    ['线型','dash',SVG_LINE_TYPES],
  ]) {
    const button=document.createElement('button');
    button.type='button';
    button.setAttribute('role','menuitem');
    button.textContent=title+' ›';
    button.addEventListener('click',()=>{
      secondary.replaceChildren();
      for(const option of options) {
        const item=document.createElement('button');
        item.type='button';
        item.setAttribute('role','menuitem');
        item.textContent=option;
        if(kind==='color') item.style.color=option;
        item.addEventListener('click',()=>{void changeLegendStyle(label,kind,option);});
        secondary.append(item);
      }
      secondary.hidden=false;
      const primaryWidth=primary.offsetWidth;
      const popupWidth=secondary.offsetWidth;
      // Right-opening vertically stacked options, with edge fallback.
      secondary.style.left=(parseFloat(legendMenu.style.left||'0')
        +primaryWidth+popupWidth<=pane.clientWidth ? primaryWidth : -popupWidth)+'px';
      secondary.style.top=Math.max(0,Math.min(
        button.offsetTop,pane.clientHeight-secondary.offsetHeight-
        parseFloat(legendMenu.style.top||'0')))+'px';
    });
    primary.append(button);
  }
  const close=document.createElement('button');
  close.type='button';
  close.setAttribute('role','menuitem');
  close.textContent='退出';
  close.addEventListener('click',()=>removeReferenceOverlay(label));
  primary.append(close);
  legendMenu.hidden=false;
  legendMenu.style.left=Math.max(0,Math.min(x-bounds.left,
    pane.clientWidth-legendMenu.offsetWidth))+'px';
  legendMenu.style.top=Math.max(0,Math.min(y-bounds.top,
    pane.clientHeight-legendMenu.offsetHeight))+'px';
}
document.addEventListener('pointerdown',event=>{
  if(!legendMenu.contains(event.target)) legendMenu.hidden=true;
});
document.addEventListener('keydown',event=>{
  if(event.key==='Escape') legendMenu.hidden=true;
});

function clampFloatingLog() {
  if(svgHistory.style.display==='none') return;
  const pane=document.getElementById('reference-pane');
  if(!svgHistory.style.left) return;
  svgHistory.style.left=Math.max(0,Math.min(parseFloat(svgHistory.style.left)||0,
    pane.clientWidth-svgHistory.offsetWidth))+'px';
  svgHistory.style.top=Math.max(0,Math.min(parseFloat(svgHistory.style.top)||0,
    pane.clientHeight-svgHistory.offsetHeight))+'px';
}

function installFloatingLogDrag() {
  const pane=document.getElementById('reference-pane');
  let move=null;
  svgHistory.addEventListener('pointerdown',event=>{
    if(event.button!==0) return;
    const panelRect=pane.getBoundingClientRect();
    const box=svgHistory.getBoundingClientRect();
    svgHistory.style.left=(box.left-panelRect.left)+'px';
    svgHistory.style.top=(box.top-panelRect.top)+'px';
    svgHistory.style.right='auto';
    move={pointer:event.pointerId,x:event.clientX,y:event.clientY,
          left:box.left-panelRect.left,top:box.top-panelRect.top};
    svgHistory.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  svgHistory.addEventListener('pointermove',event=>{
    if(!move || event.pointerId!==move.pointer) return;
    const left=move.left+event.clientX-move.x;
    const top=move.top+event.clientY-move.y;
    svgHistory.style.left=Math.max(0,Math.min(left,pane.clientWidth-svgHistory.offsetWidth))+'px';
    svgHistory.style.top=Math.max(0,Math.min(top,pane.clientHeight-svgHistory.offsetHeight))+'px';
  });
  for (const name of ['pointerup','pointercancel','lostpointercapture']) {
    svgHistory.addEventListener(name,()=>{move=null;});
  }
}
installFloatingLogDrag();

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
  const left=clampMainDivider(event.clientX-bounds.left,bounds.width,8,displayedSvgWidth);
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
new ResizeObserver(()=>{
  fitSvgHeightToPane();
  clampFloatingLog();
}).observe(document.getElementById('reference-frames'));
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
    document.title=workbookName || 'Fab / Subfab CAD';

    const layerImages=data.layers.map(src=>
      src?.objects?.find(item=>item.type==='image') || null);
    const textures=await Promise.all(layerImages.map(item=>loadCadTexture(item?.image_url)));
    const bounds=layerImages.map(item=>({
      width:(item?.bounds_emu?.width||9525)*EMU_TO_PX,
      height:(item?.bounds_emu?.height||9525)*EMU_TO_PX,
    }));
    const ratios=textures.map((texture,i)=>{
      const picture=texture?.image;
      const width=picture?.naturalWidth||picture?.width;
      const height=picture?.naturalHeight||picture?.height;
      return width && height ? height/width : bounds[i].height/bounds[i].width;
    });
    const transforms=pictureLayerScales(bounds,ratios);

    const targets=[fab,subfab];
    for(let i=0;i<targets.length;i++) {
      const layerData=data.layers[i],layer=targets[i];
      if(!layerData?.available) continue;
      layer.objects=layerData.objects;
      layer.sheetName=layerData.sheet || '';
      layer.scaleX=transforms[i].x;
      layer.scaleY=transforms[i].y;
      layer.images=layerImages[i] ? [layerImages[i]] : [];
      const rectangles=rectangleSpecs(layer.objects,obj=>toWorldRect(obj,layer));
      for(const item of layer.objects) {
        if(item.type==='image') drawImage(layer,item,textures[i]);
        if(item.type==='shape') drawShape(layer,item,rectangles);
      }
    }
    collectPictureBounds();
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
