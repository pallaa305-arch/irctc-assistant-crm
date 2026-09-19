Set WshShell = CreateObject("WScript.Shell")
strPath = WshShell.CurrentDirectory
WshShell.Run chr(34) & Replace(WScript.ScriptFullName, "run_background.vbs", "run_server_silent.bat") & chr(34), 0
Set WshShell = Nothing
