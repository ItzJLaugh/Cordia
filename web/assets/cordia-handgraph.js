/* Live node/edge hand.

   Renders real geometry from assets/hand-graph.json (271 nodes, 705 edges,
   generated parametrically — see gen_hand.py) and animates it:

     pulse        a node briefly brightens and swells
     fast signal  a packet crosses several edges quickly
     slow signal  the same, drawn out
     lag          a packet stalls mid-edge, then resumes

   Only a handful of attributes change per frame; the rest of the SVG is
   static. Fully disabled under prefers-reduced-motion, where it renders once
   and holds — the hand still reads, it just stops moving.

   mount: CordiaHandGraph.mount(svgElement)
*/
window.CordiaHandGraph = (function () {
  'use strict';

  var SRC = 'assets/hand-graph.json';
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  function mount(svg) {
    if (!svg) return;
    fetch(SRC)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (g) { if (g && g.nodes && g.edges) build(svg, g); })
      .catch(function () { /* decorative only — silence is correct */ });
  }

  function build(svg, g) {
    var NS = 'http://www.w3.org/2000/svg';
    var nodes = g.nodes, edges = g.edges;

    // adjacency, for routing signals along real connections
    var adj = nodes.map(function () { return []; });
    edges.forEach(function (e, i) {
      adj[e[0]].push({ to: e[1], edge: i });
      adj[e[1]].push({ to: e[0], edge: i });
    });

    svg.setAttribute('viewBox', '0 0 1 1.12');
    svg.setAttribute('preserveAspectRatio', 'xMidYMax meet');

    var gEdges = document.createElementNS(NS, 'g');
    gEdges.setAttribute('stroke', 'currentColor');
    gEdges.setAttribute('stroke-width', '0.0016');
    gEdges.setAttribute('opacity', '0.30');
    var edgeEls = edges.map(function (e) {
      var l = document.createElementNS(NS, 'line');
      l.setAttribute('x1', nodes[e[0]].x); l.setAttribute('y1', nodes[e[0]].y);
      l.setAttribute('x2', nodes[e[1]].x); l.setAttribute('y2', nodes[e[1]].y);
      gEdges.appendChild(l);
      return l;
    });
    svg.appendChild(gEdges);

    var gNodes = document.createElementNS(NS, 'g');
    gNodes.setAttribute('fill', 'currentColor');
    var nodeEls = nodes.map(function (n) {
      var c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', n.x); c.setAttribute('cy', n.y);
      c.setAttribute('r', (0.0026 + n.d * 0.00075).toFixed(5));
      c.setAttribute('opacity', '0.62');
      gNodes.appendChild(c);
      return c;
    });
    svg.appendChild(gNodes);

    if (reduce) return;               // rendered, held, no motion

    var packets = document.createElementNS(NS, 'g');
    packets.setAttribute('fill', 'currentColor');
    svg.appendChild(packets);

    /* ---- pulses ---- */
    var pulses = [];
    function firePulse() {
      var i = (Math.random() * nodes.length) | 0;
      pulses.push({ i: i, t: 0, dur: 900 + Math.random() * 700 });
    }

    /* ---- signals: walk a real path across the graph ---- */
    var signals = [];
    function fireSignal(kind) {
      var start = (Math.random() * nodes.length) | 0;
      var path = [start], seen = {};
      seen[start] = 1;
      var hops = kind === 'fast' ? 7 + (Math.random() * 5 | 0)
                                 : 4 + (Math.random() * 4 | 0);
      var cur = start;
      for (var h = 0; h < hops; h++) {
        var opts = adj[cur].filter(function (a) { return !seen[a.to]; });
        if (!opts.length) break;
        var pick = opts[(Math.random() * opts.length) | 0];
        seen[pick.to] = 1;
        path.push(pick.to);
        cur = pick.to;
      }
      if (path.length < 2) return;

      var dot = document.createElementNS(NS, 'circle');
      dot.setAttribute('r', kind === 'fast' ? '0.0058' : '0.0048');
      packets.appendChild(dot);
      signals.push({
        path: path, dot: dot, seg: 0, t: 0,
        segDur: kind === 'fast' ? 90 : 300,
        // a 'lag' signal stalls once, partway, then carries on
        lagAt: kind === 'lag' ? 1 + (Math.random() * (path.length - 2) | 0) : -1,
        lagFor: 700 + Math.random() * 600, lagged: 0,
      });
    }

    var last = performance.now(), acc = 0;
    function frame(now) {
      var dt = Math.min(now - last, 64);
      last = now;
      acc += dt;

      // cadence: pulses often, signals occasionally
      if (acc > 260) {
        acc = 0;
        if (Math.random() < 0.75) firePulse();
        var r = Math.random();
        if (r < 0.12) fireSignal('fast');
        else if (r < 0.20) fireSignal('slow');
        else if (r < 0.24) fireSignal('lag');
      }

      for (var p = pulses.length - 1; p >= 0; p--) {
        var pu = pulses[p];
        pu.t += dt;
        var k = pu.t / pu.dur;
        if (k >= 1) {
          nodeEls[pu.i].setAttribute('opacity', '0.62');
          nodeEls[pu.i].setAttribute('r', (0.0026 + nodes[pu.i].d * 0.00075).toFixed(5));
          pulses.splice(p, 1);
          continue;
        }
        var e = Math.sin(k * Math.PI);            // rise and fall
        nodeEls[pu.i].setAttribute('opacity', (0.62 + 0.38 * e).toFixed(3));
        nodeEls[pu.i].setAttribute('r',
          (0.0026 + nodes[pu.i].d * 0.00075 + 0.0042 * e).toFixed(5));
      }

      for (var s = signals.length - 1; s >= 0; s--) {
        var sg = signals[s];
        if (sg.seg === sg.lagAt && sg.lagged < sg.lagFor) {
          sg.lagged += dt;
          sg.dot.setAttribute('opacity',
            (0.45 + 0.3 * Math.sin(sg.lagged / 90)).toFixed(3));
          continue;
        }
        sg.t += dt;
        var f = sg.t / sg.segDur;
        while (f >= 1 && sg.seg < sg.path.length - 2) {
          sg.seg++; sg.t -= sg.segDur; f = sg.t / sg.segDur;
        }
        if (sg.seg >= sg.path.length - 1 || (sg.seg === sg.path.length - 2 && f >= 1)) {
          packets.removeChild(sg.dot);
          signals.splice(s, 1);
          continue;
        }
        var a = nodes[sg.path[sg.seg]], b = nodes[sg.path[sg.seg + 1]];
        sg.dot.setAttribute('cx', (a.x + (b.x - a.x) * f).toFixed(5));
        sg.dot.setAttribute('cy', (a.y + (b.y - a.y) * f).toFixed(5));
        sg.dot.setAttribute('opacity', (0.85 * Math.sin(Math.min(f, 1) * Math.PI) + 0.15).toFixed(3));
        var el = edgeEls[edgeIndex(sg.path[sg.seg], sg.path[sg.seg + 1])];
        if (el) {
          el.setAttribute('opacity', '0.85');
          setTimeout(function (x) { return function () { x.setAttribute('opacity', '0.30'); }; }(el), 260);
        }
      }
      requestAnimationFrame(frame);
    }

    var edgeKey = {};
    edges.forEach(function (e, i) { edgeKey[e[0] + ':' + e[1]] = i; edgeKey[e[1] + ':' + e[0]] = i; });
    function edgeIndex(a, b) { return edgeKey[a + ':' + b]; }

    requestAnimationFrame(frame);
  }

  return { mount: mount };
})();
