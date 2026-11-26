#!/usr/bin/env bash
set -e
echo "==> pull with submodules"
git pull --rebase --recurse-submodules
echo "==> submodule status"
git submodule status --recursive
echo "==> repo status"
git status