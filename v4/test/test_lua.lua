-- Cross-check nlink.lua against reference frames from the C++ codec.
-- Run: lua5.4 test/test_lua.lua   (from the project root)

-- Stubs for the Nspire environment bits nlink.lua touches at load time
timer = { getMilliSecCounter = function() return 0 end }

dofile("calculator/nlink.lua")

local failures = 0
local function check(cond, msg)
  if cond then print("ok:   " .. msg)
  else print("FAIL: " .. msg) failures = failures + 1 end
end

-- Fake port capturing writes
local captured = ""
local fakePort = {
  write = function(_, s) captured = captured .. s end,
  read = function() end,
}

local statusGot, resultGot, errGot
local link = NLink.new{
  onStatus = function(s) statusGot = s end,
  onResult = function(b) resultGot = b end,
  onError = function(e) errGot = e end,
}
link.port = fakePort
link.connected = true

-- 1. Lua TX frames must be byte-identical to the C++ codec's
link:_sendFrame("C", "PING")
check(captured == "~1C00|UElORw==|4636\n",
      "Lua frame for C/0/PING matches C++ reference")

captured = ""
link.txSeq = 5
link:_sendFrame("S", "WIFI OK 192.168.1.42")
check(captured == "~1S05|V0lGSSBPSyAxOTIuMTY4LjEuNDI=|9400\n",
      "Lua frame for S/5/'WIFI OK …' matches C++ reference")

-- 2. Lua RX: parse a C++-style status frame
link:_processLine("~1S05|V0lGSSBPSyAxOTIuMTY4LjEuNDI=|9400")
check(statusGot == "WIFI OK 192.168.1.42", "Lua parses C++ status frame payload")

-- 3. Corrupt frame is rejected (and NAK sent), handler not fired
statusGot = nil
captured = ""
link:_processLine("~1S05|V0lGSSBPSyAxOTIuMTY4LjEuNDI=|9401")  -- bad CRC
check(statusGot == nil, "Lua rejects corrupt frame")
check(captured:sub(1, 3) == "~1N", "Lua sends NAK on corrupt frame")

-- 4. Chunked body reassembly with END verification
-- Body "hello world" split in two D frames + E with len,crc
local function b64(s)  -- quick local encoder for building test frames
  local B = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
  local out = {}
  for i = 1, #s, 3 do
    local a, b2, c = s:byte(i, i + 2)
    local n = a * 65536 + (b2 or 0) * 256 + (c or 0)
    local c1 = math.floor(n / 262144) % 64
    local c2 = math.floor(n / 4096) % 64
    local c3 = math.floor(n / 64) % 64
    local c4 = n % 64
    out[#out + 1] = B:sub(c1 + 1, c1 + 1) .. B:sub(c2 + 1, c2 + 1)
        .. (b2 and B:sub(c3 + 1, c3 + 1) or "=")
        .. (c and B:sub(c4 + 1, c4 + 1) or "=")
  end
  return table.concat(out)
end

-- CRC helper mirroring the frame body checksum
local function crcOf(bodyStr)
  -- reuse the library's own crc via a frame: build body, ask _processLine to
  -- accept it — instead compute with a local copy of the algorithm
  local crc = 0xFFFF
  for i = 1, #bodyStr do
    crc = (crc ~ (bodyStr:byte(i) << 8)) & 0xFFFF
    for _ = 1, 8 do
      if (crc & 0x8000) ~= 0 then crc = ((crc << 1) ~ 0x1021) & 0xFFFF
      else crc = (crc << 1) & 0xFFFF end
    end
  end
  return crc
end

local function makeFrame(t, seq, payload)
  local body = t .. string.format("%02X", seq) .. "|" .. b64(payload)
  return "~1" .. body .. "|" .. string.format("%04X", crcOf(body))
end

resultGot, errGot = nil, nil
link:_processLine(makeFrame("D", 10, "hello "))
link:_processLine(makeFrame("D", 11, "world"))
local bodyCrc = crcOf("hello world")
link:_processLine(makeFrame("E", 12, string.format("11,%x", bodyCrc)))
check(resultGot == "hello world", "Lua reassembles chunked body")
check(errGot == nil, "no error on valid body")

-- 5. Truncated body (missing chunk) fails END verification
resultGot, errGot = nil, nil
link:_processLine(makeFrame("D", 13, "hello "))
link:_processLine(makeFrame("E", 14, string.format("11,%x", bodyCrc)))
check(resultGot == nil and errGot ~= nil, "truncated body flagged as corrupt")

print(failures == 0 and "\nAll Lua tests passed." or ("\nFAILURES: " .. failures))
os.exit(failures)
