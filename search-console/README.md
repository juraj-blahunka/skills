# search-console

How this skill is put together and set up.
This file is for people; the agent reads `SKILL.md` only.

## Files

| Path | What it is |
|---|---|
| `SKILL.md` | Agent instructions: commands, how to debug with them, API limits |
| `scripts/gsc.py` | The CLI, a `uv` inline script that installs its own dependencies (`google-auth`, `requests`) |
| `~/.claude/skills/search-console` | Symlink to this directory, made by the repo's `install.sh` |
| `~/.config/search-console/service-account.json` | Service account key, mode 600, never in a repo; override with `GSC_CREDENTIALS` |
| `~/.config/search-console/site` | Default property, one line such as `sc-domain:example.com`; override with `GSC_SITE` or `--site` |

## How it is wired

The CLI signs in as a Google Cloud service account and calls the Search Console API directly.
Search Console does not use Cloud IAM roles: the service account is added as a user on each property, like a person would be.
Read commands request the `webmasters.readonly` scope; sitemap `submit` and `delete` request `webmasters`.

## Setup

Done once per machine, with the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (`brew install --cask gcloud-cli`).

```sh
gcloud auth login
P=search-console-$(openssl rand -hex 3)
gcloud projects create "$P" --name="Search Console API"
gcloud services enable searchconsole.googleapis.com --project "$P"
gcloud iam service-accounts create search-console-reader --display-name="Search Console reader" --project "$P"
mkdir -p ~/.config/search-console && chmod 700 ~/.config/search-console
(umask 077; gcloud iam service-accounts keys create ~/.config/search-console/service-account.json \
  --iam-account "search-console-reader@$P.iam.gserviceaccount.com" --project "$P")
echo 'sc-domain:example.com' > ~/.config/search-console/site
```

Key creation can fail with `NOT_FOUND` for a few seconds after the account is created, and the new key can fail with `Invalid JWT Signature` for about a minute; retry both.

Then in Search Console, open the property, Settings, Users and permissions, Add user, and paste the service account email.
Restricted is enough to read; Full also allows sitemap submit and delete.
A domain property (`sc-domain:`) covers every subdomain, so one grant is usually enough.

Check it with:

```sh
uv run scripts/gsc.py whoami
uv run scripts/gsc.py sites
```

## Rotating or removing access

- New key: `gcloud iam service-accounts keys create` as above, then delete the old one with `gcloud iam service-accounts keys list` and `keys delete`.
- Revoke: remove the user in Search Console, or delete the service account or the whole project.
