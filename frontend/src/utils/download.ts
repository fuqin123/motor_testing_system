function safeCell(value: unknown): string {
  const text = value === null || value === undefined ? '' : String(value)
  if (/^[=+\-@\t]/.test(text)) return `'${text}`
  return text
}

export function downloadText(text: string, filename: string, mime: string): void {
  const blob = new Blob([text], { type: `${mime};charset=utf-8` })
  downloadBlob(blob, filename)
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 800)
}

export function downloadCsv(rows: unknown[][], filename: string): void {
  const content = rows
    .map((row) => row.map((cell) => `"${safeCell(cell).replace(/"/g, '""')}"`).join(','))
    .join('\r\n')
  downloadText(`\ufeff${content}`, filename, 'text/csv')
}
