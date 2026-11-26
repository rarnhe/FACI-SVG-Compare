/** Pure CAD spatial helpers, shared between Three.js and Node tests. */

const ALT_HEIGHT = /^z\s*=\s*(\d+(?:\.\d+)?|\.\d+)\s*([xy])$/i;
const EPS = 1e-9;

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
  const centerX = rect.x + rect.width / 2;
  const centerY = rect.y - rect.height / 2;
  const radius = Math.hypot(rect.width, rect.height) / 2;
  const local = localPoint(centerX, centerY, spec);
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
