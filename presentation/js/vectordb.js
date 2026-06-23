// Visualización 3D de una base vectorial (three.js).
// Muestra mensajes agrupados por tema (clusters) y una "consulta" que se
// conecta con sus vecinos más cercanos = cómo funciona el retrieval.
(function () {
  let inited = false;

  function gauss() {
    return (Math.random() + Math.random() + Math.random() - 1.5) * 2;
  }

  function init() {
    if (inited) return;
    const host = document.getElementById("vectordb");
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
    camera.position.set(0, 0, 92);
    const group = new THREE.Group();
    scene.add(group);

    const clusters = [
      { name: "Deploys", color: 0x38e0c6, c: [-30, 15, 2] },
      { name: "Bugs / staging", color: 0xff6b6b, c: [28, 17, -8] },
      { name: "Clientes", color: 0x7c9cf5, c: [26, -19, 10] },
      { name: "RRHH / onboarding", color: 0xffd166, c: [-27, -17, -6] },
      { name: "Decisiones", color: 0xb088f9, c: [0, 1, 24] },
    ];

    clusters.forEach((cl) => {
      const N = 45;
      const pos = new Float32Array(N * 3);
      for (let i = 0; i < N; i++) {
        pos[i * 3] = cl.c[0] + gauss() * 3.5;
        pos[i * 3 + 1] = cl.c[1] + gauss() * 3.5;
        pos[i * 3 + 2] = cl.c[2] + gauss() * 3.5;
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      const m = new THREE.PointsMaterial({
        color: cl.color, size: 1.7, transparent: true, opacity: 0.9,
        blending: THREE.AdditiveBlending, depthWrite: false,
      });
      group.add(new THREE.Points(g, m));
      cl.pos = pos;
    });

    // La consulta: cae cerca del cluster "Bugs / staging"
    const qc = clusters[1];
    const qv = new THREE.Vector3(qc.c[0] - 6, qc.c[1] - 4, qc.c[2] + 3);
    const qGeo = new THREE.BufferGeometry();
    qGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array([qv.x, qv.y, qv.z]), 3));
    const qMat = new THREE.PointsMaterial({ color: 0xffffff, size: 5, transparent: true, depthWrite: false });
    group.add(new THREE.Points(qGeo, qMat));

    // Líneas de la consulta a sus k vecinos más cercanos
    const lp = [];
    for (let i = 0; i < 6; i++) {
      lp.push(qv.x, qv.y, qv.z, qc.pos[i * 3], qc.pos[i * 3 + 1], qc.pos[i * 3 + 2]);
    }
    const lGeo = new THREE.BufferGeometry();
    lGeo.setAttribute("position", new THREE.Float32BufferAttribute(lp, 3));
    const lines = new THREE.LineSegments(lGeo, new THREE.LineBasicMaterial({
      color: 0xffffff, transparent: true, opacity: 0.5,
    }));
    group.add(lines);

    // Etiquetas HTML (proyectadas cada frame)
    const labels = clusters.map((cl) => {
      const el = document.createElement("div");
      el.className = "vlabel";
      el.textContent = cl.name;
      el.style.color = "#" + cl.color.toString(16).padStart(6, "0");
      host.appendChild(el);
      return { el, v: new THREE.Vector3(cl.c[0], cl.c[1], cl.c[2]) };
    });
    const qEl = document.createElement("div");
    qEl.className = "vlabel vquery";
    qEl.textContent = "“¿qué pasó con el error en staging?”";
    host.appendChild(qEl);
    labels.push({ el: qEl, v: qv });

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
    function frame(t) {
      group.rotation.y = t * 0.00018;
      camera.position.x += (mx * 34 - camera.position.x) * 0.05;
      camera.position.y += (-my * 22 - camera.position.y) * 0.05;
      camera.lookAt(0, 0, 0);
      group.updateMatrixWorld();
      const pulse = 0.5 + Math.sin(t * 0.005) * 0.5;
      qMat.size = 4 + pulse * 2.5;
      lines.material.opacity = 0.3 + pulse * 0.35;
      renderer.render(scene, camera);

      const w = W(), h = H();
      labels.forEach((L) => {
        tmp.copy(L.v).applyMatrix4(group.matrixWorld).project(camera);
        if (tmp.z > 1) { L.el.style.display = "none"; return; }
        L.el.style.display = "block";
        L.el.style.left = (tmp.x * 0.5 + 0.5) * w + "px";
        L.el.style.top = (-tmp.y * 0.5 + 0.5) * h + "px";
      });
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function check() {
    const s = window.Reveal && Reveal.getCurrentSlide();
    if (s && s.querySelector("#vectordb")) init();
  }
  if (window.Reveal) {
    Reveal.on("ready", check);
    Reveal.on("slidechanged", check);
  }
})();
