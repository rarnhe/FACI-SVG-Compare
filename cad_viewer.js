// Two independent WebGL canvases sharing ONE CAD camera pose and target.
// Excel A1 is the common origin for both sheets: x to the right, y down.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const PIXEL_PER_EMU = 1 / 9525;
const layers = [];
const pointerStates = new WeakMap();
const selectedInfo = document.getElementById('selected-info');
let synchronizing = false;
let fittedBounds = {minX:0, maxX:500, minY:0, maxY:400};
let chosenShape = null;

function makeLayer(stageId, statusId) {
  const stage = document.getElementById(stageId);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0e2231);
  const renderer = new THREE.WebGLRenderer({antialias:true, alpha:false});
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1,2));
  const camera = new THREE.OrthographicCamera(-200,200,150,-150,0.1,200000);
  camera.position.set(0,0,3000);
  camera.up.set(0,1,0);
  const controls = new OrbitControls(camera,renderer.domElement);
  controls.enableDamping = false;
  controls.screenSpacePanning = true;
  controls.enableRotate = true;
  controls.mouseButtons = {
    LEFT: THREE.MOUSE.ROTATE,
    MIDDLE: THREE.MOUSE.DOLLY,
    RIGHT: THREE.MOUSE.PAN,
  };
  controls.minZoom = 0.02;
  controls.maxZoom = 24;
  controls.target.set(0,0,0);
  controls.update();
  stage.insertBefore(renderer.domElement,stage.firstChild);
  const layer = {stage, scene, renderer, camera, controls,
                 status:document.getElementById(statusId), clickable:[]};
  controls.addEventListener('change',() => synchronizeFrom(layer));
  renderer.domElement.addEventListener('contextmenu', event => event.preventDefault());
  installPicking(layer);
  layers.push(layer);
  return layer;
}

function synchronizeFrom(source) {
  if (synchronizing) return;
  synchronizing = true;
  try {
    for (const other of layers) {
      if (source === other) continue;
      other.camera.position.copy(source.camera.position);
      other.camera.quaternion.copy(source.camera.quaternion);
      other.camera.zoom = source.camera.zoom;
      other.camera.updateProjectionMatrix();
      other.controls.target.copy(source.controls.target);
      other.controls.update();
    }
  } finally {
    synchronizing = false;
  }
}

function toWorldRect(item) {
  const b = item.bounds_emu;
  return {
    x: b.x * PIXEL_PER_EMU,
    y: -b.y * PIXEL_PER_EMU,
    width: Math.max(0.2, b.width * PIXEL_PER_EMU),
    height: Math.max(0.2, b.height * PIXEL_PER_EMU),
    rotation: -(item.rotation_degrees || 0) * Math.PI / 180,
  };
}

function fillColor(color, fallback) {
  if (typeof color === 'string' && /^#[0-9a-f]{6}$/i.test(color))
    return Number.parseInt(color.slice(1),16);
  return fallback;
}

function drawLabel(group, label, width, height, foreground) {
  if (!label) return;
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 256;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0,0,1024,256);
  const lines = label.split(/\n/).slice(0,3);
  const available = Math.max(...lines.map(line => line.length),1);
  const fontSize = Math.max(22,Math.min(94,Math.floor(1460/available)));
  ctx.font = '600 '+fontSize+'px "Microsoft YaHei", sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = foreground;
  lines.forEach((line,i) => ctx.fillText(line,512,128+(i-(lines.length-1)/2)*fontSize*1.1,985));
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const text = new THREE.Mesh(
    new THREE.PlaneGeometry(width,height),
    new THREE.MeshBasicMaterial({map:texture,transparent:true,depthWrite:false,side:THREE.DoubleSide})
  );
  text.position.z = 1.5;
  group.add(text);
}

function drawShape(layer, item, sheetTitle) {
  const rect = toWorldRect(item);
  const group = new THREE.Group();
  group.position.set(rect.x + rect.width/2,rect.y - rect.height/2,2);
  group.rotation.z = rect.rotation;

  const colors = item.colors || {};
  const color = fillColor(colors.fill,0x289dcb);
  const mat = new THREE.MeshBasicMaterial({
    color,transparent:true,
    opacity:colors.fill === '无/透明' ? 0.06 : 0.55,
    side:THREE.DoubleSide,depthWrite:false,
  });
  const fill = new THREE.Mesh(new THREE.PlaneGeometry(rect.width,rect.height),mat);
  fill.userData = {cadObject:item, sheetTitle};
  group.add(fill);
  layer.clickable.push(fill);

  const outlineColor = fillColor(colors.outline,0x6ce4ff);
  const w=rect.width/2, h=rect.height/2;
  const points=[new THREE.Vector3(-w,-h,0.5),new THREE.Vector3(w,-h,0.5),
                new THREE.Vector3(w,h,0.5),new THREE.Vector3(-w,h,0.5)];
  const outline = new THREE.LineLoop(
    new THREE.BufferGeometry().setFromPoints(points),
    new THREE.LineBasicMaterial({color:outlineColor,transparent:true,opacity:0.95}),
  );
  group.add(outline);
  drawLabel(group,item.text || item.name,rect.width,rect.height,colors.text || '#e9fbff');
  layer.scene.add(group);
}

function drawImage(layer, item) {
  if (!item.image_url) return;
  const rect=toWorldRect(item);
  const group=new THREE.Group();
  group.position.set(rect.x+rect.width/2,rect.y-rect.height/2,0);
  group.rotation.z=rect.rotation;
  const textureLoader=new THREE.TextureLoader();
  textureLoader.load(item.image_url,texture=>{
    texture.colorSpace=THREE.SRGBColorSpace;
    texture.anisotropy=Math.min(8,layer.renderer.capabilities.getMaxAnisotropy());
    const mesh=new THREE.Mesh(
      new THREE.PlaneGeometry(rect.width,rect.height),
      new THREE.MeshBasicMaterial({map:texture,side:THREE.DoubleSide,transparent:true,depthWrite:false}),
    );
    group.add(mesh);
    layer.scene.add(group);
  },undefined,error=>{
    console.warn('Cannot display XLSX embedded image:',item.name,error);
    layer.status.textContent='一张 XLSX 图片无法解码，其他对象仍可查看';
  });
}

function installPicking(layer) {
  const dom=layer.renderer.domElement;
  const raycaster=new THREE.Raycaster();
  const normalized=new THREE.Vector2();
  dom.addEventListener('pointerdown',event=>{
    pointerStates.set(dom,{x:event.clientX,y:event.clientY,button:event.button});
  });
  dom.addEventListener('pointerup',event=>{
    const start=pointerStates.get(dom);
    pointerStates.delete(dom);
    if (!start || start.button!==0 || Math.hypot(event.clientX-start.x,event.clientY-start.y)>5) return;
    const rect=dom.getBoundingClientRect();
    normalized.set((event.clientX-rect.left)/rect.width*2-1,
                   -((event.clientY-rect.top)/rect.height*2-1));
    raycaster.setFromCamera(normalized,layer.camera);
    const hit=raycaster.intersectObjects(layer.clickable,false)[0];
    if (!hit) return;
    if (chosenShape) chosenShape.material.opacity=chosenShape.userData.baseOpacity;
    const mesh=hit.object;
    if (mesh.userData.baseOpacity===undefined) mesh.userData.baseOpacity=mesh.material.opacity;
    mesh.material.opacity=0.86;
    chosenShape=mesh;
    const item=mesh.userData.cadObject;
    selectedInfo.textContent = [mesh.userData.sheetTitle,item.name,item.text]
      .filter(Boolean).join(' · ');
    selectedInfo.title=selectedInfo.textContent;
  });
}

function resizeLayer(layer) {
  const width=Math.max(1,layer.stage.clientWidth),height=Math.max(1,layer.stage.clientHeight);
  layer.renderer.setSize(width,height,false);
  layer.camera.left=-width/2; layer.camera.right=width/2;
  layer.camera.top=height/2; layer.camera.bottom=-height/2;
  layer.camera.updateProjectionMatrix();
}
function fitView() {
  const width=Math.max(40,fittedBounds.maxX-fittedBounds.minX);
  const height=Math.max(40,fittedBounds.maxY-fittedBounds.minY);
  const centerX=(fittedBounds.minX+fittedBounds.maxX)/2;
  const centerY=-(fittedBounds.minY+fittedBounds.maxY)/2;
  const zoom=Math.max(0.02,Math.min(
    ...layers.map(layer=>Math.min(layer.stage.clientWidth/(width*1.12),
                                 layer.stage.clientHeight/(height*1.12))),
  ));
  const distance=Math.max(1000,Math.max(width,height)*4);
  synchronizing=true;
  try {
    for (const layer of layers) {
      layer.camera.position.set(centerX,centerY,distance);
      layer.camera.zoom=Math.min(24,zoom);
      layer.camera.updateProjectionMatrix();
      layer.controls.target.set(centerX,centerY,0);
      layer.controls.update();
    }
  } finally { synchronizing=false; }
}
function collectBounds(manifest) {
  const boxes=manifest.layers.flatMap(layer=>layer.objects.map(object=>object.bounds_emu));
  if (!boxes.length) return;
  fittedBounds={
    minX:Math.min(...boxes.map(b=>b.x))*PIXEL_PER_EMU,
    maxX:Math.max(...boxes.map(b=>b.x+b.width))*PIXEL_PER_EMU,
    minY:Math.min(...boxes.map(b=>b.y))*PIXEL_PER_EMU,
    maxY:Math.max(...boxes.map(b=>b.y+b.height))*PIXEL_PER_EMU,
  };
}

function referenceImage(key, item) {
  const img=document.getElementById(key+'-reference');
  const placeholder=document.getElementById(key+'-placeholder');
  if (!item?.available) return;
  img.onload=()=>{img.style.display='block';placeholder.hidden=true;};
  img.onerror=()=>{placeholder.textContent='SVG 加载失败：请检查资源文件';};
  img.src=item.url;
}

const fab=makeLayer('fab-stage','fab-status');
const subfab=makeLayer('subfab-stage','subfab-status');
document.getElementById('reset-view').addEventListener('click',fitView);
new ResizeObserver(()=>{
  for (const layer of layers) resizeLayer(layer);
}).observe(document.getElementById('cad-layers'));
for(const layer of layers) resizeLayer(layer);

async function initialize() {
  try {
    const response=await fetch('./cad-layout.json',{cache:'no-store'});
    if(!response.ok) throw new Error('CAD layout HTTP '+response.status);
    const manifest=await response.json();
    const targets=[fab,subfab];
    for(let i=0;i<targets.length;i++) {
      const layer=targets[i],source=manifest.layers[i];
      const label=source?.sheet || 'Sheet '+(i+1);
      if(!source?.available) {
        layer.status.textContent='缺少 '+label+'，请检查 assets/ 中的 XLSX';
        continue;
      }
      for(const item of source.objects) {
        if(item.type==='image') drawImage(layer,item);
        if(item.type==='shape') drawShape(layer,item,label);
      }
      const images=source.objects.filter(item=>item.type==='image' && item.image_url);
      layer.status.textContent=label+' · 图片 '+images.length+' · 形状 '
        +source.objects.filter(item=>item.type==='shape').length;
    }
    collectBounds(manifest);
    fitView();
    referenceImage('psd',manifest.reference_svgs?.psd);
    referenceImage('octave',manifest.reference_svgs?.octave);
  } catch(error) {
    console.error('Cannot load XLSX CAD layout:',error);
    for(const layer of layers) layer.status.textContent='CAD 数据载入失败，请查看终端或控制台';
  }
}
initialize();
function animate() {
  requestAnimationFrame(animate);
  for(const layer of layers) layer.renderer.render(layer.scene,layer.camera);
}
animate();
