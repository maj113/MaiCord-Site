"""Renders MaiCord's developer guides (guides/*.md, copied from the MaiCord repository by sync_guides.py)
to the HTML of /plugins/develop/ and /effects/develop/.

The guides are plain Markdown written for GitHub: headings, paragraphs, `-` and numbered lists with
indented continuation lines, tables, fenced code, `code`, **bold**, *italic* and https links. This
renders exactly that and nothing else; every character is escaped. Code blocks are coloured with
a small tokenizer (comments, strings, numbers, keywords), so the page needs no script."""
import html
import re

from markup import inline

C_WORDS = frozenset("""alignas auto bool break case char class const constexpr consteval constinit continue default delete
do else enum explicit extern false float for if inline int long namespace noexcept nullptr operator private public
return short signed sizeof static struct switch template this true typedef typename union unsigned using void while
double uint uint2 uint3 uint4 float2 float3 float4 float4x4 int2 int3 int4 Texture2D SamplerState cbuffer
u8 u16 u32 u64 i8 i16 i32 i64""".split())
TOKENS = re.compile(r"""
    (?P<c>//[^\n]*|/\*.*?\*/)
  | (?P<s>"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')
  | (?P<p>^[ \t]*\#[a-z]+)
  | (?P<n>\b0[xX][0-9A-Fa-f']+\b|\b\d[\d'.]*[fFuUlL]?\b)
  | (?P<w>[A-Za-z_][A-Za-z_0-9]*)
""", re.S | re.M | re.X)
SHELL_TOKENS = re.compile(r"(?P<c>(?<![\w`])\#[^\n]*)|(?P<s>\"(?:`.|[^\"`\n])*\"|'[^'\n]*')", re.M)
CLASSES = {"c": "c", "s": "s", "n": "s", "p": "k", "w": "k"}


def highlight(code, lang):
    """The escaped `code` with <span class="c|s|k"> around comments, strings and keywords."""
    if lang in ("cpp", "c", "hlsl", "cxx"):
        pattern = TOKENS
    elif lang in ("powershell", "ps1", "sh", "bash"):
        pattern = SHELL_TOKENS
    else:
        return html.escape(code)
    out, last = [], 0
    for m in pattern.finditer(code):
        kind = m.lastgroup
        if kind == "w" and m[0] not in C_WORDS:
            continue
        out.append(html.escape(code[last:m.start()]))
        out.append(f'<span class="{CLASSES[kind]}">{html.escape(m[0])}</span>')
        last = m.end()
    out.append(html.escape(code[last:]))
    return "".join(out)


def slug(text, taken):
    base = re.sub(r"[^a-z0-9]+", "-", re.sub(r"`", "", text).lower()).strip("-") or "section"
    name, n = base, 2
    while name in taken:
        name, n = f"{base}-{n}", n + 1
    taken.add(name)
    return name


def cells(row):
    """The cells of a table row, splitting on `|` outside code spans."""
    out, cell, code = [], [], False
    for ch in row.strip().strip("|"):
        if ch == "`":
            code = not code
        if ch == "|" and not code:
            out.append("".join(cell).strip())
            cell = []
        else:
            cell.append(ch)
    out.append("".join(cell).strip())
    return out


def render(text, links=None):
    """(title, sections, html) for a guide: its `#` title, its `##` headings as [(id, text)] and the page
    body. `links` maps an inline-code text to a URL to link it to."""
    links = links or {}
    taken, sections = set(), []
    title, out = "", []
    paragraph, items, ordered, code, lang = [], [], False, None, ""
    lines = text.replace("\r", "").split("\n")
    heading_text = ""

    def span(source):
        done = inline(source, True)
        for target, url in links.items():
            done = done.replace(f"<code>{html.escape(target)}</code>", f'<a href="{html.escape(url)}"><code>{html.escape(target)}</code></a>')
        return done

    def flush():
        nonlocal ordered
        if paragraph:
            out.append("<p>" + span(" ".join(paragraph)) + "</p>")
            paragraph.clear()
        if items:
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{span(' '.join(i))}</li>" for i in items) + f"</{tag}>")
            items.clear()
            ordered = False

    n = 0
    while n < len(lines):
        line = lines[n].rstrip()
        n += 1
        if code is not None:
            if line.startswith("```"):
                body = highlight("\n".join(code), lang)
                out.append(f'<pre tabindex="0"><code>{body}</code></pre>')
                code = None
            else:
                code.append(lines[n - 1].rstrip("\n"))
            continue
        heading = re.match(r"(#{1,3}) +(.+)", line)
        bullet = re.match(r"- +(.*)", line)
        number = re.match(r"\d+\. +(.*)", line)
        if line.startswith("```"):
            flush()
            code, lang = [], line[3:].strip().lower()
        elif heading:
            flush()
            level, text_ = len(heading[1]), heading[2]
            if level == 1:
                title = re.sub(r"`", "", text_)
                continue
            heading_text = re.sub(r"`", "", text_)
            name = slug(text_, taken)
            if level == 2:
                sections.append((name, heading_text))
            out.append(f'<h{level} id="{name}"><a class="anchor" href="#{name}" aria-label="Link to {html.escape(heading_text)}">'
                       f'{inline(text_)}</a></h{level}>')
        elif line.startswith("|") and n < len(lines) and re.match(r"\|[\s:|-]+\|$", lines[n].strip()):
            flush()
            head = cells(line)
            n += 1
            rows = []
            while n < len(lines) and lines[n].startswith("|"):
                rows.append(cells(lines[n]))
                n += 1
            label = html.escape(heading_text or "Table")
            out.append(f'<div class="scroll" role="region" aria-label="{label}" tabindex="0"><table class="sheet"><thead><tr>'
                       + "".join(f"<th>{span(c)}</th>" for c in head) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{span(c)}</td>" for c in row) + "</tr>" for row in rows)
                       + "</tbody></table></div>")
        elif bullet or number:
            if paragraph or (items and ordered != bool(number)):
                flush()
            ordered = bool(number)
            items.append([(bullet or number)[1]])
        elif not line:
            flush()
        elif line[0] == " " and items:
            items[-1].append(line.strip())
        else:
            if items:
                flush()
            paragraph.append(line.strip())
    flush()
    if code is not None:
        raise ValueError("unterminated code fence")
    return title, sections, "".join(out)
