#!/usr/bin/env bash
# Block the FxOCRbot container from private/LAN addresses and from the host itself, while keeping
# its internet access (Telegram, package downloads at build time are unaffected).
#
# Why: the bot processes files from strangers. If a parser bug were ever exploited, the worker
# must not be able to reach the router, NAS, admin panels or other containers.
#
# Matches only traffic entering from the bot's bridge (compose sets com.docker.network.bridge.name),
# so nothing else on the host is affected. DNS keeps working: Docker's embedded resolver forwards
# queries from the host namespace, not from the bridge.
#
# Usage (root):  lan-block.sh apply | remove | status        [IFACE env, default br-fxocr]
set -euo pipefail
IFACE=${IFACE:-br-fxocr}
FWD=FXOCR-FWD
IN=FXOCR-IN
PRIVATE4=(10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10 169.254.0.0/16 224.0.0.0/4 240.0.0.0/4)

[[ $EUID -eq 0 ]] || { echo "run as root" >&2; exit 1; }

ensure_chain() { iptables -N "$1" 2>/dev/null || iptables -F "$1"; }
ensure_jump()  { iptables -C "$1" -i "$IFACE" -j "$2" 2>/dev/null || iptables -I "$1" 1 -i "$IFACE" -j "$2"; }
drop_jump()    { while iptables -D "$1" -i "$IFACE" -j "$2" 2>/dev/null; do :; done; }
v6()           { command -v ip6tables >/dev/null 2>&1; }

apply() {
  # Container -> other networks (routed): drop private/LAN destinations.
  ensure_chain "$FWD"
  for net in "${PRIVATE4[@]}"; do iptables -A "$FWD" -d "$net" -j DROP; done
  iptables -A "$FWD" -j RETURN
  iptables -N DOCKER-USER 2>/dev/null || true
  ensure_jump DOCKER-USER "$FWD"

  # Container -> the host itself (any host IP, incl. LAN IP and bridge gateways): drop new connections.
  ensure_chain "$IN"
  iptables -A "$IN" -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
  iptables -A "$IN" -j DROP
  ensure_jump INPUT "$IN"

  # The bridge has no IPv6, but make sure nothing v6 ever leaves it towards the host/LAN.
  if v6; then
    ip6tables -C FORWARD -i "$IFACE" -j DROP 2>/dev/null || ip6tables -I FORWARD 1 -i "$IFACE" -j DROP
    ip6tables -C INPUT -i "$IFACE" -j DROP 2>/dev/null || ip6tables -I INPUT 1 -i "$IFACE" -j DROP
  fi
  echo "lan-block applied on $IFACE"
}

remove() {
  drop_jump DOCKER-USER "$FWD"
  drop_jump INPUT "$IN"
  for c in "$FWD" "$IN"; do iptables -F "$c" 2>/dev/null || true; iptables -X "$c" 2>/dev/null || true; done
  if v6; then
    while ip6tables -D FORWARD -i "$IFACE" -j DROP 2>/dev/null; do :; done
    while ip6tables -D INPUT -i "$IFACE" -j DROP 2>/dev/null; do :; done
  fi
  echo "lan-block removed from $IFACE"
}

status() {
  iptables -S DOCKER-USER 2>/dev/null | grep -- "$FWD" || echo "DOCKER-USER: no jump"
  iptables -S INPUT | grep -- "$IN" || echo "INPUT: no jump"
  iptables -S "$FWD" 2>/dev/null || true
  iptables -S "$IN" 2>/dev/null || true
}

case "${1:-}" in
  apply) apply ;;
  remove) remove ;;
  status) status ;;
  *) echo "usage: $0 apply|remove|status" >&2; exit 2 ;;
esac
