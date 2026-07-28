/* ============================================================
   Cordia Canvas — window manager
   Vanilla JS. Pointer Events unify mouse + touch.
   - drag by title bar (1 finger / mouse)
   - resize by corner handle (1 finger / mouse)
   - pinch with 2 pointers anywhere on a window to scale it
   - blanket canvas warps beneath focused window
   ============================================================ */
(function(){
"use strict";

const page = document.querySelector('.canvas-page');
const blanket = document.getElementById('blanket');
const bctx = blanket.getContext('2d');
let windows = [];
let zTop = 40;

/* ---------- blanket: dark olive fabric with organic noise ---------- */
function sizeBlanket(){
  blanket.width = innerWidth * devicePixelRatio;
  blanket.height = innerHeight * devicePixelRatio;
  blanket.style.width = innerWidth + 'px';
  blanket.style.height = innerHeight + 'px';
  bctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
}
sizeBlanket();
addEventListener('resize', sizeBlanket);

/* pre-render static fabric texture once */
const fabric = document.createElement('canvas');
function renderFabric(){
  fabric.width = innerWidth; fabric.height = innerHeight;
  const fx = fabric.getContext('2d');
  /* base gradient */
  const g = fx.createLinearGradient(0,0,innerWidth,innerHeight);
  g.addColorStop(0,'#2b351a');
  g.addColorStop(.5,'#232b14');
  g.addColorStop(1,'#1e2510');
  fx.fillStyle = g;
  fx.fillRect(0,0,fabric.width,fabric.height);
  /* soft organic blobs */
  for(let i=0;i<26;i++){
    const x = Math.random()*fabric.width, y = Math.random()*fabric.height;
    const r = 90 + Math.random()*260;
    const gg = fx.createRadialGradient(x,y,0,x,y,r);
    const hue = Math.random() < .5 ? '143,181,115' : '94,120,70';
    gg.addColorStop(0,`rgba(${hue},${.03+Math.random()*.05})`);
    gg.addColorStop(1,'rgba(0,0,0,0)');
    fx.fillStyle = gg;
    fx.fillRect(x-r,y-r,r*2,r*2);
  }
  /* weave lines — the blanket threads */
  fx.strokeStyle = 'rgba(238,242,228,.022)';
  fx.lineWidth = 1;
  for(let y=0; y<fabric.height; y+=7){
    fx.beginPath();
    fx.moveTo(0,y + Math.sin(y*.05)*2);
    fx.lineTo(fabric.width, y + Math.sin(y*.05)*2);
    fx.stroke();
  }
}
renderFabric();
addEventListener('resize', renderFabric);

/* draw blanket each frame, warped under the focused window */
let focusRect = null;
function drawBlanket(){
  bctx.clearRect(0,0,innerWidth,innerHeight);
  bctx.drawImage(fabric,0,0);

  if(focusRect){
    const {x,y,w,h} = focusRect;
    const cx = x + w/2, cy = y + h/2;
    /* dent: radial shadow pool beneath the window */
    const pool = bctx.createRadialGradient(cx,cy,0,cx,cy,Math.max(w,h)*.95);
    pool.addColorStop(0,'rgba(10,14,4,.5)');
    pool.addColorStop(.55,'rgba(10,14,4,.22)');
    pool.addColorStop(1,'rgba(10,14,4,0)');
    bctx.fillStyle = pool;
    bctx.fillRect(0,0,innerWidth,innerHeight);

    /* pinched threads: rings converging toward the window edges */
    bctx.save();
    bctx.strokeStyle = 'rgba(238,242,228,.05)';
    for(let i=1;i<=5;i++){
      const pad = i*16;
      bctx.beginPath();
      bctx.roundRect(x-pad, y-pad, w+pad*2, h+pad*2, 22+pad*.4);
      bctx.stroke();
    }
    bctx.restore();
  }
  requestAnimationFrame(drawBlanket);
}
requestAnimationFrame(drawBlanket);

/* ---------- window registry ---------- */
function register(win){
  windows.push(win);
  bringToFront(win.el);
}
function bringToFront(el){
  windows.forEach(w => w.el.classList.remove('focused'));
  el.classList.add('focused');
  el.style.zIndex = ++zTop;
}
function updateFocus(){
  const top = windows.reduce((a,w) =>
    (+w.el.style.zIndex > (+a?.el.style.zIndex||0) ? w : a), null);
  if(top && !top.el.classList.contains('minimized')){
    focusRect = { x: top.el.offsetLeft, y: top.el.offsetTop,
                  w: top.el.offsetWidth, h: top.el.offsetHeight };
  } else focusRect = null;
}

/* ---------- gestures per window ---------- */
function attachGestures(win){
  const el = win.el;
  const bar = el.querySelector('.cwin-bar');
  const handle = el.querySelector('.cwin-handle');
  const pointers = new Map();   /* pointerId -> {x,y} */
  let mode = null;              /* 'drag' | 'resize' | 'pinch' */
  let start = null;

  function ptDist(){
    const pts = [...pointers.values()];
    if(pts.length < 2) return 0;
    return Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
  }

  function onDown(e){
    el.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, {x:e.clientX, y:e.clientY});
    bringToFront(el); updateFocus();

    if(pointers.size === 2){
      /* second finger down → pinch from anywhere on the window */
      mode = 'pinch';
      start = {
        dist: ptDist(),
        w: el.offsetWidth, h: el.offsetHeight,
        x: el.offsetLeft, y: el.offsetTop,
        cx: el.offsetLeft + el.offsetWidth/2,
        cy: el.offsetTop + el.offsetHeight/2
      };
    } else if(e.target.closest('.cwin-handle')){
      mode = 'resize';
      start = { mx:e.clientX, my:e.clientY, w:el.offsetWidth, h:el.offsetHeight };
    } else if(e.target.closest('.cwin-bar') && !e.target.closest('.cwin-btn')){
      mode = 'drag';
      start = { mx:e.clientX, my:e.clientY, x:el.offsetLeft, y:el.offsetTop };
    }
  }

  function onMove(e){
    if(!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, {x:e.clientX, y:e.clientY});
    if(!mode || !start) return;

    if(mode === 'pinch' && pointers.size >= 2){
      const scale = Math.min(2.2, Math.max(.5, ptDist() / start.dist));
      const nw = Math.max(230, start.w * scale);
      const nh = Math.max(140, start.h * scale);
      /* scale around the window's center */
      el.style.left = (start.cx - nw/2) + 'px';
      el.style.top  = (start.cy - nh/2) + 'px';
      el.style.width = nw + 'px';
      el.style.height = nh + 'px';
    } else if(mode === 'resize'){
      const nw = Math.max(230, start.w + (e.clientX - start.mx));
      const nh = Math.max(140, start.h + (e.clientY - start.my));
      el.style.width = nw + 'px';
      el.style.height = nh + 'px';
    } else if(mode === 'drag'){
      let nx = start.x + (e.clientX - start.mx);
      let ny = start.y + (e.clientY - start.my);
      /* keep 40px of the window reachable on screen */
      nx = Math.min(innerWidth - 60, Math.max(-el.offsetWidth + 60, nx));
      ny = Math.min(innerHeight - 40, Math.max(0, ny));
      el.style.left = nx + 'px';
      el.style.top = ny + 'px';
    }
    updateFocus();
  }

  function onUp(e){
    pointers.delete(e.pointerId);
    if(pointers.size < 2 && mode === 'pinch') mode = null;
    if(pointers.size === 0){ mode = null; start = null; }
  }

  el.addEventListener('pointerdown', onDown);
  el.addEventListener('pointermove', onMove);
  el.addEventListener('pointerup', onUp);
  el.addEventListener('pointercancel', onUp);

  /* controls */
  el.querySelector('[data-min]').addEventListener('click', ev => {
    ev.stopPropagation();
    el.classList.toggle('minimized');
    updateFocus();
  });
  el.querySelector('[data-max]').addEventListener('click', ev => {
    ev.stopPropagation();
    if(el.dataset.prev){
      const p = JSON.parse(el.dataset.prev);
      Object.assign(el.style, {left:p.left, top:p.top, width:p.width, height:p.height});
      delete el.dataset.prev;
    } else {
      el.dataset.prev = JSON.stringify({
        left: el.style.left, top: el.style.top,
        width: el.style.width, height: el.style.height });
      Object.assign(el.style, {left:'12px', top:'64px',
        width:(innerWidth-24)+'px', height:(innerHeight-90)+'px'});
    }
    updateFocus();
  });
  el.querySelector('[data-close]').addEventListener('click', ev => {
    ev.stopPropagation();
    el.style.transition = 'opacity .25s, transform .25s';
    el.style.opacity = '0';
    el.style.transform = 'scale(.94)';
    setTimeout(() => {
      windows = windows.filter(w => w !== win);
      el.remove(); updateFocus();
    }, 240);
  });
}

/* ---------- public: spawn window ---------- */
window.CordiaCanvas = {
  spawn({title, dot='#8fb573', x=80, y=90, w=420, h='auto', html, enter=true}){
    const el = document.createElement('div');
    el.className = 'cwin' + (enter ? ' enter' : '');
    el.style.left = x+'px'; el.style.top = y+'px'; el.style.width = w+'px';
    if(h !== 'auto') el.style.height = h+'px';
    el.innerHTML = `
      <div class="cwin-bar">
        <span class="cwin-dot" style="background:${dot}"></span>
        <span class="cwin-title">${title}</span>
        <div class="cwin-controls">
          <button class="cwin-btn" data-min title="Shrink">–</button>
          <button class="cwin-btn" data-max title="Expand">▢</button>
          <button class="cwin-btn" data-close title="Close">×</button>
        </div>
      </div>
      <div class="cwin-body">${html}</div>
      <div class="cwin-handle"></div>`;
    page.appendChild(el);
    const win = { el };
    register(win);
    attachGestures(win);
    updateFocus();
    return win;
  }
};

})();
