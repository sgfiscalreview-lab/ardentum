#!/bin/sh
# Starts the API image the way Render runs it and fails unless it answers: as the image's
# own non-root user, through its entrypoint (migrations first), against PostgreSQL. Then
# restarts it, as a free instance does when it wakes after sleeping, and checks again.
# Building is not enough: an image whose interpreter its user cannot run builds fine.
#
# Usage: scripts/check_api_image.sh IMAGE DATABASE_URL   (Docker with host networking)
set -eu
image=$1
database_url=$2
port=8000
base="http://127.0.0.1:$port/api/v1"

wait_until_ready() {
  i=0
  while [ "$i" -lt 60 ]; do
    if curl -fsS "$base/health/db" >/dev/null 2>&1; then
      return 0
    fi
    if [ "$(docker inspect -f '{{.State.Running}}' api)" != "true" ]; then
      echo "The container stopped:" >&2
      docker logs api >&2
      return 1
    fi
    i=$((i + 1))
    sleep 3
  done
  echo "No answer from $base/health/db within 3 minutes:" >&2
  docker logs api >&2
  return 1
}

docker run -d --name api --network host \
  -e ARDENTUM_DATABASE_URL="$database_url" -e PORT="$port" "$image" >/dev/null
trap 'docker rm -f api >/dev/null 2>&1 || true' EXIT

echo "Interpreter for the image's user: $(docker exec api python -c 'import sys; print(sys.version.split()[0], sys.executable)' 2>&1 || true)"
wait_until_ready
curl -fsS "$base/health/db" && echo
curl -fsS "$base/meta" && echo

docker restart api >/dev/null
wait_until_ready
echo "Answers again after a restart."
