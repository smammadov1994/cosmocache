# Multi-stage build:
#  1) alpine-builder: fetches the `three` npm tarball and extracts only the
#     files we ship (three.module.min.js + a handful of /examples/jsm files
#     for EffectComposer + UnrealBloomPass). No Node, no npm — just curl + tar.
#  2) nginx:alpine: serves static web + compiles universe.json at container
#     start from a read-only bind mount.
#
# The universe markdown only exists at `docker compose up` time via the bind
# mount — it is not part of the build context. Compiling at entrypoint keeps
# the image small and always matches the current markdown on disk.

# --- stage 1: vendor three.js ----------------------------------------------
FROM alpine:3.20 AS three-vendor
ARG THREE_VERSION=0.183.2
RUN apk add --no-cache curl tar
WORKDIR /src
RUN curl -fsSL "https://registry.npmjs.org/three/-/three-${THREE_VERSION}.tgz" -o three.tgz \
 && mkdir -p pkg \
 && tar -xzf three.tgz -C pkg \
 && mkdir -p /vendor/three/jsm/postprocessing /vendor/three/jsm/shaders \
 && cp pkg/package/build/three.module.min.js                                  /vendor/three/three.module.min.js \
 && cp pkg/package/build/three.core.min.js                                    /vendor/three/three.core.min.js \
 && cp pkg/package/examples/jsm/postprocessing/Pass.js                        /vendor/three/jsm/postprocessing/Pass.js \
 && cp pkg/package/examples/jsm/postprocessing/MaskPass.js                    /vendor/three/jsm/postprocessing/MaskPass.js \
 && cp pkg/package/examples/jsm/postprocessing/ShaderPass.js                  /vendor/three/jsm/postprocessing/ShaderPass.js \
 && cp pkg/package/examples/jsm/postprocessing/RenderPass.js                  /vendor/three/jsm/postprocessing/RenderPass.js \
 && cp pkg/package/examples/jsm/postprocessing/EffectComposer.js              /vendor/three/jsm/postprocessing/EffectComposer.js \
 && cp pkg/package/examples/jsm/postprocessing/UnrealBloomPass.js             /vendor/three/jsm/postprocessing/UnrealBloomPass.js \
 && cp pkg/package/examples/jsm/postprocessing/OutputPass.js                  /vendor/three/jsm/postprocessing/OutputPass.js \
 && cp pkg/package/examples/jsm/shaders/CopyShader.js                         /vendor/three/jsm/shaders/CopyShader.js \
 && cp pkg/package/examples/jsm/shaders/LuminosityHighPassShader.js           /vendor/three/jsm/shaders/LuminosityHighPassShader.js \
 && cp pkg/package/examples/jsm/shaders/OutputShader.js                       /vendor/three/jsm/shaders/OutputShader.js

# --- stage 2: runtime ------------------------------------------------------
FROM nginx:alpine

# Python stdlib is enough; no pip needed.
RUN apk add --no-cache python3 && rm -rf /var/cache/apk/*

# Static web assets
COPY web/ /usr/share/nginx/html/
# Vendored three.js (ES module + postprocessing) — no CDN at runtime.
COPY --from=three-vendor /vendor/three/ /usr/share/nginx/html/vendor/three/

# Build script + entrypoint + nginx config
COPY build/build_universe.py /opt/build_universe.py
COPY docker/entrypoint.sh    /opt/entrypoint.sh
COPY docker/nginx.conf       /etc/nginx/conf.d/default.conf

RUN chmod +x /opt/entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/opt/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
