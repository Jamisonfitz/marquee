#!/bin/sh
# A bind-mounted /config (e.g. Unraid appdata) arrives owned by the host, usually
# root, which the unprivileged marquee user can't write. Fix it, then drop privileges.
chown -R marquee:marquee /config 2>/dev/null || true
exec su-exec marquee "$@"
