-- \multivoiceinline: joins adjacent "(a)" "(b)" second-voice fragments into one
-- "(a b)" once the line is assembled. See docs/internals.md#multi-voice-hlasycfg.
local attr = luatexbase.attributes["zub@mvattr"]
local OPEN, CLOSE, SPACE = 1, 2, 3
local GLYPH, HLIST, VLIST = node.id("glyph"), node.id("hlist"), node.id("vlist")
local RULE, PENALTY, GLUE = node.id("rule"), node.id("penalty"), node.id("glue")

local function lyricrow(v)
  local last = node.tail(v.head)
  while last and last.id ~= HLIST do last = last.prev end
  return last
end

-- Filler spacing (~) is \nobreak plus a space, like any lyric it splits. A
-- chord over no lyric ends in the same pair, so after one it isn't filler.
local function isfiller(n)
  if n.penalty ~= 10000 or not (n.next and n.next.id == GLUE) then return false end
  local p = n.prev
  if p and p.id == VLIST and p.head then
    local row = lyricrow(p)
    return row ~= nil and node.has_glyph(row.head) ~= nil
  end
  return true
end

-- Lyric glyphs, splitters and marked glue in reading order; a chord's vbox is
-- walked through its last row only (the lyric), so chord names never count as
-- text. A measure bar's rule and a ~ split the parens like text does.
local function walk(head, path, out)
  for n in node.traverse(head) do
    if n.id == GLYPH or node.has_attribute(n, attr) then
      out[#out + 1] = { n = n, path = path }
    elseif n.id == RULE or (n.id == PENALTY and isfiller(n)) then
      out[#out + 1] = { n = n, path = path, split = true }
    elseif n.id == HLIST and n.head then
      walk(n.head, { box = n, up = path }, out)
    elseif n.id == VLIST and n.head then
      local last = lyricrow(n)
      if last and last.head then
        walk(last.head, { box = last, up = { box = n, up = path } }, out)
      end
    end
  end
end

local function remove(head, e)
  local w = e.n.width or 0
  if not e.path then
    head = node.remove(head, e.n)
    node.free(e.n)
    return head
  end
  local box = e.path.box
  box.head = node.remove(box.head, e.n)
  node.free(e.n)
  local p = e.path
  while p do
    local b = p.box
    if b.id == HLIST then
      if b.glue_sign == 0 then b.width = b.width - w end
    else
      local m = 0
      for c in node.traverse(b.head) do
        if c.width and c.width > m then m = c.width end
      end
      b.width = m
    end
    p = p.up
  end
  return head
end

local function merge(head)
  local out = {}
  walk(head, nil, out)
  local close, spaces = nil, {}
  local doomed = {}
  for _, e in ipairs(out) do
    local a = node.has_attribute(e.n, attr)
    if a == CLOSE then
      close, spaces = e, {}
    elseif a == OPEN then
      if close then
        doomed[#doomed + 1] = close
        for _, s in ipairs(spaces) do doomed[#doomed + 1] = s end
        doomed[#doomed + 1] = e
      end
      close = nil
    elseif a == SPACE then
      if close then spaces[#spaces + 1] = e end
    elseif e.split or e.n.id == GLYPH then
      close = nil
    end
  end
  for _, e in ipairs(doomed) do head = remove(head, e) end
  return head
end

luatexbase.add_to_callback("pre_linebreak_filter", function(head)
  return merge(head)
end, "zub.multivoice")
