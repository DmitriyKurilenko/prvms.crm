const escapeHtml = (s: string): string =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

const inline = (s: string): string => {
  let out = escapeHtml(s)
  out = out.replace(/`([^`]+)`/g, (_, c) => `<code>${c}</code>`)
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  out = out.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
  out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text: string, href: string) => {
    const safe = href.replace(/"/g, '&quot;')
    const isExternal = /^https?:\/\//.test(href)
    const attrs = isExternal ? ' target="_blank" rel="noopener"' : ''
    return `<a href="${safe}"${attrs}>${text}</a>`
  })
  return out
}

export const slugify = (text: string): string =>
  text
    .toLowerCase()
    .trim()
    .replace(/[^\p{L}\p{N}\s-]/gu, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')

export interface MarkdownHeading {
  level: number
  text: string
  slug: string
}

export interface RenderedMarkdown {
  html: string
  headings: MarkdownHeading[]
}

export const renderMarkdown = (source: string): RenderedMarkdown => {
  const lines = source.replace(/\r\n?/g, '\n').split('\n')
  const out: string[] = []
  const headings: MarkdownHeading[] = []

  let i = 0
  let listType: 'ul' | 'ol' | null = null
  let inPara = false
  let paraBuf: string[] = []

  const closeList = () => {
    if (listType) {
      out.push(`</${listType}>`)
      listType = null
    }
  }

  const flushPara = () => {
    if (inPara) {
      out.push(`<p>${inline(paraBuf.join(' '))}</p>`)
      paraBuf = []
      inPara = false
    }
  }

  while (i < lines.length) {
    const line = lines[i]

    if (/^\s*$/.test(line)) {
      flushPara()
      closeList()
      i++
      continue
    }

    const hrMatch = /^(-{3,}|\*{3,})\s*$/.test(line.trim())
    if (hrMatch) {
      flushPara()
      closeList()
      out.push('<hr />')
      i++
      continue
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.*)$/)
    if (headingMatch) {
      flushPara()
      closeList()
      const level = headingMatch[1].length
      const text = headingMatch[2].trim()
      const slug = slugify(text)
      headings.push({ level, text, slug })
      out.push(`<h${level} id="${slug}">${inline(text)}</h${level}>`)
      i++
      continue
    }

    const ulMatch = line.match(/^[-*]\s+(.*)$/)
    const olMatch = line.match(/^\d+\.\s+(.*)$/)
    if (ulMatch || olMatch) {
      flushPara()
      const wanted: 'ul' | 'ol' = ulMatch ? 'ul' : 'ol'
      if (listType !== wanted) {
        closeList()
        listType = wanted
        out.push(`<${wanted}>`)
      }
      const content = (ulMatch ? ulMatch[1] : (olMatch as RegExpMatchArray)[1]).trim()
      out.push(`<li>${inline(content)}</li>`)
      i++
      continue
    }

    closeList()
    inPara = true
    paraBuf.push(line.trim())
    i++
  }

  flushPara()
  closeList()

  return { html: out.join('\n'), headings }
}
