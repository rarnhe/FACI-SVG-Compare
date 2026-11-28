/** Pure CAD spatial helpers, shared between Three.js and Node tests. */

const ALT_HEIGHT = /^z\s*=\s*(\d+(?:\.\d+)?|\.\d+)\s*([xy])$/i;
const EPS = 1e-9;

// All top-level objects, irrespective of shape kind, use the same exact
// image-relative EMU geometry. One scalar preserves every XY proportion.
export function worldRectFromEmu(item,scale=1) {
  const b=item.bounds_emu;
  if(!b || ![b.x,b.y,b.width,b.height,scale,item.rotation_degrees??0].every(Number.isFinite)
    || b.width<=0 || b.height<=0 || scale<=0)
    throw new Error('Invalid saved XLSX geometry: '+(item.name||item.shape_kind||item.type));
  const unit=scale/9525;
  return {x:b.x*unit,y:-b.y*unit,width:b.width*unit,height:b.height*unit,
    rotation:-(item.rotation_degrees??0)*Math.PI/180};
}

// Preserve the diagonal diameter; the reconstructed circle's bounding
// square starts at the same upper-left anchor as every other shape.
export function reconstructedCircleRadius(width,height) {
  return Math.hypot(width,height)/2;
}

// Geometry offset from the sole upper-left anchor, not a second XLSX
// positioning source. A circle uses its own bounding square.
export function reconstructedCirclePlacement(rect) {
  const radius=reconstructedCircleRadius(rect.width,rect.height);
  return {radius,x:rect.x+radius,y:rect.y-radius};
}


/**
 * Rectangle's alternative text (DrawingML cNvPr@descr/title) defines height.
 * z=0.5x means half the x/width, z=0.2y means 0.2 * height.
 * The visible shape label is never parsed as a height directive.
 */
export function rectangleHeight(altText, width, height) {
  const description=typeof altText==='string'
    ? altText : (altText?.description || altText?.title || '');
  const clean=String(description).replaceAll('_x000D_','').trim();
  const match=ALT_HEIGHT.exec(clean);
  if(!match) return 0;
  const fraction=Number(match[1]);
  if(!Number.isFinite(fraction)||fraction<0) return 0;
  const length=match[2].toLowerCase()==='x' ? width : height;
  const depth=fraction*length;
  return Number.isFinite(depth) ? depth : 0;
}

export function rectangleSpecs(items, toRect) {
  return items.filter(item => item.type === 'shape' && item.shape_kind === 'rectangle')
    .map(item => {
      const rect = toRect(item);
      return {
        rect,
        depth: rectangleHeight(item.alt_text, rect.width, rect.height),
        centerX: rect.x + rect.width / 2,
        centerY: rect.y - rect.height / 2,
        label: item.text || item.name || 'rectangle',
      };
    });
}

export function localPoint(x, y, spec) {
  const dx = x - spec.centerX, dy = y - spec.centerY;
  const angle = spec.rect.rotation;
  return {
    x: dx * Math.cos(angle) + dy * Math.sin(angle),
    y: -dx * Math.sin(angle) + dy * Math.cos(angle),
  };
}

export function pointInsideRotatedRectangle(x, y, spec) {
  const local = localPoint(x, y, spec);
  return Math.abs(local.x) <= spec.rect.width / 2 + EPS &&
    Math.abs(local.y) <= spec.rect.height / 2 + EPS;
}

export function circleRectangleRelation(ellipse, toRect, spec) {
  const rect = toRect(ellipse);
  const {x,y,radius}=reconstructedCirclePlacement(rect);
  const local = localPoint(x,y,spec);
  const dx = Math.abs(local.x), dy = Math.abs(local.y);
  const halfW = spec.rect.width / 2, halfH = spec.rect.height / 2;
  if (dx + radius <= halfW + EPS && dy + radius <= halfH + EPS) {
    return 'inside';
  }
  const distX = Math.max(dx - halfW, 0), distY = Math.max(dy - halfH, 0);
  return Math.hypot(distX, distY) > radius + EPS ? 'outside' : 'partial';
}

export function rectangleOverlap(a, b) {
  // SAT for rotated rectangles. Shared edges are not positive-area overlaps.
  const axes = [a, b].flatMap(spec => {
    const c = Math.cos(spec.rect.rotation), s = Math.sin(spec.rect.rotation);
    return [[c, s], [-s, c]];
  });
  const extent = (spec, ax, ay) => {
    const c = Math.cos(spec.rect.rotation), s = Math.sin(spec.rect.rotation);
    return spec.rect.width / 2 * Math.abs(c * ax + s * ay) +
      spec.rect.height / 2 * Math.abs(-s * ax + c * ay);
  };
  for (const [ax, ay] of axes) {
    const gap = Math.abs((a.centerX - b.centerX) * ax + (a.centerY - b.centerY) * ay);
    if (gap >= extent(a,ax,ay) + extent(b,ax,ay) - EPS) return false;
  }
  return true;
}

export function ellipseElevation(ellipse, toRect, rectangles) {
  const intersecting = rectangles.filter(spec =>
    circleRectangleRelation(ellipse, toRect, spec) !== 'outside');
  if (intersecting.length > 1) {
    throw new Error('Reconstructed circle intersects multiple rectangles');
  }
  if (intersecting.length === 0) return 0;
  return intersecting[0].depth *
    (circleRectangleRelation(ellipse, toRect, intersecting[0]) === 'inside' ? 1 : 0.5);
}
