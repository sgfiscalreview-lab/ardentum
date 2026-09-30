# Publishing a release with a DOI

A DOI (a permanent citation link) comes from Zenodo, which archives a copy of the code
each time a GitHub release is published. Connect Zenodo **before** publishing the
release; releases made earlier are not archived.

## One-time set-up (about 5 minutes)

1. Go to https://zenodo.org and choose **Log in**, then **Log in with GitHub**.
2. Open your name (top right), then **GitHub**.
3. Find `sgfiscalreview-lab/ardentum` in the list and switch it **On**. If it is not
   listed, choose **Sync now** and wait a minute. The repository must be public.
4. In `CITATION.cff`, replace `name: "The Ardentum authors"` with your own name in
   the form Zenodo expects:

   ```yaml
   authors:
     - family-names: "Your family name"
       given-names: "Your given name"
   ```

   Do the same on the second line of `LICENSE` if you want your name there, and add
   `date-released: "YYYY-MM-DD"` (the release date) to `CITATION.cff`. Commit to
   `main`.

## Each release

1. On GitHub, open **Releases**, then **Draft a new release**.
2. **Choose a tag**: type `v1.0.0` and choose **Create new tag on publish**; target
   `main`.
3. **Release title**: `Ardentum 1.0.0`.
4. **Description**: paste the contents of `docs/releases/v1.0.0.md`.
5. **Publish release**.
6. After a few minutes Zenodo shows the new record under **Uploads**, with a DOI
   such as `10.5281/zenodo.1234567`. Copy the DOI badge from the record into
   `README.md` (in the "Citing Ardentum" section) and commit.

For later versions, update `CHANGELOG.md`, bump the version in
`backend/pyproject.toml`, `backend/src/ardentum/__init__.py` and
`frontend/package.json` (then `uv lock` and `npm install`), write
`docs/releases/vX.Y.Z.md`, and repeat the steps above. Zenodo keeps one "concept"
DOI for all versions plus one DOI per version.
