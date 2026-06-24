// Cómo razona el agente (three.js): una señal recorre el ciclo
// Pregunta → Agente → tool ask_kb → Knowledge Base → Agente → Claude → Respuesta.
(function () {
  let inited = false;

  function init() {
    if (inited) return;
    const host = document.getElementById("agent3d");
    if (!host || !window.THREE) return;
    inited = true;
    const THREE = window.THREE;
    const W = () => host.clientWidth || 800, H = () => host.clientHeight || 440;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    host.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 1000);
    camera.position.set(0, 0, 96);

    const TEAL = 0x38e0c6, PERI = 0x7c9cf5, PURPLE = 0xb088f9, WHITE = 0xffffff;
    const V = (x, y, z) => new THREE.Vector3(x, y, z);
    const AG = V(0, 0, 0), TOOL = V(26, 15, -4), KB = V(46, -2, -10),
      CLAUDE = V(26, -15, 4), QIN = V(-54, 3, 0), AOUT = V(54, 3, 0);

    // Agente: icosaedro wireframe + núcleo
    const ag = new THREE.Group(); ag.position.copy(AG); scene.add(ag);
    const agWire = new THREE.Mesh(new THREE.IcosahedronGeometry(8, 1),
      new THREE.MeshBasicMaterial({ color: TEAL, wireframe: true, transparent: true, opacity: 0.9 }));
    ag.add(agWire, new THREE.Mesh(new THREE.IcosahedronGeometry(5, 0),
      new THREE.MeshBasicMaterial({ color: TEAL, transparent: true, opacity: 0.22 })));

    const node = (color, pos) => {
      const m = new THREE.Mesh(new THREE.SphereGeometry(3.6, 20, 20),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.85 }));
      m.position.copy(pos); scene.add(m); return m;
    };
    const tool = node(PERI, TOOL), claude = node(PURPLE, CLAUDE);

    // Knowledge Base: mini nube
    const KN = 90, kp = new Float32Array(KN * 3);
    for (let i = 0; i < KN; i++) {
      const r = 6 * Math.cbrt(Math.random()), th = Math.random() * 6.283, ph = Math.acos(2 * Math.random() - 1);
      kp[i * 3] = KB.x + r * Math.sin(ph) * Math.cos(th);
      kp[i * 3 + 1] = KB.y + r * Math.sin(ph) * Math.sin(th);
      kp[i * 3 + 2] = KB.z + r * Math.cos(ph);
    }
    const kg = new THREE.BufferGeometry();
    kg.setAttribute("position", new THREE.BufferAttribute(kp, 3));
    const kbMat = new THREE.PointsMaterial({
      color: TEAL, size: 1.3, transparent: true, opacity: 0.9,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    scene.add(new THREE.Points(kg, kbMat));

    // Recorrido (polilínea) + señal viajera
    const path = [QIN, AG, TOOL, KB, AG, CLAUDE, AG, AOUT];
    const lp = [];
    for (let i = 0; i < path.length - 1; i++)
      lp.push(path[i].x, path[i].y, path[i].z, path[i + 1].x, path[i + 1].y, path[i + 1].z);
    const lg = new THREE.BufferGeometry();
    lg.setAttribute("position", new THREE.Float32BufferAttribute(lp, 3));
    scene.add(new THREE.LineSegments(lg,
      new THREE.LineBasicMaterial({ color: 0x33415a, transparent: true, opacity: 0.55 })));
    const sig = new THREE.Mesh(new THREE.SphereGeometry(2.3, 16, 16),
      new THREE.MeshBasicMaterial({ color: WHITE }));
    scene.add(sig);

    const label = (text, color) => {
      const d = document.createElement("div");
      d.className = "vlabel"; d.textContent = text; d.style.color = color;
      host.appendChild(d); return d;
    };
    const labels = [
      { el: label("Pregunta", "#e8eef6"), v: QIN.clone().add(V(0, 7, 0)) },
      { el: label("Agente", "#38e0c6"), v: AG.clone().add(V(0, 13, 0)) },
      { el: label("tool: ask_kb", "#7c9cf5"), v: TOOL.clone().add(V(0, 7, 0)) },
      { el: label("Knowledge Base", "#38e0c6"), v: KB.clone().add(V(0, 9, 0)) },
      { el: label("Claude", "#b088f9"), v: CLAUDE.clone().add(V(0, -8, 0)) },
      { el: label("Respuesta + citas", "#e8eef6"), v: AOUT.clone().add(V(0, 7, 0)) },
    ];

    function resize() {
      renderer.setSize(W(), H(), false);
      camera.aspect = W() / H(); camera.updateProjectionMatrix();
    }
    resize();
    window.addEventListener("resize", resize);
    if (window.ResizeObserver) new ResizeObserver(resize).observe(host);
    let mx = 0, my = 0;
    host.addEventListener("mousemove", (e) => {
      const r = host.getBoundingClientRect();
      mx = (e.clientX - r.left) / r.width - 0.5; my = (e.clientY - r.top) / r.height - 0.5;
    });

    const SEG = path.length - 1, CYCLE = 9000;
    const tmp = new THREE.Vector3(), spos = new THREE.Vector3();
    const pulse = (obj, c) => obj.scale.setScalar(1 + 0.8 * Math.exp(-(spos.distanceToSquared(c)) / 130));

    function frame(now) {
      agWire.rotation.y = now * 0.0006; agWire.rotation.x = now * 0.0003;
      const f = ((now % CYCLE) / CYCLE) * SEG;
      let i = Math.min(Math.floor(f), SEG - 1);
      const lt = f - i, e = lt * lt * (3 - 2 * lt);
      spos.copy(path[i]).lerp(path[i + 1], e);
      sig.position.copy(spos);
      sig.material.color.setHex(i >= 3 ? TEAL : WHITE);   // tras el KB, viaja el contexto (teal)
      pulse(ag, AG); pulse(tool, TOOL); pulse(claude, CLAUDE);
      kbMat.size = 1.3 + 1.8 * Math.exp(-(spos.distanceToSquared(KB)) / 130);

      camera.position.x += (mx * 14 - camera.position.x) * 0.05;
      camera.position.y += (-my * 10 - camera.position.y) * 0.05;
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);

      const w = W(), h = H();
      labels.forEach((L) => {
        tmp.copy(L.v).project(camera);
        L.el.style.left = (tmp.x * 0.5 + 0.5) * w + "px";
        L.el.style.top = (-tmp.y * 0.5 + 0.5) * h + "px";
      });
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function check() {
    const s = window.Reveal && Reveal.getCurrentSlide();
    if (s && s.querySelector("#agent3d")) init();
  }
  if (window.Reveal) {
    Reveal.on("ready", check);
    Reveal.on("slidechanged", check);
  }
})();
