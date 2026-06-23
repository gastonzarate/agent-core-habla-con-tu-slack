// Pipeline 3D del Knowledge Base (three.js), en loop:
// documento entero → se parte en chunks → cada chunk vuela al índice → reinicia.
(function () {
  let inited = false;

  function init() {
    if (inited) return;
    const host = document.getElementById("kbpipeline");
    if (!host || !window.THREE) return;
    inited = true;
    const THREE = window.THREE;
    const W = () => host.clientWidth || 800;
    const H = () => host.clientHeight || 440;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    host.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 1000);
    camera.position.set(0, 2, 74);

    const DOC_X = -38, CLOUD_X = 34, K = 6;
    const BASE = new THREE.Color(0x2f5680), TEAL = new THREE.Color(0x38e0c6);
    const EDGE = new THREE.Color(0x9fb4d4);

    // --- Índice (derecha): nube de vectores ---
    const idx = new THREE.Group();
    idx.position.set(CLOUD_X, 0, 0);
    scene.add(idx);
    const IN = 260, ip = new Float32Array(IN * 3);
    for (let i = 0; i < IN; i++) {
      const r = 11 * Math.cbrt(Math.random());
      const th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
      ip[i * 3] = r * Math.sin(ph) * Math.cos(th);
      ip[i * 3 + 1] = r * Math.sin(ph) * Math.sin(th);
      ip[i * 3 + 2] = r * Math.cos(ph);
    }
    const ig = new THREE.BufferGeometry();
    ig.setAttribute("position", new THREE.BufferAttribute(ip, 3));
    idx.add(new THREE.Points(ig, new THREE.PointsMaterial({
      color: 0x38e0c6, size: 1.4, transparent: true, opacity: 0.9,
      blending: THREE.AdditiveBlending, depthWrite: false,
    })));

    // --- Chunks: K piezas que juntas forman el documento ---
    const chunks = [];
    for (let i = 0; i < K; i++) {
      const g = new THREE.Group();
      const fill = new THREE.Mesh(new THREE.BoxGeometry(15, 2.4, 0.6),
        new THREE.MeshBasicMaterial({ color: BASE.clone(), transparent: true }));
      const wire = new THREE.Mesh(new THREE.BoxGeometry(15.2, 2.6, 0.7),
        new THREE.MeshBasicMaterial({ color: EDGE.clone(), wireframe: true, transparent: true }));
      g.add(fill, wire);
      scene.add(g);
      const r = 8 * Math.cbrt(Math.random());
      const th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
      chunks.push({
        g, fill, wire,
        slotY: 7 - i * 2.8,                                  // posición apilada (forma el doc)
        target: new THREE.Vector3(                            // destino dentro de la nube
          CLOUD_X + r * Math.sin(ph) * Math.cos(th),
          r * Math.sin(ph) * Math.sin(th),
          r * Math.cos(ph)),
        start: 0.20 + i * 0.055,                              // arranque escalonado
      });
    }

    // --- Etiquetas ---
    function label(text, color) {
      const d = document.createElement("div");
      d.className = "vlabel"; d.textContent = text; d.style.color = color;
      host.appendChild(d); return d;
    }
    const labels = [
      { el: label("Documento", "#9fb4d4"), v: new THREE.Vector3(DOC_X, 12, 0) },
      { el: label("se parte en chunks", "#e8eef6"), v: new THREE.Vector3(-4, 13, 0) },
      { el: label("S3 Vectors · índice", "#38e0c6"), v: new THREE.Vector3(CLOUD_X, 14, 0) },
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
      mx = (e.clientX - r.left) / r.width - 0.5;
      my = (e.clientY - r.top) / r.height - 0.5;
    });

    const CYCLE = 7000, TDUR = 0.42, REFORM = 0.9;
    const smooth = (x) => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
    const tmp = new THREE.Vector3();

    function frame(now) {
      const u = (now % CYCLE) / CYCLE;
      idx.rotation.y = now * 0.0004;
      idx.rotation.x = now * 0.00018;

      chunks.forEach((c) => {
        let x, y, z, scl, op, mix;
        if (u >= REFORM) {                       // se rearma el documento (fade-in)
          op = (u - REFORM) / (1 - REFORM);
          x = DOC_X; y = c.slotY; z = 0; scl = 1; mix = 0;
        } else if (u < c.start) {                // documento entero, en espera
          op = 1; x = DOC_X; y = c.slotY; z = 0; scl = 1; mix = 0;
        } else {                                 // viaja al índice
          const p = smooth((u - c.start) / TDUR);
          x = DOC_X + (c.target.x - DOC_X) * p;
          y = c.slotY + (c.target.y - c.slotY) * p;
          z = c.target.z * p + Math.sin(p * Math.PI) * 9;
          scl = 1 - 0.82 * p;
          mix = Math.min(1, p * 1.3);
          op = p < 0.82 ? 1 : Math.max(0, 1 - (p - 0.82) / 0.18);
        }
        c.g.position.set(x, y, z);
        c.g.scale.setScalar(scl);
        c.g.rotation.z = mix * 0.6;
        c.fill.material.color.copy(BASE).lerp(TEAL, mix);
        c.fill.material.opacity = op;
        c.wire.material.color.copy(EDGE).lerp(TEAL, mix);
        c.wire.material.opacity = op * 0.6;
      });

      camera.position.x += (mx * 14 - camera.position.x) * 0.05;
      camera.position.y += (2 - my * 10 - camera.position.y) * 0.05;
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
    if (s && s.querySelector("#kbpipeline")) init();
  }
  if (window.Reveal) {
    Reveal.on("ready", check);
    Reveal.on("slidechanged", check);
  }
})();
