-- TI-Nspire AI Camera Solver
-- Protocol: SNAP -> OK:PROCESSING -> LEN:<n> -> RESULT:<response> -> >>>END<<<

platform.apilevel = '2.7'

-- Configuration
local CONFIG = {
    READ_TIMEOUT = 3000,
    BUFFER_SIZE = 4096,
    LINE_HEIGHT = 14,
    MARGIN = 8,
    HEADER_HEIGHT = 30,
    FOOTER_HEIGHT = 25,
}

-- Color palette
local COLORS = {
    bg_white = {255, 255, 255},
    bg_header = {0, 51, 102},
    bg_footer = {240, 240, 240},
    bg_input = {245, 245, 255},
    bg_wifi = {255, 248, 240},
    bg_selected = {0, 100, 200},

    text_primary = {0, 0, 0},
    text_white = {255, 255, 255},
    text_muted = {128, 128, 128},
    text_hint = {100, 100, 100},

    status_ok = {0, 150, 0},
    status_err = {200, 0, 0},
    status_warn = {200, 150, 0},
    status_info = {0, 100, 200},

    border = {200, 200, 200},
    border_input = {100, 100, 200},
    scrollbar_track = {220, 220, 220},
    scrollbar_thumb = {150, 150, 150},
    progress_bg = {220, 220, 220},
    progress_fill = {0, 150, 0},
}

local function markDirty()
    platform.window:invalidate()
end

-- State
local State = {
    status = "Initializing...",
    responseText = "",
    responseBuffer = "",
    wrappedLines = {},
    scrollOffset = 0,
    isConnected = false,
    isProcessing = false,
    processingStartTime = 0,
    port = nil,
    portList = {},
    asiAvailable = false,
    expectedLen = 0,
    inputMode = false,
    inputText = "",
    wifiMode = false,
    wifiStep = "menu",
    wifiNetworks = {},
    wifiSelected = 1,
    wifiSSID = "",
    wifiPassword = "",
    showHelp = false,
    pendingRescan = false,
    wifiConnected = false,
    wifiIP = "",
}

local PROCESSING_TIMEOUT = 60

-- ASI serial setup

local function initASI()
    local success = pcall(function() require 'asi' end)
    if success then
        State.asiAvailable = true
        State.status = "[*] ASI loaded. Scanning..."
        asi.addStateListener(onASIStateChange)
        asi.startScanning(onPortFound)
    else
        State.asiAvailable = false
        State.status = "[ERR] ASI not available"
    end
    markDirty()
end

function onASIStateChange(event)
    if event == asi.ON_SCANNING_STOPPED then
        if not State.isConnected then
            State.status = "[!] Scan stopped. No device."
        end
    end
    markDirty()
end

function onPortFound(foundPort)
    table.insert(State.portList, foundPort)

    if not State.port and not State.isConnected then
        State.status = "[*] Port found. Connecting..."
        State.port = foundPort
        foundPort:connect(onPortStateChange)
        markDirty()
    end
end

function onPortStateChange(port, event, errorMsg)
    if event == asi.CONNECTED then
        State.isConnected = true
        State.status = "[OK] Connected! W=WiFi"
        State.responseBuffer = ""
        State.expectedLen = 0
        State.isProcessing = false

        port:setReadListener(onDataReceived)
        port:setWriteListener(onDataSent)
        port:setReadTimeout(CONFIG.READ_TIMEOUT)
        port:read()

    elseif event == asi.DISCONNECTED then
        State.isConnected = false
        State.port = nil
        State.status = "[!] Disconnected"

    elseif event == asi.ERROR then
        State.isConnected = false
        State.status = "[ERR] " .. (errorMsg or "Unknown")
    end

    markDirty()
end

function onDataSent(port, errorMsg)
    if errorMsg then
        State.status = "[ERR] Send: " .. errorMsg
    end
    markDirty()
end

function onDataReceived(port, errorMsg)
    if errorMsg then
        local isNormalError = errorMsg:find("timeout") or errorMsg:find("Timeout")
            or errorMsg:find("reading") or errorMsg:find("Reading")

        if State.isConnected and State.port then
            local ok = pcall(function() State.port:read() end)
            if not ok and not isNormalError then
                State.status = "[!] Connection lost. Press R."
                State.isConnected = false
                State.isProcessing = false
            end
        end

        if not isNormalError and not State.isProcessing then
            State.status = "[OK] Ready. R=reconnect"
        end

        markDirty()
        return
    end

    local data = port:getValue() or ""

    if data ~= "" then
        State.responseBuffer = State.responseBuffer .. data

        if #State.responseBuffer > 50000 then
            State.responseBuffer = State.responseBuffer:sub(-30000)
            State.status = "[!] Buffer trimmed"
        end

        processResponseBuffer()
    end

    if State.isConnected and State.port then
        pcall(function() State.port:read() end)
    end

    markDirty()
end

-- Protocol handling

function processResponseBuffer()
    local buffer = State.responseBuffer

    if buffer:find("ERR:BUSY") then
        State.status = "[!] Device busy! Wait or ESC"
        State.isProcessing = false
        buffer = buffer:gsub("ERR:BUSY%s*", "")
        State.responseBuffer = buffer
        return
    end

    if buffer:find("OK:RESET") or buffer:find("OK:CLEARED") then
        buffer = buffer:gsub("OK:RESET%s*", ""):gsub("OK:CLEARED%s*", "")
        State.responseBuffer = buffer
        return
    end

    if buffer:find("OK:PROCESSING") then
        State.status = "[*] Processing..."
        buffer = buffer:gsub("OK:PROCESSING%s*", "")
    end

    if buffer:find("OK:SCANNING") then
        State.status = "[*] Scanning WiFi..."
        buffer = buffer:gsub("OK:SCANNING%s*", "")
    end

    if buffer:find("OK:CONNECTING") then
        State.status = "[*] Connecting WiFi..."
        buffer = buffer:gsub("OK:CONNECTING%s*", "")
    end

    -- Parse network list
    local networksStart = buffer:find("NETWORKS:")
    if networksStart then
        local lineEnd = buffer:find("[\r\n]", networksStart)
        if not lineEnd then
            State.status = "[*] Receiving networks..."
            State.responseBuffer = buffer
            return
        end

        local networksLine = buffer:sub(networksStart + 9, lineEnd - 1)
        networksLine = networksLine:gsub("[\r\n]", "")

        State.wifiNetworks = {}
        if networksLine ~= "None found" and networksLine ~= "" then
            for network in networksLine:gmatch("[^|]+") do
                table.insert(State.wifiNetworks, network)
            end
        end

        State.wifiStep = "list"
        State.wifiSelected = 1
        if #State.wifiNetworks > 0 then
            State.status = "[OK] Found " .. #State.wifiNetworks .. " networks"
        else
            State.status = "[!] No networks found"
        end
        local afterLine = buffer:sub(lineEnd)
        afterLine = afterLine:gsub("^[\r\n]+", "")
        State.responseBuffer = afterLine
        markDirty()
        return
    end

    -- Parse WiFi connection result
    local wifiOk = buffer:find("WIFI:OK:")
    if wifiOk then
        local lineEnd = buffer:find("\n", wifiOk) or #buffer + 1
        local ip = buffer:sub(wifiOk + 8, lineEnd - 1)
        ip = ip:gsub("[%s\r\n]+", "")
        State.wifiConnected = true
        State.wifiIP = ip
        State.status = "[OK] WiFi: " .. ip
        State.wifiMode = false
        State.wifiStep = "menu"
        buffer = buffer:sub(lineEnd + 1)
        State.responseBuffer = buffer
        markDirty()
        return
    end

    if buffer:find("WIFI:FAIL") then
        State.wifiConnected = false
        State.wifiIP = ""
        State.status = "[ERR] WiFi failed. W=retry"
        State.wifiMode = false
        State.wifiStep = "menu"
        buffer = buffer:gsub("WIFI:FAIL%s*", "")
        State.responseBuffer = buffer
        markDirty()
        return
    end

    if buffer:find("WIFI:NONE") then
        State.wifiConnected = false
        State.wifiIP = ""
        State.status = "[!] No WiFi. W=setup"
        buffer = buffer:gsub("WIFI:NONE%s*", "")
        State.responseBuffer = buffer
        markDirty()
        return
    end

    if buffer:find("READY") then
        buffer = buffer:gsub("READY%s*", "")
        State.responseBuffer = buffer
        return
    end

    if buffer:find("PONG") then
        State.status = "[OK] PONG! Serial OK"
        buffer = buffer:gsub("PONG%s*", "")
        State.responseBuffer = buffer
        return
    end

    if buffer:find("OK:RESTARTED") then
        State.status = "[OK] Restarted! Ready"
        buffer = buffer:gsub("OK:RESTARTED%s*", "")
        State.responseBuffer = buffer
        return
    end

    if buffer:find("OK:REBOOTING") then
        State.status = "[*] Rebooting... 5s, then R"
        if State.port then
            pcall(function() State.port:disconnect() end)
        end
        State.isConnected = false
        State.port = nil
        State.portList = {}
        State.wifiConnected = false
        State.wifiIP = ""
        State.isProcessing = false
        State.expectedLen = 0
        pcall(function() asi.stopScanning() end)
        buffer = buffer:gsub("OK:REBOOTING%s*", "")
        State.responseBuffer = ""
        return
    end

    local ipStart = buffer:find("IP:")
    if ipStart then
        local lineEnd = buffer:find("\n", ipStart) or #buffer + 1
        local ip = buffer:sub(ipStart + 3, lineEnd - 1)
        State.status = "IP: " .. ip
        buffer = buffer:sub(lineEnd + 1)
    end

    -- Parse expected response length
    local lenStart = buffer:find("LEN:")
    if lenStart then
        local lenEnd = buffer:find("[\r\n]", lenStart)
        if lenEnd then
            local lenStr = buffer:sub(lenStart + 4, lenEnd - 1)
            lenStr = lenStr:gsub("[%s\r\n]+", "")
            State.expectedLen = tonumber(lenStr) or 0
            local afterLen = buffer:sub(lenEnd)
            afterLen = afterLen:gsub("^[\r\n]+", "")
            buffer = afterLen
        end
    end

    -- Parse result payload
    local resultStart = buffer:find("RESULT:")
    if resultStart then
        local afterResult = buffer:sub(resultStart + 7)
        local normalizedResult = afterResult:gsub("\r\n", "\n"):gsub("\r", "\n")

        local endPos = normalizedResult:find(">>>END<<<")
        local hasEnoughBytes = State.expectedLen and State.expectedLen > 0 and #normalizedResult >= State.expectedLen

        if endPos or hasEnoughBytes then
            local result
            if endPos then
                result = normalizedResult:sub(1, endPos - 1)
            else
                result = normalizedResult:sub(1, State.expectedLen)
            end
            result = result:gsub("^%s+", ""):gsub("%s+$", "")

            State.responseText = result
            State.wrappedLines = wordWrap(result, getTextAreaWidth())
            State.scrollOffset = 0
            State.status = "[OK] Done! ENTER=new T=ask"
            State.isProcessing = false
            State.expectedLen = 0
            State.responseBuffer = ""
        else
            local received = #normalizedResult
            if State.expectedLen and State.expectedLen > 0 then
                local pct = math.floor((received / State.expectedLen) * 100)
                local barLen = 10
                local filled = math.floor(barLen * pct / 100)
                local bar = string.rep("=", filled) .. ">" .. string.rep(" ", barLen - filled)
                State.status = "[" .. bar .. "] " .. pct .. "%"
            else
                State.status = "[*] Receiving... " .. received .. "b"
            end
        end
    end

    State.responseBuffer = buffer
end

-- Commands

function sendSnap()
    if not State.isConnected or not State.port then
        State.status = "[ERR] Not connected!"
        markDirty()
        return
    end

    if not State.wifiConnected then
        State.status = "[!] WiFi required! W=setup"
        markDirty()
        return
    end

    if State.isProcessing then
        State.status = "[!] Already processing..."
        markDirty()
        return
    end

    State.responseText = ""
    State.responseBuffer = ""
    State.wrappedLines = {}
    State.scrollOffset = 0
    State.isProcessing = true
    State.processingStartTime = timer.getMilliSecCounter()
    State.status = "[*] Sending SNAP..."
    markDirty()

    local success, err = pcall(function()
        State.port:write("SNAP\n")
    end)

    if not success then
        State.status = "[ERR] Send: " .. tostring(err)
        State.isProcessing = false
    else
        State.status = "[*] SNAP sent. Waiting..."
    end

    markDirty()
end

function sendPing()
    if not State.isConnected or not State.port then
        State.status = "[ERR] Not connected!"
        markDirty()
        return
    end

    State.status = "[*] Sending PING..."
    State.port:write("PING\n")
    markDirty()
end

function sendTextQuery()
    if not State.isConnected or not State.port then
        State.status = "[ERR] Not connected!"
        markDirty()
        return
    end

    if not State.wifiConnected then
        State.status = "[!] WiFi required! W=setup"
        markDirty()
        return
    end

    if State.isProcessing then
        State.status = "[!] Already processing..."
        markDirty()
        return
    end

    if State.inputText == "" then
        State.status = "[!] Type a question first!"
        markDirty()
        return
    end

    State.responseText = ""
    State.responseBuffer = ""
    State.wrappedLines = {}
    State.scrollOffset = 0
    State.isProcessing = true
    State.processingStartTime = timer.getMilliSecCounter()
    State.status = "[*] Asking: " .. State.inputText:sub(1, 18) .. "..."
    markDirty()

    local success, err = pcall(function()
        State.port:write("ASK:" .. State.inputText .. "\n")
    end)

    if not success then
        State.status = "[ERR] Send: " .. tostring(err)
        State.isProcessing = false
    else
        State.inputText = ""
        State.inputMode = false
    end

    markDirty()
end

function toggleInputMode()
    State.inputMode = not State.inputMode
    if State.inputMode then
        State.status = "[*] Type question, ENTER=send"
    else
        State.status = State.isConnected and "[OK] Ready. W=WiFi T=type" or "[!] Not connected"
    end
    markDirty()
end

function startWifiSetup()
    if not State.isConnected or not State.port then
        State.status = "[ERR] Not connected!"
        markDirty()
        return
    end

    State.wifiMode = true
    State.wifiStep = "scanning"
    State.wifiNetworks = {}
    State.wifiSelected = 1
    State.wifiSSID = ""
    State.wifiPassword = ""
    State.status = "[*] Scanning WiFi..."
    markDirty()

    local success, err = pcall(function()
        State.port:write("SCAN\n")
    end)

    if not success then
        State.status = "[ERR] Send: " .. tostring(err)
        State.wifiMode = false
    else
        pcall(function() State.port:read() end)
    end

    markDirty()
end

function selectWifiNetwork()
    if #State.wifiNetworks == 0 then
        State.status = "[!] No networks. W=rescan"
        State.wifiMode = false
        return
    end

    local selected = State.wifiNetworks[State.wifiSelected] or ""
    State.wifiSSID = selected:match("^(.-)%(") or selected
    State.wifiStep = "password"
    State.wifiPassword = ""
    State.status = "[*] Password for " .. State.wifiSSID
    markDirty()
end

function connectToWifi()
    if State.wifiSSID == "" then
        State.status = "[!] No network selected"
        return
    end

    State.wifiStep = "connecting"
    State.status = "[*] Connecting to " .. State.wifiSSID .. "..."
    markDirty()

    pcall(function()
        State.port:write("WIFI:" .. State.wifiSSID .. ":" .. State.wifiPassword .. "\n")
    end)
end

function getWifiIP()
    if not State.isConnected or not State.port then
        State.status = "[ERR] Not connected!"
        return
    end

    pcall(function()
        State.port:write("IP\n")
    end)
end

function clearConversation()
    if not State.isConnected or not State.port then
        State.status = "[ERR] Not connected!"
        markDirty()
        return
    end

    local success, err = pcall(function()
        State.port:write("CLEAR\n")
    end)

    if success then
        State.responseText = ""
        State.wrappedLines = {}
        State.scrollOffset = 0
        State.status = "[OK] Conversation cleared"
    else
        State.status = "[ERR] " .. tostring(err)
    end

    markDirty()
end

-- Text wrapping

function getTextAreaWidth()
    local w = platform.window:width() or 320
    return w - (CONFIG.MARGIN * 2) - 10
end

function wordWrap(text, maxWidth)
    local lines = {}

    if not text or text == "" then
        return lines
    end

    local charWidth = 6
    local maxChars = math.floor(maxWidth / charWidth)

    for paragraph in text:gmatch("[^\n]+") do
        local words = {}
        for word in paragraph:gmatch("%S+") do
            table.insert(words, word)
        end

        local currentLine = ""
        for i, word in ipairs(words) do
            local testLine = currentLine == "" and word or (currentLine .. " " .. word)

            if #testLine > maxChars and currentLine ~= "" then
                table.insert(lines, currentLine)
                currentLine = word
            else
                currentLine = testLine
            end
        end

        if currentLine ~= "" then
            table.insert(lines, currentLine)
        end
    end

    if #lines == 0 and text ~= "" then
        table.insert(lines, text)
    end

    return lines
end

-- Drawing

function on.paint(gc)
    local w = platform.window:width() or 320
    local h = platform.window:height() or 240

    if State.inputMode then
        gc:setColorRGB(unpack(COLORS.bg_input))
    elseif State.wifiMode then
        gc:setColorRGB(unpack(COLORS.bg_wifi))
    else
        gc:setColorRGB(unpack(COLORS.bg_white))
    end
    gc:fillRect(0, 0, w, h)

    drawHeader(gc, w)
    drawTextArea(gc, w, h)
    drawFooter(gc, w, h)
    drawScrollIndicator(gc, w, h)
end

function drawHeader(gc, w)
    gc:setColorRGB(unpack(COLORS.bg_header))
    gc:fillRect(0, 0, w, CONFIG.HEADER_HEIGHT)

    gc:setColorRGB(unpack(COLORS.text_white))
    gc:setFont("sansserif", "b", 11)
    gc:drawString("AI Camera Solver", CONFIG.MARGIN, 2, "top")

    local modeText = ""
    if State.inputMode then
        modeText = "[INPUT]"
        gc:setColorRGB(unpack(COLORS.status_info))
    elseif State.wifiMode then
        modeText = "[WIFI]"
        gc:setColorRGB(unpack(COLORS.status_warn))
    elseif State.isProcessing then
        modeText = "[BUSY]"
        gc:setColorRGB(unpack(COLORS.status_warn))
    elseif State.isConnected and State.wifiConnected then
        modeText = "[OK]"
        gc:setColorRGB(unpack(COLORS.status_ok))
    elseif State.isConnected then
        modeText = "[NoWiFi]"
        gc:setColorRGB(unpack(COLORS.status_warn))
    else
        modeText = "[--]"
        gc:setColorRGB(unpack(COLORS.status_err))
    end
    gc:setFont("sansserif", "b", 9)
    local modeWidth = gc:getStringWidth(modeText) or 40
    gc:drawString(modeText, w - modeWidth - CONFIG.MARGIN, 5, "top")
end

function drawHelpScreen(gc, w, textTop, textHeight)
    gc:setColorRGB(unpack(COLORS.bg_header))
    gc:setFont("sansserif", "b", 11)
    gc:drawString("AI Camera Solver - Help", CONFIG.MARGIN + 5, textTop + 2, "top")

    gc:setColorRGB(unpack(COLORS.text_primary))
    gc:setFont("sansserif", "r", 9)

    local y = textTop + 22
    local lines = {
        "CONTROLS:",
        "  ENTER = Take photo & solve",
        "  T = Type question (chat mode)",
        "  W = WiFi setup",
        "  C = Clear conversation",
        "  X = Soft restart",
        "  Z = Hard reset (full reboot)",
        "  R = Reconnect serial port",
        "  P = Ping (test connection)",
        "  I = Show IP address",
        "  H = Toggle this help",
        "  ESC = Cancel/Reset",
        "",
        "NAVIGATION:",
        "  Up/Down = Scroll response",
        "",
        "TIPS:",
        "  - Press Z if slow, wait 5s, R",
        "  - Follow up with T to correct",
    }

    for _, line in ipairs(lines) do
        gc:drawString(line, CONFIG.MARGIN + 5, y, "top")
        y = y + 12
    end
end

function drawTextArea(gc, w, h)
    local textTop = CONFIG.HEADER_HEIGHT + 5
    local textBottom = h - CONFIG.FOOTER_HEIGHT - 5
    local textHeight = textBottom - textTop

    gc:setColorRGB(unpack(COLORS.border))
    gc:drawRect(CONFIG.MARGIN - 2, textTop - 2, w - (CONFIG.MARGIN * 2) + 4, textHeight + 4)

    if State.showHelp then
        drawHelpScreen(gc, w, textTop, textHeight)
        return
    end

    if State.inputMode then
        drawInputArea(gc, w, textTop, textHeight)
        return
    end

    if State.wifiMode then
        drawWifiSetup(gc, w, textTop, textHeight)
        return
    end

    gc:setColorRGB(unpack(COLORS.text_primary))
    gc:setFont("sansserif", "r", 10)

    if #State.wrappedLines == 0 then
        gc:setColorRGB(unpack(COLORS.text_muted))
        gc:drawString("W=WiFi | T=Type | ENTER=Photo", CONFIG.MARGIN + 5, textTop + 10, "top")
    else
        local visibleLines = math.floor(textHeight / CONFIG.LINE_HEIGHT)
        local startLine = State.scrollOffset + 1
        local endLine = math.min(startLine + visibleLines - 1, #State.wrappedLines)

        local y = textTop + 5
        for i = startLine, endLine do
            if State.wrappedLines[i] then
                gc:drawString(State.wrappedLines[i], CONFIG.MARGIN + 5, y, "top")
                y = y + CONFIG.LINE_HEIGHT
            end
        end
    end
end

function drawInputArea(gc, w, textTop, textHeight)
    gc:setColorRGB(unpack(COLORS.bg_header))
    gc:setFont("sansserif", "b", 10)
    gc:drawString("Type your question:", CONFIG.MARGIN + 5, textTop + 5, "top")

    gc:setColorRGB(unpack(COLORS.bg_input))
    gc:fillRect(CONFIG.MARGIN + 2, textTop + 25, w - (CONFIG.MARGIN * 2) - 4, textHeight - 35)

    gc:setColorRGB(unpack(COLORS.border_input))
    gc:drawRect(CONFIG.MARGIN + 2, textTop + 25, w - (CONFIG.MARGIN * 2) - 4, textHeight - 35)

    gc:setColorRGB(unpack(COLORS.text_primary))
    gc:setFont("sansserif", "r", 10)

    local displayText = State.inputText .. "_"
    local inputLines = wordWrap(displayText, w - (CONFIG.MARGIN * 2) - 20)

    local y = textTop + 30
    for i, line in ipairs(inputLines) do
        if y < textTop + textHeight - 15 then
            gc:drawString(line, CONFIG.MARGIN + 8, y, "top")
            y = y + CONFIG.LINE_HEIGHT
        end
    end
end

function drawWifiSetup(gc, w, textTop, textHeight)
    gc:setColorRGB(unpack(COLORS.bg_header))
    gc:setFont("sansserif", "b", 11)
    gc:drawString("WiFi Setup", CONFIG.MARGIN + 5, textTop + 5, "top")

    gc:setColorRGB(unpack(COLORS.text_primary))
    gc:setFont("sansserif", "r", 10)

    if State.wifiStep == "scanning" then
        gc:drawString("Scanning for networks...", CONFIG.MARGIN + 5, textTop + 25, "top")

    elseif State.wifiStep == "list" then
        if #State.wifiNetworks == 0 then
            gc:drawString("No networks found", CONFIG.MARGIN + 5, textTop + 25, "top")
            gc:drawString("Press W to scan again", CONFIG.MARGIN + 5, textTop + 40, "top")
        else
            local y = textTop + 25
            local maxVisible = math.floor((textHeight - 30) / 16)

            for i, network in ipairs(State.wifiNetworks) do
                if i <= maxVisible then
                    if i == State.wifiSelected then
                        gc:setColorRGB(unpack(COLORS.bg_selected))
                        gc:fillRect(CONFIG.MARGIN + 2, y - 2, w - CONFIG.MARGIN * 2 - 4, 16)
                        gc:setColorRGB(unpack(COLORS.text_white))
                    else
                        gc:setColorRGB(unpack(COLORS.text_primary))
                    end
                    gc:drawString(i .. ". " .. network, CONFIG.MARGIN + 5, y, "top")
                    y = y + 16
                end
            end
        end

    elseif State.wifiStep == "password" then
        gc:drawString("Network: " .. State.wifiSSID, CONFIG.MARGIN + 5, textTop + 25, "top")
        gc:drawString("Password:", CONFIG.MARGIN + 5, textTop + 45, "top")

        gc:setColorRGB(unpack(COLORS.bg_input))
        gc:fillRect(CONFIG.MARGIN + 5, textTop + 62, w - CONFIG.MARGIN * 2 - 10, 20)
        gc:setColorRGB(unpack(COLORS.border_input))
        gc:drawRect(CONFIG.MARGIN + 5, textTop + 62, w - CONFIG.MARGIN * 2 - 10, 20)

        gc:setColorRGB(unpack(COLORS.text_primary))
        local displayPw = string.rep("*", #State.wifiPassword) .. "_"
        gc:drawString(displayPw, CONFIG.MARGIN + 10, textTop + 65, "top")

        gc:setColorRGB(unpack(COLORS.text_hint))
        gc:setFont("sansserif", "r", 8)
        gc:drawString("ENTER=Connect | ESC=Cancel", CONFIG.MARGIN + 5, textTop + 90, "top")

    elseif State.wifiStep == "connecting" then
        gc:drawString("Connecting to " .. State.wifiSSID .. "...", CONFIG.MARGIN + 5, textTop + 25, "top")
        gc:drawString("Please wait...", CONFIG.MARGIN + 5, textTop + 45, "top")
    end
end

function drawFooter(gc, w, h)
    local footerTop = h - CONFIG.FOOTER_HEIGHT

    gc:setColorRGB(unpack(COLORS.bg_footer))
    gc:fillRect(0, footerTop, w, CONFIG.FOOTER_HEIGHT)

    local statusColor = COLORS.text_primary
    if State.status:find("^%[OK%]") then
        statusColor = COLORS.status_ok
    elseif State.status:find("^%[ERR%]") then
        statusColor = COLORS.status_err
    elseif State.status:find("^%[!%]") then
        statusColor = COLORS.status_warn
    elseif State.status:find("^%[%*%]") then
        statusColor = COLORS.status_info
    end
    gc:setColorRGB(unpack(statusColor))
    gc:setFont("sansserif", "r", 9)
    gc:drawString(State.status, CONFIG.MARGIN, footerTop + 3, "top")

    gc:setColorRGB(unpack(COLORS.text_hint))
    gc:setFont("sansserif", "r", 8)
    if State.wifiMode then
        gc:drawString("Arrows=Select | ENTER=Choose | ESC=Cancel", CONFIG.MARGIN, footerTop + 14, "top")
    elseif State.inputMode then
        gc:drawString("Type question | ENTER=Send | ESC=Cancel", CONFIG.MARGIN, footerTop + 14, "top")
    else
        gc:drawString("ENTER=Photo T=Chat H=Help Z=Reset", CONFIG.MARGIN, footerTop + 14, "top")
    end
end

function drawScrollIndicator(gc, w, h)
    if #State.wrappedLines == 0 then return end

    local textTop = CONFIG.HEADER_HEIGHT + 5
    local textBottom = h - CONFIG.FOOTER_HEIGHT - 5
    local textHeight = textBottom - textTop
    local visibleLines = math.floor(textHeight / CONFIG.LINE_HEIGHT)

    if #State.wrappedLines <= visibleLines then return end

    local scrollBarHeight = math.max(20, textHeight * (visibleLines / #State.wrappedLines))
    local maxScroll = #State.wrappedLines - visibleLines
    local scrollRatio = State.scrollOffset / maxScroll
    local scrollBarY = textTop + (textHeight - scrollBarHeight) * scrollRatio

    gc:setColorRGB(unpack(COLORS.scrollbar_track))
    gc:fillRect(w - CONFIG.MARGIN - 6, textTop, 4, textHeight)

    gc:setColorRGB(unpack(COLORS.scrollbar_thumb))
    gc:fillRect(w - CONFIG.MARGIN - 6, scrollBarY, 4, scrollBarHeight)
end

-- Event handlers

function on.construction()
    timer.start(0.1)
end

function on.timer()
    if not State.asiAvailable then
        timer.stop()
        initASI()
        timer.start(1)
    else
        if State.pendingRescan then
            State.pendingRescan = false
            State.status = "[*] Scanning for device..."
            asi.startScanning(onPortFound)
            markDirty()
        end

        if State.isProcessing and State.processingStartTime > 0 then
            local elapsed = timer.getMilliSecCounter() - State.processingStartTime
            if elapsed > PROCESSING_TIMEOUT * 1000 then
                State.isProcessing = false
                State.processingStartTime = 0
                State.status = "[ERR] Timeout! Press ESC to clear."
                markDirty()
            end
        end
    end
end

function on.enterKey()
    if State.wifiMode then
        if State.wifiStep == "list" then
            selectWifiNetwork()
        elseif State.wifiStep == "password" then
            connectToWifi()
        end
    elseif State.inputMode then
        sendTextQuery()
    else
        sendSnap()
    end
end

function forceReset()
    State.responseText = ""
    State.wrappedLines = {}
    State.scrollOffset = 0
    State.responseBuffer = ""
    State.isProcessing = false
    State.processingStartTime = 0
    State.inputMode = false
    State.inputText = ""
    State.expectedLen = 0
    State.showHelp = false

    if State.isConnected and State.port then
        pcall(function() State.port:write("RESET\n") end)
        pcall(function() State.port:read() end)
    end

    State.status = State.isConnected and "[OK] Reset! H=help" or "[!] Not connected"
    markDirty()
end

function on.escapeKey()
    if State.showHelp then
        State.showHelp = false
    elseif State.wifiMode then
        State.wifiMode = false
        State.wifiStep = "menu"
        State.status = State.isConnected and "[OK] Ready. H=help" or "[!] Not connected"
    elseif State.inputMode then
        State.inputMode = false
        State.inputText = ""
        State.status = State.isConnected and "[OK] Ready. H=help" or "[!] Not connected"
    else
        forceReset()
    end
    markDirty()
end

function on.arrowUp()
    if State.wifiMode and State.wifiStep == "list" then
        if State.wifiSelected > 1 then
            State.wifiSelected = State.wifiSelected - 1
            markDirty()
        end
    elseif State.scrollOffset > 0 then
        State.scrollOffset = State.scrollOffset - 1
        markDirty()
    end
end

function on.arrowDown()
    if State.wifiMode and State.wifiStep == "list" then
        if State.wifiSelected < #State.wifiNetworks then
            State.wifiSelected = State.wifiSelected + 1
            markDirty()
        end
    else
        local h = platform.window:height() or 240
        local textHeight = h - CONFIG.HEADER_HEIGHT - CONFIG.FOOTER_HEIGHT - 10
        local visibleLines = math.floor(textHeight / CONFIG.LINE_HEIGHT)
        local maxScroll = math.max(0, #State.wrappedLines - visibleLines)

        if State.scrollOffset < maxScroll then
            State.scrollOffset = State.scrollOffset + 1
            markDirty()
        end
    end
end

function on.charIn(char)
    if State.wifiMode and State.wifiStep == "password" then
        State.wifiPassword = State.wifiPassword .. char
        markDirty()
        return
    end

    if State.inputMode then
        State.inputText = State.inputText .. char
        markDirty()
        return
    end

    if char == "w" or char == "W" then
        startWifiSetup()
    elseif char == "i" or char == "I" then
        getWifiIP()
    elseif char == "t" or char == "T" then
        toggleInputMode()
    elseif char == "c" or char == "C" then
        clearConversation()
    elseif char == "p" or char == "P" then
        sendPing()
    elseif char == "r" or char == "R" then
        if State.asiAvailable then
            if State.port then
                pcall(function() State.port:disconnect() end)
            end
            State.port = nil
            State.isConnected = false
            State.isProcessing = false
            State.responseBuffer = ""
            State.expectedLen = 0
            State.portList = {}
            State.wifiConnected = false
            State.wifiIP = ""

            pcall(function() asi.stopScanning() end)

            State.status = "[*] Rescanning..."
            State.pendingRescan = true
            markDirty()
        end
    elseif char == "h" or char == "H" then
        State.showHelp = not State.showHelp
        markDirty()
    elseif char == "x" or char == "X" then
        if State.isConnected and State.port then
            State.status = "[*] Restarting..."
            State.responseText = ""
            State.responseBuffer = ""
            State.wrappedLines = {}
            State.scrollOffset = 0
            State.isProcessing = false
            State.expectedLen = 0
            State.inputMode = false
            State.inputText = ""
            State.showHelp = false
            pcall(function() State.port:write("RESTART\n") end)
            pcall(function() State.port:read() end)
            markDirty()
        else
            State.status = "[ERR] Not connected!"
            markDirty()
        end
    elseif char == "z" or char == "Z" then
        if State.isConnected and State.port then
            State.status = "[*] Hard reset..."
            State.responseText = ""
            State.responseBuffer = ""
            State.wrappedLines = {}
            State.scrollOffset = 0
            State.isProcessing = false
            State.expectedLen = 0
            State.inputMode = false
            State.inputText = ""
            State.showHelp = false
            State.wifiConnected = false
            State.wifiIP = ""
            pcall(function() State.port:write("HARDRESET\n") end)
            markDirty()
        else
            State.status = "[ERR] Not connected!"
            markDirty()
        end
    end
end

function on.backspaceKey()
    if State.wifiMode and State.wifiStep == "password" and #State.wifiPassword > 0 then
        State.wifiPassword = State.wifiPassword:sub(1, -2)
        markDirty()
    elseif State.inputMode and #State.inputText > 0 then
        State.inputText = State.inputText:sub(1, -2)
        markDirty()
    end
end

function on.resize(w, h)
    if State.responseText ~= "" then
        State.wrappedLines = wordWrap(State.responseText, getTextAreaWidth())
    end
    markDirty()
end

function on.activate()
    markDirty()
end

function on.deactivate()
end

function on.destroy()
    if State.port then
        pcall(function() State.port:disconnect() end)
    end
    if State.asiAvailable then
        pcall(function() asi.stopScanning() end)
    end
end
