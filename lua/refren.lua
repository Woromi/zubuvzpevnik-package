-- \insertchorus*: the first line of a captured chorus that carries text. A line
-- of commands alone -- \chordsoffonsmallpage right after \beginchorus, a
-- \memorize, a \usechords{verse} -- is setup, not the line to remind of.
-- Kept in its own file because \directlua expands its argument as TeX.
-- See docs/internals.md#source-capture.
zubchorus = {}

-- s is the chorus as \detokenize left it: catcode-12 text, lines split by CR.
function zubchorus.first(s)
  for line in (s .. "\r"):gmatch("(.-)\r") do
    local text = line:gsub("\\[%a@]+%*?", ""):gsub("%b{}", ""):gsub("[%s~]", "")
    if text ~= "" then
      tex.sprint(-2, line)          -- back as the same catcode-12 string
      return
    end
  end
end
