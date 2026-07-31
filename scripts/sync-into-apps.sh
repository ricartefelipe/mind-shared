#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source="$root/mind-shared/openapi/vuemind-wallet-openapi.yaml"

for app in vuemind reactmind angularmind; do
  target="$root/$app/docs/contracts/vuemind-wallet-openapi.yaml"
  mkdir -p "$(dirname "$target")"
  cp "$source" "$target"
done

echo "Contrato sincronizado nos aplicativos. Para desenvolvimento local, use \"@ricartefelipe/mind-wallet-shared\": \"file:../mind-shared\" em cada package.json."
