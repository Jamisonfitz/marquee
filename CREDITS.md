# Credits

Marquee's Street‑scene weather effects were built with technique and inspiration
from these open CodePens. Each was adapted (not copied wholesale) to fit the
scene and to keep the card self‑contained; the authors deserve the credit for
the underlying approaches.

| Effect | Author | Source |
|---|---|---|
| Rain (canvas streaks + splash) | **sheepjs** | https://codepen.io/sheepjs/pen/nXZKLy |
| Snow (canvas flakes, wind drift) | **Ivan Odintsov** | https://codepen.io/ivanodintsov/pen/KVgwRG |
| Fog (layered drift + opacity pulse) | **Braeden Craig** | https://codepen.io/braedencraig/pen/dBVKzO |
| Neon sign glow + flicker | **Tiff Wong** | https://codepen.io/tiffwong/pen/ErGgxq |

### Notes on the adaptations
- **Rain** — kept the canvas approach (streak length proportional to fall speed,
  splash droplets on impact) but recoloured from blue toward near‑white, and
  dropped the interactive `dat.GUI` controls.
- **Snow** — kept the canvas circle‑flake model (random radius, speed, and wind
  drift); merged into the same canvas/loop as the rain.
- **Fog** — Braeden Craig's CSS fog layers Daniel Stuart's fog PNGs
  (https://github.com/danielstuart14/CSS_FOG_ANIMATION, MIT). Marquee ships as a
  single self‑contained card with no external asset fetches, so the fog was
  rebuilt PNG‑free using drifting gradient tiles with the same layered,
  independently‑pulsing‑opacity structure.
- **Neon** — used only the neon glow (layered `drop-shadow`/`text-shadow`) and the
  irregular `flicker` keyframes for the "NOW PLAYING" sign; none of the pen's
  layout was used.
