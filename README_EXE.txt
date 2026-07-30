NITEOS CONCEPT LIGHT v1.3.9
===========================

This package is prepared for building a portable Windows EXE.

HOW TO BUILD
------------
1. Extract this ZIP into a separate folder, for example:
   C:\Users\ASUS\Desktop\niteos_concept_light_build

2. Open the extracted folder.

3. Run:
   build_exe.bat

4. Wait until the build is complete.

5. The portable application folder will be:
   dist\NITEOS_Concept_Light

6. Run:
   dist\NITEOS_Concept_Light\NITEOS_Concept_Light.exe

IMPORTANT
---------
Move the whole folder to another computer:
   dist\NITEOS_Concept_Light

Do not move only the EXE. The program needs its folder structure for:
- input
- ies_library
- references
- output
- project_export

If Windows Defender warns you:
This is common for unsigned PyInstaller builds. For internal testing, allow the app.
For commercial distribution, use code signing later.

LOGO FIX
--------
v1.3.7 fixes logo/resource paths in PyInstaller one-folder builds.

RGBW FIX
--------
v1.3.8: RGBW alone no longer means Russian flag. Flag mode only if prompt says flag/tricolor or white+blue+red.

RGBW NEUTRAL WORDING
--------------------
v1.3.9: generic RGBW wording is neutral and no longer mentions Russian flag/tricolor unless explicitly requested.
