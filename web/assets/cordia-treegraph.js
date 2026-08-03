/* Live tree → neural network.

   One continuous form. Above ground it is a tree: organic, curved, tapering
   branches. Below ground the same structure straightens into a graph —
   circular nodes, straight edges, and cross-links between root branches that
   no real root system has. That crossover is the whole idea, so the transition
   is gradual rather than a hard line: branches lose their curve and gain nodes
   as they descend.

   Signals travel UP, from the roots into the canopy — the network feeds the
   tree, not the other way round.

   Geometry is generated procedurally from a fixed seed, so it is identical on
   every load without shipping a JSON file or spending a request on it.

   Decorative only. Silent on failure, static under prefers-reduced-motion.

   mount: CordiaTreeGraph.mount(svgElement)
*/
window.CordiaTreeGraph = (function () {
  'use strict';

  var W = 1600, H = 1000;
  var CX = 800;                      // trunk centre
  var GROUND = 505;                  // where tree becomes network
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var NS = 'http://www.w3.org/2000/svg';

  // Deterministic PRNG (mulberry32) — same tree every visit.
  function rng(seed) {
    return function () {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  function el(name, attrs) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  }

  /* ---------------------------------------------------------------- build */

  function generate() {
    var rand = rng(20260803);
    var branches = [], nodes = [], edges = [];

    // --- canopy: recursive organic branching, upward from the trunk ---
    function grow(x, y, angle, len, width, depth) {
      if (depth > 4 || len < 18) return;
      var spread = (rand() - 0.5) * 0.42;
      var x2 = x + Math.sin(angle + spread) * len;
      var y2 = y - Math.cos(angle + spread) * len;
      // control point offset perpendicular to travel gives the limb its bend
      var cx = (x + x2) / 2 + Math.cos(angle) * len * 0.20 * (rand() - 0.5) * 2;
      var cy = (y + y2) / 2 + Math.sin(angle) * len * 0.14;

      branches.push({ d: 'M' + x.toFixed(1) + ' ' + y.toFixed(1) +
                          ' Q' + cx.toFixed(1) + ' ' + cy.toFixed(1) +
                          ' ' + x2.toFixed(1) + ' ' + y2.toFixed(1),
                      w: Math.max(0.7, width) });

      // a node at every junction, faint up here, so the graph reading is
      // already latent in the canopy rather than arriving suddenly at the roots
      if (depth >= 2) nodes.push({ x: x2, y: y2, r: Math.max(1.5, 4.6 - depth), up: true });

      var forks = depth < 2 ? 2 : (rand() < 0.82 ? 2 : 3);
      for (var i = 0; i < forks; i++) {
        var a = angle + (i - (forks - 1) / 2) * (0.50 + rand() * 0.30);
        grow(x2, y2, a, len * (0.68 + rand() * 0.16), width * 0.62, depth + 1);
      }
    }

    // trunk
    branches.push({ d: 'M' + CX + ' ' + GROUND + ' L' + CX + ' 390', w: 15 });
    grow(CX, 390, -0.06, 112, 11, 0);

    // --- roots: same recursion, but straight segments and heavier nodes ---
    // angle 0 is straight DOWN. The first version passed Math.PI here and used
    // cos() for the vertical step, so cos(PI) = -1 drove the whole root system
    // upward and it rendered as a fan on either side of the canopy.
    var rootTips = [];
    function root(x, y, angle, len, width, depth) {
      if (depth > 4 || len < 20) return;
      var x2 = x + Math.sin(angle) * len * 2.10;    // spread well past the card
      var y2 = y + Math.cos(angle) * len;
      if (y2 > H - 30) y2 = H - 30;

      edges.push({ x1: x, y1: y, x2: x2, y2: y2, w: Math.max(0.8, width) });
      var n = { x: x2, y: y2, r: Math.max(3.0, 7.4 - depth * 1.1), up: false };
      nodes.push(n);
      if (depth >= 1) rootTips.push(n);

      var forks = depth < 1 ? 3 : 2;
      for (var i = 0; i < forks; i++) {
        var a = angle + (i - (forks - 1) / 2) * (0.62 + rand() * 0.24);
        root(x2, y2, a, len * (0.76 + rand() * 0.10), width * 0.66, depth + 1);
      }
    }
    root(CX, GROUND, 0, 104, 13, -1);

    // --- cross-links: what makes it a network and not a root system ---
    // Deliberately sparse. An earlier pass generated ~2300 of these and the
    // root system rendered as grey fog — the individual nodes and edges, which
    // are the entire point of the bottom half, stopped being legible at all.
    // Capped, and only between near neighbours at similar depth.
    var links = 0;
    for (var i = 0; i < rootTips.length && links < 34; i++) {
      for (var j = i + 1; j < rootTips.length && links < 34; j++) {
        var a = rootTips[i], b = rootTips[j];
        if (Math.abs(a.y - b.y) > 42) continue;
        var dx = a.x - b.x, dy = a.y - b.y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > 132 || dist < 40) continue;
        if (rand() > 0.30) continue;
        edges.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y, w: 0.9, link: true });
        links++;
      }
    }

    return { branches: branches, nodes: nodes, edges: edges };
  }

  /* ---------------------------------------------------------------- mount */

  function mount(svg) {
    if (!svg) return;
    var g;
    try { g = generate(); } catch (e) { return; }

    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');

    var root = el('g', { fill: 'none', stroke: 'currentColor',
                         'stroke-linecap': 'round', 'stroke-linejoin': 'round' });

    // edges first so nodes sit on top
    g.edges.forEach(function (e) {
      root.appendChild(el('line', {
        x1: e.x1.toFixed(1), y1: e.y1.toFixed(1),
        x2: e.x2.toFixed(1), y2: e.y2.toFixed(1),
        'stroke-width': e.w.toFixed(1),
        'stroke-opacity': e.link ? 0.34 : 0.78,
        'stroke-dasharray': e.link ? '3 5' : null
      }));
    });

    g.branches.forEach(function (b) {
      root.appendChild(el('path', { d: b.d, 'stroke-width': b.w.toFixed(1),
                                    'stroke-opacity': 0.8 }));
    });

    var dots = [];
    g.nodes.forEach(function (n) {
      var c = el('circle', {
        cx: n.x.toFixed(1), cy: n.y.toFixed(1), r: n.r.toFixed(1),
        fill: 'currentColor', stroke: 'none',
        'fill-opacity': n.up ? 0.38 : 0.72
      });
      root.appendChild(c);
      dots.push({ el: c, base: n.r, baseOp: n.up ? 0.38 : 0.72 });
    });

    svg.appendChild(root);
    if (reduce || !dots.length) return;      // renders once and holds

    // --- animation: nodes pulse, brightest at the roots and rising ---
    var t = 0;
    (function frame() {
      t += 1;
      for (var k = 0; k < 3; k++) {
        var d = dots[(Math.random() * dots.length) | 0];
        if (!d || d.busy) continue;
        d.busy = true;
        var start = performance.now();
        (function pulse(d, start) {
          function step(now) {
            var p = (now - start) / 900;
            if (p >= 1) {
              d.el.setAttribute('r', d.base.toFixed(1));
              d.el.setAttribute('fill-opacity', d.baseOp);
              d.busy = false;
              return;
            }
            var s = Math.sin(p * Math.PI);
            d.el.setAttribute('r', (d.base * (1 + s * 0.85)).toFixed(2));
            d.el.setAttribute('fill-opacity', (d.baseOp + s * 0.45).toFixed(2));
            requestAnimationFrame(step);
          }
          requestAnimationFrame(step);
        })(d, start);
      }
      setTimeout(function () { requestAnimationFrame(frame); }, 620);
    })();
  }

  return { mount: mount };
})();
