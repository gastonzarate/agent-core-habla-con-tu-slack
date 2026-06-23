// Pipeline 3D del Knowledge Base (three.js).
// Documento → flujo de partículas (chunks→embeddings) → nube de vectores (índice).
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
    camera.position.set(0, 2, 72);

    // --- Documento (izquierda) ---
    const doc = new THREE.Group();
    doc.position.set(-42, 0, 0);
    scene.add(doc);
    doc.add(new THREE.Mesh(new THREE.BoxGeometry(16, 21, 0.6),
      new THREE.MeshBasicMaterial({ color: 0x14283c })));
    doc.add(new THREE.Mesh(new THREE.BoxGeometry(16, 21, 0.6),
      new THREE.MeshBasicMaterial({ color: 0x7c9cf5, wireframe: true, transparent: true, opacity: 0.5 })));
    for (let i = 0; i < 6; i++) {
      const ln = new THREE.Mesh(new THREE.BoxGeometry(11, 0.7, 0.7),
        new THREE.MeshBasicMaterial({ color: 0x9fb4d4, transparent: true, opacity: 0.55 }));
      ln.position.set(-1.5, 7 - i * 2.6, 0.4);
      doc.add(ln);
    }

    // --- Índice (derecha): nube de vectores ---
    const idx = new THREE.Group();
    idx.position.set(34, 0, 0);
    scene.add(idx);
    const IN = 260;
    const ip = new Float32Array(IN * 3);
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

    // --- Flujo de partículas: chunks → embeddings ---
    const M = 150, startX = -34, endX = 34;
    const fp = new Float32Array(M * 3), fc = new Float32Array(M * 3);
    const t = new Float32Array(M), spd = new Float32Array(M);
    const sy = new Float32Array(M), sz = new Float32Array(M);
    const ey = new Float32Array(M), ez = new Float32Array(M), sgn = new Float32Array(M);
    const WHITE = new THREE.Color(0xffffff), TEAL = new THREE.Color(0x38e0c6), C = new THREE.Color();
    function reset(i, t0) {
      t[i] = t0;
      spd[i] = 0.0026 + Math.random() * 0.004;
      sy[i] = (Math.random() - 0.5) * 7; sz[i] = (Math.random() - 0.5) * 7;
      ey[i] = (Math.random() - 0.5) * 20; ez[i] = (Math.random() - 0.5) * 20;
      sgn[i] = Math.random() > 0.5 ? 1 : -1;
    }
    for (let i = 0; i < M; i++) reset(i, Math.random());
    const fg = new THREE.BufferGeometry();
    fg.setAttribute("position", new THREE.BufferAttribute(fp, 3));
    fg.setAttribute("color", new THREE.BufferAttribute(fc, 3));
    const flow = new THREE.Points(fg, new THREE.PointsMaterial({
      size: 2.6, vertexColors: true, transparent: true, opacity: 0.95,
      blending: THREE.AdditiveBlending, depthWrite: false,
    }));
    scene.add(flow);

    // --- Etiquetas ---
    function label(text, color) {
      const d = document.createElement("div");
      d.className = "vlabel";
      d.textContent = text;
      d.style.color = color;
      host.appendChild(d);
      return d;
    }
    const labels = [
      { el: label("Documento", "#9fb4d4"), v: new THREE.Vector3(-42, 13, 0) },
      { el: label("chunking → embeddings", "#e8eef6"), v: new THREE.Vector3(0, 13, 0) },
      { el: label("S3 Vectors · índice", "#38e0c6"), v: new THREE.Vector3(34, 14, 0) },
    ];

    function resize() {
      renderer.setSize(W(), H(), false);
      camera.aspect = W() / H();
      camera.updateProjectionMatrix();
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

    const tmp = new THREE.Vector3();
    function frame(now) {
      doc.position.y = Math.sin(now * 0.0015) * 1.2;
      doc.rotation.y = Math.sin(now * 0.0008) * 0.15;
      idx.rotation.y = now * 0.0004;
      idx.rotation.x = now * 0.00018;

      for (let i = 0; i < M; i++) {
        t[i] += spd[i];
        if (t[i] >= 1) reset(i, 0);
        const tt = t[i], e = tt * tt * (3 - 2 * tt);
        fp[i * 3] = startX + (endX - startX) * e;
        fp[i * 3 + 1] = sy[i] + (ey[i] - sy[i]) * e + Math.sin(tt * Math.PI) * 6 * sgn[i];
        fp[i * 3 + 2] = sz[i] + (ez[i] - sz[i]) * e;
        C.copy(WHITE).lerp(TEAL, Math.min(1, e * 1.4));
        fc[i * 3] = C.r; fc[i * 3 + 1] = C.g; fc[i * 3 + 2] = C.b;
      }
      fg.attributes.position.needsUpdate = true;
      fg.attributes.color.needsUpdate = true;

      camera.position.x += (mx * 16 - camera.position.x) * 0.05;
      camera.position.y += (2 - my * 12 - camera.position.y) * 0.05;
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
