// Loop del agente (animado): revela el transcript paso a paso y resalta la etapa
// del ciclo (Razona → Llama tool → Observa → repite → Responde).
(function () {
  let started = false;

  function run(host) {
    const chips = Array.from(host.querySelectorAll(".al-chip"));
    const lines = Array.from(host.querySelectorAll(".al-line"));
    const chipFor = (st) => chips.find((c) => c.dataset.st === st);
    const stageOf = (line) =>
      line.classList.contains("t-think") ? "think" :
      line.classList.contains("t-act") ? "act" :
      line.classList.contains("t-observe") ? "observe" : "answer";

    let i = 0;
    function step() {
      if (i === 0) {
        lines.forEach((l) => l.classList.remove("show"));
        chips.forEach((c) => c.classList.remove("active"));
      }
      if (i < lines.length) {
        const line = lines[i];
        line.classList.add("show");
        chips.forEach((c) => c.classList.remove("active"));
        const ch = chipFor(stageOf(line));
        if (ch) ch.classList.add("active");
        i += 1;
        setTimeout(step, 1300);
      } else {
        setTimeout(() => { i = 0; step(); }, 2400);  // pausa y vuelve a empezar
      }
    }
    step();
  }

  function check() {
    const s = window.Reveal && Reveal.getCurrentSlide();
    const host = s && s.querySelector("#agentloop");
    if (host && !started) { started = true; run(host); }
  }
  if (window.Reveal) { Reveal.on("ready", check); Reveal.on("slidechanged", check); }
})();
