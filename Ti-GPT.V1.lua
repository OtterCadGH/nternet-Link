require "asi" 
require "color"
platform.window:setBackgroundColor(0x212121)

function on.resize()
   W, H = platform.window:width(), platform.window:height()
   fontSize = W/25
   leftMargin = fontSize / 5
   lineSpace = fontSize * 1.5
end

function reset()
   txString, rxString = "", ""
   platform.window:invalidate()
end

local PORT

-- Define ASI state listener (start port scan when ASI is ready)
function stateListener(state)
   if state == asi.ON then
      asi.startScanning(portScanner)
   end
end

-- Define port scanner (send a connection request to the found port)
function portScanner(port)
   PORT = port
   port:connect(portConnector)
end

-- Define port connector
function portConnector(port, event)
   if event == asi.CONNECTED then
      asi.stopScanning()
      port:setReadListener(readListener)
   end
end

-- Define read listener
function readListener(port)
   rxString = port:getValue()
   platform.window:invalidate()
end

-- Register ASI state listener
function on.construction()
   reset()
   asi.addStateListener(stateListener)
end

function on.charIn(char)
   txString = txString..char
   platform.window:invalidate()
end

function on.backspaceKey()
   txString = string.usub(txString, 1, -2)
   platform.window:invalidate()
end

function on.enterKey()
   PORT:write(txString.."\n")
   PORT:read()
   txString = ""
   platform.window:invalidate()
end

function on.escapeKey()
   reset()
end

function splitTextByWidth(text, maxWidth, gc)
   local lines = {}
   local currentLine = ""
   for i = 1, #text do
      local char = text:sub(i, i)
      -- Check if adding the next character exceeds maxWidth
      if gc:getStringWidth(currentLine .. char) > maxWidth then
         table.insert(lines, currentLine)
         currentLine = char
      else
         currentLine = currentLine .. char
      end
   end
   if currentLine ~= "" then
      table.insert(lines, currentLine)
   end
   return lines
end

function on.paint(gc)
    local W, H = platform.window:width(), platform.window:height()  -- Get window dimensions
    local fontSize = 18  -- Example fixed font size
    
    -- Draw rectangles
    gc:setColorRGB(0x303030)
    gc:fillRect(9, H - 65, 296, 50)
    gc:fillRect(15, H - 71, 285, 61)
    
    -- Helper function to draw filled circles
    local function drawFilledCircle(x, y, radius)
        gc:fillArc(x - radius, y - radius, 2*radius, 2*radius, 0, 360)
    end
    -- Drawing filled circles for text inputs
    local circleRadius = 10
    drawFilledCircle(W - 299, 151, circleRadius)  -- Top left text input
    drawFilledCircle(W - 299, 192, circleRadius)  -- Bottom left text input
    drawFilledCircle(W - 23, 192, circleRadius)   -- Bottom right text input
    drawFilledCircle(W - 23, 151, circleRadius)   -- Top right text input
    gc:setColorRGB(0xFEFEFE)
    drawFilledCircle(W - 27, 188, circleRadius)
    
    -- Set a larger font size for the CHATgpt label
    gc:setFont("sansserif", "b", fontSize * 0.65)  -- 50% larger than the base fontSize
    gc:setColorRGB(0xb4b4b4)
    gc:drawString("TI-GPT", leftMargin, H - fontSize * 0.5 - 205)
    gc:setFont("sansserif", "r", fontSize * 0.6)
    gc:drawString("v", leftMargin + 55, H - fontSize * 0.5 - 205)
    gc:setColorRGB(0x000000)
    gc:setFont("sansserif", "b", fontSize * 0.6)
    gc:drawString("^", leftMargin + 285, H - fontSize * 0.5 - 26)
    gc:setFont("sansserif", "r", fontSize * 0.5)
    gc:drawString("I", leftMargin + 288, H - fontSize * 0.5 - 24)
    gc:setFont("sansserif", "r", 11)
    gc:setColorRGB(0x2D2D2D)
    gc:drawString("Created by OtterCad", leftMargin + 177, H - fontSize * 0.5 - 205)
    
    -- Set font and color for text
    gc:setFont("sansserif", "r", fontSize/1.75)
    gc:setColorRGB(0xfefefe)  -- Very light grey, almost white

    -- Define positions for txString and rxString
    local txX = leftMargin + 15
    local txY = 122
    
    -- Wrap txString into lines where each line is at most 285 pixels wide
    local wrappedLines = splitTextByWidth(txString or "", 285, gc)
    
    -- Draw each line of txString, offsetting vertically by lineSpace
    for i, line in ipairs(wrappedLines) do
       gc:drawString(line, txX, txY + 20 + (i-1)*lineSpace)
    end
    
    gc:setColorRGB(0x212121) -- Box to cover hidden line
    gc:fillRect(9, H - 93, 325, 20)
    
    gc:setColorRGB(0xfefefe)
    local rxX = leftMargin + 10
    local rxY = txY - 105

    -- Apply text-wrapping logic to rxString if it exists
    if rxString then
       -- Ensure that rxString has at least 2 characters before trimming
       local trimmedRx = (#rxString > 2) and rxString:sub(1, -3) or ""
       local rxWrappedLines = splitTextByWidth(trimmedRx, 285, gc)
       for i, line in ipairs(rxWrappedLines) do
          gc:drawString(line, rxX, rxY + (i-1)*lineSpace)
       end
    end
    
end
