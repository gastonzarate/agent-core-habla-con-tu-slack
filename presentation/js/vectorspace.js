// Nube de vectores 3D (three.js) — fondo ambiente del hero.
// Representa "mensajes embebidos" en el espacio vectorial.
(function () {
  if (!window.THREE) return;
  const canvas = document.getElementById("bg-canvas");
  if (!canvas) return;

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 1000);
  camera.position.z = 60;

  // Puntos = vectores
  const N = 1400;
  const positions = new Float32Array(N * 3);
  const R = 46;
  for (let i = 0; i < N; i++) {
    // distribución en una esfera difusa
    const r = R * Math.cbrt(Math.random());
    const t = Math.random() * Math.PI * 2;
    const p = Math.acos(2 * Math.random() - 1);
    positions[i * 3] = r * Math.sin(p) * Math.cos(t);
    positions[i * 3 + 1] = r * Math.sin(p) * Math.sin(t);
    positions[i * 3 + 2] = r * Math.cos(p);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const mat = new THREE.PointsMaterial({
    color: 0x38e0c6, size: 0.55, transparent: true, opacity: 0.85,
    blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const points = new THREE.Points(geo, mat);
  scene.add(points);

  // Algunas líneas tenues entre vecinos (sensación de grafo)
  const linePos = [];
  for (let i = 0; i < 90; i++) {
    const a = (Math.random() * N) | 0;
    const b = (Math.random() * N) | 0;
    linePos.push(positions[a*3], positions[a*3+1], positions[a*3+2],
                 positions[b*3], positions[b*3+1], positions[b*3+2]);
  }
  const lgeo = new THREE.BufferGeometry();
  lgeo.setAttribute("position", new THREE.Float32BufferAttribute(linePos, 3));
  const lines = new THREE.LineSegments(lgeo,
    new THREE.LineBasicMaterial({ color: 0x7c9cf5, transparent: true, opacity: 0.12 }));
  scene.add(lines);

  let mx = 0, my = 0;
  window.addEventListener("mousemove", (e) => {
    mx = (e.clientX / window.innerWidth - 0.5);
    my = (e.clientY / window.innerHeight - 0.5);
  });

  function resize() {
    const w = window.innerWidth, h = window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize); resize();

  function tick(t) {
    points.rotation.y = lines.rotation.y = t * 0.00006;
    points.rotation.x = lines.rotation.x = t * 0.00003;
    camera.position.x += (mx * 14 - camera.position.x) * 0.04;
    camera.position.y += (-my * 10 - camera.position.y) * 0.04;
    camera.lookAt(0, 0, 0);
    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  // Atenuar el fondo fuera del hero (slide 0)
  if (window.Reveal) {
    const setDim = () => {
      const i = Reveal.getIndices().h;
      canvas.style.transition = "opacity .6s";
      canvas.style.opacity = i === 0 ? "1" : "0.28";
    };
    Reveal.on("ready", setDim);
    Reveal.on("slidechanged", setDim);
  }
})();
