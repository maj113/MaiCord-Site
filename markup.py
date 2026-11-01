"""Small, safe markup helpers shared by the page builders: inline Markdown for
release notes and catalog text, and the block subset catalog descriptions use.
Everything is escaped; only https links are kept."""
import html
import re


def inline(text):
    """Escapes text and renders `code`, **bold** and [links](https://...)."""
    out, i = [], 0
    while i < len(text):
        if text[i] == "`":
            run = len(text[i:]) - len(text[i:].lstrip("`"))
            end = text.find("`" * run, i + run)
            if end > 0:
                out.append("<code>" + html.escape(text[i + run:end].strip()) + "</code>")
                i = end + run
                continue
        if text.startswith("**", i):
            end = text.find("**", i + 2)
            if end > 0:
                out.append("<strong>" + inline(text[i + 2:end]) + "</strong>")
                i = end + 2
                continue
        link = re.match(r"\[([^\]]+)\]\((https://[^)\s]+)\)", text[i:])
        if link:
            out.append(f'<a href="{html.escape(link[2])}">{inline(link[1])}</a>')
            i += link.end()
            continue
        out.append(html.escape(text[i]))
        i += 1
    return "".join(out)


def markdown(text, top=3):
    """Renders headings (`#`..`###`, shown from <h{top}>), paragraphs, `- `
    lists and ``` code fences. Anything else is a paragraph line."""
    out, paragraph, items, code = [], [], [], None

    def flush():
        if paragraph:
            out.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
            items.clear()

    for line in text.replace("\r", "").split("\n"):
        if code is not None:
            if line.startswith("```"):
                out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
                code = None
            else:
                code.append(line)
            continue
        line = line.rstrip()
        heading = re.match(r"(#{1,3}) +(.+)", line)
        if line.startswith("```"):
            flush()
            code = []
        elif heading:
            flush()
            level = min(top + len(heading[1]) - 1, 6)
            out.append(f"<h{level}>{inline(heading[2])}</h{level}>")
        elif line.startswith("- "):
            if paragraph:
                flush()
            items.append(line[2:])
        elif not line:
            flush()
        else:
            if items:
                flush()
            paragraph.append(line.strip())
    if code is not None:
        out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
    flush()
    return "".join(out)
