#!/usr/bin/env bash
# Install + enable the LAN block as a boot-persistent systemd unit, then verify from the container.
# Usage: sudo bash deploy/install-lan-block.sh            (uninstall: --uninstall)
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "run with sudo" >&2; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)

if [[ "${1:-}" == "--uninstall" ]]; then
  systemctl disable --now fxocr-lan-block.service || true
  rm -f /etc/systemd/system/fxocr-lan-block.service /usr/local/sbin/fxocr-lan-block
  systemctl daemon-reload
  echo "uninstalled"; exit 0
fi

# Root-owned copy: systemd must not run a script that a non-root user can edit.
install -o root -g root -m 0755 "$HERE/lan-block.sh" /usr/local/sbin/fxocr-lan-block
install -o root -g root -m 0644 "$HERE/fxocr-lan-block.service" /etc/systemd/system/fxocr-lan-block.service
systemctl daemon-reload
systemctl enable fxocr-lan-block.service
systemctl restart fxocr-lan-block.service
/usr/local/sbin/fxocr-lan-block status

CONTAINER=${CONTAINER:-fxocrbot}
if docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "--- probes from $CONTAINER (private targets must be BLOCKED, internet must be REACHABLE)"
  GW=$(ip -4 -o addr show dev br-fxocr 2>/dev/null | awk '{print $4}' | cut -d/ -f1)
  HOSTIP=$(ip -4 route get 1.1.1.1 | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
  ROUTER=$(ip -4 route show default | awk '{print $3; exit}')
  docker exec -i -e GW="$GW" -e HOSTIP="$HOSTIP" -e ROUTER="$ROUTER" "$CONTAINER" python - <<'PY'
import os, socket, sys
want = [(f"router {os.environ['ROUTER']}:80", os.environ['ROUTER'], 80, False),
        (f"host LAN IP {os.environ['HOSTIP']}:22", os.environ['HOSTIP'], 22, False),
        (f"bridge gateway {os.environ['GW']}:22", os.environ['GW'], 22, False),
        ("docker0 172.17.0.1:22", "172.17.0.1", 22, False),
        ("internet api.telegram.org:443", "api.telegram.org", 443, True)]
bad = 0
for name, host, port, should in want:
    s = socket.socket(); s.settimeout(3)
    try:
        s.connect((host, port)); ok = True
    except ConnectionRefusedError:
        ok = True   # an RST came back: the packet got through (port just closed)
    except Exception:
        ok = False  # timeout = dropped by the firewall
    finally:
        s.close()
    verdict = "OK  " if ok == should else "FAIL"
    bad += ok != should
    print(f"{verdict} {name:40s} {'REACHABLE' if ok else 'BLOCKED'}")
sys.exit(1 if bad else 0)
PY
  echo "--- all good"
fi
