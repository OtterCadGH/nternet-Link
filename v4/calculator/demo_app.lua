-- Minimal demo app for nlink.lua — proves the V4 protocol end-to-end.
-- Paste nlink.lua above this block in the TI Script Editor (or concatenate
-- the two files when building the .tns).
--
-- Keys: ENTER=photo  T=type question  W=wifi (SCAN then pick via number keys
--       is left to the full app — this demo uses cfg'd wifi)  P=ping
--       N=new chat  R=reconnect  up/down=scroll

platform.apilevel = "2.7"

local status = "Starting..."
local lines = {}
local scroll = 0
local inputMode = false
local inputText = ""
local progressPct = nil

local function setStatus(s) status = s platform.window:invalidate() end

local function wrap(text, maxChars)
  local out = {}
  for para in text:gmatch("[^\n]*") do
    if para == "" then
      out[#out + 1] = ""
    else
      local line = ""
      for word in para:gmatch("%S+") do
        local t = line == "" and word or line .. " " .. word
        if #t > maxChars and line ~= "" then
          out[#out + 1] = line
          line = word
        else
          line = t
        end
      end
      if line ~= "" then out[#out + 1] = line end
    end
  end
  return out
end

local link = NLink.new{
  onReady = function(ver, caps)
    setStatus("Connected: fw " .. ver .. " [" .. caps .. "]")
  end,
  onStatus = function(s)
    progressPct = nil
    setStatus(s)
  end,
  onProgress = function(got, total)
    if total and total > 0 then
      progressPct = math.floor(got * 100 / total)
      setStatus("Receiving " .. progressPct .. "%")
    else
      setStatus("Receiving " .. got .. "b")
    end
  end,
  onResult = function(body)
    progressPct = nil
    lines = wrap(body, 50)
    scroll = 0
    setStatus("Done. ENTER=photo T=ask N=new")
  end,
  onError = function(err)
    progressPct = nil
    setStatus("ERR: " .. err)
  end,
}

function on.construction()
  timer.start(0.25)
  link:start()
end

function on.timer()
  link:tick()
end

function on.enterKey()
  if inputMode then
    inputMode = false
    if inputText ~= "" then link:ask(inputText) end
    inputText = ""
  else
    link:snap()
  end
  platform.window:invalidate()
end

function on.charIn(ch)
  if inputMode then
    inputText = inputText .. ch
  elseif ch == "t" or ch == "T" then
    inputMode = true
    inputText = ""
    setStatus("Type question, ENTER=send")
  elseif ch == "p" or ch == "P" then
    link:ping()
  elseif ch == "n" or ch == "N" then
    link:newChat()
  elseif ch == "r" or ch == "R" then
    setStatus("Reconnecting...")
    link:reconnect()
  end
  platform.window:invalidate()
end

function on.backspaceKey()
  if inputMode and #inputText > 0 then
    inputText = inputText:sub(1, -2)
    platform.window:invalidate()
  end
end

function on.escapeKey()
  inputMode = false
  inputText = ""
  setStatus("Ready")
end

function on.arrowUp()
  if scroll > 0 then scroll = scroll - 1 platform.window:invalidate() end
end

function on.arrowDown()
  if scroll < math.max(0, #lines - 12) then
    scroll = scroll + 1
    platform.window:invalidate()
  end
end

function on.paint(gc)
  local w = platform.window:width()
  local h = platform.window:height()

  gc:setColorRGB(255, 255, 255)
  gc:fillRect(0, 0, w, h)

  gc:setColorRGB(0, 51, 102)
  gc:fillRect(0, 0, w, 24)
  gc:setColorRGB(255, 255, 255)
  gc:setFont("sansserif", "b", 10)
  gc:drawString("nternet-Link V4 demo", 6, 4, "top")

  gc:setColorRGB(0, 0, 0)
  gc:setFont("sansserif", "r", 9)
  if inputMode then
    gc:drawString("> " .. inputText .. "_", 6, 32, "top")
  else
    local y = 32
    for i = scroll + 1, math.min(scroll + 12, #lines) do
      gc:drawString(lines[i], 6, y, "top")
      y = y + 13
    end
  end

  gc:setColorRGB(80, 80, 80)
  gc:setFont("sansserif", "r", 8)
  gc:drawString(status, 6, h - 14, "top")
end
