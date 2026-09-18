-- nlink.lua — reference client library for the nlink wire protocol v1
-- Runs on TI-Nspire (Lua, ASI serial API). See docs/PROTOCOL.md.
--
-- Usage from an app script:
--
--   local nlink = NLink.new{
--     onReady    = function(fwVersion, caps) ... end,
--     onStatus   = function(text) ... end,        -- "PROCESSING", "WIFI OK …"
--     onProgress = function(got, total) ... end,  -- body transfer progress
--     onResult   = function(body) ... end,        -- verified full body
--     onError    = function(text) ... end,
--   }
--   nlink:start()                    -- begins ASI scan + handshake
--   nlink:command("ASK what is 2+2")
--   nlink:command("SNAP")
--
-- The library owns framing, CRC checking, chunk reassembly, acking and
-- retries; apps only see whole verified bodies.

NLink = {}
NLink.__index = NLink

local PROTO_VER = "1"
local CLIENT_VER = "4.0.0"

-- ---------------------------------------------------------------------------
-- CRC16-CCITT (poly 0x1021, init 0xFFFF) — must match firmware
-- ---------------------------------------------------------------------------
local band, bxor, blshift
if bit32 then
  band, bxor, blshift = bit32.band, bit32.bxor, bit32.lshift
else
  -- Fallback arithmetic implementations (Nspire Lua has bit32 on 3.2+)
  band = function(a, b)
    local r, p = 0, 1
    while a > 0 and b > 0 do
      if a % 2 == 1 and b % 2 == 1 then r = r + p end
      a, b, p = math.floor(a / 2), math.floor(b / 2), p * 2
    end
    return r
  end
  bxor = function(a, b)
    local r, p = 0, 1
    while a > 0 or b > 0 do
      if (a % 2) ~= (b % 2) then r = r + p end
      a, b, p = math.floor(a / 2), math.floor(b / 2), p * 2
    end
    return r
  end
  blshift = function(a, n) return a * (2 ^ n) end
end

local function crc16(s)
  local crc = 0xFFFF
  for i = 1, #s do
    crc = bxor(crc, blshift(s:byte(i), 8)) % 0x10000
    for _ = 1, 8 do
      if band(crc, 0x8000) ~= 0 then
        crc = bxor((crc * 2) % 0x10000, 0x1021)
      else
        crc = (crc * 2) % 0x10000
      end
    end
  end
  return crc
end

-- ---------------------------------------------------------------------------
-- Base64 — must match firmware
-- ---------------------------------------------------------------------------
local B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
local B64INV = {}
for i = 1, #B64 do B64INV[B64:sub(i, i)] = i - 1 end

local function b64encode(s)
  local out = {}
  for i = 1, #s, 3 do
    local a, b, c = s:byte(i, i + 2)
    local n = a * 65536 + (b or 0) * 256 + (c or 0)
    local c1 = math.floor(n / 262144) % 64
    local c2 = math.floor(n / 4096) % 64
    local c3 = math.floor(n / 64) % 64
    local c4 = n % 64
    out[#out + 1] = B64:sub(c1 + 1, c1 + 1) .. B64:sub(c2 + 1, c2 + 1)
        .. (b and B64:sub(c3 + 1, c3 + 1) or "=")
        .. (c and B64:sub(c4 + 1, c4 + 1) or "=")
  end
  return table.concat(out)
end

local function b64decode(s)
  local out, buf, bits = {}, 0, 0
  for i = 1, #s do
    local v = B64INV[s:sub(i, i)]
    if v then
      buf = buf * 64 + v
      bits = bits + 6
      if bits >= 8 then
        bits = bits - 8
        local byte = math.floor(buf / (2 ^ bits)) % 256
        out[#out + 1] = string.char(byte)
        buf = buf % (2 ^ bits)  -- keep buf small: exact float math on Nspire
      end
    end
  end
  return table.concat(out)
end

-- ---------------------------------------------------------------------------
-- Construction
-- ---------------------------------------------------------------------------
function NLink.new(handlers)
  local self = setmetatable({}, NLink)
  self.handlers = handlers or {}
  self.port = nil
  self.connected = false
  self.ready = false          -- handshake completed
  self.rxLine = ""
  self.txSeq = 0
  self.body = nil             -- accumulating D-chunks
  self.pendingCmd = nil       -- {text=, sentAt=, tries=}
  self.ackTimeoutMs = 2000
  self.maxTries = 3
  return self
end

function NLink:emit(name, ...)
  local fn = self.handlers[name]
  if fn then fn(...) end
end

-- ---------------------------------------------------------------------------
-- ASI plumbing
-- ---------------------------------------------------------------------------
function NLink:start()
  local ok = pcall(function() require "asi" end)
  if not ok then
    self:emit("onError", "ASI not available on this OS")
    return false
  end
  asi.addStateListener(function(state)
    if state == asi.ON then
      asi.startScanning(function(port) self:_onPortFound(port) end)
    end
  end)
  return true
end

function NLink:_onPortFound(port)
  if self.port then return end
  self.port = port
  port:connect(function(p, event, err)
    if event == asi.CONNECTED then
      asi.stopScanning()
      self.connected = true
      p:setReadListener(function() self:_onData(p) end)
      p:setReadTimeout(3000)
      p:read()
      self:_sendFrame("H", "NLINK," .. CLIENT_VER)
    elseif event == asi.DISCONNECTED then
      self.connected, self.ready, self.port = false, false, nil
      self:emit("onError", "DISCONNECTED")
    elseif event == asi.ERROR then
      self.connected, self.ready = false, false
      self:emit("onError", err or "PORT_ERROR")
    end
  end)
end

function NLink:reconnect()
  if self.port then pcall(function() self.port:disconnect() end) end
  self.port, self.connected, self.ready = nil, false, false
  self.rxLine, self.body, self.pendingCmd = "", nil, nil
  pcall(function() asi.stopScanning() end)
  asi.startScanning(function(port) self:_onPortFound(port) end)
end

-- ---------------------------------------------------------------------------
-- Frame TX
-- ---------------------------------------------------------------------------
function NLink:_sendFrame(ftype, payload)
  if not self.port then return end
  local seq = self.txSeq
  self.txSeq = (self.txSeq + 1) % 256
  local body = ftype .. string.format("%02X", seq) .. "|" .. b64encode(payload or "")
  local frame = "~1" .. body .. "|" .. string.format("%04X", crc16(body)) .. "\n"
  pcall(function()
    self.port:write(frame)
    self.port:read()
  end)
end

-- Public: send a command; retries handled internally via tick().
function NLink:command(text)
  if not self.connected then
    self:emit("onError", "NOT_CONNECTED")
    return false
  end
  self.body = nil
  self.pendingCmd = { text = text, sentAt = timer.getMilliSecCounter(), tries = 1 }
  self:_sendFrame("C", text)
  return true
end

-- Call from on.timer() (e.g. every 250 ms): drives command retries.
function NLink:tick()
  local p = self.pendingCmd
  if not p then return end
  local elapsed = timer.getMilliSecCounter() - p.sentAt
  if elapsed > self.ackTimeoutMs then
    if p.tries >= self.maxTries then
      self.pendingCmd = nil
      self:emit("onError", "NO_RESPONSE (device unplugged?)")
    else
      p.tries = p.tries + 1
      p.sentAt = timer.getMilliSecCounter()
      self:_sendFrame("C", p.text)
    end
  end
end

-- ---------------------------------------------------------------------------
-- Frame RX
-- ---------------------------------------------------------------------------
function NLink:_onData(port)
  local data = port:getValue() or ""
  for i = 1, #data do
    local ch = data:sub(i, i)
    if ch == "\n" or ch == "\r" then
      if #self.rxLine > 0 then self:_processLine(self.rxLine) end
      self.rxLine = ""
    else
      self.rxLine = self.rxLine .. ch
      if #self.rxLine > 600 then self.rxLine = "" end
    end
  end
  pcall(function() port:read() end)
end

function NLink:_processLine(line)
  local start = line:find("~1", 1, true)
  if not start then return end
  local f = line:sub(start + 2)

  local lastBar
  for i = #f, 1, -1 do
    if f:sub(i, i) == "|" then lastBar = i break end
  end
  if not lastBar or #f - lastBar ~= 4 or lastBar < 5 then return end

  local body = f:sub(1, lastBar - 1)
  local wantCrc = tonumber(f:sub(lastBar + 1), 16)
  if not wantCrc or crc16(body) ~= wantCrc then
    self:_sendFrame("N", body:sub(2, 3))
    return
  end

  local ftype = body:sub(1, 1)
  local bar = body:find("|", 1, true)
  local payload = bar and b64decode(body:sub(bar + 1)) or ""

  self:_handleFrame(ftype, payload)
end

function NLink:_handleFrame(ftype, payload)
  if ftype == "h" then
    self.ready = true
    local ver, caps = payload:match("^NLINK,([^,]+),?(.*)$")
    self:emit("onReady", ver or "?", caps or "")

  elseif ftype == "A" then
    if self.pendingCmd then self.pendingCmd.acked = true end
    -- keep pendingCmd until S/D/E/X arrives? A means accepted: stop retrying.
    self.pendingCmd = nil

  elseif ftype == "S" then
    self.pendingCmd = nil
    self:emit("onStatus", payload)

  elseif ftype == "D" then
    self.pendingCmd = nil
    self.body = (self.body or "") .. payload
    self:emit("onProgress", #self.body, self.expectedLen)

  elseif ftype == "E" then
    local lenStr, crcStr = payload:match("^(%d+),(%x+)$")
    local total = tonumber(lenStr or "")
    local bodyCrc = tonumber(crcStr or "", 16)
    local body = self.body or ""
    self.body = nil
    if total and #body == total and (not bodyCrc or crc16(body) == bodyCrc) then
      self:emit("onResult", body)
    else
      self:emit("onError", "BODY_CORRUPT (" .. #body .. "/" .. tostring(total) .. ") — retry the command")
    end

  elseif ftype == "X" then
    self.pendingCmd = nil
    self.body = nil
    self:emit("onError", payload)

  elseif ftype == "N" then
    -- Device saw one of our frames corrupted; resend pending command once.
    if self.pendingCmd then self:_sendFrame("C", self.pendingCmd.text) end
  end
end

-- ---------------------------------------------------------------------------
-- Convenience wrappers
-- ---------------------------------------------------------------------------
function NLink:ping()               self:command("PING") end
function NLink:ask(text)            self:command("ASK " .. text) end
function NLink:snap(prompt)         self:command(prompt and ("SNAP " .. prompt) or "SNAP") end
function NLink:newChat()            self:command("NEWCHAT") end
function NLink:scanWifi()           self:command("SCAN") end
function NLink:joinWifi(ssid, pass) self:command("WIFI " .. ssid .. "\t" .. pass) end
function NLink:info()               self:command("INFO") end
function NLink:ls(dir)              self:command("LS " .. (dir or "/")) end
function NLink:getFile(name)        self:command("GET " .. name) end
function NLink:putFile(name, text)  self:command("PUT " .. name .. "\t" .. text) end
function NLink:cfgSet(key, value)   self:command("CFG SET " .. key .. " " .. value) end
function NLink:cfgGet(key)          self:command("CFG GET " .. key) end

return NLink
