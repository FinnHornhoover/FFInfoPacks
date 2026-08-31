# Retrobution Exclusion Editor

Static Vite application for reviewing and updating `config/exclude-retrobution.yml`. Item metadata, icons, and the catalog build time are encrypted at build time, while banned status is fetched live after unlock.

## Local testing

Requirements: Node.js 22, Python 3, Docker, and `yq` v4.

The released artifact is already filtered, so banned items will be missing. To build a complete unfiltered artifact first:

```sh
export SSH_PRIVATE_KEY='...'
export SSH_PASSPHRASE='...'
export EDITOR_KEY='...'
mkdir -p editor-artifacts
docker build \
  --build-arg FFINFO_FORCED_BUILD=retrobution \
  --build-arg FFINFO_SKIP_FILTERING=1 \
  --tag ffinfo-editor-artifact \
  --secret id=SSH_PRIVATE_KEY,env=SSH_PRIVATE_KEY \
  --secret id=SSH_PASSPHRASE,env=SSH_PASSPHRASE \
  .
container_id="$(docker create ffinfo-editor-artifact)"
revision="$(yq -r '.config.retrobution.revision' config/build-config.yml)"
docker cp \
  "$container_id:/app/artifacts/retrobution_r${revision}.zip" \
  "editor-artifacts/retrobution_r${revision}_unfiltered.zip"
docker rm "$container_id"
python scripts/pack_editor_catalog.py \
  "editor-artifacts/retrobution_r${revision}_unfiltered.zip" \
  retrobution-exclude-editor/public/catalog.enc
```

Configure the local Pages Function:

```sh
cp retrobution-exclude-editor/.dev.vars.example retrobution-exclude-editor/.dev.vars
```

Set the same `EDITOR_KEY` in `.dev.vars`, then add `GITHUB_TOKEN`, `GITHUB_OWNER`, and `GITHUB_REPO`. Use a fork if you intend to test Submit.

Build and serve the app with its Pages Function:

```sh
npm run build --prefix retrobution-exclude-editor
npm run preview:pages --prefix retrobution-exclude-editor
```

Open the URL printed by Wrangler and enter `EDITOR_KEY`. The Refresh catalog button dispatches `.github/workflows/editor.yml`, polls its run status, and prompts you to reload after deployment.

## Deployment configuration

GitHub Actions secrets:

- `SSH_PRIVATE_KEY`
- `SSH_PASSPHRASE`
- `EDITOR_KEY`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

GitHub Actions variable:

- `CLOUDFLARE_PAGES_PROJECT`

Cloudflare Pages Function secrets:

- `EDITOR_KEY`: must match the key used to encrypt the catalog.
- `GITHUB_TOKEN`: fine-grained token scoped to the target repository with Contents read/write and Actions read/write permissions.

Optional Pages variables `GITHUB_OWNER` and `GITHUB_REPO` default to `FinnHornhoover` and `FFInfoPacks`. The editor workflow can be run manually and is also called by the release workflow when a release is created.

The function only updates `config/exclude-retrobution.yml` on `main` and rejects concurrent changes using GitHub's blob SHA. Rotating `EDITOR_KEY` requires rebuilding the catalog and updating the Pages secret.
