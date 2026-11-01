(() => {
  const root = document.documentElement, picker = document.querySelector(".picker"), button = picker.firstElementChild,
    menu = button.nextElementSibling, items = [...menu.children], light = matchMedia("(prefers-color-scheme: light)");
  // Until a theme is chosen, Aurora or Aurora light follows the system scheme.
  const current = () => root.dataset.theme || (light.matches ? "aurora-light" : "aurora");
  const mark = () => {
    for (const item of items) item.setAttribute("aria-checked", item.dataset.theme === current());
    wake();
  };
  const show = open => {
    menu.hidden = !open;
    button.setAttribute("aria-expanded", open);
    if (open) menu.querySelector("[aria-checked=true]").focus();
  };
  if (!items.some(i => i.dataset.theme === root.dataset.theme)) delete root.dataset.theme;
  button.onclick = () => show(menu.hidden);
  button.onkeydown = e => { if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); show(true); } };
  menu.onclick = e => {
    const item = e.target.closest("button");
    if (!item) return;
    root.dataset.theme = item.dataset.theme;
    try { localStorage.setItem("theme", item.dataset.theme); } catch {}
    mark();
    show(false);
    button.focus();
  };
  menu.onkeydown = e => {
    const keys = { ArrowDown: 1, ArrowUp: -1, Home: -99, End: 99 }, n = items.length;
    if (e.key === "Escape") { show(false); button.focus(); }
    else if (e.key === "Tab") show(false);
    else if (e.key in keys) {
      e.preventDefault();
      const step = keys[e.key], at = items.indexOf(document.activeElement);
      items[Math.abs(step) > 1 ? (step < 0 ? 0 : n - 1) : (at + step + n) % n].focus();
    }
  };
  document.addEventListener("click", e => { if (!menu.hidden && !picker.contains(e.target)) show(false); });

  // Motion rests after a minute without input: the backdrop effect holds its last frame.
  let seen = performance.now();
  for (const type of ["pointermove", "keydown", "scroll", "touchstart"])
    addEventListener(type, () => { seen = performance.now(); wake(); }, { passive: true });

  // Stars and Comets: MaiCord's fx_builtin (src/render/shaders/background_fx.hlsl) at the
  // client's default speed, density and strength, in CSS pixels where the client uses DIPs.
  // At most 30 fps; none for reduced motion; without WebGL 2 the CSS stars stay.
  const sky = document.querySelector(".sky"), canvas = document.createElement("canvas");
  let gl = !matchMedia("(prefers-reduced-motion: reduce)").matches &&
    canvas.getContext("webgl2", { antialias: false, depth: false, stencil: false, powerPreference: "low-power" });
  let draw, pending = false, dark = 1;
  if (gl) {
    const program = gl.createProgram();
    for (const [type, source] of [[gl.VERTEX_SHADER, `#version 300 es
void main() { gl_Position = vec4(vec2(gl_VertexID & 1, gl_VertexID >> 1) * 4. - 1., 0, 1); }`],
      [gl.FRAGMENT_SHADER, `#version 300 es
precision highp float;
uniform float time, dark;
uniform vec3 view, settings;
out vec4 color;
float hash(vec2 cell) {
  vec3 p = fract(vec3(cell.xyx) * .1031);
  p += dot(p, p.yzx + 33.33);
  return fract((p.x + p.y) * p.z);
}
void main() {
  float speed = settings.x, density = settings.y, strength = settings.z, t = time * speed, detail = 0.;
  vec2 extent = view.xy / view.z, coordinate = vec2(gl_FragCoord.x, view.y - gl_FragCoord.y) / view.z;
  float pitch = mix(180., 48., density);
  vec2 cell = floor(coordinate / pitch);
  float seed = hash(cell);
  vec2 center = (cell + vec2(.15 + seed * .7, .15 + hash(cell + 13.) * .7)) * pitch;
  float distance = length(coordinate - center);
  float star = clamp((1.1 + seed * .8 - distance) / max(fwidth(distance), .5), 0., 1.) +
               exp2(-distance * distance * .14) * .12;
  float clock = t / (2.5 + seed * 5.) + seed * 11., window = floor(clock), progress = fract(clock);
  float pulseSeed = hash(cell + vec2(window * 17.1, window * .7));
  float offset = (progress - (.2 + pulseSeed * .6)) / (.08 + hash(cell + window + 29.) * .12);
  float pulse = exp2(-offset * offset * 4.) * smoothstep(0., .08, progress) * (1. - smoothstep(.92, 1., progress));
  detail += star * (.07 + pulse * .93);
  int lanes = clamp(int(ceil(density * 4.)), 1, 4);
  for (int lane = 0; lane < lanes; ++lane) {
    float laneSeed = hash(vec2(37. + float(lane), 19.));
    float laneClock = t / (7. + laneSeed * 8.) + .16 + laneSeed * .45;
    float laneWindow = floor(laneClock), cycle = fract(laneClock);
    float eventSeed = hash(vec2(float(lane) + 71., laneWindow + 53.));
    float slope = (eventSeed < .5 ? -1. : 1.) * (.18 + hash(vec2(float(lane) + 17., laneWindow + 91.)) * .24);
    vec2 path = vec2((extent.y + 96.) * slope, extent.y + 96.), axis = normalize(path);
    vec2 delta = coordinate - vec2(extent.x * (.225 + eventSeed * .55) - path.x * .5, -48.) - path * cycle;
    float along = dot(delta, axis), across = dot(delta, vec2(-axis.y, axis.x));
    float tail = clamp(1. + along / 36., 0., 1.) * step(along, 0.) * exp2(-across * across * .7);
    float head = exp2(-dot(delta, delta) * .5);
    float fade = smoothstep(.03, .13, cycle) * (1. - smoothstep(.82, .96, cycle));
    detail += (tail * .8 + head) * fade;
  }
  // Additive light ink on dark themes, a lerp toward dark ink on light ones.
  float amount = min(clamp(detail, 0., 1.) * strength * .38, .42);
  color = dark > .5 ? vec4(vec3(.82, .9, 1.) * amount, 0.) : vec4(vec3(.1, .18, .3) * amount, amount);
}`]]) {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      gl.attachShader(program, shader);
    }
    gl.linkProgram(program);
    if (gl.getProgramParameter(program, gl.LINK_STATUS)) {
      gl.useProgram(program);
      const uniform = name => gl.getUniformLocation(program, name), time = uniform("time"), view = uniform("view"),
        ink = uniform("dark");
      // The hero screenshot's settings (showcase probe): speed 80, density 80, strength 100.
      gl.uniform3f(uniform("settings"), .8, .8, 1);
      draw = () => {
        const scale = Math.min(devicePixelRatio, 2), width = Math.round(sky.clientWidth * scale),
          height = Math.round(sky.clientHeight * scale);
        if (canvas.width !== width || canvas.height !== height) {
          canvas.width = width;
          canvas.height = height;
          gl.viewport(0, 0, width, height);
        }
        gl.uniform3f(view, width, height, scale);
        gl.uniform1f(ink, dark);
        gl.uniform1f(time, performance.now() / 1000);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      };
      canvas.addEventListener("webglcontextlost", () => { gl = null; canvas.remove(); root.classList.remove("fx"); });
      sky.append(canvas);
      root.classList.add("fx");
    } else gl = null;
  }
  const tick = () => {
    pending = gl && !document.hidden && !/^(dark|light)$/.test(current()) && performance.now() - seen < 60000;
    if (!pending) return;
    draw();
    setTimeout(() => requestAnimationFrame(tick), 1000 / 30);
  };
  function wake() {
    dark = getComputedStyle(root).colorScheme === "light" ? 0 : 1;
    if (!pending) {
      pending = true;
      requestAnimationFrame(tick);
    }
  }
  document.addEventListener("visibilitychange", wake);
  light.addEventListener("change", mark);
  mark();
  picker.hidden = false;
})();
