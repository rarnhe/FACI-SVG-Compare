/** Pure Excel-CAD geometry helpers. Pixel coordinates, Z=0 at picture plane. */

const HEIGHT_SUFFIX = /^([xy])(\d+(?:\.\d+)?|\.\d+)$/;

export function rectangleHeight(text, width, height) {
  // Only the substring after the FINAL underscore is a height directive.
  const value = String(text ?? '').trim();
  const underscore = value.lastIndexOf('_');
  if (underscore < 0) return 0;
  const suffix = value.slice(underscore + 1);
  const match = HEIGHT_SUFFIX.exec(suffix);
  if (!match) return 0;
  const ratio = Number(match[2]);
  if (!Number.isFinite(ratio) || ratio < 0) return 0;
  const reference = match[1] === 'x' ? width : height;
  const depth = reference * ratio;
  return Number.isFinite(depth) ? depth : 0;
}

export function rectangleSpecs(items, toRect) {
  return items.filter(item => item.type === 'shape' && item.shape_kind === 'rectangle')
    .map(item => {
      const rect = toRect(item);
      return {
        rect,
        depth: rectangleHeight(item.text, rect.width, rect.height),
        centerX: rect.x + rect.width / 2,
        centerY: rect.y - rect.height / 2,
      };
    });
}

export function pointInsideRotatedRectangle(x, y, spec) {
  const dx = x - spec.centerX, dy = y - spec.centerY;
  const theta = spec.rect.rotation;
  const localX = dx * Math.cos(theta) + dy * Math.sin(theta);
  const localY = -dx * Math.sin(theta) + dy * Math.cos(theta);
  const tolerance = 1e-7;
  return Math.abs(localX) <= spec.rect.width / 2 + tolerance &&
    Math.abs(localY) <= spec.rect.height / 2 + tolerance;
}

export function ellipseElevation(ellipse, toRect, rectangles) {
  const rect = toRect(ellipse);
  const centerX = rect.x + rect.width / 2;
  const centerY = rect.y - rect.height / 2;
  // Check ellipse center against each rotated rectangular footprint.
  // When multiple rectangles overlap, attach to the highest top surface.
  const containing = rectangles.filter(spec =>
    pointInsideRotatedRectangle(centerX, centerY, spec));
  return containing.length ? Math.max(...containing.map(spec => spec.depth)) : 0;
}
