# Cordia Desktop

This Electron shell displays the existing Cordia cloud workspace without
duplicating its state locally. Its default target is `https://cordiacode.com`.

For a local development preview only, set `CORDIA_DESKTOP_URL` to a `http`
localhost URL. Other origins are rejected at launch.

## Security boundary

- Renderer Node integration is disabled.
- Context isolation and sandboxing are enabled.
- The preload bridge exposes only `window.cordiaDesktop.getRuntimeInfo()` and
  `window.cordiaDesktop.pickRepository()`.
- New browser windows are denied.

The repository picker requires the user to select a Git repository directory.
It returns only a stable opaque identifier, folder label, Git-root flag, and
branch name. It does not return an absolute path, read project files, or expose
shell access.
