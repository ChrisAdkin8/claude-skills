#!/usr/bin/env bash
# Look up GCP list prices in the Cloud Billing Catalog API, the only machine-readable Google
# pricing source. The access token stays inside this script, so the agent that runs it never
# sees it and can't send it anywhere else.
#
# Usage:
#   gcp-skus.sh --services <name regex>              find a service's ID, e.g. "Compute Engine"
#   gcp-skus.sh <service-id> <description regex> [region]
#       e.g. gcp-skus.sh 6F81-5844-456A 'E2 Instance Core' europe-west2
#
# Prints one row per matching SKU: description, regions, unit and USD price per tier, then a
# line to cite. Needs gcloud logged in; if it isn't, says so and exits 1.
set -euo pipefail

api=https://cloudbilling.googleapis.com/v1
usage() {
  sed -n '6,8p' "$0" >&2
  exit 2
}
[ $# -ge 2 ] || usage

token=$(gcloud auth print-access-token 2>/dev/null) || {
  echo "gcloud isn't logged in, so GCP prices can't be checked against a Google source; mark them (unverified)" >&2
  exit 1
}

# Follow nextPageToken, printing each page's JSON on its own line.
fetch() {
  local url=$1 page="" resp
  while :; do
    resp=$(curl -sf -H "Authorization: Bearer $token" "$url${page:+&pageToken=$page}") || {
      echo "request failed: ${url%%\?*}" >&2
      exit 1
    }
    printf '%s\n' "$resp"
    page=$(jq -r '.nextPageToken // ""' <<<"$resp")
    [ -n "$page" ] || break
  done
}

if [ "$1" = --services ]; then
  fetch "$api/services?pageSize=5000" |
    jq -r --arg f "$2" '.services[] | select(.displayName | test($f; "i")) | "\(.serviceId)  \(.displayName)"'
  echo "Source: Cloud Billing Catalog API, GET $api/services, checked $(date -u +%Y-%m-%d)"
  exit 0
fi

svc=$1 filter=$2 region=${3:-}
[[ $svc =~ ^[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}$ ]] || {
  echo "service ID should look like 6F81-5844-456A; find it with --services" >&2
  exit 2
}
fetch "$api/services/$svc/skus?currencyCode=USD&pageSize=5000" |
  jq -r --arg f "$filter" --arg r "$region" '
    .skus[]
    | select(.description | test($f; "i"))
    | select($r == "" or (.serviceRegions | index($r)))
    | .pricingInfo[0].pricingExpression as $p
    | [.description, (.serviceRegions | join(",")), $p.usageUnitDescription,
       ($p.tieredRates | map("from \(.startUsageAmount): $\((.unitPrice.units // "0" | tonumber) + (.unitPrice.nanos // 0) / 1e9)") | join("; "))]
    | join(" | ")'
echo "Source: Cloud Billing Catalog API, GET $api/services/$svc/skus?currencyCode=USD (description ~ /$filter/${region:+, region $region}), checked $(date -u +%Y-%m-%d)"
