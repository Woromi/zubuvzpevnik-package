-- Per-book song transposition (\transposesong): the key the printed shapes end
-- up in, the sharps/flats choice that follows from it, and the LilyPond header
-- that transposes a re-shaped song's scores. See docs/internals.md#per-book-transposition.
zubtr = { cur = nil }

-- Pitch classes, C = 0. B is B-flat in German naming, H is B-natural.
local NATURAL = { C = 0, D = 2, E = 4, F = 5, G = 7, A = 9, B = 11, H = 11 }

-- One note name at the start of s, read in the song's naming: pitch class,
-- the accidental written (-1, 0, 1) and the rest of the string.
local function readnote(s, german)
  s = s:gsub("^[%s{}]+", "")
  local root = s:sub(1, 1)
  local pc = NATURAL[root]
  if not pc or (root == "H" and not german) then return nil end
  if root == "B" and german then pc = 10 end
  local rest, acc = s:sub(2), 0
  if rest:match("^\\shrp") then acc, rest = 1, rest:sub(6)
  elseif rest:match("^\\flt") then acc, rest = -1, rest:sub(5)
  elseif rest:match("^#") then acc, rest = 1, rest:sub(2)
  elseif rest:match("^&") then acc, rest = -1, rest:sub(2)
  end
  return (pc + acc) % 12, acc, rest:gsub("^[%s{}]+", "")
end

-- A key= value (only the home key of "A\rightarrow Hm"): pitch class, minor?,
-- written accidental.
local function readkey(s, german)
  local pc, acc, rest = readnote(s or "", german)
  if not pc then return nil end
  return { pc = pc, minor = rest:match("^m") ~= nil and not rest:match("^maj"), acc = acc }
end

-- Semitones a uniform tun= detuning moves every shape (as checkkeys.py reads it).
local STANDARD = { 4, 9, 2, 7, 11, 4 }
local function readtuning(s, german)
  local name = (s or ""):lower():gsub("^%s+", ""):gsub("%s+$", "")
  if name == "" or name == "standard" then return 0 end
  if name == "half-step down" or name == "half step down" then return -1 end
  local notes = {}
  for word in s:gmatch("%S+") do
    local pc = readnote(word, german)
    if not pc then return 0 end
    notes[#notes + 1] = pc
  end
  if #notes ~= #STANDARD then return 0 end
  local shift
  for i, pc in ipairs(notes) do
    local d = (pc - STANDARD[i] + 6) % 12 - 6
    if shift and d ~= shift then return 0 end
    shift = d
  end
  return shift
end

-- Which accidentals a key's signature uses.
local MAJOR_SHARP = { [0] = true, [2] = true, [4] = true, [6] = true, [7] = true, [9] = true, [11] = true }
local MINOR_SHARP = { [1] = true, [4] = true, [6] = true, [8] = true, [9] = true, [11] = true }
local function sharpkey(pc, minor)
  if minor then return MINOR_SHARP[pc] or false end
  return MAJOR_SHARP[pc] or false
end

-- LilyPond spelling of a pitch class: notename (c = 0) and alteration in tones.
local SHARP_NAME = { [0] = { 0, 0 }, { 0, 1 }, { 1, 0 }, { 1, 1 }, { 2, 0 }, { 3, 0 },
                     { 3, 1 }, { 4, 0 }, { 4, 1 }, { 5, 0 }, { 5, 1 }, { 6, 0 } }
local FLAT_NAME = { [0] = { 0, 0 }, { 1, -1 }, { 1, 0 }, { 2, -1 }, { 2, 0 }, { 3, 0 },
                    { 4, -1 }, { 4, 0 }, { 5, -1 }, { 5, 0 }, { 6, -1 }, { 6, 0 } }
local SCALE = { [0] = 0, 2, 4, 5, 7, 9, 11 }
local function spell(pc, sharps)
  local s = (sharps and SHARP_NAME or FLAT_NAME)[pc]
  return s[1], s[2]
end

-- The interval from the source key to the target as (octave, notename,
-- alteration in half-tone steps), spelled key to key so the notes land in the
-- target key's spelling; exactly n semitones.
local function interval(from_pc, from_sharps, to_pc, to_sharps, n)
  local fn, fa = spell(from_pc, from_sharps)
  local tn, ta = spell(to_pc, to_sharps)
  local dn = (tn - fn) % 7
  local da = ((SCALE[tn] + ta) - (SCALE[fn] + fa) - SCALE[dn] + 6) % 12 - 6
  local oct = (n - SCALE[dn] - da) // 12
  return oct, dn, da
end

-- Song start: a.n semitones of re-shaping. Works out the key the printed home
-- shapes are in (target sounding key, less capo and detuning) and returns the
-- accidental pin for it, "sharps", "flats" or "" when no key is known.
function zubtr.song(a)
  local german = a.german
  local book = readkey(a.bookkey, german)
  local own = readkey(a.key, german)
  local target
  if book then
    target = book
  elseif own then
    target = { pc = (own.pc + a.n) % 12, minor = own.minor, acc = 0 }
  end
  local offset = (a.transcapos and 0 or (tonumber(a.cap) or 0)) + readtuning(a.tun, german)
  local cur = { n = a.n }
  if target then
    local pc = (target.pc - offset) % 12
    local sharps = sharpkey(pc, target.minor)
    -- A spelling written in key= wins where it is the printed key itself.
    if book and offset % 12 == 0 and book.acc ~= 0 then sharps = book.acc > 0 end
    local from = (pc - a.n) % 12
    cur.pin = sharps and "sharps" or "flats"
    cur.oct, cur.step, cur.alt = interval(from, sharpkey(from, target.minor), pc, sharps, a.n)
  else
    cur.pin = ""
    local pc = a.n % 12
    cur.oct, cur.step, cur.alt = interval(0, true, pc, sharpkey(pc, false), a.n)
  end
  zubtr.cur = cur
  return cur.pin
end

-- Header for a re-shaped song's scores: a toplevel-score-handler that
-- transposes every score before it is set. Bump the version when the Scheme
-- changes -- lyluatex's cache hashes the include's name, not its contents.
local VERSION = 1
local HEADER = [[
%% Written by zubuvzpevnik (lua/transpozice.lua) for \transposesong
#(define zub-tr-pitch (ly:make-pitch %d %d %s))
#(define zub-tr-next-handler toplevel-score-handler)
#(define (toplevel-score-handler score . rest)
   (let* ((music (ly:music-transpose
                   (ly:music-deep-copy (ly:score-music score)) zub-tr-pitch))
          (new (ly:make-score music))
          (header (ly:score-header score)))
     (for-each (lambda (od) (ly:score-add-output-def! new od))
               (reverse (ly:score-output-defs score)))
     (if (module? header) (ly:score-set-header! new header))
     (apply zub-tr-next-handler new rest)))
]]

local function readfile(name)
  local path = kpse.find_file(name) or name
  local f = io.open(path, "r")
  if not f then return nil end
  local text = f:read("*a")
  f:close()
  return text
end

-- lyluatex options for \lilypondfile{file} in the current song: "" when it is
-- not re-shaped, else an include_header naming the transposing header.
function zubtr.lyopts(file)
  local cur = zubtr.cur
  if not cur or cur.n == 0 then return "" end
  local text = readfile(file)
  if text and text:find('\\include%s*"tinwhistle%.ily"') then
    tex.sprint("\\PackageWarning{zubuvzpevnik}{Score '" .. file .. "' is a tin"
      .. " whistle part: its fingerings are for one whistle, so \\string"
      .. "\\transposesong leaves it as written}")
    return ""
  end
  local alt = cur.alt == 0 and "0" or (cur.alt .. "/2")
  local dir = lua_options.get_option("ly", "tmpdir") or "tmp-ly"
  if not lfs.isdir(dir) then lfs.mkdir(dir) end
  local name = string.format("%s/zubtranspose%d_%d_%d_%d", dir, VERSION,
    cur.oct, cur.step, cur.alt)
  local f = io.open(name .. ".ly", "w")
  f:write(HEADER:format(cur.oct, cur.step, alt))
  f:close()
  return "include_header=" .. name
end
