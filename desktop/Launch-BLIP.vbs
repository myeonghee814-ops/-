' Double-click target for the desktop shortcut. Runs start.ps1 with the
' PowerShell window fully hidden (style 0) so no console flashes on screen.
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set shell = CreateObject("WScript.Shell")
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & scriptDir & "\start.ps1"""
shell.Run cmd, 0, False
