#!/usr/bin/env bash
# Search Reddit posts through Reddit's Data API, for attention data in /research notes. The
# credentials stay in the macOS keychain and inside this script, so the agent that runs it never
# sees them: its guard blocks `security`, and the secret never appears in a command line.
#
# Usage: reddit-search.sh "<query>" [subreddit] [top|relevance|new|comments] [hour|day|week|month|year|all]
#   e.g. reddit-search.sh "rightsizing" kubernetes top year
#
# Prints a markdown table (date, subreddit, title, score, comments, URL), then a line to cite.
# If there are no credentials, or Reddit refuses, it says "Reddit unavailable" and why, and
# exits 1: write "Reddit unavailable" in the note rather than fetching reddit.com pages, which
# return block pages to scripts. There is no fallback: the pullpush.io archive refuses agents
# (HTTP 429, checked 2026-09-14).
#
# One-time setup, by hand:
#   1. Signed in to Reddit, open https://www.reddit.com/prefs/apps and create an app of type
#      "script" (redirect URI http://localhost:8080). Reddit may ask you to request API access
#      first; follow its form. The client ID is the string under the app's name.
#   2. Store the ID, the secret and your username in the login keychain:
#        security add-generic-password -s reddit-search -a client-id -w '<client id>'
#        security add-generic-password -s reddit-search -a client-secret -w '<secret>'
#        security add-generic-password -s reddit-search -a username -w '<reddit username>'
#   3. Test: ~/.claude/skills/research/scripts/reddit-search.sh "rightsizing" kubernetes
# Reads only: an app-only token (client_credentials grant), then one search. Rate-limited to
# one request per second.
set -uo pipefail

usage() {
  sed -n '6,7p' "$0" >&2
  exit 2
}
unavailable() {
  echo "Reddit unavailable: $1"
  exit 1
}
[ $# -ge 1 ] && [ -n "$1" ] || usage
query=$1 sub=${2:-} sort=${3:-top} window=${4:-year}
[[ -z $sub || $sub =~ ^[A-Za-z0-9_]{2,21}$ ]] || { echo "subreddit should be a name like kubernetes, without r/" >&2; exit 2; }
[[ $sort =~ ^(top|relevance|new|comments)$ ]] || usage
[[ $window =~ ^(hour|day|week|month|year|all)$ ]] || usage

secret() { security find-generic-password -s reddit-search -a "$1" -w 2>/dev/null; }
id=$(secret client-id) && key=$(secret client-secret) ||
  unavailable "no credentials in the keychain (service reddit-search); see the setup steps at the top of $0"
user=$(secret username) || user=unknown
ua="macos:notes-research-reddit-search:v1.0 (by /u/$user)"

# curl reads the credentials and the token from a config on stdin, never from its arguments.
resp=$(printf 'user = "%s:%s"\n' "$id" "$key" |
  curl -s -m 20 -A "$ua" -K - -w '\n%{http_code}' -d grant_type=client_credentials \
    https://www.reddit.com/api/v1/access_token) || unavailable "couldn't reach www.reddit.com"
code=${resp##*$'\n'}
token=$(jq -r '.access_token // empty' <<<"${resp%$'\n'*}" 2>/dev/null)
[ "$code" = 200 ] && [ -n "$token" ] || unavailable "the token request returned HTTP $code; check the app's ID and secret"
unset key resp

sleep 1
q=$(jq -rn --arg q "$query" '$q | @uri')
if [ -n "$sub" ]; then
  path="/r/$sub/search" extra="&restrict_sr=1"
else
  path="/search" extra=""
fi
url="https://oauth.reddit.com$path?q=$q&sort=$sort&t=$window&type=link&limit=25&raw_json=1$extra"
resp=$(printf 'header = "Authorization: bearer %s"\n' "$token" |
  curl -s -m 20 -A "$ua" -K - -w '\n%{http_code}' "$url") || unavailable "couldn't reach oauth.reddit.com"
code=${resp##*$'\n'}
[ "$code" = 200 ] || unavailable "the search returned HTTP $code"

echo "| Date | Subreddit | Title | Score | Comments | URL |"
echo "|---|---|---|---:|---:|---|"
jq -r '
  .data.children[].data
  | [(.created_utc | floor | todate | .[:10]), "r/\(.subreddit)",
     (.title | gsub("\\|"; "\\|") | gsub("\n"; " ")), (.score | tostring),
     (.num_comments | tostring), "https://www.reddit.com\(.permalink)"]
  | "| " + join(" | ") + " |"' <<<"${resp%$'\n'*}" || unavailable "the response wasn't the expected JSON"
echo "Source: Reddit Data API, GET https://oauth.reddit.com$path?q=$q&sort=$sort&t=$window (\`reddit-search.sh \"$query\"${sub:+ $sub} $sort $window\`), checked $(date -u +%Y-%m-%d)"
