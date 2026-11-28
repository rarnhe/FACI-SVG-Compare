// Linked Fab/Subfab Excel CAD viewer. Each picture starts at (0,0) in local XY.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { rectangleHeight, rectangleSpecs, ellipseElevation, worldRectFromEmu, reconstructedCircleRadius } from './cad_geometry.mjs';
import {
  INITIAL_REFERENCE_SPLIT, selectOnButton, selectionParts, shapeAncestors, shapeLabel,
  pictureLayerScales, fitSvgPane, clampMainDivider, clampReferenceSplit,
  requiredSvgRatio, canAddOverlay, fitLegendSubmenu, nextLegendColor,
  restyleSvgMarkup, mergeSvgStyle, SVG_COLOR_CHOICES, SVG_LINE_WIDTHS, SVG_LINE_TYPES, svgLegendName, svgSelectionKey,
  cadOutlineSpec, cadOutlineSegments,
  rectangleHasAltText, planarOutlineVertices,
  CUBOID_FACE_OPACITY, CUBOID_SELECTED_OPACITY,
  CAD_DRAW_ORDER, cadShapeRenderOrder, cadShapeZOffset,
  textboxFont, layoutTextboxText,
} from './cad_ui.mjs';

const EMU_TO_PX = 1 / 9525;
export const layers = []; // read-only binding for browser integration tests
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
    stage,scene,renderer,camera,controls,clickable:[],hoverable:[],objects:[],images:[],outlineMeshes:[],outlineZoom:null,
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
  return worldRectFromEmu(item,layer?.scaleX??1);
}

function colorValue(value,fallback) {
  return typeof value==='string' && /^#[0-9a-f]{6}$/i.test(value)
    ? parseInt(value.slice(1),16) : fallback;
}

// Use actual instanced mesh cylinders, not WebGL line widths. All edges
// (including vertical ones) have a visible screen-space thickness at
// arbitrary camera angles. Each shape owns its own instance buffer.
const outlineCylinder=new THREE.CylinderGeometry(1,1,1,10,1,false);
const outlineUp=new THREE.Vector3(0,1,0);
function updateOutlineMesh(mesh,zoom) {
  const radius=mesh.userData.outlineWidth/(2*Math.max(0.01,zoom));
  const transform=new THREE.Object3D();
  for(let i=0;i<mesh.userData.outlineSegments.length;i++) {
    const segment=mesh.userData.outlineSegments[i];
    transform.position.fromArray(segment.center);
    transform.quaternion.setFromUnitVectors(outlineUp,new THREE.Vector3(...segment.direction));
    // Slight overlap at joints closes gaps on rectangles and circles.
    transform.scale.set(radius,segment.length+radius*0.8,radius);
    transform.updateMatrix();
    mesh.setMatrixAt(i,transform.matrix);
  }
  mesh.instanceMatrix.needsUpdate=true;
}
function updateLayerOutlines(layer) {
  const zoom=layer.camera.zoom;
  if(layer.outlineZoom===zoom) return;
  for(const mesh of layer.outlineMeshes) updateOutlineMesh(mesh,zoom);
  layer.outlineZoom=zoom;
}
function makeThickSegments(positions,outline,layer) {
  const segments=cadOutlineSegments(positions);
  if(!segments.length) return [];
  // Only the original XLSX RGB (or exact fill RGB for a missing border).
  // No contrast underlay, shading, or alternate color fallback.
  const material=new THREE.MeshBasicMaterial({
    color:parseInt(outline.color.slice(1),16),transparent:true,opacity:1,
    depthTest:false,depthWrite:false,toneMapped:false,
  });
  const mesh=new THREE.InstancedMesh(outlineCylinder,material,segments.length);
  mesh.frustumCulled=false;
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  Object.assign(mesh.userData,{isCadOutline:true,
    outlineWidth:outline.width,outlineSegments:segments});
  updateOutlineMesh(mesh,layer.camera.zoom);
  layer.outlineMeshes.push(mesh);
  return [mesh];
}
function makeOutline(points,outline,layer) {
  const positions=[];
  for(let i=0;i<points.length;i++) {
    const a=points[i],b=points[(i+1)%points.length];
    positions.push(a.x,a.y,a.z,b.x,b.y,b.z);
  }
  return makeThickSegments(positions,outline,layer);
}

// Both sensor circles and rectangles without alternative text use the
// same closed-loop renderer and DrawingML-derived outline specification.
function makePlanarOutline(kind,w,h,outline,layer) {
  return makeOutline(planarOutlineVertices(kind,w,h).map(p=>new THREE.Vector3(...p)),outline,layer);
}

function drawTextboxText(group,item,worldRect) {
  if(!item.text) return;
  const w=Math.max(1,item.bounds_emu.width*EMU_TO_PX);
  const h=Math.max(1,item.bounds_emu.height*EMU_TO_PX);
  const layout=item.text_layout || {
    anchor:'top',insets_px:{left:4,right:4,top:4,bottom:4},
    paragraphs:item.text.split('\n').map(text=>({
      align:'left',runs:[{text,font_family:'Calibri',
        font_size_pt:11,color:'#000000'}],
    })),
  };
  // Bounded CanvasTexture avoids blurry text and unbounded WebGL textures
  // from exceptionally large DrawingML objects.
  const resolution=Math.max(0.2,Math.min(2.5,
    Math.min(4096/w,4096/h),window.devicePixelRatio||1.5));
  const canvas=document.createElement('canvas');
  canvas.width=Math.max(1,Math.ceil(w*resolution));
  canvas.height=Math.max(1,Math.ceil(h*resolution));
  const context=canvas.getContext('2d');
  if(!context) return;
  context.scale(resolution,resolution);
  context.textBaseline='top';
  const widths=new Map();
  const commands=layoutTextboxText(layout,w,h,(text,run)=>{
    const font=textboxFont(run);
    context.font=font;
    const key=font+'\u0000'+text;
    if(!widths.has(key)) widths.set(key,context.measureText(text).width);
    return widths.get(key);
  });
  context.save();
  context.beginPath();
  context.rect(0,0,w,h);
  context.clip();
  for(const part of commands) {
    context.font=textboxFont(part.run);
    context.fillStyle=/^#[\da-f]{6}$/i.test(part.run?.color||'')
      ? part.run.color : '#000000';
    context.fillText(part.text,part.x,part.y);
  }
  context.restore();
  const texture=new THREE.CanvasTexture(canvas);
  texture.colorSpace=THREE.SRGBColorSpace;
  const textMesh=new THREE.Mesh(
    new THREE.PlaneGeometry(worldRect.width,worldRect.height),
    new THREE.MeshBasicMaterial({
      map:texture,transparent:true,side:THREE.DoubleSide,
      depthWrite:false,depthTest:false,
    }),
  );
  // Slightly in front of the textbox plane, yet still in the textbox
  // semantic layer, so a rotated cuboid/ellipse remains above the text.
  textMesh.position.z=0.9;
  textMesh.userData.isTextboxText=true;
  group.add(textMesh);
}

function kindForElevation(item, rect, rectangles,layer) {
  return item.shape_kind==='ellipse'
    ? ellipseElevation(item,x=>toWorldRect(x,layer),rectangles) : 0;
}

function drawShape(layer,item,rectangles=[]) {
  const r=toWorldRect(item,layer);
  const w=r.width,h=r.height;
  const group=new THREE.Group();
  const kind=item.shape_kind || 'other';
  const priority=cadShapeRenderOrder(kind);
  // Keep the real rectangle height/ellipse elevation while making the
  // textbox a true bottom layer and ellipses the topmost shape layer.
  const raisedZ=kindForElevation(item, r, rectangles,layer);
  group.position.set(r.x+w/2,r.y-h/2,raisedZ+cadShapeZOffset(kind));
  group.rotation.z=r.rotation;
  group.renderOrder=priority;
  const colors=item.colors || {};
  const fillColor=colorValue(colors.fill,kind==='textbox'?0xffffff:0x3599c3);
  const outline=cadOutlineSpec(item);
  if(item.outline_status==='unresolved') console.warn('Unresolved XLSX outline:',layer.sheetName,item.name);
  const opacity=kind==='textbox'
    ? (colors.fill==='无/透明'?0:1)
    : colors.fill==='无/透明' ? 0.13 : 0.68;
  const mat=new THREE.MeshBasicMaterial({
    color:fillColor,transparent:true,opacity,
    side:THREE.DoubleSide,depthWrite:false,
  });
  let clickTarget;
  if(kind==='ellipse') {
    // Per drawing requirement: the diagonals meet at the center, and
    // upper-left -> lower-right is the diameter (not the minor axis).
    const radius=reconstructedCircleRadius(w,h);
    clickTarget=new THREE.Mesh(new THREE.CircleGeometry(radius,72),mat);
    clickTarget.position.z=0.5;
    clickTarget.renderOrder=2;
    group.add(clickTarget);
    if(outline) group.add(...makePlanarOutline('ellipse',w,h,outline,layer));
  } else if(kind==='rectangle') {
    // Translucent solid (NOT a wireframe): both roof and side faces remain
    // visible while allowing elevated ellipse measurement points to show.
    const depth=rectangleHeight(item.alt_text,w,h);
    if (depth>0) {
      const cube=new THREE.BoxGeometry(w,h,depth);
      const translucent=new THREE.MeshBasicMaterial({
        color:fillColor,transparent:true,opacity:CUBOID_FACE_OPACITY,
        side:THREE.FrontSide,wireframe:false,depthTest:true,depthWrite:false,
      });
      clickTarget=new THREE.Mesh(cube,translucent);
      clickTarget.position.z=depth/2;
      clickTarget.renderOrder=1;
      clickTarget.userData.isTransparentCuboid=true;
      group.add(clickTarget);
      // Outline all 12 edges using the original DrawingML line color.
      // Draw after the solid faces so the cuboid remains readable on
      // rotation, including near-parallel views.
      if(outline) {
        const geometry=new THREE.EdgesGeometry(cube);
        const edges=makeThickSegments(geometry.attributes.position.array,outline,layer);
        geometry.dispose();
        for(const mesh of edges) mesh.position.copy(clickTarget.position);
        group.add(...edges);
      }
    } else {
      // Missing/invalid directive: zero height, no artificial thickness.
      clickTarget=new THREE.Mesh(new THREE.PlaneGeometry(w,h),mat);
      clickTarget.position.z=0;
      group.add(clickTarget);
      if(outline && !rectangleHasAltText(item.alt_text)) {
        // Same planar boundary routine as ellipse. A nested group with a
        // later group order keeps every flat border above rectangle fills,
        // but below the existing ellipse layer, even after tilting.
        const borderGroup=new THREE.Group();
        borderGroup.renderOrder=priority+0.75;
        borderGroup.userData.isFlatRectangleOutline=true;
        borderGroup.add(...makePlanarOutline('rectangle',w,h,outline,layer));
        group.add(borderGroup);
      } else if(outline) {
        // A nonempty but invalid/zero height directive retains old behavior.
        const hw=w/2,hh=h/2;
        group.add(...makeOutline([
          new THREE.Vector3(-hw,hh,0.2),new THREE.Vector3(hw,hh,0.2),
          new THREE.Vector3(hw,-hh,0.2),new THREE.Vector3(-hw,-hh,0.2),
        ],outline,layer));
      }
    }
  } else {
    // Textboxes follow XLSX fill/outline colors; unrecognized shapes stay flat.
    clickTarget=new THREE.Mesh(new THREE.PlaneGeometry(w,h),mat);
    clickTarget.position.z=0.5;
    group.add(clickTarget);
    const hw=w/2,hh=h/2;
    const vertices=[
      new THREE.Vector3(-hw,hh,0.8),new THREE.Vector3(hw,hh,0.8),
      new THREE.Vector3(hw,-hh,0.8),new THREE.Vector3(-hw,-hh,0.8),
    ];
    if(outline) group.add(...makeOutline(vertices,outline,layer));
    if(kind==='textbox') drawTextboxText(group,item,r);
  }
  // Explicit render order overrides the reversed transparent-object
  // distance sort during rotation. All materials are transparent and
  // depthWrite:false; outlines remain above their own filled surfaces.
  group.traverse(node=>{
    if(node.isMesh || node.isLine || node.isLineSegments) {
      node.renderOrder=priority+(node.userData.isCadOutline
        ? 0.5
        : node.userData.isTextboxText ? 0.1 : 0);
    }
  });
  clickTarget.userData.cadObject=item;
  layer.hoverable.push(clickTarget);
  if (kind !== 'textbox') layer.clickable.push(clickTarget);
  layer.scene.add(group);
}

function drawImage(layer,item,texture) {
  if(!texture) return;
  const r=toWorldRect(item,layer);
  const group=new THREE.Group();
  group.position.set(r.x+r.width/2,r.y-r.height/2,0);
  group.rotation.z=r.rotation;
  group.renderOrder=CAD_DRAW_ORDER.image;
  texture.colorSpace=THREE.SRGBColorSpace;
  texture.anisotropy=Math.min(8,layer.renderer.capabilities.getMaxAnisotropy());
  const image=new THREE.Mesh(
    new THREE.PlaneGeometry(r.width,r.height),
    new THREE.MeshBasicMaterial({
      map:texture,side:THREE.DoubleSide,transparent:true,depthWrite:false,
    }),
  );
  image.renderOrder=CAD_DRAW_ORDER.image;
  group.add(image);
  layer.scene.add(group);
}

function loadCadTexture(url) {
  if (!url) return Promise.resolve(null);
  return new Promise(resolve=>{
    new THREE.TextureLoader().load(url,texture=>resolve(texture),undefined,error=>{
      console.error('XLSX embedded picture could not be loaded:',url,error);
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
        item.title='没有匹配当前矩形或测点、时间及方向的成对 SVG 文件';
        return;
      }
      try {
        const label=svgLegendName(catalog,axis);
        const key=svgSelectionKey(catalog,date,axis);
        await switchReferencePair(pair,key,label,catalog.csv_files?.[date]?.[axis]??[]);
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
      empty.textContent='无可用测试结果';
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
    layer.camera.updateMatrixWorld();
    layer.scene.updateMatrixWorld(true);
    raycaster.setFromCamera(mouse,layer.camera);
    const targets=button===null ? layer.hoverable : layer.clickable.filter(mesh=>
      selectOnButton(mesh.userData.cadObject,button));
    const hits=raycaster.intersectObjects(targets,false);
    if(button===null) {
      // Hover follows the same semantic layering as the visible drawings,
      // not the ray's nearest hit from an oblique camera angle.
      hits.sort((a,b)=>cadShapeRenderOrder(b.object.userData.cadObject?.shape_kind)
        -cadShapeRenderOrder(a.object.userData.cadObject?.shape_kind)
        || a.distance-b.distance);
    }
    return hits[0]?.object || null;
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
    mesh.material.opacity=mesh.userData.isTransparentCuboid
      ? CUBOID_SELECTED_OPACITY : 0.95;
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

// Original SVG sources are immutable, fetched once per URL (including
// concurrent requests). No SVG is ever written back to assets/ or POSTed.
const svgSourceCache=new Map();
function originalSvg(url) {
  if(!svgSourceCache.has(url)) {
    const reading=fetch(url).then(response=>{
      if(!response.ok) throw new Error('SVG source HTTP '+response.status);
      return response.text();
    }).catch(error=>{
      svgSourceCache.delete(url); // Permit a later retry.
      throw error;
    });
    svgSourceCache.set(url,reading);
  }
  return svgSourceCache.get(url);
}

function releaseColoredPair(pair) {
  for(const key of ['psd','octave']) {
    if(pair?.[key]?.blobUrl) URL.revokeObjectURL(pair[key].blobUrl);
  }
}

async function makeColoredPair(sourcePair,style) {
  const [psdMarkup,octaveMarkup]=await Promise.all([
    originalSvg(sourcePair.psd),originalSvg(sourcePair.octave),
  ]);
  const result={};
  try {
    for(const [key,markup] of [['psd',psdMarkup],['octave',octaveMarkup]]) {
      const colorized=restyleSvgMarkup(markup,style,key);
      const blobUrl=URL.createObjectURL(new Blob([colorized],{
        type:'image/svg+xml;charset=utf-8',
      }));
      result[key]={blobUrl};
    }
    const [psd,octave]=await Promise.all([
      prefetchSvg(result.psd.blobUrl),prefetchSvg(result.octave.blobUrl),
    ]);
    Object.assign(result.psd,psd);
    Object.assign(result.octave,octave);
    return result;
  } catch(error) {
    releaseColoredPair(result);
    throw error;
  }
}

async function switchReferencePair(pair,key,label,csvFiles=[]) {
  // Internally dedupe by actual date as well as named shape and axis.
  if(!canAddOverlay(overlaySelections,overlayLoads,key)) return false;
  overlayLoads.add(key);
  try {
    const color=nextLegendColor(colorCursor++);
    const style=mergeSvgStyle({color,lineStyle:'none',lineWidth:2});
    const previews=await makeColoredPair(pair,style);
    if(overlaySelections.has(key)) {
      releaseColoredPair(previews);
      return false;
    }
    const entry={sourcePair:{psd:pair.psd,octave:pair.octave},color,style,saving:false,csvFiles,downloading:false};
    for(const key of ['psd','octave']) {
      const preview=previews[key],element=document.createElement('img');
      element.alt='';
      element.decoding='async';
      element.className='reference-overlay-image';
      element.style.background='transparent';
      element.src=preview.url;
      entry[key]={element,ratio:preview.height/preview.width,
        blobUrl:preview.blobUrl};
    }
    overlaySelections.set(key,entry);
    document.getElementById('psd-overlays').append(entry.psd.element);
    document.getElementById('octave-overlays').append(entry.octave.element);
    appendReferenceHistory(key,label,entry);
    fitSvgHeightToPane();
    return true;
  } finally {
    overlayLoads.delete(key);
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

function appendReferenceHistory(key,label,entry) {
  svgHistory.style.display='block';
  const line=document.createElement('span');
  line.className='reference-log-line';
  line.dataset.legend=key;
  line.textContent=label;
  line.style.color=entry.color;
  line.addEventListener('contextmenu',event=>{
    event.preventDefault();
    event.stopPropagation();
    showLegendMenu(key,event.clientX,event.clientY);
  });
  entry.legend=line;
  svgHistory.append(line);
  clampFloatingLog();
}

function removeReferenceOverlay(key) {
  const entry=overlaySelections.get(key);
  if(!entry) return;
  entry.psd.element.remove();
  entry.octave.element.remove();
  entry.legend.remove();
  overlaySelections.delete(key);
  releaseColoredPair(entry);
  legendMenu.hidden=true;
  if(!overlaySelections.size) svgHistory.style.display='none';
  fitSvgHeightToPane();
  clampFloatingLog();
}

async function changeLegendStyle(key,patch) {
  const entry=overlaySelections.get(key);
  if(!entry || entry.saving) return;
  const style=mergeSvgStyle(entry.style,patch);
  if(Object.keys(style).every(name=>style[name]===entry.style[name])) return;
  entry.saving=true;
  try {
    const next=await makeColoredPair(entry.sourcePair,style);
    if(overlaySelections.get(key)!==entry) {
      releaseColoredPair(next);
      return;
    }
    const previous={psd:{blobUrl:entry.psd.blobUrl},
      octave:{blobUrl:entry.octave.blobUrl}};
    for(const key of ['psd','octave']) {
      entry[key].element.src=next[key].url;
      entry[key].ratio=next[key].height/next[key].width;
      entry[key].blobUrl=next[key].blobUrl;
    }
    entry.style=style;
    entry.color=style.color??'#808080';
    entry.legend.style.color=entry.color;
    fitSvgHeightToPane();
    legendMenu.hidden=true;
    releaseColoredPair(previous);
  } catch(error) {
    console.error('SVG style adjustment failed:',error);
    legendMenu.title='样式调整失败: '+error.message;
    window.alert('SVG 样式调整失败：'+error.message);
  } finally {
    entry.saving=false;
  }
}

async function downloadLegendCsv(entry) {
  if(entry.downloading) return;
  if(!entry.csvFiles.length) {
    window.alert('未提供符合当前测点、时间和方向的测试文件');
    return;
  }
  entry.downloading=true;
  const failures=[];
  try {
    for(const file of entry.csvFiles) {
      let url;
      try {
        const response=await fetch(file.url);
        if(!response.ok) throw new Error('HTTP '+response.status);
        url=URL.createObjectURL(await response.blob());
        const link=document.createElement('a');
        link.href=url;
        link.download=file.name;
        document.body.append(link);
        link.click();
        link.remove();
        // Allow the browser to consume the object URL before revoking it.
        const heldUrl=url;
        setTimeout(()=>URL.revokeObjectURL(heldUrl),30000);
        url=null;
      } catch(error) {
        if(url) URL.revokeObjectURL(url);
        failures.push(file.name+': '+error.message);
      }
    }
    if(failures.length) window.alert('部分 CSV 下载失败：'+failures.join('\n'));
  } finally {
    entry.downloading=false;
  }
}

function showLegendMenu(key,x,y) {
  if(!overlaySelections.has(key)) return;
  const pane=document.getElementById('reference-pane');
  const bounds=pane.getBoundingClientRect();
  legendMenu.replaceChildren();
  const primary=document.createElement('div');
  primary.className='legend-menu-primary';
  const secondary=document.createElement('div');
  secondary.className='legend-menu-secondary';
  secondary.hidden=true;
  legendMenu.append(primary,secondary);
  legendMenu.title='';
  const entry=overlaySelections.get(key);
  function submenu(label,property,choices) {
    const button=document.createElement('button');
    button.type='button';
    button.setAttribute('role','menuitem');
    button.textContent=label+' ›';
    button.addEventListener('click',()=>{
      secondary.replaceChildren();
      for(const choice of choices) {
        const item=document.createElement('button');
        item.type='button';
        item.setAttribute('role','menuitemradio');
        item.setAttribute('aria-checked',String(entry.style[property]===choice.value));
        item.textContent=choice.label;
        if(property==='color' && choice.value!==null) item.style.color=choice.value;
        item.addEventListener('click',()=>{void changeLegendStyle(key,{[property]:choice.value});});
        secondary.append(item);
      }
      secondary.hidden=false;
      secondary.style.maxWidth=pane.clientWidth+'px';
      secondary.style.maxHeight=pane.clientHeight+'px';
      secondary.style.minWidth=Math.min(118,pane.clientWidth)+'px';
      const menuRect=legendMenu.getBoundingClientRect();
      const buttonRect=button.getBoundingClientRect();
      const paneRect=pane.getBoundingClientRect();
      const pos=fitLegendSubmenu(pane.clientWidth,pane.clientHeight,
        {x:menuRect.left-paneRect.left,y:menuRect.top-paneRect.top,width:menuRect.width},
        {y:buttonRect.top-paneRect.top},
        {width:secondary.offsetWidth,height:secondary.offsetHeight});
      // Absolute child coordinates are relative to the parent's padding box.
      secondary.style.left=(pos.x-(menuRect.left-paneRect.left)-legendMenu.clientLeft)+'px';
      secondary.style.top=(pos.y-(menuRect.top-paneRect.top)-legendMenu.clientTop)+'px';
    });
    primary.append(button);
  }
  submenu('颜色','color',[...SVG_COLOR_CHOICES,{label:'初始颜色',value:null}]);
  submenu('线型','lineStyle',[...SVG_LINE_TYPES,{label:'初始线型',value:null}]);
  submenu('线宽','lineWidth',[...SVG_LINE_WIDTHS.map(value=>({label:String(value),value})),{label:'初始线宽',value:null}]);
  const download=document.createElement('button');
  download.type='button';
  download.setAttribute('role','menuitem');
  download.textContent='下载';
  download.addEventListener('click',()=>{
    legendMenu.hidden=true;
    void downloadLegendCsv(entry);
  });
  primary.append(download);
  const close=document.createElement('button');
  close.type='button';
  close.setAttribute('role','menuitem');
  close.textContent='关闭';
  close.addEventListener('click',()=>removeReferenceOverlay(key));
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
    document.title=workbookName.replace(/\.xlsx$/i,'') || 'Fab / Subfab CAD';

    // XLSX image anchors supply the origin, size and displayed aspect.
    // Decoded pixels are texture data only; never use them to rescale geometry.
    const layerImages=data.layers.map(src=>
      src?.objects?.find(item=>item.type==='image') || null);
    const textures=await Promise.all(layerImages.map(item=>
      loadCadTexture(item?.image_url)));
    const bounds=layerImages.map(item=>({
      width:(item?.bounds_emu?.width||9525)*EMU_TO_PX,
      height:(item?.bounds_emu?.height||9525)*EMU_TO_PX,
    }));
    // Keep shared world-space image width, but apply one uniform scale
    // per sheet to the picture, shapes, and all XY offsets.
    const transforms=pictureLayerScales(bounds);

    const targets=[fab,subfab];
    for(let i=0;i<targets.length;i++) {
      const layerData=data.layers[i],layer=targets[i];
      if(!layerData?.available) continue;
      layer.objects=layerData.objects;
      layer.sheetName=layerData.sheet || '';
      layer.scaleX=transforms[i].x;
      layer.scaleY=layer.scaleX;
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
  for(const layer of layers) {
    updateLayerOutlines(layer);
    layer.renderer.render(layer.scene,layer.camera);
  }
}
animate();
