# sinairusinek.github.io

Front door for this account: an index of every **public** GitHub Pages site
published from it, live at <https://sinairusinek.github.io/>.

GitHub has no built-in way to browse your Pages sites. The repository tab
filters by language, type and visibility, never by whether Pages is enabled;
`has_pages` is exposed only through the REST API. Hence this page.

## How it works

`scripts/build.py` lists the account's repos, keeps those with
`has_pages == true` that are **public**, probes each site for its HTTP status
and `<title>`, and writes `index.html`. The workflow commits the result only
when it changed.

Rebuilds run Mondays at 06:00 UTC, on pushes that touch the generator, and
whenever you press **Run workflow** on the Actions tab.

## Private-repo sites are omitted

Two Pages sites are served from private repos. They are left out on purpose.

Everything this repo serves is public — GitHub Pages has no access control on
personal accounts, and an unlinked path is not a private one. A "secret" route
would also appear in this public repo's history. Listing those URLs here would
therefore turn link-only sites into discoverable ones.

The footer links to a fuller list held outside this repo, which opens only for
accounts it has been shared with. To regenerate the complete list locally:

```sh
gh api --paginate "/user/repos?per_page=100&affiliation=owner" \
  --jq '.[] | select(.has_pages) | [.name, .private] | @tsv'
```

## The token

A workflow's default `GITHUB_TOKEN` is scoped to this repository alone, so it
cannot enumerate the account's other repos. Without a better token the build
finds nothing and exits non-zero rather than publishing an empty index.

To give it proper access, add a repository secret named `PAGES_INDEX_TOKEN`:

1. Create a fine-grained PAT at
   <https://github.com/settings/personal-access-tokens/new> —
   all repositories, **Repository permissions → Metadata: Read-only**.
   Nothing else is needed; the build only reads repo listings.
2. Add it at
   <https://github.com/sinairusinek/sinairusinek.github.io/settings/secrets/actions>
   as `PAGES_INDEX_TOKEN`.

Fine-grained PATs expire. When one does, the workflow starts failing — the
build exits with an error instead of committing a truncated list, so a stale
token never silently shortens the index.

## Running it locally

```sh
GITHUB_TOKEN=$(gh auth token) python3 scripts/build.py
```

Writes `index.html` in the repo root; open it directly in a browser.
