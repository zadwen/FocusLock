FocusLock Windows single-instance lock fix

Apply to the FocusLock-v2-upgrade project you already extracted.

1. Close FocusLock if it is running.
2. Extract this ZIP into the existing FocusLock project folder (the folder containing build.bat).
3. Allow replacement of src/platform_support.py and tests/test_core.py.
4. In PowerShell, from that project folder, run:

   .\.venv-build\Scripts\python.exe .\scripts\build.py

5. If tests and the build succeed, run:

   .\dist\FocusLock.exe

The fixed lock acquires byte zero without reading or writing it first.
Windows locks can cover bytes beyond EOF, so initializing the file is unnecessary.
Failed lock acquisition closes its handle and reports the existing instance.

Verification: 23 core tests passed locally on Linux, including two Windows-backend
regressions with a simulated backend. Native Windows confirmation remains for
your rebuild; the existing real single-instance test has not been removed.
The complete suite now has 29 tests when a GUI is available.

This is a targeted patch, not a complete app or a prebuilt Windows EXE.

References:
https://docs.python.org/3/library/msvcrt.html#msvcrt.locking
https://learn.microsoft.com/en-us/windows/win32/fileio/locking-and-unlocking-byte-ranges-in-files
