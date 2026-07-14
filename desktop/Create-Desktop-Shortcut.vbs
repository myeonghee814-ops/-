' Run this once (double-click) to create Desktop shortcuts for launching
' and stopping BLIP. Safe to run again later -- it just overwrites them.
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set shell = CreateObject("WScript.Shell")
desktop = shell.SpecialFolders("Desktop")

Set startLink = shell.CreateShortcut(desktop & "\BLIP.lnk")
startLink.TargetPath = scriptDir & "\Launch-BLIP.vbs"
startLink.WorkingDirectory = scriptDir
startLink.IconLocation = "%SystemRoot%\System32\SHELL32.dll,13"
startLink.Description = "Launch BLIP (Battery Literature Intelligence Platform)"
startLink.Save

Set stopLink = shell.CreateShortcut(desktop & "\Stop BLIP.lnk")
stopLink.TargetPath = scriptDir & "\Stop-BLIP.vbs"
stopLink.WorkingDirectory = scriptDir
stopLink.IconLocation = "%SystemRoot%\System32\SHELL32.dll,131"
stopLink.Description = "Stop BLIP"
stopLink.Save

MsgBox "Desktop shortcuts created: 'BLIP' and 'Stop BLIP'.", 64, "BLIP setup"
