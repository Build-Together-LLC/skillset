#!/usr/bin/env bash
# Stop everything that belongs to ONE bench (web, socketio, watch, scheduler, worker, redis, vite/esbuild helpers).
# Usage: stop-bench.sh [BENCH_DIR]      (default: ~/frappe/bt)
# Only touches processes whose command line or cwd is inside BENCH_DIR, plus the bench's own redis ports.
# Safe to run when nothing is running. Exits 0 when all four bench ports are free, 1 otherwise.

set -u
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
BENCH_DIR="${1:-$HOME/frappe/bt}"
BENCH_DIR="${BENCH_DIR%/}"
[ -d "$BENCH_DIR/sites" ] || { echo "Not a bench directory: $BENCH_DIR" >&2; exit 2; }

QUEUE_PORT=11000; CACHE_PORT=13000; WEB_PORT=8000; SOCKET_PORT=9000
if [ -f "$BENCH_DIR/sites/common_site_config.json" ]; then
  # Read ports from config when present (falls back to the defaults above).
  read_port() { python3 - "$1" "$2" <<'PY' 2>/dev/null
import json,sys,re
cfg=json.load(open(sys.argv[1]+"/sites/common_site_config.json"))
key=sys.argv[2]
v=cfg.get(key)
if isinstance(v,int): print(v)
elif isinstance(v,str):
    m=re.search(r":(\d+)",v); print(m.group(1) if m else "")
PY
  }
  p=$(read_port "$BENCH_DIR" redis_queue);   [ -n "${p:-}" ] && QUEUE_PORT=$p
  p=$(read_port "$BENCH_DIR" redis_cache);   [ -n "${p:-}" ] && CACHE_PORT=$p
  p=$(read_port "$BENCH_DIR" webserver_port);[ -n "${p:-}" ] && WEB_PORT=$p
  p=$(read_port "$BENCH_DIR" socketio_port); [ -n "${p:-}" ] && SOCKET_PORT=$p
fi

# Safety: never stop while a long-running bench JOB of THIS bench is active (restore, migrate, backup, new-site,
# install-app, drop-site, ...). Killing one mid-way can corrupt the site database. Override with FORCE_STOP=1.
busy=$(pgrep -fl "$BENCH_DIR/env/bin/python.* frappe .*(restore|migrate|backup|new-site|install-app|uninstall-app|drop-site|reinstall)" 2>/dev/null || true)
if [ -n "$busy" ] && [ "${FORCE_STOP:-0}" != "1" ]; then
  echo "REFUSING to stop the bench: a bench job is still running (killing it could corrupt a site database):"
  echo "$busy" | cut -c1-150 | sed 's/^/    /'
  echo "Wait for it to finish, then run this again. (To stop anyway: FORCE_STOP=1 $0 $BENCH_DIR)"
  exit 3
fi

listening() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
any_listening() { listening $WEB_PORT || listening $SOCKET_PORT || listening $QUEUE_PORT || listening $CACHE_PORT; }

echo "Stopping bench at $BENCH_DIR (ports: web $WEB_PORT, socketio $SOCKET_PORT, redis queue $QUEUE_PORT, redis cache $CACHE_PORT)"

# 1. Graceful: Ctrl+C-equivalent to the honcho supervisor that `bench start` runs for THIS bench.
for pid in $(pgrep -f "honcho start" 2>/dev/null); do
  cwd=$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')
  if [ "$cwd" = "$BENCH_DIR" ]; then echo "  SIGINT honcho pid $pid"; kill -INT "$pid" 2>/dev/null; fi
done
for _ in $(seq 1 15); do any_listening || break; sleep 1; done

# 2. Redis: ask nicely (queue is saved, cache is disposable).
if listening $QUEUE_PORT; then echo "  redis queue shutdown"; redis-cli -p $QUEUE_PORT shutdown >/dev/null 2>&1; fi
if listening $CACHE_PORT; then echo "  redis cache shutdown"; redis-cli -p $CACHE_PORT shutdown nosave >/dev/null 2>&1; fi
sleep 1

# 3. Leftovers: anything still running out of this bench's env/ or apps/ (python, node, vite, esbuild, flow).
leftovers=$(pgrep -f "$BENCH_DIR/(env|apps|flow-server)" 2>/dev/null | grep -v "^$$\$" || true)
if [ -n "$leftovers" ]; then
  echo "  TERM leftovers: $(echo $leftovers | tr '\n' ' ')"
  kill -TERM $leftovers 2>/dev/null
  sleep 2
  still=$(pgrep -f "$BENCH_DIR/(env|apps|flow-server)" 2>/dev/null | grep -v "^$$\$" || true)
  [ -n "$still" ] && { echo "  KILL stubborn: $(echo $still | tr '\n' ' ')"; kill -KILL $still 2>/dev/null; sleep 1; }
fi

# 4. Report.
rc=0
for p in $WEB_PORT $SOCKET_PORT $QUEUE_PORT $CACHE_PORT; do
  if listening "$p"; then echo "  port $p: STILL LISTENING"; lsof -nP -iTCP:"$p" -sTCP:LISTEN | tail -n +2 | awk '{print "    "$1" pid "$2}'; rc=1; else echo "  port $p: free"; fi
done
[ $rc -eq 0 ] && echo "Bench stopped." || echo "Some ports are still in use (another app, or a process outside this bench)."
exit $rc
