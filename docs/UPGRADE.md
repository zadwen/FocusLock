# Apply the v2 upgrade

This package contains an upgraded working tree. It has not been pushed to GitHub or published as a release by the assistant.

## With Git (recommended)

1. Make a backup of your existing checkout and ensure any personal changes are committed.
2. In your existing `FocusLock` repository, create a branch:

   ```bash
   git switch -c upgrade/windows-linux-v2
   ```

3. Copy the contents of the supplied `FocusLock` source folder into that repository, including `.github`, replacing matching files. Do not copy an unrelated `.git` folder.
4. Remove the old **nested** `FocusLock/` folder inside the repository and the old root `workflows/` directory. These are obsolete duplicates; the canonical app is now in root `src/` and automation in `.github/workflows/`.
5. Inspect and commit:

   ```bash
   git status
   git diff
   python3 -m unittest discover -s tests -v
   git add -A
   git commit -m "Upgrade FocusLock design, session reliability and Windows/Linux releases"
   git push -u origin upgrade/windows-linux-v2
   ```

   On Windows use `py -3` instead of `python3`.

6. Open a pull request, let Actions finish, test the downloaded builds, and merge when satisfied.
7. On the merged default branch, create/push `v2.0.0` as described in the README. This generates the actual `.exe` download; the source ZIP itself is not a Windows executable.

## Existing data

Windows keeps using `%APPDATA%\FocusLock`. Linux uses `$XDG_CONFIG_HOME/FocusLock` or `~/.config/FocusLock`. Existing Windows v1 configuration and hashes remain readable; old total minutes convert to seconds. No historical accuracy can be recovered from v1's overcounted time.

The old tray option is replaced by an explicit minimize-to-taskbar option. There is no auto-started focus session. Linux defaults use Linux process names; review migrated Windows `.exe` names if you copy configuration between systems.
