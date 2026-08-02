# Credits

Marquee's Street‑scene weather effects were built with technique and inspiration
from these open CodePens. Each was adapted (not copied wholesale) to fit the
scene and to keep the card self‑contained; the authors deserve the credit for
the underlying approaches.

| Effect | Author | Source |
|---|---|---|
| Rain (canvas streaks + splash) | **sheepjs** | https://codepen.io/sheepjs/pen/nXZKLy |
| Snow (canvas flakes, wind drift) | **Ivan Odintsov** | https://codepen.io/ivanodintsov/pen/KVgwRG |
| Fog (rising smoke particles) | **dburrell** | https://codepen.io/dburrell/pen/RNpgRg |
| Neon sign glow + flicker | **Tiff Wong** | https://codepen.io/tiffwong/pen/ErGgxq |

### Notes on the adaptations
- **Rain** — kept the canvas approach (streak length proportional to fall speed,
  splash droplets on impact) but recoloured from blue toward near‑white, and
  dropped the interactive `dat.GUI` controls.
- **Snow** — kept the canvas circle‑flake model (random radius, speed, and wind
  drift); merged into the same canvas/loop as the rain.
- **Fog** — dburrell's "Particle Fog Generator": canvas smoke sprites that
  rise from the bottom, drift sideways, grow, and fade. Marquee ships as a
  single self‑contained card with no external asset fetches, so his smoke PNG
  is replaced with a procedurally drawn sprite (layered soft radial blobs on
  an offscreen canvas), and the one‑shot burst becomes a looping field whose
  density follows the Effect‑intensity setting. An earlier fog adapted
  Braeden Craig's layered CSS approach — thanks to him for the first version.
- **Neon** — used only the neon glow (layered `drop-shadow`/`text-shadow`) and the
  irregular `flicker` keyframes for the "NOW PLAYING" sign; none of the pen's
  layout was used.
