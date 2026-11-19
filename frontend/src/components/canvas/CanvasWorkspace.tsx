import React, { useEffect, useRef, useState } from 'react';
import { canvasItems } from './registry';
type Camera = { x: number; y: number; z: number };
type Point = { x: number; y: number };
const key = 'finsight.component-canvas.layout.v1';
const bound = (n: number, min = -20000, max = 20000) => Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : 0;
const initial = () => Object.fromEntries(canvasItems.map(i => [i.id, { x: i.x, y: i.y }]));
export function CanvasWorkspace() {
  const shell = useRef<HTMLDivElement>(null), world = useRef<HTMLDivElement>(null);
  const camera = useRef<Camera>({ x: 0, y: 0, z: 1 });
  const positions = useRef<Record<string, Point>>(initial());
  const frames = useRef(new Map<string, HTMLDivElement>());
  const raf = useRef(0), timer = useRef(0), space = useRef(false);
  const drag = useRef<{ id?: string; x: number; y: number; moved: boolean } | null>(null);
  const [message, setMessage] = useState('Synthetic data only. Light is the current product theme.');
  function save() { try { localStorage.setItem(key, JSON.stringify({ version: 1, camera: camera.current, positions: positions.current })); } catch { /* Storage is optional. */ } }
  function paint() {
    if (raf.current) return;
    raf.current = requestAnimationFrame(() => {
      raf.current = 0;
      const c = camera.current;
      if (world.current) world.current.style.transform = `translate(${c.x}px,${c.y}px) scale(${c.z})`;
      frames.current.forEach((el, id) => { const p = positions.current[id]; el.style.transform = `translate(${p.x}px,${p.y}px)`; });
    });
    clearTimeout(timer.current); timer.current = window.setTimeout(save, 250);
  }
  function zoom(factor: number, x?: number, y?: number) {
    const c = camera.current, el = shell.current; if (!el) return;
    const px = x ?? el.clientWidth / 2, py = y ?? el.clientHeight / 2;
    const z = bound(c.z * factor, .25, 3), ratio = z / c.z;
    camera.current = { x: bound(px - (px - c.x) * ratio), y: bound(py - (py - c.y) * ratio), z }; paint();
  }
  function fit() {
    const el = shell.current; if (!el) return;
    const left = Math.min(...canvasItems.map(i => positions.current[i.id].x));
    const top = Math.min(...canvasItems.map(i => positions.current[i.id].y));
    const right = Math.max(...canvasItems.map(i => positions.current[i.id].x + i.width));
    const bottom = Math.max(...canvasItems.map(i => positions.current[i.id].y + i.height + 40));
    const z = bound(Math.min((el.clientWidth - 64) / (right - left), (el.clientHeight - 64) / (bottom - top), 1), .25, 3);
    camera.current = { x: (el.clientWidth - (right - left) * z) / 2 - left * z, y: 40 - top * z, z }; paint();
  }
  useEffect(() => {
    try {
      const text = localStorage.getItem(key); const data = text && text.length < 10000 ? JSON.parse(text) : null;
      if (data?.version === 1) {
        const c = data.camera;
        if (c && [c.x, c.y, c.z].every(Number.isFinite)) camera.current = { x: bound(c.x), y: bound(c.y), z: bound(c.z, .25, 3) };
        canvasItems.forEach(i => { const p = data.positions?.[i.id]; if (p && [p.x, p.y].every(Number.isFinite)) positions.current[i.id] = { x: bound(p.x), y: bound(p.y) }; });
      }
    } catch { /* Malformed saved layout falls back to source. */ }
    paint();
    const root = document.documentElement, old = root.style.overscrollBehaviorX; root.style.overscrollBehaviorX = 'none';
    const cancel = () => { space.current = false; drag.current = null; };
    const up = () => { space.current = false; };
    window.addEventListener('blur', cancel); window.addEventListener('keyup', up); document.addEventListener('visibilitychange', cancel);
    const el = shell.current!;
    const wheel = (e: WheelEvent) => {
      if (e.ctrlKey || e.metaKey) { e.preventDefault(); const r = el.getBoundingClientRect(); zoom(Math.exp(-e.deltaY * .002), e.clientX - r.left, e.clientY - r.top); return; }
      if ((e.target as HTMLElement).closest('[data-preview]')) return;
      e.preventDefault(); camera.current.x = bound(camera.current.x - e.deltaX); camera.current.y = bound(camera.current.y - e.deltaY); paint();
    };
    el.addEventListener('wheel', wheel, { passive: false });
    return () => { save(); clearTimeout(timer.current); cancelAnimationFrame(raf.current); raf.current = 0; root.style.overscrollBehaviorX = old; el.removeEventListener('wheel', wheel); window.removeEventListener('blur', cancel); window.removeEventListener('keyup', up); document.removeEventListener('visibilitychange', cancel); };
  }, []);
  const button = 'rounded border border-line-strong bg-surface px-3 py-2 text-sm hover:bg-subtle';
  return <div className="flex h-dvh flex-col bg-canvas text-ink">
    <header className="flex flex-wrap items-center gap-2 border-b border-line p-3">
      <a href="/" className={button}>Back to dashboard</a><h1 className="mr-auto text-base font-semibold">Component canvas</h1>
      <button className={button} onClick={() => zoom(.8)} aria-label="Zoom out">−</button><button className={button} onClick={() => zoom(1.25)} aria-label="Zoom in">+</button>
      <button className={button} onClick={fit}>Fit all</button><button className={button} onClick={() => { camera.current = { x: 0, y: 0, z: 1 }; paint(); }}>Reset camera</button>
    </header>
    <p id="canvas-help" className="px-4 py-2 text-xs text-muted">Drag empty space to pan. Use +/− or arrow keys with the canvas focused. Move handles support arrow keys; Shift moves 10 pixels. Names copy on activation.</p>
    <div ref={shell} tabIndex={0} aria-label="Component workspace" aria-describedby="canvas-help" className="ui-canvas relative min-h-0 flex-1 overflow-hidden"
      onKeyDown={e => { if (e.target !== e.currentTarget) return; if (e.code === 'Space') { space.current = true; e.preventDefault(); } else if (e.key === '+' || e.key === '=') { zoom(1.25); e.preventDefault(); } else if (e.key === '-') { zoom(.8); e.preventDefault(); } else if (e.key.startsWith('Arrow')) { e.preventDefault(); camera.current.x = bound(camera.current.x + (e.key === 'ArrowLeft' ? 40 : e.key === 'ArrowRight' ? -40 : 0)); camera.current.y = bound(camera.current.y + (e.key === 'ArrowUp' ? 40 : e.key === 'ArrowDown' ? -40 : 0)); paint(); } }}
      onPointerDown={e => { const target = e.target as HTMLElement; const handle = target.closest<HTMLElement>('[data-move]'); if (!handle && e.target !== e.currentTarget && e.button !== 1 && !space.current) return; e.preventDefault(); drag.current = { id: e.button === 1 || space.current ? undefined : handle?.dataset.move, x: e.clientX, y: e.clientY, moved: false }; e.currentTarget.setPointerCapture(e.pointerId); }}
      onPointerMove={e => { const d = drag.current; if (!d) return; const dx = e.clientX - d.x, dy = e.clientY - d.y; if (Math.abs(dx) + Math.abs(dy) > 2) d.moved = true; if (d.id) { const p = positions.current[d.id]; p.x = bound(p.x + dx / camera.current.z); p.y = bound(p.y + dy / camera.current.z); } else { camera.current.x = bound(camera.current.x + dx); camera.current.y = bound(camera.current.y + dy); } d.x = e.clientX; d.y = e.clientY; paint(); }}
      onPointerUp={e => { if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId); drag.current = null; save(); }} onPointerCancel={() => { drag.current = null; }} onLostPointerCapture={() => { drag.current = null; }}>
      <div ref={world} className="absolute left-0 top-0 origin-top-left">
        {canvasItems.map(item => <div key={item.id} ref={el => { if (el) frames.current.set(item.id, el); else frames.current.delete(item.id); }} className="absolute left-0 top-0" style={{ width: item.width, transform: `translate(${item.x}px,${item.y}px)` }}>
          <div className="mb-2 flex items-center gap-3 text-xs text-secondary">
            <button title="Copy exact preview name" onClick={async () => { try { await navigator.clipboard.writeText(item.name); setMessage(`Copied: ${item.name}`); } catch { setMessage(`Select and copy this name: ${item.name}`); } }}>{item.name}</button>
            <button data-move={item.id} aria-label={`Move ${item.name}`} aria-describedby="canvas-help" className="cursor-default rounded border border-line-strong px-2 py-1" onKeyDown={e => { if (!e.key.startsWith('Arrow')) return; e.stopPropagation(); e.preventDefault(); const p = positions.current[item.id], step = e.shiftKey ? 10 : 1; p.x = bound(p.x + (e.key === 'ArrowLeft' ? -step : e.key === 'ArrowRight' ? step : 0)); p.y = bound(p.y + (e.key === 'ArrowUp' ? -step : e.key === 'ArrowDown' ? step : 0)); paint(); }}>Move</button>
          </div>
          <div data-preview className="ui-canvas-preview" style={{ minHeight: item.height }}><item.component /></div>
        </div>)}
      </div>
    </div><p role="status" className="border-t border-line px-4 py-2 text-xs text-muted">{message}</p>
  </div>;
}
