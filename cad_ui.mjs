/** Pure CAD UI geometry and responsive layout helpers (no DOM dependencies). */
const EPS = 1e-7;

export const INITIAL_REFERENCE_SPLIT = 5.8 / (5.8 + 18.1);

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

export function selectionPath(workbookName,sheetName,items,selected,toRect) {
  const book=String(workbookName||'').replace(/\.xlsx$/i,'');
  const components=[book,String(sheetName||'')];
  components.push(...shapeAncestors(items,selected,toRect).map(shapeLabel));
  components.push(shapeLabel(selected));
  return components.filter(Boolean).join('·');
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

