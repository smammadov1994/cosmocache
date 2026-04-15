// cosmocache dashboard — v4 spacetime-warp scene.
//
// One WebGL scene renders the cosmos:
//   - Enigma: a warped grid (spacetime fabric) that dips into a gravity well
//     at the origin. A dark disc + thin violet ring mark the hole's mouth.
//   - Planets: procedural-texture spheres on elliptical orbits above the grid.
//     Orbit radii and speeds scale with planet count (Kepler-ish falloff).
//   - Stars: sparse point cloud backdrop.
//   - Mild bloom via UnrealBloomPass so the ring + brightest stars glow.
//
// All chrome (top bar, hint, labels, panel) is HTML overlay, positioned from
// worldToScreen() each frame so labels stay pixel-crisp.
//
// Interaction model:
//   - click-vs-drag is measured: pointerdown records {x,y,t}; pointermove
//     promotes to drag after 5px; pointerup without drag AND <300ms dispatches
//     a raycast pick. Prevents the v2 "drag eats click" bug.
//   - scroll = dolly zoom toward cursor.
//   - click a planet -> tween camera to orbit that planet.
//   - click a creature label -> open side panel.
//   - ESC or background click -> return to universe view.

import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

/* ------------------------------------------------------------------ */
/*  PALETTE — Claude (copper / clay / sage / amber on warm near-black) */
/* ------------------------------------------------------------------ */
const PALETTE = {
  sceneBg:     new THREE.Color("#140e09"),  // warm near-black space
  violet:      new THREE.Color("#d97757"),  // copper — primary accent
  violetLilac: new THREE.Color("#e8a98a"),  // rosé copper — core highlight
  hotWhite:    new THREE.Color("#fff0e0"),  // warm white
  coral:       new THREE.Color("#c15f3c"),  // deep clay
  moss:        new THREE.Color("#8c9a6f"),  // warm sage
  gold:        new THREE.Color("#c8945a"),  // amber
};

// Planet palette — cycles by index so any planet count lands in-palette.
// Data-provided layout.color is ignored in favor of this so the scene
// stays cohesive as planets are birthed/renamed.
const CLAUDE_PLANET_COLORS = [
  "#d97757", // copper
  "#8c9a6f", // sage
  "#bc5f41", // clay
  "#c8945a", // amber
  "#b98b7a", // mauve-clay
  "#9a8060", // taupe
];

/* ------------------------------------------------------------------ */
/*  DOM refs                                                          */
/* ------------------------------------------------------------------ */
const canvas    = document.getElementById("scene");
const labelsDiv = document.getElementById("labels");
const hintEl    = document.getElementById("hint");
const focusEl   = document.getElementById("focus");
const focusName = document.getElementById("focus-name");
const focusMeta = document.getElementById("focus-meta");
const panelEl   = document.getElementById("panel");
const panelBody = document.getElementById("panel-body");
const panelClose = document.getElementById("panel-close");
const btnExplore = document.getElementById("btn-explore");

/* ------------------------------------------------------------------ */
/*  RENDERER + SCENE + CAMERA                                         */
/* ------------------------------------------------------------------ */
const renderer = new THREE.WebGLRenderer({
  canvas, antialias: true, alpha: false, powerPreference: "high-performance",
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setClearColor(PALETTE.sceneBg, 1);
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
scene.background = PALETTE.sceneBg;

const camera = new THREE.PerspectiveCamera(45, 2, 0.1, 5000);
camera.position.set(0, 120, 360);
camera.lookAt(0, 0, 0);

/* ------------------------------------------------------------------ */
/*  STARFIELD — sparse, subtle                                        */
/* ------------------------------------------------------------------ */
function buildStarfield() {
  const N = 900;
  const pos = new Float32Array(N * 3);
  const sizes = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    // place on a large sphere shell so parallax feels right
    const r = 900 + Math.random() * 600;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    pos[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
    pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    pos[i * 3 + 2] = r * Math.cos(phi);
    sizes[i] = Math.random() < 0.08 ? 2.2 : 1.2;
  }
  const geom = new THREE.BufferGeometry();
  geom.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geom.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 } },
    vertexShader: /* glsl */`
      attribute float aSize;
      uniform float uTime;
      varying float vTwinkle;
      void main() {
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = aSize * (300.0 / max(-mv.z, 1.0));
        vTwinkle = 0.7 + 0.3 * sin(uTime * 0.9 + position.x * 0.01 + position.y * 0.013);
      }
    `,
    fragmentShader: /* glsl */`
      varying float vTwinkle;
      void main() {
        vec2 d = gl_PointCoord - 0.5;
        float r = length(d);
        if (r > 0.5) discard;
        float falloff = smoothstep(0.5, 0.0, r);
        vec3 c = mix(vec3(0.78, 0.78, 0.92), vec3(1.0), 0.4);
        gl_FragColor = vec4(c, falloff * 0.75 * vTwinkle);
      }
    `,
    transparent: true, depthWrite: false,
  });
  return new THREE.Points(geom, mat);
}
const stars = buildStarfield();
scene.add(stars);

/* ------------------------------------------------------------------ */
/*  ENIGMA — spacetime warp grid (gravity well)                       */
/* ------------------------------------------------------------------ */
// A grid of line segments that dips into a gravity well at the origin.
// Vertices are displaced downward by a 1/(1 + (r/soft)²) falloff — the
// classic spacetime-fabric look. A small dark disc + thin violet ring
// mark the mouth of the hole. No accretion disk, no photon ring — just
// the bend.

const WELL_DEPTH = 70;   // y-depth at the center of the well
const WELL_SOFT  = 110;  // softness: smaller = steeper well
const GRID_SIZE  = 520;
const GRID_DIV   = 44;
const HOLE_R     = 12;   // mouth radius at the bottom of the well

function buildSpacetimeGrid() {
  const step = GRID_SIZE / GRID_DIV;
  const half = GRID_SIZE / 2;
  const positions = [];

  // horizontal lines (constant Z)
  for (let i = 0; i <= GRID_DIV; i++) {
    const z = -half + i * step;
    for (let j = 0; j < GRID_DIV; j++) {
      positions.push(-half + j * step, 0, z, -half + (j + 1) * step, 0, z);
    }
  }
  // vertical lines (constant X)
  for (let i = 0; i <= GRID_DIV; i++) {
    const x = -half + i * step;
    for (let j = 0; j < GRID_DIV; j++) {
      positions.push(x, 0, -half + j * step, x, 0, -half + (j + 1) * step);
    }
  }

  const geom = new THREE.BufferGeometry();
  geom.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));

  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uTime:      { value: 0 },
      uDepth:     { value: WELL_DEPTH },
      uSoft:      { value: WELL_SOFT },
      uFade:      { value: half * 0.92 },
      uColor:     { value: PALETTE.violet.clone() },
      uColorCore: { value: PALETTE.violetLilac.clone() },
    },
    transparent: true,
    depthWrite: false,
    vertexShader: /* glsl */`
      uniform float uTime;
      uniform float uDepth;
      uniform float uSoft;
      varying float vR;
      varying float vK;
      void main() {
        float r = length(position.xz);
        // 1 / (1 + (r/soft)²) — classic gravity-well falloff, bounded at 1.
        float k = 1.0 / (1.0 + pow(r / uSoft, 2.0));
        float y = -uDepth * k;
        // a gentle ripple out in the flatter regions gives the fabric life
        y += sin(uTime * 0.55 + r * 0.035) * 0.7 * (1.0 - k);
        vR = r;
        vK = k;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position.x, y, position.z, 1.0);
      }
    `,
    fragmentShader: /* glsl */`
      uniform vec3 uColor;
      uniform vec3 uColorCore;
      uniform float uFade;
      varying float vR;
      varying float vK;
      void main() {
        // brighter in the well, fade to nothing at the edge of the plane
        vec3 col = mix(uColor, uColorCore, smoothstep(0.1, 0.9, vK));
        float edge = smoothstep(uFade, uFade * 0.45, vR);
        float alpha = edge * (0.22 + 0.55 * vK);
        gl_FragColor = vec4(col, alpha);
      }
    `,
  });

  return new THREE.LineSegments(geom, mat);
}

const spacetimeGrid = buildSpacetimeGrid();
scene.add(spacetimeGrid);

// Mouth of the well — a very dark disc at the bottom + a thin violet ring
// at its rim. Bloom just clips the ring. No sphere.
const enigmaHole = new THREE.Mesh(
  new THREE.CircleGeometry(HOLE_R, 64),
  new THREE.MeshBasicMaterial({ color: 0x050010 })
);
enigmaHole.rotation.x = -Math.PI / 2;
enigmaHole.position.y = -WELL_DEPTH + 0.2;
scene.add(enigmaHole);

const enigmaRing = new THREE.Mesh(
  new THREE.RingGeometry(HOLE_R * 1.0, HOLE_R * 1.12, 128),
  new THREE.MeshBasicMaterial({
    color: 0x7b5cd6, transparent: true, opacity: 0.7, side: THREE.DoubleSide,
  })
);
enigmaRing.rotation.x = -Math.PI / 2;
enigmaRing.position.y = -WELL_DEPTH + 0.25;
scene.add(enigmaRing);

// Morphing liquid core — Enigma's body. A subdivided icosahedron whose
// vertices are swayed by a sum of sinusoids in the vertex shader, so the
// shape slowly morphs between states like a drop of mercury. A rim term
// in the fragment gives it a bright silhouette so it reads at a distance.
const enigmaCore = (() => {
  const geom = new THREE.IcosahedronGeometry(HOLE_R * 0.82, 5);
  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uTime:    { value: 0 },
      uColor:   { value: PALETTE.violet.clone() },
      uColorHi: { value: PALETTE.violetLilac.clone() },
    },
    transparent: true,
    depthWrite: true,
    vertexShader: /* glsl */`
      uniform float uTime;
      varying vec3  vNormal;
      varying float vDisp;
      float sway(vec3 p, float t) {
        float n = 0.0;
        n += sin(p.x * 1.6 + t * 1.1);
        n += sin(p.y * 1.4 - t * 0.9) * 0.8;
        n += sin(p.z * 1.8 + t * 1.3) * 0.6;
        n += sin((p.x + p.y) * 2.1 + t * 0.7) * 0.5;
        n += sin((p.y + p.z) * 2.5 - t * 1.2) * 0.35;
        return n * 0.2;
      }
      void main() {
        vec3  n = normalize(position);
        float d = sway(position, uTime);
        vec3  displaced = position + n * d * 2.4;
        vDisp   = d;
        vNormal = normalize(normalMatrix * n);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
      }
    `,
    fragmentShader: /* glsl */`
      uniform vec3 uColor;
      uniform vec3 uColorHi;
      varying vec3 vNormal;
      varying float vDisp;
      void main() {
        float rim = 1.0 - max(0.0, dot(vNormal, vec3(0.0, 0.0, 1.0)));
        rim = pow(rim, 2.0);
        vec3 col = mix(uColor, uColorHi, smoothstep(-0.25, 0.3, vDisp));
        col += rim * 0.55;
        gl_FragColor = vec4(col, 0.94);
      }
    `,
  });
  const mesh = new THREE.Mesh(geom, mat);
  mesh.position.y = -WELL_DEPTH + HOLE_R * 0.9;
  return mesh;
})();
scene.add(enigmaCore);

// Y-offset where the Enigma label floats (used by updateLabels).
const ENIGMA_LABEL_Y = 6;

/* ------------------------------------------------------------------ */
/*  PLANETS                                                           */
/* ------------------------------------------------------------------ */
//
// Low-poly cartoon planets: a random polyhedron per slug, flat-shaded,
// with 1-2 random features drawn from a small pool (spikes / moon / cap
// / aura / ring). Everything is deterministic from the slug hash so the
// same planet looks the same across reloads.

function seededRand(seed) {
  let s = seed || 1;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 0xffffffff);
}

const planetMeshes = [];

// Orbit belt
const ORBIT_R_MIN = 95;
const ORBIT_R_MAX = 220;

// Pick a body geometry. Icosahedron and dodecahedron are the common blobs;
// tetra/box show up rarely for deliberate weirdos.
function pickGeometry(rand, size) {
  const r = rand();
  if (r < 0.38) return new THREE.IcosahedronGeometry(size, 0);
  if (r < 0.66) return new THREE.DodecahedronGeometry(size, 0);
  if (r < 0.82) return new THREE.OctahedronGeometry(size, 0);
  if (r < 0.92) return new THREE.IcosahedronGeometry(size, 1);
  if (r < 0.97) return new THREE.BoxGeometry(size * 1.4, size * 1.4, size * 1.4);
  return new THREE.TetrahedronGeometry(size * 1.2, 0);
}

// Displace each unique vertex outward by a random scalar so the silhouette
// lumps instead of staying regular. Vertices at the same position share a
// scalar so faces don't split along seams.
function lumpify(geom, rand, amt) {
  const nonIdx = geom.toNonIndexed();
  const pos = nonIdx.attributes.position;
  const cache = new Map();
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    const key = `${x.toFixed(3)},${y.toFixed(3)},${z.toFixed(3)}`;
    let k = cache.get(key);
    if (k === undefined) {
      k = 1 + (rand() - 0.5) * amt;
      cache.set(key, k);
    }
    pos.setXYZ(i, x * k, y * k, z * k);
  }
  nonIdx.computeVertexNormals();
  return nonIdx;
}

// Spikes — 3-7 cones pointing outward from the body surface.
function addSpikes(body, size, color, rand) {
  const n = 3 + Math.floor(rand() * 5);
  const mat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(color).multiplyScalar(1.15),
    roughness: 0.6,
    metalness: 0.05,
    flatShading: true,
  });
  for (let i = 0; i < n; i++) {
    const dir = new THREE.Vector3(
      rand() - 0.5, rand() - 0.5, rand() - 0.5
    ).normalize();
    const len = size * (0.45 + rand() * 0.45);
    const cone = new THREE.Mesh(
      new THREE.ConeGeometry(size * 0.22, len, 6),
      mat
    );
    cone.position.copy(dir.clone().multiplyScalar(size * 0.9));
    cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    body.add(cone);
  }
}

// A tiny moon. The animation loop orbits it using the returned descriptor.
function addMoon(group, size, rand) {
  const moonSize = size * (0.15 + rand() * 0.18);
  const r = size * (1.9 + rand() * 1.3);
  const speed = 0.6 + rand() * 1.2;
  const phase = rand() * Math.PI * 2;
  const tilt  = (rand() - 0.5) * Math.PI * 0.6;
  const moon = new THREE.Mesh(
    new THREE.IcosahedronGeometry(moonSize, 0),
    new THREE.MeshStandardMaterial({
      color: "#e8d9bf",
      roughness: 0.85,
      metalness: 0.02,
      flatShading: true,
    })
  );
  group.add(moon);
  return { moon, r, speed, phase, tilt };
}

// Beret — a short cone perched on top, tilted a little off-axis.
function addCap(body, size, color, rand) {
  const cap = new THREE.Mesh(
    new THREE.ConeGeometry(size * 0.55, size * 0.55, 6),
    new THREE.MeshStandardMaterial({
      color: new THREE.Color(color).lerp(new THREE.Color("#2c2620"), 0.55),
      roughness: 0.8,
      metalness: 0.02,
      flatShading: true,
    })
  );
  cap.position.y = size * 1.05;
  cap.rotation.z = (rand() - 0.5) * 0.4;
  body.add(cap);
}

// Aura — a larger back-face shell that glows softly around the silhouette.
function addAura(group, size, color) {
  const aura = new THREE.Mesh(
    new THREE.IcosahedronGeometry(size * 1.28, 1),
    new THREE.MeshBasicMaterial({
      color: new THREE.Color(color).lerp(new THREE.Color("#ffffff"), 0.3),
      transparent: true,
      opacity: 0.12,
      side: THREE.BackSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
  );
  group.add(aura);
}

// A slim, rare, tilted ring. Solid color — no canvas texture.
function addRing(group, size, color, rand) {
  const rInner = size * 1.5;
  const rOuter = size * (1.9 + rand() * 0.3);
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(rInner, rOuter, 48),
    new THREE.MeshBasicMaterial({
      color: new THREE.Color(color).lerp(new THREE.Color("#ffffff"), 0.35),
      transparent: true,
      opacity: 0.55,
      side: THREE.DoubleSide,
      depthWrite: false,
    })
  );
  ring.rotation.x = Math.PI / 2 + (rand() - 0.5) * 0.5;
  ring.rotation.z = (rand() - 0.5) * 0.4;
  group.add(ring);
}

const FEATURE_POOL = ["spikes", "moon", "cap", "aura", "ring"];

function buildPlanet(data, idx, total) {
  const color = CLAUDE_PLANET_COLORS[idx % CLAUDE_PLANET_COLORS.length];
  const seed = hashString(data.slug);
  const rand = seededRand(seed ^ 0xa5a5a5a5);

  // Base radius ±25% variance
  const baseSize = (data.layout?.size || 32) * 0.22;
  const size = baseSize * (0.78 + rand() * 0.5);

  // Orbit slot across the belt; data-provided radius nudges it
  const t = total > 1 ? idx / (total - 1) : 0.5;
  const nudge = (((data.layout?.radius || 260) - 260) / 260) * 12;
  const orbitR = ORBIT_R_MIN + (ORBIT_R_MAX - ORBIT_R_MIN) * t + nudge;
  const ecc = 0.05 + ((idx * 0.037) % 0.10);
  const a = orbitR;
  const b = orbitR * (1 - ecc);
  const tiltX = THREE.MathUtils.degToRad(-5 + ((idx * 3) % 12));
  const tiltZ = THREE.MathUtils.degToRad(10 - ((idx * 4) % 14));
  const orbitSpeed = 0.45 / Math.sqrt(orbitR / ORBIT_R_MIN);

  // Wider axial tilt + varied spin per planet
  const axialTilt = (rand() - 0.5) * THREE.MathUtils.degToRad(80);
  const wobble    = (rand() - 0.5) * THREE.MathUtils.degToRad(24);
  const spinSpeed = 0.15 + rand() * 0.5;

  // Outer group carries orbit position + axial tilt
  const group = new THREE.Group();
  group.rotation.z = axialTilt;
  group.rotation.x = wobble;

  // Body — low-poly, optionally lumpy, flat-shaded solid color
  let geom = pickGeometry(rand, size);
  if (rand() < 0.6) geom = lumpify(geom, rand, 0.32);

  const body = new THREE.Mesh(
    geom,
    new THREE.MeshStandardMaterial({
      color,
      roughness: 0.55 + rand() * 0.3,
      metalness: 0.05,
      emissive: new THREE.Color(color),
      emissiveIntensity: 0.08 + rand() * 0.14,
      flatShading: true,
    })
  );
  body.userData = { kind: "planet-body" };
  group.add(body);

  // Pick 1-2 distinct features from the pool. Ring is rare — if drawn,
  // it's kept only about a quarter of the time.
  const pool = FEATURE_POOL.slice();
  const featureCount = 1 + (rand() < 0.55 ? 1 : 0);
  const features = [];
  for (let i = 0; i < featureCount && pool.length; i++) {
    let pick = pool.splice(Math.floor(rand() * pool.length), 1)[0];
    if (pick === "ring" && rand() > 0.25 && pool.length) {
      pool.push("ring");
      pick = pool.splice(Math.floor(rand() * pool.length), 1)[0];
    }
    features.push(pick);
  }

  const moons = [];
  for (const f of features) {
    if (f === "spikes") addSpikes(body, size, color, rand);
    else if (f === "moon") moons.push(addMoon(group, size, rand));
    else if (f === "cap") addCap(body, size, color, rand);
    else if (f === "aura") addAura(group, size, color);
    else if (f === "ring") addRing(group, size, color, rand);
  }

  // Evolution halo — a back-face shell with a rim-glowing, pulsing shader.
  // Hidden by default; pollEvolutions() flips it on when status === 'running'.
  const evolveAura = new THREE.Mesh(
    new THREE.IcosahedronGeometry(size * 1.7, 1),
    new THREE.ShaderMaterial({
      uniforms: {
        uTime:  { value: 0 },
        uColor: { value: new THREE.Color("#c8945a") }, // amber pulse
      },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
      vertexShader: /* glsl */`
        uniform float uTime;
        varying float vRim;
        void main() {
          vec3 n = normalize(position);
          float breathe = 1.0 + sin(uTime * 2.2) * 0.04;
          vec4 mv = modelViewMatrix * vec4(position * breathe, 1.0);
          vec3 vn = normalize(normalMatrix * n);
          vRim = 1.0 - max(0.0, abs(vn.z));
          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: /* glsl */`
        uniform float uTime;
        uniform vec3 uColor;
        varying float vRim;
        void main() {
          float pulse = 0.55 + 0.45 * sin(uTime * 2.8);
          float a = pow(vRim, 1.3) * 0.85 * pulse;
          gl_FragColor = vec4(uColor, a);
        }
      `,
    })
  );
  evolveAura.visible = !!(data.evolution && data.evolution.status === "running");
  group.add(evolveAura);

  const startPhase = (idx / Math.max(total, 1)) * Math.PI * 2 + (data.layout?.angle || 0);
  group.userData = {
    kind: "planet", data, body, moons, spinSpeed, evolveAura,
    orbit: { a, b, tiltX, tiltZ, phase: startPhase, speed: orbitSpeed },
  };
  scene.add(group);
  planetMeshes.push(group);
  return group;
}

function hashString(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = (h * 16777619) >>> 0;
  }
  return h;
}

// keyed lights so planets have a little lift against the dark.
const ambient = new THREE.AmbientLight(0x4a3f70, 0.9);
scene.add(ambient);
const keyLight = new THREE.DirectionalLight(0xfff4e3, 0.9);
keyLight.position.set(200, 250, 150);
scene.add(keyLight);
const fillLight = new THREE.DirectionalLight(0x7b5cd6, 0.35);
fillLight.position.set(-200, -100, -150);
scene.add(fillLight);

/* ------------------------------------------------------------------ */
/*  CREATURE MARKERS (shown when zoomed into a planet)                */
/* ------------------------------------------------------------------ */
// We represent creatures as DOM labels positioned around the focused
// planet. In universe view they're hidden.

/* ------------------------------------------------------------------ */
/*  POST-PROCESSING                                                   */
/* ------------------------------------------------------------------ */
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(
  new THREE.Vector2(window.innerWidth, window.innerHeight),
  0.45,  // strength — subtle now; no hot disk to glow
  0.5,   // radius
  0.72   // threshold — just the ring + brightest stars
);
composer.addPass(bloom);
composer.addPass(new OutputPass());

/* ------------------------------------------------------------------ */
/*  CAMERA CONTROLS — orbit + dolly, custom (no OrbitControls dep)    */
/* ------------------------------------------------------------------ */

// Spherical coords around a target.
const cam = {
  target: new THREE.Vector3(0, 0, 0),
  yaw: 0,        // rotation around Y
  pitch: 0.36,   // rotation above horizontal
  dist: 260,
  minDist: 60,
  maxDist: 900,
};

// tween state for focus transitions
let tween = null;

function applyCamera() {
  const x = cam.target.x + cam.dist * Math.cos(cam.pitch) * Math.sin(cam.yaw);
  const y = cam.target.y + cam.dist * Math.sin(cam.pitch);
  const z = cam.target.z + cam.dist * Math.cos(cam.pitch) * Math.cos(cam.yaw);
  camera.position.set(x, y, z);
  camera.lookAt(cam.target);
}
applyCamera();

/* ---- pointer handling with click-vs-drag detection ---------- */
const pointer = {
  down: false,
  id: -1,
  startX: 0, startY: 0,
  startT: 0,
  dragged: false,
  lastX: 0, lastY: 0,
};
const DRAG_PX = 5;
const CLICK_MS = 300;

canvas.addEventListener("pointerdown", (e) => {
  pointer.down = true;
  pointer.id = e.pointerId;
  pointer.startX = e.clientX;
  pointer.startY = e.clientY;
  pointer.lastX = e.clientX;
  pointer.lastY = e.clientY;
  pointer.startT = performance.now();
  pointer.dragged = false;
  canvas.setPointerCapture(e.pointerId);
});

canvas.addEventListener("pointermove", (e) => {
  if (!pointer.down) {
    // hover — check if over a pickable (planet)
    const hit = raycastPick(e.clientX, e.clientY);
    canvas.classList.toggle("pickable", !!hit);
    return;
  }
  const dx = e.clientX - pointer.lastX;
  const dy = e.clientY - pointer.lastY;
  pointer.lastX = e.clientX;
  pointer.lastY = e.clientY;

  const dxTotal = e.clientX - pointer.startX;
  const dyTotal = e.clientY - pointer.startY;
  if (!pointer.dragged && Math.hypot(dxTotal, dyTotal) > DRAG_PX) {
    pointer.dragged = true;
    canvas.classList.add("dragging");
    // cancel any in-flight tween since user is driving now
    tween = null;
  }
  if (pointer.dragged) {
    // orbit
    cam.yaw   -= dx * 0.005;
    cam.pitch += dy * 0.005;
    cam.pitch = Math.max(-1.2, Math.min(1.3, cam.pitch));
    applyCamera();
  }
});

canvas.addEventListener("pointerup", (e) => {
  if (!pointer.down) return;
  pointer.down = false;
  canvas.classList.remove("dragging");
  try { canvas.releasePointerCapture(e.pointerId); } catch (_) { /* noop */ }

  const duration = performance.now() - pointer.startT;
  if (!pointer.dragged && duration < CLICK_MS) {
    // clean click -> dispatch pick
    handleClick(e.clientX, e.clientY);
  }
});

canvas.addEventListener("pointercancel", () => {
  pointer.down = false;
  pointer.dragged = false;
  canvas.classList.remove("dragging");
});

// wheel / trackpad — dolly toward cursor.
canvas.addEventListener("wheel", (e) => {
  e.preventDefault();
  const scale = Math.exp(e.deltaY * 0.0015);
  cam.dist = Math.max(cam.minDist, Math.min(cam.maxDist, cam.dist * scale));
  applyCamera();
}, { passive: false });

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") exitFocus();
});

// Double-click on empty space -> snap to a top-down "map view" of the cosmos.
// A double-click on a planet is a no-op (single-click already focuses it).
canvas.addEventListener("dblclick", (e) => {
  if (raycastPick(e.clientX, e.clientY)) return;
  resetTopDown();
});

/* ------------------------------------------------------------------ */
/*  RAYCAST + CLICK HANDLING                                          */
/* ------------------------------------------------------------------ */
const raycaster = new THREE.Raycaster();
const ndc = new THREE.Vector2();

function raycastPick(clientX, clientY) {
  const rect = canvas.getBoundingClientRect();
  ndc.x = ((clientX - rect.left) / rect.width) * 2 - 1;
  ndc.y = -((clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(ndc, camera);
  // planets are Groups; recurse into children to hit the body mesh, then
  // walk up to the group so callers always see a kind:"planet" object.
  const hits = raycaster.intersectObjects(planetMeshes, true);
  if (!hits.length) return null;
  let obj = hits[0].object;
  while (obj && obj.userData?.kind !== "planet") obj = obj.parent;
  return obj || null;
}

function handleClick(clientX, clientY) {
  const hit = raycastPick(clientX, clientY);
  if (hit && hit.userData.kind === "planet") {
    focusPlanet(hit);
  } else {
    // background click -> exit focus if zoomed
    if (focused) exitFocus();
  }
}

/* ------------------------------------------------------------------ */
/*  FOCUS / TWEEN                                                     */
/* ------------------------------------------------------------------ */
let focused = null; // planet mesh

function focusPlanet(mesh) {
  focused = mesh;
  const d = mesh.userData.data;
  focusName.textContent = d.title || d.slug;
  focusMeta.textContent = `${d.domain || ""} · ${d.creatures?.length || 0} creature${d.creatures?.length === 1 ? "" : "s"}`;
  focusEl.classList.add("visible");
  hintEl.classList.add("hidden");

  // Open the side panel with planet info + clickable creature roster.
  openPlanetPanel(d);

  // tween camera target to planet, dist close, pitch gentle.
  startTween({
    toTarget: mesh.position.clone(),
    toDist: 48,
    toYaw: cam.yaw,            // keep yaw, feels continuous
    toPitch: 0.25,
    ms: 700,
  });
}

function exitFocus() {
  if (!focused) {
    // already at universe view — nothing to do
    closePanel();
    return;
  }
  focused = null;
  focusEl.classList.remove("visible");
  hintEl.classList.remove("hidden");
  closePanel();
  startTween({
    toTarget: new THREE.Vector3(0, 0, 0),
    toDist: 260,
    toYaw: cam.yaw,
    toPitch: 0.36,
    ms: 700,
  });
}

// Top-down map view — camera above origin looking straight down. Any active
// focus is cleared so the follow loop doesn't drag the camera back to a planet.
function resetTopDown() {
  if (focused) {
    focused = null;
    focusEl.classList.remove("visible");
    hintEl.classList.remove("hidden");
    closePanel();
  }
  startTween({
    toTarget: new THREE.Vector3(0, 0, 0),
    toDist: 360,
    toYaw: 0,
    toPitch: Math.PI / 2 - 0.08,
    ms: 800,
  });
}

function startTween({ toTarget, toDist, toYaw, toPitch, ms }) {
  const from = {
    target: cam.target.clone(),
    dist: cam.dist, yaw: cam.yaw, pitch: cam.pitch,
  };
  const to = {
    target: toTarget.clone(), dist: toDist, yaw: toYaw, pitch: toPitch,
  };
  const t0 = performance.now();
  tween = { from, to, t0, ms };
}

function updateTween(now) {
  if (tween) {
    const u = Math.min(1, (now - tween.t0) / tween.ms);
    const e = 1 - Math.pow(1 - u, 3); // easeOutCubic
    // If a planet is focused, chase its live position so the tween ends
    // on-target even though the planet kept orbiting during the tween.
    const toTarget = focused ? focused.position : tween.to.target;
    cam.target.lerpVectors(tween.from.target, toTarget, e);
    cam.dist  = tween.from.dist  + (tween.to.dist  - tween.from.dist)  * e;
    cam.yaw   = tween.from.yaw   + (tween.to.yaw   - tween.from.yaw)   * e;
    cam.pitch = tween.from.pitch + (tween.to.pitch - tween.from.pitch) * e;
    applyCamera();
    if (u >= 1) tween = null;
    return;
  }
  if (focused) {
    // Post-tween follow: keep the camera pinned to the planet as it orbits.
    cam.target.copy(focused.position);
    applyCamera();
  }
}

/* ------------------------------------------------------------------ */
/*  SIDE PANEL                                                        */
/* ------------------------------------------------------------------ */
// panelMode tracks what the panel is showing so live updates (from the
// poll loop) re-render the right content. openFile is the path of a
// markdown file currently being viewed (rendered inline below the tree).
let panelMode = null; // "planet" | "creature" | "universe"
let openFile = null;  // { path, source: "planet" | "universe" }
let planetTab = "roster"; // active tab within planet panel: "roster" | "summary" | "files"

function renderRosterTab(data) {
  const creatures = data.creatures || [];
  if (!creatures.length) {
    return `<p class="panel-creature-empty">no creatures yet</p>`;
  }
  return `<ul class="panel-roster">${creatures.map((c, i) => `
    <li class="panel-creature" data-idx="${i}">
      <span class="panel-creature-name">${escapeHtml(c.title || c.slug)}</span>
      ${c.expertise ? `<span class="panel-creature-meta">${escapeHtml(c.expertise)}</span>` : ""}
    </li>`).join("")}</ul>`;
}

function renderSummaryTab(data) {
  const run = data.latest_run;
  if (!run) {
    return `<p class="panel-creature-empty">no autoresearch runs yet</p>`;
  }
  return `
    <p class="panel-run-meta">${escapeHtml(run.date)}</p>
    <p class="panel-wisdom-label">summary</p>
    <p class="panel-run-text">${escapeHtml(run.summary) || "<em>no summary recorded</em>"}</p>
    ${run.questions ? `
    <p class="panel-wisdom-label">open questions</p>
    <p class="panel-run-text">${escapeHtml(run.questions)}</p>` : ""}
  `;
}

function openPlanetPanel(data, opts = {}) {
  panelMode = "planet";
  if (!opts.preserveOpenFile) openFile = null;
  if (opts.tab) planetTab = opts.tab;
  const creatures = data.creatures || [];

  const evolution = data.evolution || null;
  const evolutionPill = evolution
    ? `<span class="panel-evolving is-${escapeAttr(evolution.status)}">${escapeHtml(evolution.status)}</span>`
    : "";
  let evolutionMeta = "";
  if (evolution) {
    const bits = [];
    if (evolution.started_at) bits.push(`started ${timeAgo(evolution.started_at)}`);
    if (evolution.updated_at) bits.push(`updated ${timeAgo(evolution.updated_at)}`);
    if (evolution.message)    bits.push(`"${escapeHtml(evolution.message)}"`);
    if (bits.length) {
      evolutionMeta = `<p class="panel-evolution-meta">${bits.join(" · ")}</p>`;
    }
  }

  const treeHtml = data.tree
    ? `<div class="panel-explorer"><div class="tree">${renderTree(data.tree, data.files || {})}</div>${renderFileView(data.files || {}, "planet")}</div>`
    : "";

  const tabsHtml = `
    <div class="panel-tabs" role="tablist">
      <button class="panel-tab ${planetTab === "roster" ? "is-active" : ""}" data-tab="roster" role="tab" aria-selected="${planetTab === "roster"}">roster</button>
      <button class="panel-tab ${planetTab === "summary" ? "is-active" : ""}" data-tab="summary" role="tab" aria-selected="${planetTab === "summary"}">summary</button>
      <button class="panel-tab ${planetTab === "files" ? "is-active" : ""}" data-tab="files" role="tab" aria-selected="${planetTab === "files"}">files</button>
    </div>
    <div class="panel-tab-content">
      ${planetTab === "roster" ? renderRosterTab(data) : ""}
      ${planetTab === "summary" ? renderSummaryTab(data) : ""}
      ${planetTab === "files" ? treeHtml : ""}
    </div>
  `;

  panelBody.innerHTML = `
    <h3>${escapeHtml(data.title || data.slug)} ${evolutionPill}</h3>
    <p class="panel-sub">planet · ${escapeHtml(data.domain || "—")}</p>
    ${evolutionMeta}
    ${data.flavor ? `<p class="panel-flavor">${escapeHtml(data.flavor)}</p>` : ""}
    <dl class="panel-kv">
      <dt>generation</dt><dd>${escapeHtml(String(data.generation ?? "g1"))}</dd>
      <dt>last visited</dt><dd>${escapeHtml(data.last_visited || "—")}</dd>
      <dt>creatures</dt><dd>${creatures.length}</dd>
    </dl>
    ${tabsHtml}
  `;

  panelBody.querySelectorAll(".panel-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      planetTab = btn.getAttribute("data-tab");
      openPlanetPanel(data, { preserveOpenFile: true, tab: planetTab });
    });
  });

  panelBody.querySelectorAll(".panel-creature").forEach((li) => {
    const idx = parseInt(li.getAttribute("data-idx"), 10);
    const c = creatures[idx];
    if (c) li.addEventListener("click", () => openCreaturePanel(c, data));
  });
  panelEl.classList.add("open");
  panelEl.setAttribute("aria-hidden", "false");
}

function openCreaturePanel(creature, planet) {
  panelMode = "creature";
  openFile = null;
  planetTab = "roster";
  const sessions = creature.sessions ?? creature.journal_entries ?? 0;
  const preview = (creature.wisdom_preview || creature.wisdom || "").slice(0, 220);
  panelBody.innerHTML = `
    <h3>${escapeHtml(creature.title || creature.slug)}</h3>
    <p class="panel-sub">lives on ${escapeHtml(planet.title || planet.slug)}</p>
    ${creature.flavor ? `<p class="panel-flavor">${escapeHtml(creature.flavor)}</p>` : ""}
    <dl class="panel-kv">
      <dt>expertise</dt><dd>${escapeHtml(creature.expertise || "—")}</dd>
      <dt>sessions</dt><dd>${sessions}</dd>
      <dt>last seen</dt><dd>${escapeHtml(creature.last_seen || "—")}</dd>
      <dt>born</dt><dd>${escapeHtml(creature.born || "—")}</dd>
    </dl>
    <p class="panel-wisdom-label">distilled wisdom</p>
    <p class="panel-wisdom">${escapeHtml(preview) || "<em>No wisdom recorded yet.</em>"}</p>
  `;
  panelEl.classList.add("open");
  panelEl.setAttribute("aria-hidden", "false");
}

// Universe-wide explorer — opens when no planet is focused.
function openUniversePanel(opts = {}) {
  if (!universeState) return;
  panelMode = "universe";
  if (!opts.preserveOpenFile) openFile = null;
  const tree = universeState.universe_tree;
  const files = universeState.universe_files || {};
  const treeHtml = tree
    ? `<div class="tree">${renderTree(tree, files)}</div>`
    : "<p class=\"panel-creature-empty\">no universe tree</p>";

  panelBody.innerHTML = `
    <h3>universe</h3>
    <p class="panel-sub">everything on disk — click a file to read</p>
    <div class="panel-explorer">${treeHtml}${renderFileView(files, "universe")}</div>
  `;
  panelEl.classList.add("open");
  panelEl.setAttribute("aria-hidden", "false");
}

function closePanel() {
  panelEl.classList.remove("open");
  panelEl.setAttribute("aria-hidden", "true");
  panelMode = null;
  openFile = null;
  planetTab = "roster";
}
panelClose.addEventListener("click", closePanel);

if (btnExplore) {
  btnExplore.addEventListener("click", () => {
    // If a planet panel is open, the explore button jumps to the universe-
    // wide tree (most natural reading). Otherwise toggle open/closed.
    if (panelMode === "universe" && panelEl.classList.contains("open")) {
      closePanel();
    } else {
      openUniversePanel();
    }
  });
}

// Event delegation — tree item clicks + "close file" button + back to root.
panelBody.addEventListener("click", (e) => {
  const fileEl = e.target.closest(".tree-file-open");
  if (fileEl) {
    const path = fileEl.getAttribute("data-path");
    const source = fileEl.getAttribute("data-source");
    openFile = { path, source };
    rerenderCurrentPanel();
    return;
  }
  const closer = e.target.closest(".file-close");
  if (closer) {
    openFile = null;
    rerenderCurrentPanel();
  }
});

// Re-render the panel in its current mode (used after file selection changes
// or after a live update mutates the underlying data).
function rerenderCurrentPanel() {
  if (panelMode === "planet" && focused) {
    openPlanetPanel(focused.userData.data, { preserveOpenFile: true, tab: planetTab });
  } else if (panelMode === "universe") {
    openUniversePanel({ preserveOpenFile: true });
  }
}

// Render a nested tree. `filesMap` tells us which entries have content
// available so we can style them as clickable. `sourceTag` is carried on
// each file node so the click handler knows where to look up content.
function renderTree(node, filesMap, depth = 0, sourceTag) {
  const tag = sourceTag || (panelMode === "universe" ? "universe" : "planet");
  const openAttr = depth < 1 ? " open" : "";
  if (node.type === "dir") {
    const children = (node.children || [])
      .map((c) => renderTree(c, filesMap, depth + 1, tag)).join("");
    return `<details class="tree-dir"${openAttr}>
      <summary class="tree-dir-name">${escapeHtml(node.name)}</summary>
      <div class="tree-children">${children}</div>
    </details>`;
  }
  const viewable = Object.prototype.hasOwnProperty.call(filesMap, node.path);
  const cls = "tree-file" + (viewable ? " tree-file-open" : "");
  return `<div class="${cls}" data-path="${escapeAttr(node.path)}" data-source="${tag}">
    ${escapeHtml(node.name)}
  </div>`;
}

// Render the currently-open file (or nothing). `filesMap`/`source` tell us
// where to look up the text body for `openFile`.
function renderFileView(filesMap, source) {
  if (!openFile || openFile.source !== source) return "";
  const body = filesMap[openFile.path];
  if (body == null) {
    return `<div class="file-view">
      <header class="file-view-head">
        <span class="file-view-path">${escapeHtml(openFile.path)}</span>
        <button class="file-close" type="button">close</button>
      </header>
      <p class="file-missing">file content not available</p>
    </div>`;
  }
  const isMd = /\.md$/i.test(openFile.path);
  const rendered = isMd ? renderMarkdown(body) : `<pre class="file-plain">${escapeHtml(body)}</pre>`;
  return `<div class="file-view">
    <header class="file-view-head">
      <span class="file-view-path">${escapeHtml(openFile.path)}</span>
      <button class="file-close" type="button">close</button>
    </header>
    <article class="file-view-body">${rendered}</article>
  </div>`;
}

// Minimal, safe markdown renderer. Handles frontmatter strip, headings,
// fenced + inline code, bold/italic, links, bullet lists, paragraphs.
// Everything else gets HTML-escaped so injected html in a .md file can't
// break out. Good enough for reading MD files; not a spec-compliant parser.
function renderMarkdown(src) {
  src = src.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, "");
  const codes = [];
  src = src.replace(/```([^\n]*)\n([\s\S]*?)```/g, (_m, lang, body) => {
    codes.push({ lang: lang.trim(), body });
    return `§CODE${codes.length - 1}§`;
  });
  src = escapeHtml(src);
  src = src.replace(/`([^`]+)`/g, "<code>$1</code>");
  src = src.replace(/^(#{1,6})\s+(.+)$/gm,
    (_m, h, t) => `<h${h.length}>${t}</h${h.length}>`);
  src = src.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  src = src.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
  src = src.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_m, t, u) => {
    const safe = /^(?:https?:|mailto:|#|\/|\.\.?\/)/i.test(u) ? u : "#";
    return `<a href="${safe}" target="_blank" rel="noopener">${t}</a>`;
  });
  src = src.replace(/(?:^|\n)((?:[-*+] .+\n?)+)/g, (_m, block) => {
    const items = block.trim().split(/\n/)
      .map((l) => `<li>${l.replace(/^[-*+]\s+/, "")}</li>`).join("");
    return `\n<ul>${items}</ul>\n`;
  });
  src = src.split(/\n{2,}/).map((p) => {
    p = p.trim();
    if (!p) return "";
    if (/^<(?:h\d|ul|ol|pre|blockquote)/.test(p) || p.startsWith("§CODE")) return p;
    return `<p>${p.replace(/\n/g, "<br>")}</p>`;
  }).join("\n");
  src = src.replace(/§CODE(\d+)§/g, (_m, i) => {
    const c = codes[+i];
    return `<pre><code${c.lang ? ` class="lang-${escapeAttr(c.lang)}"` : ""}>${escapeHtml(c.body)}</code></pre>`;
  });
  return src;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
function escapeAttr(s) {
  return String(s).replace(/["<>&]/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
  }[c]));
}

// timeAgo("2026-04-14T02:14:01Z") -> "12s ago" / "3m ago" / "2h ago".
// Returns "" for missing/unparseable input so callers can chain safely.
function timeAgo(iso) {
  if (!iso) return "";
  const then = Date.parse(iso);
  if (isNaN(then)) return "";
  const diffSec = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (diffSec < 60)    return `${diffSec}s ago`;
  if (diffSec < 3600)  return `${Math.round(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.round(diffSec / 3600)}h ago`;
  return `${Math.round(diffSec / 86400)}d ago`;
}

/* ------------------------------------------------------------------ */
/*  DOM LABELS                                                        */
/* ------------------------------------------------------------------ */
const labelPool = new Map(); // key -> HTMLElement

function getOrCreateLabel(key, text, className) {
  let el = labelPool.get(key);
  if (!el) {
    el = document.createElement("div");
    el.className = "label " + (className || "");
    el.textContent = text;
    labelsDiv.appendChild(el);
    labelPool.set(key, el);
  } else if (el.textContent !== text) {
    el.textContent = text;
  }
  return el;
}

function worldToScreen(v3) {
  const p = v3.clone().project(camera);
  const rect = canvas.getBoundingClientRect();
  return {
    x: rect.left + (p.x * 0.5 + 0.5) * rect.width,
    y: rect.top + (-p.y * 0.5 + 0.5) * rect.height,
    behind: p.z > 1,
  };
}

function updateLabels() {
  // Enigma label — hovers just above the rim of the well
  {
    const s = worldToScreen(new THREE.Vector3(0, ENIGMA_LABEL_Y, 0));
    const el = getOrCreateLabel("enigma", "Enigma the One", "");
    if (s.behind) { el.style.opacity = "0"; }
    else {
      el.style.opacity = focused ? "0.25" : "0.9";
      el.style.left = `${s.x}px`;
      el.style.top  = `${s.y - 22}px`;
    }
  }

  // Planet labels
  for (const mesh of planetMeshes) {
    const key = "p-" + mesh.userData.data.slug;
    const text = mesh.userData.data.title || mesh.userData.data.slug;
    const el = getOrCreateLabel(key, text, "");
    const lifted = mesh.position.clone().add(new THREE.Vector3(0, 9, 0));
    const s = worldToScreen(lifted);
    if (s.behind) { el.style.opacity = "0"; continue; }
    const isFocused = focused && focused === mesh;
    const isDim = focused && focused !== mesh;
    el.style.opacity = isDim ? "0.18" : "0.85";
    el.style.left = `${s.x}px`;
    el.style.top  = `${s.y - 18}px`;
    el.classList.toggle("creature", false);
  }

  // Creature labels — only when focused on a planet.
  if (focused) {
    const pd = focused.userData.data;
    const creatures = pd.creatures || [];
    const now = performance.now() * 0.00035;
    creatures.forEach((c, i) => {
      const key = "c-" + pd.slug + "-" + c.slug;
      const el = getOrCreateLabel(key, c.title || c.slug, "creature pickable");
      // bind click once
      if (!el.dataset.bound) {
        el.dataset.bound = "1";
        el.addEventListener("click", () => openCreaturePanel(c, pd));
      }
      // position around the focused planet, drifting slowly
      const ang = (i / Math.max(creatures.length, 1)) * Math.PI * 2 + now;
      const rad = 16 + (i % 2) * 4;
      const offset = new THREE.Vector3(
        Math.cos(ang) * rad,
        6,
        Math.sin(ang) * rad
      );
      const world = focused.position.clone().add(offset);
      const s = worldToScreen(world);
      if (s.behind) { el.style.opacity = "0"; return; }
      el.style.opacity = "0.95";
      el.style.left = `${s.x}px`;
      el.style.top  = `${s.y}px`;
    });
    // hide creature labels for non-focused planets
    for (const [k, el] of labelPool) {
      if (k.startsWith("c-") && !k.startsWith("c-" + pd.slug + "-")) {
        el.style.opacity = "0";
      }
    }
  } else {
    // hide all creature labels in universe view
    for (const [k, el] of labelPool) {
      if (k.startsWith("c-")) el.style.opacity = "0";
    }
  }
}

/* ------------------------------------------------------------------ */
/*  RESIZE                                                            */
/* ------------------------------------------------------------------ */
function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false);
  composer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  bloom.setSize(w, h);
}
window.addEventListener("resize", resize);
resize();

/* ------------------------------------------------------------------ */
/*  ANIMATION LOOP                                                    */
/* ------------------------------------------------------------------ */
const clock = new THREE.Clock();
let camDrift = 0;
let idleBaseYaw = 0;

function frame() {
  const dt = clock.getDelta();
  const t  = clock.elapsedTime;

  spacetimeGrid.material.uniforms.uTime.value = t;
  stars.material.uniforms.uTime.value = t;
  enigmaCore.material.uniforms.uTime.value = t;
  enigmaCore.rotation.y = t * 0.12;
  enigmaCore.rotation.x = Math.sin(t * 0.15) * 0.25;

  // slow camera drift when idle — just the base yaw, so user input still wins
  camDrift += dt * 0.02;
  if (!pointer.down && !tween && !focused) {
    cam.yaw += Math.sin(camDrift) * 0.00015; // very subtle
    applyCamera();
  }

  // orbit planets — each planet is a Group at orbit position; the inner
  // body spins on its own local Y inside the group's axial-tilt frame.
  for (const group of planetMeshes) {
    const o = group.userData.orbit;
    o.phase += dt * o.speed;
    const x = o.a * Math.cos(o.phase);
    const z = o.b * Math.sin(o.phase);
    let p = new THREE.Vector3(x, 0, z);
    p.applyAxisAngle(new THREE.Vector3(1, 0, 0), o.tiltX);
    p.applyAxisAngle(new THREE.Vector3(0, 0, 1), o.tiltZ);
    group.position.copy(p);
    group.userData.body.rotation.y += dt * group.userData.spinSpeed;

    // evolution halo — only advances time while visible
    const aura = group.userData.evolveAura;
    if (aura && aura.visible) {
      aura.material.uniforms.uTime.value = t;
    }

    // moons orbit inside the planet's group frame on a tilted circle
    const moons = group.userData.moons;
    if (moons && moons.length) {
      for (const m of moons) {
        m.phase += dt * m.speed;
        const mx = m.r * Math.cos(m.phase);
        const mz = m.r * Math.sin(m.phase);
        const mp = new THREE.Vector3(mx, 0, mz);
        mp.applyAxisAngle(new THREE.Vector3(1, 0, 0), m.tilt);
        m.moon.position.copy(mp);
        m.moon.rotation.y += dt * 0.4;
      }
    }
  }

  // subtle ring breathing so the hole mouth feels alive
  const pulse = 1 + Math.sin(t * 1.3) * 0.03;
  enigmaRing.scale.setScalar(pulse);

  updateTween(performance.now());
  updateLabels();

  composer.render();
  requestAnimationFrame(frame);
}

/* ------------------------------------------------------------------ */
/*  DATA LOAD + LIVE POLL                                             */
/* ------------------------------------------------------------------ */
// universeState is the most recent parsed universe.json. It's kept fresh
// by pollUniverse() (slow) so the explorer picks up content changes;
// pollEvolutions() (fast) merges per-planet evolution status.
let universeState = null;
// Heavy file (full tree + wisdom). Polled slowly — content updates are not
// time-critical and the file can be large.
const UNIVERSE_POLL_MS = 30000;
// Tiny status file. Polled fast so the UI feels live as agents work.
const EVOLUTIONS_POLL_MS = 2000;

function applyUniverseUpdate(u) {
  universeState = u;
  const bySlug = new Map((u.planets || []).map((p) => [p.slug, p]));

  // Patch live state on each existing planet: fresh data (tree, files)
  // without rebuilding meshes so orbits stay continuous. Evolution
  // status is preserved — it's owned by the evolutions poll loop.
  for (const group of planetMeshes) {
    const slug = group.userData.data.slug;
    const fresh = bySlug.get(slug);
    if (!fresh) continue;
    const prevEvolution = group.userData.data.evolution;
    group.userData.data = fresh;
    if (prevEvolution !== undefined) group.userData.data.evolution = prevEvolution;
  }

  // If the user is looking at a planet in the panel, refresh it so new
  // files, wisdom, creatures, etc. appear without a reopen.
  if (focused) {
    const slug = focused.userData.data.slug;
    const fresh = bySlug.get(slug);
    if (fresh && panelEl.classList.contains("open") && panelMode === "planet") {
      openPlanetPanel(focused.userData.data, { preserveOpenFile: true });
    }
  } else if (panelEl.classList.contains("open") && panelMode === "universe") {
    openUniversePanel({ preserveOpenFile: true });
  }
}

function applyEvolutionsUpdate(payload) {
  const evs = (payload && payload.evolutions) || {};
  let focusedDirty = false;
  for (const group of planetMeshes) {
    const slug = group.userData.data.slug;
    const row = evs[slug] || null;
    const prev = group.userData.data.evolution || null;
    group.userData.data.evolution = row;
    if (group.userData.evolveAura) {
      // Only the running state lights the halo; complete/failed/pending
      // are conveyed by the panel pill instead.
      group.userData.evolveAura.visible = !!(row && row.status === "running");
    }
    // Cheap shallow comparison — if status or message changed for the
    // currently-focused planet, refresh the panel so the meta line updates.
    if (focused && focused.userData.data.slug === slug) {
      const before = prev ? `${prev.status}|${prev.message || ""}|${prev.updated_at || ""}` : "";
      const after  = row  ? `${row.status}|${row.message  || ""}|${row.updated_at  || ""}` : "";
      if (before !== after) focusedDirty = true;
    }
  }
  if (focusedDirty && panelEl.classList.contains("open") && panelMode === "planet") {
    openPlanetPanel(focused.userData.data, { preserveOpenFile: true });
  }
}

async function pollUniverse() {
  try {
    const r = await fetch("/universe.json", { cache: "no-store" });
    if (r.ok) applyUniverseUpdate(await r.json());
  } catch (_) {
    // swallow; next tick will retry
  }
  setTimeout(pollUniverse, UNIVERSE_POLL_MS);
}

async function pollEvolutions() {
  try {
    const r = await fetch("/evolutions.json", { cache: "no-store" });
    if (r.ok) applyEvolutionsUpdate(await r.json());
  } catch (_) {
    // swallow; next tick will retry
  }
  setTimeout(pollEvolutions, EVOLUTIONS_POLL_MS);
}

fetch("/universe.json", { cache: "no-cache" })
  .then((r) => r.json())
  .then((u) => {
    universeState = u;
    const planets = u.planets || [];
    planets.forEach((p, i) => buildPlanet(p, i, planets.length));
    frame();
    setTimeout(pollUniverse, UNIVERSE_POLL_MS);
    setTimeout(pollEvolutions, 0);
  })
  .catch((err) => {
    console.error("[cosmocache] failed to load universe.json:", err);
    // still start the loop so the scene renders even if data fails
    frame();
    setTimeout(pollUniverse, UNIVERSE_POLL_MS);
    setTimeout(pollEvolutions, 0);
  });
