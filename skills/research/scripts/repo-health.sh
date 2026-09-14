#!/usr/bin/env bash
# Print a markdown maintenance-health table for one or more GitHub repos.
# Usage: repo-health.sh owner/repo [owner/repo ...]
# Needs: gh (logged in), jq.
#
# Stars measure attention; the other columns measure whether anyone still maintains the project.
# Bot commits and bot contributors (dependabot, renovate, github-actions, ...) are counted apart from
# human ones, because a repo that only bots touch looks busy but is not maintained. A failure on one
# repo prints an error row and moves on to the next.
set -uo pipefail

since=$(date -u -v-90d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '90 days ago' +%Y-%m-%dT%H:%M:%SZ)
year_ago=$(date -u -v-365d +%Y-%m-%d 2>/dev/null || date -u -d '365 days ago' +%Y-%m-%d)
today=$(date -u +%Y-%m-%d)
max_pages=5 # default-branch history is scanned newest first, 100 commits per page, up to this many pages

# Case-insensitive; matched against commit author names and logins, and contributor logins.
bot_re='\[bot\]$|^(github-actions|dependabot|renovate|pre-commit-ci|mergify)\b'

meta_q='query($owner: String!, $name: String!, $since: GitTimestamp!) {
  repository(owner: $owner, name: $name) {
    stargazerCount
    isArchived
    licenseInfo { spdxId }
    issues(states: OPEN) { totalCount }
    pullRequests(states: OPEN) { totalCount }
    latestRelease { publishedAt }
    releases(first: 10, orderBy: {field: CREATED_AT, direction: DESC}) { nodes { publishedAt } }
    refs(refPrefix: "refs/tags/", first: 1, orderBy: {field: TAG_COMMIT_DATE, direction: DESC}) {
      nodes { target { ... on Commit { committedDate } ... on Tag { target { ... on Commit { committedDate } } } } }
    }
    defaultBranchRef { target { ... on Commit { history(since: $since) { totalCount } } } }
  }
}'

hist_q='query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef { target { ... on Commit {
      history(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { committedDate author { name user { login } } }
      }
    } } }
  }
}'

# Scan recent default-branch history. Prints one JSON object:
# {human: commits by humans in 90d, authors: distinct human authors in 90d, last_human: date, capped, more}
scan_history() {
  local owner=$1 name=$2 cursor="" nodes='[]' page hist more=false capped=false stop i
  local args
  for ((i = 1; i <= max_pages; i++)); do
    args=(-f query="$hist_q" -f owner="$owner" -f name="$name")
    [ -n "$cursor" ] && args+=(-f cursor="$cursor")
    page=$(gh api graphql "${args[@]}" 2>/dev/null) || return 1
    hist=$(jq -c '.data.repository.defaultBranchRef.target.history // empty' <<<"$page")
    [ -z "$hist" ] && break # empty repo
    nodes=$(jq -c --argjson h "$hist" '. + $h.nodes' <<<"$nodes")
    more=$(jq -r '.pageInfo.hasNextPage' <<<"$hist")
    cursor=$(jq -r '.pageInfo.endCursor // ""' <<<"$hist")
    # Stop once we are past the 90-day window and have seen at least one human commit.
    stop=$(jq -r --arg since "$since" --arg re "$bot_re" '
      def bot: ((.author.name // "") | test($re; "i")) or ((.author.user.login // "") | test($re; "i"));
      (last.committedDate < $since) and any(.[]; bot | not)' <<<"$nodes")
    [ "$more" != true ] || [ "$stop" = true ] && break
  done
  # Capped: pages ran out while still inside the 90-day window, so the human counts are lower bounds.
  if [ "$more" = true ] && [ "$(jq -r --arg since "$since" 'last.committedDate >= $since' <<<"$nodes")" = true ]; then
    capped=true
  fi
  jq -c --arg since "$since" --arg re "$bot_re" --argjson capped "$capped" --argjson more "$more" '
    def bot: ((.author.name // "") | test($re; "i")) or ((.author.user.login // "") | test($re; "i"));
    map(select(bot | not)) as $humans
    | ($humans | map(select(.committedDate >= $since))) as $recent
    # Commits from an email not linked to GitHub carry only a name; map it to the login that
    # name uses elsewhere, so one person with two commit identities counts once.
    | ($humans | map(select(.author.user.login and .author.name)
        | {key: (.author.name | ascii_downcase), value: .author.user.login}) | from_entries) as $logins
    | {human: ($recent | length),
       authors: ($recent | map(.author.user.login // $logins[(.author.name // "") | ascii_downcase] // .author.name)
         | unique | length),
       last_human: (($humans | first | .committedDate) // "" | .[:10]),
       capped: $capped, more: $more}' <<<"$nodes"
}

# Print one table row for owner/repo.
row() {
  local repo=$1 owner=${1%%/*} name=${1#*/}
  local meta stars archived licence issues_prs commits rel_date rel_kind hist human authors last_human capped plus contribs
  meta=$(gh api graphql -f query="$meta_q" -f owner="$owner" -f name="$name" -f since="$since" 2>/dev/null |
    jq -ce '.data.repository // empty') || {
    echo "| $repo | not found or no access | | | | | | | | |"
    return
  }

  stars=$(jq -r .stargazerCount <<<"$meta")
  archived=$(jq -r .isArchived <<<"$meta")
  licence=$(jq -r '.licenseInfo.spdxId // "none"' <<<"$meta")
  issues_prs=$(jq -r '"\(.issues.totalCount) / \(.pullRequests.totalCount)"' <<<"$meta")
  commits=$(jq -r '.defaultBranchRef.target.history.totalCount // 0' <<<"$meta")

  # Latest full release; else the newest pre-release; else the newest tag, for projects that only tag.
  read -r rel_date rel_kind < <(jq -r '
    if .latestRelease then [.latestRelease.publishedAt[:10], ""]
    # Drafts have no publishedAt (and are visible to anyone with push access), so skip them.
    elif ([.releases.nodes[] | select(.publishedAt)] | length) > 0 then
      [([.releases.nodes[] | select(.publishedAt)][0].publishedAt[:10]), "(pre-release)"]
    elif (.refs.nodes | length) > 0 then
      [((.refs.nodes[0].target.committedDate // .refs.nodes[0].target.target.committedDate // "none")[:10]), "(tag only)"]
    else ["none", ""] end | @tsv' <<<"$meta")

  if hist=$(scan_history "$owner" "$name"); then
    human=$(jq -r .human <<<"$hist")
    authors=$(jq -r .authors <<<"$hist")
    last_human=$(jq -r .last_human <<<"$hist")
    capped=$(jq -r .capped <<<"$hist")
    [ -z "$last_human" ] && { [ "$(jq -r .more <<<"$hist")" = true ] && last_human="none in last $((max_pages * 100))" || last_human="none"; }
  else
    human="?" authors="?" last_human="?" capped=false
  fi
  plus=""
  [ "$capped" = true ] && plus="+"

  # All-time human contributors. GitHub links only the first 500 author emails to accounts, so large
  # repos are undercounted; 400 or more is shown as a lower bound.
  contribs=$(gh api "repos/$repo/contributors?per_page=100" --paginate \
    --jq ".[] | select(.type != \"Bot\" and (.login | test(\"$(sed 's/\\/\\\\/g' <<<"$bot_re")\"; \"i\") | not)) | .login" \
    2>/dev/null | wc -l | tr -d ' ') || contribs="?"
  [ "$contribs" != "?" ] && [ "$contribs" -ge 400 ] && contribs="$contribs+"

  local flags=() flag_text
  [ "$archived" = true ] && flags+=("ARCHIVED")
  [ "$human" = 0 ] && flags+=("no human commits in 90d")
  [ "$authors" != "?" ] && [ -z "$plus" ] && [ "$authors" -lt 3 ] && flags+=("under 3 human authors in 90d")
  if [ "$rel_date" = none ]; then
    flags+=("never released")
  elif [[ "$rel_date" < "$year_ago" ]]; then
    flags+=("no release in 12 months")
  fi
  case "$licence" in
    AGPL* | GPL* | SSPL* | BUSL* | Elastic* | CC-BY-NC*) flags+=("licence: $licence") ;;
    NOASSERTION) flags+=("licence: custom, read it") ;;
    none) flags+=("licence: none") ;;
  esac
  flag_text=$(IFS=';'; echo "${flags[*]:-}" | sed 's/;/; /g')

  echo "| $repo | $stars | $commits ($human$plus) | $authors$plus | $last_human | $contribs | $rel_date${rel_kind:+ $rel_kind} | $issues_prs | $licence | ${flag_text:+⚠ $flag_text} |"
}

echo '| Repo | Stars | Commits 90d (human) | Human authors 90d | Last human commit | Contributors | Last release | Open issues / PRs | Licence | Flags |'
echo '|---|---:|---:|---:|---|---:|---|---:|---|---|'

# Fetch all repos in parallel, then print the rows in the order given.
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
i=0
for repo in "$@"; do
  row "$repo" >"$tmp/$i" &
  i=$((i + 1))
done
wait
for ((j = 0; j < i; j++)); do cat "$tmp/$j"; done

echo
echo "Checked $today via the GitHub GraphQL and REST APIs. Human counts exclude bot accounts. \"+\" marks a lower bound (scan or API cap). Commits are on the default branch."
