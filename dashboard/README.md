# cosmocache dashboard

Docker-served WebGL visualization of the cosmocache universe at
`/Users/bot/universe/`. Enigma the One sits at the center as a black
hole — event horizon, tilted shader-driven accretion disk, photon ring,
bloom. Planets orbit her on faint elliptical tracks; click a planet to
zoom in and meet its creatures; click a creature to read its distilled
wisdom in the side panel.

Three.js r0.183, no bundler, no CDN at runtime. Vendored offline.

## Run

```
cd /Users/bot/universe/dashboard
docker compose up --build
```

Then open <http://localhost:8765>.

## Controls

- **Drag empty space** — orbit the camera (yaw + pitch).
- **Scroll / trackpad pinch** — dolly zoom (clamped 60…900 scene units).
- **Click a planet** — smooth 700ms tween to orbit that planet; its
  creatures appear around it as clickable labels.
- **Click a creature** — side panel slides in with expertise, session
  count, last_seen, and a ~220-char preview of their distilled wisdom.
- **ESC** or background click — return to the universe view.

## Point it at a different universe

```
UNIVERSE_PATH=/path/to/some/other/universe docker compose up --build
```

If the target's `planets/` directory is empty, the build script falls
back to the seed universe at
`<root>/.system/eval/scenarios/seed_universe/planets/` so the dashboard
always has something to show.

## At container start

1. `docker/entrypoint.sh` runs `build/build_universe.py` against the
   mounted `/data` directory.
2. That script scans `planets/<slug>/planet.md`, creature files, and
   `enigma/glossary.md`, extracts YAML frontmatter and `## Distilled
   Wisdom`, writes `/usr/share/nginx/html/universe.json`.
3. nginx starts, serves the static site + JSON from
   `/usr/share/nginx/html`.

Editing markdown on the host only requires `docker compose restart
dashboard` to refresh — no rebuild.

## Layout

```
dashboard/
  Dockerfile                 nginx:alpine + python3 stdlib + vendored three.js
  docker-compose.yml         binds /Users/bot/universe -> /data:ro, port 8765
  DECISION.md                v3 blackhole architecture + size measurements
  README.md                  this file
  build/
    build_universe.py        markdown -> universe.json (stdlib only)
  docker/
    entrypoint.sh            compile + exec nginx
    nginx.conf               gzip, no-cache for universe.json
  web/
    index.html               canvas + HTML chrome + import map
    styles.css               cream chrome tokens (matches site/styles.css)
    main.js                  three.js scene + disk shader + interactions
    universe.json            generated at container start
    vendor/three/...         three.module.min.js + postprocessing (copied in build)
```

## Caveats

- First paint is slightly slower than v1 SVG because Three.js (~160 KB
  gzipped) has to parse before the scene appears. Subsequent loads hit
  the browser cache.
- Markdown is compiled once per container start. Run `docker compose
  restart dashboard` to pick up edits.
- Mobile: works but bloom is expensive on integrated GPUs — drop
  `pixelRatio` further or disable `UnrealBloomPass` if needed.
- No client-side router — refreshing returns to universe view.
