#!/usr/bin/env bash
# Manual production deploy, guarded so the deployed source always exists in git.
#
# Pushes normally reach production through Vercel's GitHub integration, which
# can only ever build committed code. This script exists for shipping straight
# from a workstation, so it refuses to run unless the tree is clean and HEAD
# matches origin: a deploy from uncommitted state leaves production running code
# that no commit contains, and the next push silently reverts it.
#
# Usage: scripts/deploy.sh [extra vercel deploy flags]
set -euo pipefail

PRODUCTION_BRANCH="${PRODUCTION_BRANCH:-Booking-Tours-Marketplace}"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "error: not inside a git repository" >&2
    exit 1
fi

branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" != "$PRODUCTION_BRANCH" ]; then
    echo "error: on '$branch', but production deploys from '$PRODUCTION_BRANCH'" >&2
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "error: the working tree has uncommitted changes:" >&2
    git status --short >&2
    echo >&2
    echo "Commit them, or stash them: production has to build from a commit." >&2
    exit 1
fi

git fetch --quiet origin "$PRODUCTION_BRANCH"
head=$(git rev-parse HEAD)
remote=$(git rev-parse "origin/$PRODUCTION_BRANCH")
if [ "$head" != "$remote" ]; then
    echo "error: HEAD ($head) is not on origin/$PRODUCTION_BRANCH ($remote)" >&2
    echo "Push it and let Vercel's integration deploy, or push first." >&2
    exit 1
fi

echo "Deploying $head from $branch to production..."
exec vercel deploy --prod --yes "$@"
