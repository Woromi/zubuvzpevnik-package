-- Merged chord chart for \insertallchords: every diagram in the book once,
-- sorted. Kept in its own file because \directlua expands its argument as TeX,
-- which mangles the backslashes and percent signs this code needs.
-- See docs/internals.md#collected-chord-diagrams.
zubchr = { seen = {}, list = {} }

-- Chord names arrive detokenized, so \shrp and \flt are literal text. Fold them
-- to characters that sort after letters and digits, so a root's plain chords
-- come first and its altered ones follow: C7, C9, Cmaj7, then C\flt .., C\shrp ..
-- Folding to a literal # would instead file C\shrp 7b9 ahead of C7.
local function sortkey(name)
  local k = name:gsub("\\shrp%s*", "}"):gsub("\\flt%s*", "|")
  return k:lower()
end

function zubchr.add(name, fing)
  local key = name .. ":" .. fing
  if not zubchr.seen[key] then
    zubchr.seen[key] = true
    zubchr.list[#zubchr.list + 1] =
      { name = name, fing = fing, key = sortkey(name) }
  end
end

function zubchr.emit()
  table.sort(zubchr.list, function(a, b)
    if a.key == b.key then return a.fing < b.fing end
    return a.key < b.key
  end)
  for _, c in ipairs(zubchr.list) do
    -- one input line each: the line end supplies the interword glue TeX
    -- needs to break the chart into rows.
    tex.print("\\gtab{" .. c.name .. "}{" .. c.fing .. "}")
  end
end
