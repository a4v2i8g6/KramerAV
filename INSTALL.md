# KramerAV initial GitHub CI

Copy `.github/workflows/validate.yml` to the root of the `a4v2i8g6/KramerAV` repository, preserving the folder structure.

Using GitHub's web UI:
1. Open the repository and choose Add file > Create new file.
2. Enter `.github/workflows/validate.yml` as the filename.
3. Paste the YAML contents of the included file.
4. Commit the new file (preferably on a feature branch with a pull request).
5. Open the Actions tab and check the `Kramer AV Routing validation` workflow.

This workflow runs two local unit-test versions, Python compilation, Home Assistant's hassfest and HACS repository validation. The external validators may find issues in the existing prototype. CI success does not prove compatibility with real Kramer hardware.

Documentation:
https://www.hacs.dev/docs/publish/action/
https://contributors.home-assistant.io/marketplace/reference/validation/
