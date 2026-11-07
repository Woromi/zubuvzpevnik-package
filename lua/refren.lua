-- \insertchorus*: the one-line reminder built from a captured chorus. Kept in
-- its own file because \directlua expands its argument as TeX.
-- See docs/internals.md#source-capture.
zubchorus = {}

-- \detokenize puts a space after every control word, so these are the marks as
-- they appear in the captured string.
local LREP = { "\\lrep ~", "\\lrep \\ ", "\\lrep " }
local RREP, ROLE = "\\rrep ", "\\role "

-- The first line that carries text. A line of commands alone --
-- \chordsoffonsmallpage right after \beginchorus, a \memorize, a
-- \usechords{verse} -- is setup, not the line to remind of.
local function first(s)
  for line in (s .. "\r"):gmatch("(.-)\r") do
    local text = line:gsub("\\[%a@]+%*?", ""):gsub("%b{}", ""):gsub("[%s~]", "")
    if text ~= "" then return line end
  end
end

local function starts(s, p) return s:sub(1, #p) == p end

-- s is the chorus as \detokenize left it: catcode-12 text, lines split by CR.
-- Prints the reminder, chords and second voice off, as the same catcode-12
-- string; nothing if the chorus has no text line. extra (a \rep{n}) follows
-- the dots.
function zubchorus.reminder(s, extra)
  local line = first(s)
  if not line then return end
  -- One line, so its repeat marks would not pair up.
  for _, p in ipairs(LREP) do
    if starts(line, p) then line = line:sub(#p + 1) end
  end
  local role = ""
  local at = line:find(RREP, 1, true)
  while at do
    line = line:sub(1, at - 1) .. line:sub(at + #RREP)
    at = line:find(RREP, 1, true)
  end
  line = line:gsub("%s+$", "")
  -- A \role label ending the line is not lyrics: the dots go before it.
  at = line:find(ROLE, 1, true)
  if at then
    role = " " .. line:sub(at)
    line = line:sub(1, at - 1):gsub("%s+$", "")
  end
  -- Trailing punctuation (and dots already there) give way to the "...".
  line = line:gsub("[,.;:!?]+$", "")
  if extra and extra ~= "" then extra = " " .. extra else extra = "" end
  tex.sprint(-2, "\\chordsoff\\multivoiceoff " .. line .. "..." .. extra .. role)
end
