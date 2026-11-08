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

-- What \multivoiceoff prints of a \multivoice{main}{second}: main alone.
local MV = "\\multivoice (%b{})(%b{})"

-- Prints nothing in the reminder: chords, second voices, braces, spaces.
local function silent(s)
  s = s:gsub(MV, "%1"):gsub("\\%[[^%]]*%]", ""):gsub("[{}%s~]", "")
  return s == ""
end

-- Drops one silent piece from the end of the line -- a chord, a group or a
-- \multivoice with nothing printed -- and unwraps a final \multivoice to its
-- main voice, so its punctuation can go too.
local function untail(line)
  line = line:gsub("%s+$", "")
  local at = line:find("\\%[[^%]]*%]$") or line:find("%b{}$")
  if not at or not silent(line:sub(at)) then
    at = line:find(MV .. "$")
  end
  if not at then return line end
  if silent(line:sub(at)) then return line:sub(1, at - 1) end
  local main = line:sub(at):match("^" .. MV .. "$")
  return line:sub(1, at - 1) .. main:sub(2, -2)
end

-- s is the chorus as \detokenize left it: catcode-12 text, lines split by CR.
-- Prints the reminder as the same catcode-12 string (TeX turns its chords and
-- second voice off); nothing if the chorus has no text line. extra (a \rep{n})
-- follows the dots.
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
  -- Chords and second voices after the last word print nothing here, but
  -- would keep the space before them and shield the punctuation before that:
  -- "ation \[Am]" gave "ation ...", "know \multivoice{}{We all}" "know ...".
  -- So they go first, with their spaces.
  repeat
    local before = line
    line = untail(line)
  until line == before
  -- Trailing punctuation (and dots already there) give way to the "...".
  line = line:gsub("[,.;:!?]+$", "")
  if extra and extra ~= "" then extra = " " .. extra else extra = "" end
  tex.sprint(-2, line .. "..." .. extra .. role)
end
