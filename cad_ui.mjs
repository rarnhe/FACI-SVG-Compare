/** Pure CAD UI geometry and responsive layout helpers (no DOM dependencies). */
const EPS = 1e-7;

export const INITIAL_REFERENCE_SPLIT = 0.5;

// CAD cuboids retain a solid, translucent roof when selected.
export const CUBOID_FACE_OPACITY = 0.93;
export const CUBOID_SELECTED_OPACITY = 1.00;

// Rectangle edges are outlined separately for rotation visibility.


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

/** Resolve the font stack for a DrawingML text run. */
export function textboxFont(run) {
  const points=Number(run?.font_size_pt);
  const size=Math.max(1,Math.min(500,
    Number.isFinite(points) && points>0 ? points : 11));
  const px=+(size*96/72).toFixed(3);
  const family=String(run?.font_family||'Calibri').replace(/["\\\r\n]/g,'').trim();
  const east=String(run?.east_asian_font||'Microsoft YaHei')
    .replace(/["\\\r\n]/g,'').trim();
  return (run?.italic?'italic ':'')+(run?.bold?'bold ':'')+
    px+'px "'+(family||'Calibri')+'", "'+(east||'Microsoft YaHei')+'", sans-serif';
}

/** Calculate DrawingML run positions in the original XLSX picture coordinates.
    A measure(text,run) callback returns reference-pixel glyph widths.
    Text and its picture then receive the same transform in Three.js. */
export function layoutTextboxText(layout,width,height,measure) {
  const w=Math.max(1,Number(width)||1),h=Math.max(1,Number(height)||1);
  const margins=layout?.insets_px||{};
  const clamp=(value,max)=>Math.max(0,Math.min(max,Number(value)||0));
  const left=clamp(margins.left,w),right=clamp(margins.right,w);
  const top=clamp(margins.top,h),bottom=clamp(margins.bottom,h);
  const usable=Math.max(1,w-left-right);
  const paragraphs=layout?.paragraphs||[];
  const lines=[];
  let glyphs=0;
  for(const paragraph of paragraphs.slice(0,500)) {
    const align=['left','center','right'].includes(paragraph?.align)
      ? paragraph.align : 'left';
    let line={parts:[],width:0,height:0,align};
    const flush=()=>{
      lines.push({...line,height:Math.max(line.height,14)});
      line={parts:[],width:0,height:0,align};
    };
    for(const run of (paragraph?.runs||[]).slice(0,512)){
      const text=String(run?.text||'');
      const size=Number(run?.font_size_pt);
      const lineHeight=Math.max(14,Math.min(500,
        (Number.isFinite(size)&&size>0?size:11)*96/72*1.25));
      for(const char of text) {
        if(++glyphs>20000) break;
        if(char==='\n') {flush();continue;}
        const widthPx=Number(measure(char,run));
        const advance=Number.isFinite(widthPx)?Math.max(0,widthPx):0;
        if(line.width+advance>usable && line.parts.length) flush();
        const last=line.parts[line.parts.length-1];
        if(last?.run===run) {
          last.text+=char;
          last.width+=advance;
        } else line.parts.push({text:char,run,width:advance});
        line.width+=advance;
        line.height=Math.max(line.height,lineHeight);
      }
      if(glyphs>20000) break;
    }
    flush();
    if(glyphs>20000) break;
  }
  const totalHeight=lines.reduce((sum,line)=>sum+line.height,0);
  const usableHeight=Math.max(0,h-top-bottom);
  const anchor=layout?.anchor;
  let y=top+(anchor==='middle'?Math.max(0,(usableHeight-totalHeight)/2)
    :anchor==='bottom'?Math.max(0,usableHeight-totalHeight):0);
  const commands=[];
  for(const line of lines){
    let x=left+(line.align==='center'?Math.max(0,(usable-line.width)/2)
      :line.align==='right'?Math.max(0,usable-line.width):0);
    for(const part of line.parts){
      commands.push({text:part.text,x,y,run:part.run});
      x+=part.width;
    }
    y+=line.height;
  }
  return commands;
}

/** Prefer the actual decoded XLSX picture dimensions, not the cell anchor ratio. */
export function imageAspectRatio(image, anchor) {
  const width=Number(image?.naturalWidth || image?.width);
  const height=Number(image?.naturalHeight || image?.height);
  if(Number.isFinite(width) && width>0 && Number.isFinite(height) && height>0)
    return height/width;
  const fallbackWidth=Number(anchor?.width),fallbackHeight=Number(anchor?.height);
  return Number.isFinite(fallbackWidth) && fallbackWidth>0 &&
         Number.isFinite(fallbackHeight) && fallbackHeight>0
    ? fallbackHeight/fallbackWidth : 1;
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

export const SVG_COLOR_CHOICES=Object.freeze([
  {label:'红色',value:'#E41A1C'},
  {label:'橙色',value:'#FF7F00'},
  {label:'黄色',value:'#D6A800'},
  {label:'绿色',value:'#4DAF4A'},
  {label:'蓝色',value:'#4F99CF'},
  {label:'紫色',value:'#984EA3'},
  {label:'灰色',value:'#7E8B96'},
].map(Object.freeze));
export const SVG_COLORS=Object.freeze(SVG_COLOR_CHOICES.map(choice=>choice.value));
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


// Legend styles are independent; null restores the original width/dash pattern.
export const SVG_LINE_WIDTHS=Object.freeze([2,2.5,3,3.5,4]);
export const SVG_LINE_TYPES=Object.freeze([
  {label:'实线',value:'none'},
  {label:'虚线',value:'8 5'},
  {label:'点划线',value:'10 4 1 4'},
  {label:'双点划线',value:'10 4 1 4 1 4'},
].map(Object.freeze));

export function mergeSvgStyle(previous,patch={}) {
  const style={color:previous.color,lineWidth:previous.lineWidth??null,
    lineStyle:previous.lineStyle??null,...patch};
  if(!SVG_COLORS.includes(style.color) ||
    (style.lineWidth!==null && !SVG_LINE_WIDTHS.includes(style.lineWidth)) ||
    (style.lineStyle!==null && !SVG_LINE_TYPES.some(type=>type.value===style.lineStyle)))
    throw new RangeError('Unsupported SVG style');
  return {color:style.color,lineWidth:style.lineWidth,lineStyle:style.lineStyle};
}

const PROTECTED_SVG=/^(?:defs|mask|clippath|filter|marker|pattern|symbol|lineargradient|radialgradient|metadata|title|desc|text|tspan)$/i;
const AUXILIARY_SVG=/(?:^|[\s_.-])(?:axes?|axis|grid(?:lines?)?|[xy]?ticks?|spines?|legend|labels?|background|frame|border|patch|matplotlib\.axis)(?=$|[\s_.-]|\d)/i;
const CURVE_SVG=/(?:^|[\s_.-])(?:curve|series|trace|spectrum|psd|octave|data-series|line2d)(?=$|[\s_.-]|\d)/i;
function svgLineRole(node) {
  let marked=false;
  for(let current=node;current;current=current.parentElement) {
    if(PROTECTED_SVG.test(current.localName||'')) return 'protected';
    const name=[current.getAttribute('id'),current.getAttribute('class')].join(' ');
    // Matplotlib axes_1 is a container for the plot, not the axis itself.
    if(AUXILIARY_SVG.test(name.replace(/\baxes_\d+\b/g,''))) return 'protected';
    if(current.hasAttribute('data-series') || current.hasAttribute('data-curve') ||
       CURVE_SVG.test(name)) marked=true;
  }
  return marked?'marked':'fallback';
}

// Resolve common SVG presentation attributes, CSS selectors and inherited
// stroke without inserting potentially active SVG markup into the live page.
function paintDeclaration(css,property='stroke') {
  const pattern=new RegExp('(?:^|;)\\s*'+property+'\\s*:\\s*([^;]+?)(?:\\s*!important)?\\s*(?=;|$)','gi');
  const values=[...String(css??'').matchAll(pattern)];
  if(!values.length) return null;
  const important=values.filter(v=>/!important\s*$/i.test(v[0]));
  const last=(important.length?important:values).at(-1);
  return {value:last[1].trim(),important:/!important\s*$/i.test(last[0])};
}
function paintRules(xml,property='stroke') {
  const result=[];
  for(const sheet of xml.getElementsByTagName('style')) {
    const css=String(sheet.textContent||'').replace(/\/\*[\s\S]*?\*\//g,'');
    for(const match of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      const decl=paintDeclaration(match[2],property);
      if(!decl || match[1].trim().startsWith('@')) continue;
      for(const raw of match[1].split(',')) {
        const selector=raw.trim();
        if(!selector) continue;
        // Common class/id/tag selectors, ordered by specificity then source.
        const rank=(selector.match(/#[\w-]+/g)||[]).length*10000+
          (selector.match(/\.[\w-]+|\[[^\]]+\]|:[\w-]+/g)||[]).length*100+
          (selector.match(/(?:^|[\s>+~])[\w-]+/g)||[]).length;
        result.push({selector,rank,...decl});
      }
    }
  }
  return result;
}
function resolvedPaint(node,rules,property='stroke') {
  for(let current=node;current;current=current.parentElement) {
    let winner=current.hasAttribute(property)
      ? {value:current.getAttribute(property),rank:-1,important:false}:null;
    for(const rule of rules) {
      let matched=false;
      try {matched=current.matches?.(rule.selector)??false;} catch {continue;}
      if(matched && (!winner || Number(rule.important)>Number(winner.important) ||
        (rule.important===winner.important && rule.rank>=winner.rank))) winner=rule;
    }
    const inline=paintDeclaration(current.getAttribute('style'),property);
    if(inline && (!winner?.important || inline.important)) winner=inline;
    if(winner && !/^inherit$/i.test(winner.value)) return winner.value;
  }
  return null;
}
export function svgCurveNodes(xml) {
  const rules=paintRules(xml), marked=[], fallback=[];
  for(const node of xml.getElementsByTagName('*')) {
    const kind=(node.localName||'').toLowerCase();
    if(!['path','polyline','line','polygon','rect','use'].includes(kind)) continue;
    const role=svgLineRole(node);
    if(role==='protected' || !recolorablePaint(resolvedPaint(node,rules))) continue;
    if(role==='marked') marked.push(node);
    // Untagged SVG: use open paths / polylines, not lines, bars or frames.
    else if(kind==='polyline' || (kind==='path' &&
      !/[zZ]\s*$/.test(node.getAttribute('d')||'') &&
      ((node.getAttribute('d')||'').match(/[-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?/gi)||[]).length>=6))
      fallback.push(node);
  }
  return marked.length?marked:fallback;
}

// Octave plots may draw each measurement as a separate line and a filled
// circle, polygon or symbol (<use>). Color ALL visible line/point geometry,
// not just the PSD-style continuous curve. Keep transparent paint and
// background fills, labels, clipping geometry and gradient definitions.
const OCTAVE_GEOMETRY=/^(?:path|line|polyline|polygon|circle|ellipse|rect|use)$/i;
const NON_DATA_CONTAINER=/^(?:mask|clippath|filter|pattern|lineargradient|radialgradient|metadata|title|desc|text|tspan)$/i;
const LABEL_CONTAINER=/(?:^|[\s_.-])(?:text|labels?|background)(?=$|[\s_.-]|\d)/i;
function octavePaintable(node,definition=false) {
  for(let p=node;p;p=p.parentElement) {
    if(NON_DATA_CONTAINER.test(p.localName||'')) return false;
    if(!definition && /^(?:defs|marker|symbol)$/i.test(p.localName||'')) return false;
    if(LABEL_CONTAINER.test([p.getAttribute('id'),p.getAttribute('class')].join(' '))) return false;
  }
  return true;
}
function applySvgPaint(node,properties) {
  if(!properties.length) return;
  const old=node.getAttribute('style')||'';
  const suffix=properties.map(([key,value])=>key+':'+value+' !important').join(';');
  node.setAttribute('style',old.replace(/;+\s*$/,'')+(old.trim()?';':'')+suffix);
}
export function recolorOctaveGeometry(xml,color) {
  const stroke=paintRules(xml),fill=paintRules(xml,'fill');
  const nodes=Array.from(xml.getElementsByTagName('*'));
  const byId=new Map(nodes.filter(n=>n.getAttribute('id')).map(n=>[n.getAttribute('id'),n]));
  const processed=new Set();
  function visit(node,definition=false) {
    if(!node || processed.has(node) || !octavePaintable(node,definition)) return;
    processed.add(node);
    const kind=(node.localName||'').toLowerCase();
    if(OCTAVE_GEOMETRY.test(kind)) {
      const props=[];
      const line=resolvedPaint(node,stroke);
      const inside=resolvedPaint(node,fill,'fill');
      if(recolorablePaint(line)) props.push(['stroke',color]);
      // No new fill on open paths or lines. Filled point symbols (including
      // implicit SVG default black) and closed paths are recolored.
      const point=/^(?:circle|ellipse|polygon|use)$/.test(kind) ||
        (kind==='path' && /[zZ]\s*$/.test(node.getAttribute('d')||''));
      if(point && (inside===null || recolorablePaint(inside))) props.push(['fill',color]);
      else if(kind==='path' && recolorablePaint(inside) && svgLineRole(node)==='marked')
        props.push(['fill',color]);
      applySvgPaint(node,props);
      if(kind==='use') {
        const href=node.getAttribute('href')||node.getAttribute('xlink:href');
        if(href?.startsWith('#')) visit(byId.get(href.slice(1)),true);
      }
    }
    if(definition) for(const child of Array.from(node.children||[])) visit(child,true);
  }
  for(const node of nodes) {
    if(OCTAVE_GEOMETRY.test(node.localName||'')) visit(node);
    if(node.localName?.toLowerCase()==='marker') visit(node,true);
  }
}
// Width is in SVG user units. Compare with the median original data-line
// stroke width (SVG default = 1); never compound a previous edit.
function svgLength(value,fallback=null) {
  const m=/^\s*(\d+(?:\.\d+)?|\.\d+)\s*(px|pt|pc|mm|cm|in)?\s*$/i.exec(String(value??''));
  if(!m) return fallback;
  const n=Number(m[1])*({px:1,pt:96/72,pc:16,mm:96/25.4,cm:96/2.54,in:96}[m[2]?.toLowerCase()]??1);
  return Number.isFinite(n)&&n>0?n:fallback;
}
export function octavePointScale(xml,curves,lineWidth) {
  if(lineWidth===null || lineWidth===undefined) return 1;
  const rules=paintRules(xml,'stroke-width');
  const widths=curves.map(n=>svgLength(resolvedPaint(n,rules,'stroke-width'),1)).sort((a,b)=>a-b);
  const middle=Math.floor(widths.length/2);
  const baseline=widths.length?(widths.length%2?widths[middle]:(widths[middle-1]+widths[middle])/2):1;
  return lineWidth/baseline;
}
export function octaveLineNodes(xml) {
  const rules=paintRules(xml);
  return Array.from(xml.getElementsByTagName('*')).filter(node=>
    /^(?:line|path|polyline)$/i.test(node.localName||'') &&
    svgLineRole(node)!=='protected' &&
    recolorablePaint(resolvedPaint(node,rules)) &&
    !/[zZ]\s*$/.test(node.getAttribute('d')||''));
}
export function octavePointNodes(xml) {
  const stroke=paintRules(xml),fill=paintRules(xml,'fill');
  return Array.from(xml.getElementsByTagName('*')).filter(node=>{
    const kind=(node.localName||'').toLowerCase();
    if(!octavePaintable(node) || svgLineRole(node)==='protected') return false;
    const point=/^(?:circle|ellipse|polygon|use)$/.test(kind) ||
      (kind==='path' && /[zZ]\s*$/.test(node.getAttribute('d')||'')) ||
      (kind==='rect' && /(?:point|dot|marker)/i.test([node.getAttribute('class'),node.getAttribute('id')].join(' ')));
    if(!point) return false;
    const line=resolvedPaint(node,stroke),inside=resolvedPaint(node,fill,'fill');
    return recolorablePaint(line) || inside===null || recolorablePaint(inside);
  });
}
export function scaleOctavePoints(xml,points,factor) {
  if(!Number.isFinite(factor) || factor<=0 || Math.abs(factor-1)<1e-9) return;
  // Scale each visible instance around its own bounding-box center, not
  // around the chart origin. A fresh wrapper preserves the existing node
  // transform, x/y, and shared definition (including multiple <use>s).
  for(const point of points) {
    const parent=point.parentNode;
    if(!parent) continue;
    const wrapper=xml.createElementNS('http://www.w3.org/2000/svg','g');
    wrapper.setAttribute('data-octave-point-scale',String(factor));
    wrapper.setAttribute('style','transform-box:fill-box;transform-origin:center;transform:scale('+factor+')');
    parent.insertBefore(wrapper,point);
    wrapper.appendChild(point);
  }
  // strokeWidth markers follow their parent stroke automatically.
  // User-space markers instead need their viewport enlarged explicitly.
  for(const marker of Array.from(xml.getElementsByTagName('marker'))) {
    if(marker.getAttribute('markerUnits')!=='userSpaceOnUse') continue;
    const w=svgLength(marker.getAttribute('markerWidth'),3);
    const h=svgLength(marker.getAttribute('markerHeight'),3);
    if(!marker.hasAttribute('viewBox')) marker.setAttribute('viewBox','0 0 '+w+' '+h);
    marker.setAttribute('markerWidth',String(w*factor));
    marker.setAttribute('markerHeight',String(h*factor));
  }
}
export function restyleSvgMarkup(source,requested,kind='psd') {
  const style=mergeSvgStyle(requested);
  const xml=new DOMParser().parseFromString(source,'image/svg+xml');
  if(xml.getElementsByTagName('parsererror').length ||
     xml.documentElement?.localName!=='svg') throw new Error('Cannot parse original SVG source');
  const curves=kind==='octave'?octaveLineNodes(xml):svgCurveNodes(xml);
  const points=kind==='octave'?octavePointNodes(xml):[];
  const pointScale=kind==='octave'?octavePointScale(xml,curves,style.lineWidth):1;
  // PSD retains its conservative fallback; octave also supports plots
  // composed entirely of filled data points.
  if(!curves.length && kind!=='octave') {
    if(style.lineWidth!==null || style.lineStyle!==null)
      throw new Error('未识别到可修改线型或线宽的频谱曲线');
    return recolorSvgMarkup(source,style.color);
  }
  for(const node of curves) {
    const properties=[['stroke',style.color]];
    if(style.lineWidth!==null) properties.push(['stroke-width',String(style.lineWidth)]);
    if(style.lineStyle!==null) {
      // Keep the pattern visible at wider widths; values are SVG user units.
      const dash=style.lineStyle==='none'?'none':style.lineStyle.split(' ')
        .map(value=>String(Number(value)*Math.max(1,style.lineWidth??1))).join(' ');
      properties.push(['stroke-dasharray',dash]);
      if(style.lineStyle.includes('1')) properties.push(['stroke-linecap','round']);
    }
    // An inline important declaration overrides author CSS, including class
    // rules. Original attributes/geometry/fill remain intact.
    applySvgPaint(node,properties);
  }
  if(kind==='octave') {
    recolorOctaveGeometry(xml,style.color);
    scaleOctavePoints(xml,points,pointScale);
  }
  return new XMLSerializer().serializeToString(xml);
}


// XLSX is the sole source of outline colors. An explicitly absent
// equipment/sensor border uses its exact fill RGB; an unresolved border
// must not silently become a different color. Textboxes keep no border.
export function cadOutlineSpec(item) {
  const colors=item.colors||{};
  const valid=value=>typeof value==='string' && /^#[0-9a-f]{6}$/i.test(value);
  const equipment=['rectangle','ellipse'].includes(item.shape_kind);
  const status=item.outline_status??(valid(colors.outline)?'color':
    colors.outline==='无/透明'?'none':'unresolved');
  const color=status==='color' && valid(colors.outline)?colors.outline:
    status==='none' && equipment && valid(colors.fill)?colors.fill:null;
  if(!color) return null;
  const width=Number(item.outline_width_px);
  return {color,width:Math.min(5,Math.max(2,Number.isFinite(width)?width:2))};
}


// Independent geometry for every outline: one centered segment per edge,
// with no shared mutable instance transforms or screen-line shader state.
export function cadOutlineSegments(positions) {
  const segments=[];
  for(let i=0;i+5<positions.length;i+=6) {
    const a=Array.from(positions.slice(i,i+3)),b=Array.from(positions.slice(i+3,i+6));
    if(![...a,...b].every(Number.isFinite)) continue;
    const delta=b.map((v,j)=>v-a[j]),length=Math.hypot(...delta);
    if(length<=1e-9) continue;
    segments.push({center:a.map((v,j)=>(v+b[j])/2),
      direction:delta.map(v=>v/length),length});
  }
  return segments;
}


// Excel may omit alt text, or encode an empty description/title. Only
// those rectangles take the shared planar sensor-outline route.
export function rectangleHasAltText(altText) {
  const clean=value=>String(value??'').replaceAll('_x000D_','').trim();
  return typeof altText==='string'?Boolean(clean(altText)):
    Boolean(clean(altText?.description)||clean(altText?.title));
}
export function planarOutlineVertices(kind,width,height,z=0.7) {
  if(kind==='ellipse') {
    const radius=Math.hypot(width,height)/2;
    return Array.from({length:72},(_,i)=>{
      const t=2*Math.PI*i/72;
      return [radius*Math.cos(t),radius*Math.sin(t),z];
    });
  }
  const hw=width/2,hh=height/2;
  return [[-hw,hh,z],[hw,hh,z],[hw,-hh,z],[-hw,-hh,z]];
}
