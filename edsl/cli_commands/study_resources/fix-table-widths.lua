-- fix-table-widths.lua
-- Pandoc Lua filter: fix four causes of column overflow in PDF tables.
--
-- Problem 1: pandoc's default LaTeX output uses unconstrained `l` columns.
--   Long text overflows past column boundaries and collides with adjacent columns.
--   Fix: distribute proportional widths so LaTeX uses p{} columns (text wraps at spaces).
--
-- Problem 2: wide tables (5+ columns) are too dense even with wrapped columns.
--   Fix: wrap the entire table in \footnotesize (~8pt at 10pt base), giving
--   each column more breathing room.  \footnotesize works with longtable
--   (unlike \resizebox, which cannot contain a longtable environment).
--
-- Problem 3: compound words containing + or / have no space for LaTeX to break
--   on, so they overflow even inside a p{} column.
--   e.g. "Strength+Honor", "Farmer/food", "Leadership/plan"
--   Fix: insert \allowbreak{} after + and / so LaTeX can break there.
--
-- Problem 4: long single words (e.g. "Accountability", "Competence") are wider
--   than a narrow p{} column and overflow because LaTeX's default hyphenation
--   penalty (50) discourages mid-word breaks.
--   Fix: set \hyphenpenalty=0 and \exhyphenpenalty=0 inside every table group,
--   making hyphenation free so LaTeX always breaks words that don't fit.
--
-- Usage (in Makefile):
--   cd writeup && pandoc report.md -o report.pdf --pdf-engine=xelatex \
--     --include-in-header=report_header.tex \
--     --lua-filter=fix-table-widths.lua

local is_latex = FORMAT:match("latex") or FORMAT:match("pdf") or FORMAT == "beamer"

-- Split a Str at + and / characters, interleaving \allowbreak{} RawInlines.
local function make_breakable(text)
  local result = {}
  local current = ""
  for i = 1, #text do
    local ch = text:sub(i, i)
    current = current .. ch
    if ch == "+" or ch == "/" then
      table.insert(result, pandoc.Str(current))
      table.insert(result, pandoc.RawInline("latex", "\\allowbreak{}"))
      current = ""
    end
  end
  if current ~= "" then
    table.insert(result, pandoc.Str(current))
  end
  return result
end

local function fix_inlines(inlines)
  local result = {}
  for _, el in ipairs(inlines) do
    if el.t == "Str" then
      for _, item in ipairs(make_breakable(el.text)) do
        table.insert(result, item)
      end
    else
      table.insert(result, el)
    end
  end
  return pandoc.Inlines(result)
end

local function fix_blocks(blocks)
  local result = {}
  for _, block in ipairs(blocks) do
    if block.t == "Para" or block.t == "Plain" then
      block.content = fix_inlines(block.content)
    end
    table.insert(result, block)
  end
  return pandoc.Blocks(result)
end

local function fix_cell(cell)
  cell.contents = fix_blocks(cell.contents)
  return cell
end

local function fix_row(row)
  local new_cells = {}
  for _, cell in ipairs(row.cells) do
    table.insert(new_cells, fix_cell(cell))
  end
  row.cells = new_cells
  return row
end

local function fix_rows(rows)
  local result = {}
  for _, row in ipairs(rows) do
    table.insert(result, fix_row(row))
  end
  return result
end

function Table(el)
  -- Fix 1: distribute column widths proportionally to force p{} columns.
  local ncols = #el.colspecs
  if ncols > 0 then
    -- 0.97 leaves a small margin so the table doesn't hit the exact page edge.
    local w = 0.97 / ncols
    for i = 1, ncols do
      el.colspecs[i] = { el.colspecs[i][1], w }
    end
  end

  -- Fix 3: add \allowbreak{} after + and / in all cells (LaTeX output only).
  if is_latex then
    el.head.rows = fix_rows(el.head.rows)
    for i = 1, #el.bodies do
      el.bodies[i].head = fix_rows(el.bodies[i].head)
      el.bodies[i].body = fix_rows(el.bodies[i].body)
    end
    el.foot.rows = fix_rows(el.foot.rows)
  end

  -- Fixes 2 and 4: wrap in a LaTeX group that:
  --   \hyphenpenalty=0\exhyphenpenalty=0 — makes hyphenation free so long
  --     single words (e.g. "Accountability") always break rather than overflow.
  --   \footnotesize — for wide tables (5-7 cols), reduce font size so headers
  --     and cells fit without overlap.
  --
  -- Fix 5: for very wide tables (8+ columns) rotate the entire page to landscape
  --   using pdflscape.  Portrait \textwidth (~6.5 in) cannot fit 8 columns; landscape
  --   gives ~9 in.  longtable renders correctly inside landscape because pdflscape
  --   rotates the whole page, not a box.  (Requires \usepackage{pdflscape} in header.)
  if is_latex and ncols >= 8 then
    return {
      pandoc.RawBlock("latex", "\\begin{landscape}"),
      pandoc.RawBlock("latex", "{\\hyphenpenalty=0\\exhyphenpenalty=0"),
      el,
      pandoc.RawBlock("latex", "}"),
      pandoc.RawBlock("latex", "\\end{landscape}"),
    }
  end

  local font_cmd = ncols >= 5 and "\\footnotesize" or ""
  return {
    pandoc.RawBlock("latex", "{" .. font_cmd .. "\\hyphenpenalty=0\\exhyphenpenalty=0"),
    el,
    pandoc.RawBlock("latex", "}"),
  }
end

