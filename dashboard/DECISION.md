# Decisions — cosmocache dashboard

## v3: CodePen-inspired Three.js blackhole for Enigma

v2 tried to tell a story with textured planets, flying asteroid rocks, and a
rotating black cube at the center. The user rejected it — the scene was busy,
Enigma looked wrong as a cube, and clicks on planets were being swallowed by
the drag handler. v1 (SVG) was clean but had no way to render a real
accretion disk.

**v3 keeps Three.js and rebuilds the scene around one hero: a blackhole.**
Inspired by Sahil Kumar's [Blackhole CodePen](https://codepen.io/sahil_kumar_dev/pen/yLGoBBa),
Enigma becomes a black event horizon wrapped in a tilted, shader-driven
accretion disk that glows in our violet palette, with a thin photon ring
and `UnrealBloomPass` bloom doing the final halo. Planets are simple
procedural-texture spheres on faint elliptical orbits. No rocks. No cube.

The cream UI chrome (top bar, legend, side panel, labels) floats above as
HTML overlay so the palette still reads as cosmocache.

## Blackhole architecture

- **Event horizon** — `SphereGeometry(18, 64, 64)`, `MeshBasicMaterial(#000)`.
  Bloom threshold (0.62) is tuned so the horizon never blooms — it stays
  a true dark silhouette. A 1.7 Hz ±0.8% scale pulse keeps it alive.
- **Photon ring** — thin `TorusGeometry` at `horizon * 1.08`, tube radius
  0.35, emissive cream-white. Bloom catches it into a hairline halo.
- **Accretion disk** — `RingGeometry(inner=20.7, outer=68.4)` with a custom
  `ShaderMaterial`. Two rings overlap at slightly different tilts (25°
  and 21°) so the disk has depth. `AdditiveBlending`, `depthWrite: false`,
  `DoubleSide`.
- **Bloom** — `UnrealBloomPass(strength=0.95, radius=0.55, threshold=0.62)`
  via `RenderPass → UnrealBloomPass → OutputPass` on `EffectComposer`.
- **No lensing pass.** Disk + bloom already sells the look; refraction
  would double the shader budget with modest visual gain.

## Disk shader (one-paragraph explainer)

The fragment shader reads `vUv`: for `RingGeometry` this is `(phi, r)` in
`[0,1]²`, which is exactly what we want. It builds a Keplerian-shear FBM
noise field by evaluating `fbm(phi * shear + time*0.55 + 1.7/(r+0.15),
r*3.5 - time*0.22)` (inner radii scroll faster, matching differential
rotation), blends a radial color ramp **hot-white → lilac → violet** from
inner edge outward, multiplies by brightness that falls with radius and
is modulated by the noise (`0.55 + 0.75*swirl`), applies a one-sided
Doppler term `(0.55 + 0.9 * (0.5 + 0.5*cos(phi + 0.3)))`, and finally
alpha-masks both edges with `smoothstep` and adds a dust-lane factor so
dark streaks thread through. Additive blending + bloom does the rest.

## Click-vs-drag fix (the v2 bug)

v2 dispatched clicks on any `pointerup`, even if the user had already
dragged 20px. That meant clicks intended to zoom into a planet were
landing on whatever was under the cursor at release, and frequently on
empty space.

v3 tracks gesture state explicitly:

```
pointerdown  -> { startX, startY, startT, dragged: false }
pointermove  -> if hypot(dx,dy) > 5px, set dragged = true
pointerup    -> if (!dragged && now - startT < 300ms) handleClick()
                else no click dispatched
```

5px and 300ms thresholds prevent accidental clicks on trackpad swipes
while still feeling snappy. Once `dragged` is true it stays true for the
whole gesture, so a user who starts orbiting the camera can't trigger a
stray click on release no matter where they land. Manually verified:
each of the 3 seed planets zooms in reliably.

## Planet rendering

Kept simple on purpose — the blackhole is the hero. Each planet gets a
procedural 256×256 `CanvasTexture` generated once at load: darkened base
fill in the planet's palette color, 24 radial-gradient blobs in base +
highlight, per-pixel speckle to break banding. A `MeshStandardMaterial`
with tiny emissive intensity (0.08) lets the ambient + directional
lighting shape them without making them look stage-lit.

Orbits use elliptical paths (`a`, `b` with small eccentricity) tilted
per-planet in the X and Z axes so the three planets don't look
coplanar. Faint violet `LineLoop` trails show the orbit path.

## Interaction surface

| gesture                     | effect                                  |
|-----------------------------|-----------------------------------------|
| drag empty space            | orbit camera (yaw + pitch, 5px threshold) |
| scroll / trackpad pinch     | dolly (cam.dist clamped 60…900)         |
| click planet (not drag)     | tween camera to orbit that planet, ~700ms |
| click creature label        | slide side panel in with distilled wisdom |
| ESC                         | exit focus (planet → universe)          |
| click background in focus   | exit focus                              |

## Three.js shipped offline

Still vendored at Docker build time (Dockerfile stage 1 from v2, unchanged):
`three.module.min.js` + the six `examples/jsm/postprocessing` modules +
three `examples/jsm/shaders`. An `importmap` in `index.html` resolves
`"three"` and `"three/addons/"` to `/vendor/three/`. Zero runtime network
requests (except the Google Fonts `<link>`, matching the landing page).

## Measured sizes (v3)

Shipped to the browser:

| asset                                       | raw       | gzipped    |
|---------------------------------------------|-----------|------------|
| `main.js`                                   | ~22 KB    | **~7 KB**  |
| `vendor/three/three.module.min.js`          | 656 KB    | **~160 KB**|
| `vendor/three/jsm/*` (composer + bloom)     | ~55 KB    | **~14 KB** |
| `styles.css`                                | ~6 KB     | ~1.8 KB    |
| **total app + three.js**                    |           | **≈183 KB**|

Docker image: `cosmocache-dashboard:latest` ≈ 60–70 MB (nginx:alpine +
python3 stdlib + vendored three.js). Budget was <80 MB.

## What we didn't do (kept the scene clean)

- **No flying rocks** — user rejected. The starfield is the only backdrop.
- **No gravitational lensing** — bloom + disk already reads as blackhole.
- **No planet atmosphere halo** — would compete with the photon ring.
- **No sprite text** — DOM labels via `worldToScreen()` stay crisp at
  every zoom and let us style them with cosmocache tokens directly.

## Known trade-offs

- Bloom threshold is a lighting compromise. Too low and the cream legend
  chrome blooms; too high and the photon ring stops glowing. 0.62 is the
  current balance — adjust if we change panel/topbar opacity.
- The subtle camera drift is only applied when idle + not focused + no
  tween. This avoids fighting the user's input, but it means a motionless
  user staring at a perfectly-still scene only sees the disk swirling,
  not camera motion. That matches the "clean and confident" direction.
