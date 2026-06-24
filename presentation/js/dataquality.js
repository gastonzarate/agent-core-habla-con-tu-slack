// Calidad de datos en 3D (three.js): los mismos mensajes, crudos (dispersos)
// vs preprocesados (agrupados). En loop, con una pregunta que cambia de comportamiento.
(function () {
  let inited = false;
  const PAL = [0x38e0c6, 0x7c9cf5, 0xff6b6b, 0xffd166, 0xb088f9];
  const gauss = () => (Math.random() + Math.random() + Math.random() - 1.5);

  function init() {
    if (inited) return;
    const host = document.getElementById("dq3d");
    if (!host || !window.THREE) return;
    inited = true;
    const THREE = window.THREE;
    const W = () => host.clientWidth || 800, H = () => host.clientHeight || 440;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    host.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 1000);
    camera.position.set(0, 0, 86);
    const group = new THREE.Group();
    scene.add(group);

    const N = 240, K = 5;
    const centers = [];
    for (let k = 0; k < K; k++) {
      const a = (k / K) * 6.283;
      centers.push(new THREE.Vector3(Math.cos(a) * 26, Math.sin(a) * 15, (gauss()) * 8));
    }
    const DIM = new THREE.Color(0x5b6b82), tmpC = new THREE.Color();
    const raw = new Float32Array(N * 3), clean = new Float32Array(N * 3);
    const col = new Float32Array(N * 3), cluster = new Int8Array(N);
    const clusterColors = centers.map((_, k) => new THREE.Color(PAL[k % PAL.length]));
    for (let i = 0; i < N; i++) {
      raw[i * 3] = (Math.random() - 0.5) * 92;
      raw[i * 3 + 1] = (Math.random() - 0.5) * 34;
      raw[i * 3 + 2] = (Math.random() - 0.5) * 30;
      const k = i % K; cluster[i] = k;
      clean[i * 3] = centers[k].x + gauss() * 4;
      clean[i * 3 + 1] = centers[k].y + gauss() * 4;
      clean[i * 3 + 2] = centers[k].z + gauss() * 4;
    }
    const pos = new Float32Array(N * 3);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
    group.add(new THREE.Points(geo, new THREE.PointsMaterial({
      size: 1.8, vertexColors: true, transparent: true, opacity: 0.95,
      blending: THREE.AdditiveBlending, depthWrite: false,
    })));

    // Pregunta + líneas a "los 6 más parecidos por contenido" (cluster 0)
    const targets = [];
    for (let i = 0; i < N && targets.length < 6; i++) if (cluster[i] === 0) targets.push(i);
    const rawQ = new THREE.Vector3(-34, 11, 9), cleanQ = centers[0].clone().add(new THREE.Vector3(5, 4, 0));
    const qGeo = new THREE.BufferGeometry();
    qGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(3), 3));
    const qMat = new THREE.PointsMaterial({ color: 0xffffff, size: 6, transparent: true, depthWrite: false });
    group.add(new THREE.Points(qGeo, qMat));
    const lpos = new Float32Array(targets.length * 6);
    const lGeo = new THREE.BufferGeometry();
    lGeo.setAttribute("position", new THREE.BufferAttribute(lpos, 3));
    const lines = new THREE.LineSegments(lGeo,
      new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.4 }));
    group.add(lines);

    // Etiqueta de estado (HTML)
    const state = document.createElement("div");
    state.className = "dq-state";
    host.appendChild(state);

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

    const CYCLE = 7000, smooth = (x) => x * x * (3 - 2 * x);
    const qx = new THREE.Vector3();
    function frame(now) {
      const u = (now % CYCLE) / CYCLE;
      let t;
      if (u < 0.30) t = 0;
      else if (u < 0.45) t = smooth((u - 0.30) / 0.15);
      else if (u < 0.80) t = 1;
      else if (u < 0.95) t = 1 - smooth((u - 0.80) / 0.15);
      else t = 0;

      group.rotation.y = now * 0.00022;
      for (let i = 0; i < N; i++) {
        pos[i * 3] = raw[i * 3] + (clean[i * 3] - raw[i * 3]) * t;
        pos[i * 3 + 1] = raw[i * 3 + 1] + (clean[i * 3 + 1] - raw[i * 3 + 1]) * t;
        pos[i * 3 + 2] = raw[i * 3 + 2] + (clean[i * 3 + 2] - raw[i * 3 + 2]) * t;
        tmpC.copy(DIM).lerp(clusterColors[cluster[i]], t);
        col[i * 3] = tmpC.r; col[i * 3 + 1] = tmpC.g; col[i * 3 + 2] = tmpC.b;
      }
      geo.attributes.position.needsUpdate = true;
      geo.attributes.color.needsUpdate = true;

      qx.copy(rawQ).lerp(cleanQ, t);
      qGeo.attributes.position.setXYZ(0, qx.x, qx.y, qx.z);
      qGeo.attributes.position.needsUpdate = true;
      targets.forEach((idx, j) => {
        lpos[j * 6] = qx.x; lpos[j * 6 + 1] = qx.y; lpos[j * 6 + 2] = qx.z;
        lpos[j * 6 + 3] = pos[idx * 3]; lpos[j * 6 + 4] = pos[idx * 3 + 1]; lpos[j * 6 + 5] = pos[idx * 3 + 2];
      });
      lGeo.attributes.position.needsUpdate = true;
      lines.material.color.setHex(t < 0.5 ? 0xff6b6b : 0x38e0c6);
      lines.material.opacity = 0.25 + t * 0.3;

      if (t < 0.5) { state.textContent = "❌ crudo · disperso → trae cualquier cosa"; state.style.color = "#ff6b6b"; }
      else { state.textContent = "✅ preprocesado · agrupado → trae lo relevante"; state.style.color = "#38e0c6"; }

      camera.position.x += (mx * 16 - camera.position.x) * 0.05;
      camera.position.y += (-my * 12 - camera.position.y) * 0.05;
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  function check() {
    const s = window.Reveal && Reveal.getCurrentSlide();
    if (s && s.querySelector("#dq3d")) init();
  }
  if (window.Reveal) { Reveal.on("ready", check); Reveal.on("slidechanged", check); }
})();
