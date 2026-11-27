/** Pure CAD UI geometry and responsive layout helpers (no DOM dependencies). */
const EPS = 1e-7;

export const INITIAL_REFERENCE_SPLIT = 0.5;

// CAD cuboids retain a solid, translucent roof when selected.
export const CUBOID_FACE_OPACITY = 0.43;
export const CUBOID_SELECTED_OPACITY = 0.50;

// Translucent cuboid faces reveal elevated ellipse measurement points.


/**
 * Stable visual stacking order, independent of XLSX object enumeration or
 * the observer's camera angle. The workbook background renders first,
 * textboxes next, rectangles above, and ellipses last.
 */
export const CAD_DRAW_ORDER = Object.freeze({
  image: 0,
  textbox: 10,
  other: 15,
  rectangle: 20,
  ellipse: 30,
});

export function cadShapeRenderOrder(kind) {
  return CAD_DRAW_ORDER[kind] ?? CAD_DRAW_ORDER.other;
}

/** Keep textbox geometry physically below the XY rectangle roof and sensors. */
export function cadShapeZOffset(kind) {
  return kind === 'textbox' ? -1 : kind === 'ellipse' ? 1 : 0;
}


export function shapeLabel(shape) {
  return String(shape?.text || shape?.name || '').trim().replace(/\s*\n\s*/g, ' ');
}

export function selectOnButton(shape, button) {
  if (!shape || shape.type !== 'shape' || shape.shape_kind === 'textbox') return false;
  return shape.shape_kind === 'ellipse' ? button === 2 : button === 0;
}

function center(rect) {
  return {x: rect.x + rect.width / 2, y: rect.y - rect.height / 2};
}

function rectangleCorners(rect) {
  const c = center(rect), w = rect.width / 2, h = rect.height / 2;
  const cos = Math.cos(rect.rotation || 0), sin = Math.sin(rect.rotation || 0);
  return [[-w, -h], [w, -h], [w, h], [-w, h]].map(([x,y]) => ({
    x:c.x + x*cos - y*sin, y:c.y + x*sin + y*cos,
  }));
}

function pointInsideRect(point, rect) {
  const c=center(rect), x=point.x-c.x, y=point.y-c.y;
  const co=Math.cos(rect.rotation || 0), si=Math.sin(rect.rotation || 0);
  const lx=x*co+y*si, ly=-x*si+y*co;
  return Math.abs(lx) <= rect.width/2+EPS && Math.abs(ly) <= rect.height/2+EPS;
}

function circleInsideRect(circle, rect) {
  const c=center(circle), p=center(rect), x=c.x-p.x, y=c.y-p.y;
  const co=Math.cos(rect.rotation || 0), si=Math.sin(rect.rotation || 0);
  const lx=x*co+y*si, ly=-x*si+y*co;
  const radius=Math.hypot(circle.width,circle.height)/2;
  return Math.abs(lx)+radius <= rect.width/2+EPS &&
         Math.abs(ly)+radius <= rect.height/2+EPS;
}

export function containsShape(outer, inner, toRect) {
  if (outer === inner || outer?.type !== 'shape' || inner?.type !== 'shape' ||
      outer.shape_kind === 'ellipse') return false;
  const a=toRect(outer), b=toRect(inner);
  if (!(a.width>0 && a.height>0 && b.width>0 && b.height>0)) return false;
  // Avoid self/duplicate boxes becoming parents or creating containment cycles.
  if (a.width*a.height <= b.width*b.height+EPS) return false;
  return inner.shape_kind === 'ellipse'
    ? circleInsideRect(b,a)
    : rectangleCorners(b).every(point => pointInsideRect(point,a));
}

/** Immediate parent first in search; return ancestors ordered outermost -> innermost. */
export function shapeAncestors(items, selected, toRect) {
  const shapes=items.filter(x=>x.type==='shape' && x!==selected);
  const ancestors=[], visited=new Set();
  let child=selected;
  while (true) {
    const parents=shapes.filter(item=>!visited.has(item) && containsShape(item,child,toRect));
    if(!parents.length) break;
    parents.sort((a,b)=>{
      const ar=toRect(a), br=toRect(b);
      return ar.width*ar.height-br.width*br.height;
    });
    const parent=parents[0];
    ancestors.push(parent);
    visited.add(parent);
    child=parent;
  }
  return ancestors.reverse();
}

/** Hover breadcrumb: textbox (bold in DOM) · rectangle · sensor ellipse. */
export function selectionParts(items,selected,toRect) {
  if(!selected || selected.type!=='shape') return [];
  const ancestors=shapeAncestors(items,selected,toRect);
  const parentTextboxes=ancestors.filter(x=>x.shape_kind==='textbox');
  const parentRectangles=ancestors.filter(x=>x.shape_kind==='rectangle');
  const parts=[];
  if(parentTextboxes.length) parts.push({
    kind:'textbox',text:shapeLabel(parentTextboxes[parentTextboxes.length-1]),
  });
  if(parentRectangles.length) parts.push({
    kind:'rectangle',text:shapeLabel(parentRectangles[parentRectangles.length-1]),
  });
  if(selected.shape_kind==='textbox') {
    parts.push({kind:'textbox',text:shapeLabel(selected)});
  } else if(selected.shape_kind==='rectangle') {
    parts.push({kind:'rectangle',text:shapeLabel(selected)});
  } else {
    parts.push({kind:selected.shape_kind,text:shapeLabel(selected)});
  }
  return parts.filter(part=>part.text);
}

/** Viewer legend: folder_sheet_rectangle-or-ellipse_+direction (no date). */
export function svgLegendName(catalog,axis) {
  return [
    String(catalog.folder||'').trim(),
    String(catalog.sheet||'').trim(),
    String(catalog.identifier||'').trim(),
    '+'+String(axis||'').toUpperCase(),
  ].join('_');
}

/** Keep distinct timepoints independent even when their legend text matches. */
export function svgSelectionKey(catalog,date,axis) {
  return JSON.stringify([
    catalog.folder,catalog.sheet,catalog.target_kind,catalog.identifier,
    date,String(axis||'').toUpperCase(),
  ]);
}

/** Fit both complete SVG images at a common pixel width; never overflow. */
export function fitSvgPair(frameA, frameB, aspectA, aspectB) {
  const ratioA=Number.isFinite(aspectA)&&aspectA>0?aspectA:1;
  const ratioB=Number.isFinite(aspectB)&&aspectB>0?aspectB:1;
  const width=Math.max(0,Math.min(
    frameA.width,frameB.width,
    frameA.height/ratioA,frameB.height/ratioB,
  ));
  return {width,heightA:width*ratioA,heightB:width*ratioB};
}

/**
 * Use the embedded picture's actual pixel aspect while both CAD sheets share
 * one world-space image width (same units/pixel across both cameras).
 * Shape offsets follow the image axes so overlays never drift from their image.
 */
export function pictureLayerScales(imageBounds, naturalAspectRatios) {
  const commonWidth=Math.max(1,...imageBounds.map(box=>box.width));
  return imageBounds.map((box,i)=>{
    const ratio=naturalAspectRatios[i] > 0 ? naturalAspectRatios[i] : box.height/box.width;
    const height=commonWidth*ratio;
    return {
      x:commonWidth/Math.max(1,box.width),
      y:height/Math.max(1,box.height),
      width:commonWidth,height,
    };
  });
}

/** Responsive divider bounds: keep left controls and the current SVG width visible. */
export function clampMainDivider(position,totalWidth,dividerWidth=8,minimumRight=0) {
  const usable=Math.max(0,totalWidth-dividerWidth);
  const minLeft=Math.min(220,usable*0.35);
  const minRight=Math.min(Math.max(220,minimumRight),usable-minLeft);
  return Math.max(minLeft,Math.min(usable-minRight,position));
}

/** Clamp at the current picture dimensions before a height split could crop it. */
export function clampReferenceSplit(position,totalHeight,dividerHeight=8,minTop=0,minBottom=0) {
  const usable=Math.max(1,totalHeight-dividerHeight);
  const defaultMin=Math.min(100,usable*0.12);
  let top=Math.max(defaultMin,minTop),bottom=Math.max(defaultMin,minBottom);
  if (top+bottom>usable) {
    const scale=usable/(top+bottom);
    top*=scale;bottom*=scale;
  }
  return Math.max(top/usable,Math.min(1-bottom/usable,position/usable));
}



/** Base and active SVGs share a coordinate plane but may have different viewBox ratios. */
export function requiredSvgRatio(baseRatio, entries) {
  const candidates=[baseRatio,...entries].filter(value=>Number.isFinite(value)&&value>0);
  return candidates.length ? Math.max(...candidates) : 1;
}

/** Duplicate guard for both completed and concurrent menu selections. */
export function canAddOverlay(active,loading,label) {
  return Boolean(label) && !active.has(label) && !loading.has(label);
}


/** Fit one SVG pane independently: its own width and height always constrain it. */
export function fitSvgPane(width,height,maxHeightOverWidth) {
  const ratio=Number.isFinite(maxHeightOverWidth)&&maxHeightOverWidth>0
    ? maxHeightOverWidth : 1;
  const fittedWidth=Math.max(0,Math.min(width,height/ratio));
  return {width:fittedWidth,height:fittedWidth*ratio};
}

export const SVG_COLORS=Object.freeze([
  '#4F99CF','#E41A1C','#4DAF4A','#FF7F00','#2C3E50','#333333',
  '#3C5488','#E64B35','#00A087','#3A3935','#1F77B4',
  '#FF7F0E','#2CA02C','#9A8B7A','#7E8B96','#A6998A','#D1C7BD',
]);
export function nextLegendColor(index) {
  return SVG_COLORS[Math.abs(Math.trunc(index))%SVG_COLORS.length];
}


/**
 * Browser-only, in-memory SVG recoloring. Never alter unpainted geometry,
 * transparent fills, paint servers (url(...)), or SVG attributes other
 * than already-explicit stroke/fill paint values. Keep styles and defs.
 */
export function recolorablePaint(value) {
  const paint=String(value??'').trim();
  return Boolean(paint) &&
    !/^(none|transparent|inherit|initial|unset)$/i.test(paint) &&
    !/^url\(/i.test(paint);
}

export function recolorCssDeclarations(css,color) {
  if(!SVG_COLORS.includes(color)) throw new RangeError('Unsupported SVG color');
  return String(css).replace(/(^|[;{\s])(\b(?:fill|stroke))\s*:\s*([^;{}]+)/gim,
    (whole,prefix,property,paint)=>
      prefix+property+':'+(recolorablePaint(paint) ? color : paint));
}

export function recolorSvgMarkup(source,color) {
  if(!SVG_COLORS.includes(color)) throw new RangeError('Unsupported SVG color');
  const documentXml=new DOMParser().parseFromString(source,'image/svg+xml');
  if(documentXml.getElementsByTagName('parsererror').length ||
     documentXml.documentElement?.localName!=='svg') {
    throw new Error('Cannot parse original SVG source');
  }
  // CSS selectors sometimes define plot colors rather than attributes.
  for(const sheet of documentXml.getElementsByTagName('style')) {
    sheet.textContent=recolorCssDeclarations(sheet.textContent||'',color);
  }
  for(const node of documentXml.getElementsByTagName('*')) {
    // Preserve SVG's background, masks, gradients and definitions.
    if(['style','defs','metadata','title','desc','mask','clippath','filter',
        'lineargradient','radialgradient','stop'].includes(node.localName?.toLowerCase()))
      continue;
    for(const attr of ['fill','stroke']) {
      if(node.hasAttribute(attr) && recolorablePaint(node.getAttribute(attr)))
        node.setAttribute(attr,color);
    }
    if(node.hasAttribute('style'))
      node.setAttribute('style',recolorCssDeclarations(node.getAttribute('style'),color));
  }
  return new XMLSerializer().serializeToString(documentXml);
}
