# Updating a4v2i8g6/KramerAV to v0.2.0

Because the GitHub connection currently does not permit writing branches, the updated repository contents are packaged in `KramerAV_v0.2.0-alpha.zip`.

1. Extract the ZIP, preserving hidden directories such as `.github`.
2. Copy/commit the files into the repository root, not as a nested `KramerAV_v0.2.0-alpha` folder.
3. Check the diff and preferably open a pull request to `main`. Do not overwrite unrelated new commits.
4. GitHub Actions should run `python -m unittest discover -s tests -v`, Python compilation, and validation.
5. Install on a test Home Assistant instance and verify an actual Kramer model before assigning production automations.

The integration domain remains `kramer_av_routing`. Revisit output entity IDs on devices that switch from a legacy command family to X-ROUTE.
