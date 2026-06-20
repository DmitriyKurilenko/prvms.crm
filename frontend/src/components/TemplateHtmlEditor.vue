<template>
  <div>
    <label class="field-label">Содержимое шаблона</label>
    <div class="editor-toolbar">
      <PButton icon="pi pi-bold" text size="small" @click="editorCmd('bold')" title="Жирный" />
      <PButton icon="pi pi-italic" text size="small" @click="editorCmd('italic')" title="Курсив" />
      <PButton icon="pi pi-underline" text size="small" @click="editorCmd('underline')" title="Подчёркнутый" />
      <span class="toolbar-sep" />
      <PButton label="H1" text size="small" @click="editorCmd('formatBlock', 'h1')" />
      <PButton label="H2" text size="small" @click="editorCmd('formatBlock', 'h2')" />
      <PButton label="P" text size="small" @click="editorCmd('formatBlock', 'p')" />
      <span class="toolbar-sep" />
      <PButton icon="pi pi-list" text size="small" @click="editorCmd('insertUnorderedList')" title="Список" />
      <PButton icon="pi pi-table" text size="small" @click="insertTable" title="Таблица" />
      <span class="toolbar-sep" />
      <PSelect v-model="fieldToInsert" :options="fieldOptions" optionLabel="label" optionValue="value" placeholder="Вставить поле сделки" size="small" style="min-width:200px" @change="insertDealField" />
    </div>
    <div
      ref="editorRef"
      class="visual-editor"
      contenteditable="true"
      @input="onEditorInput"
      @paste="onEditorPaste"
      @blur="saveSelection"
      @keyup="saveSelection"
      @mouseup="saveSelection"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

/**
 * Презентационный WYSIWYG-редактор HTML-шаблона документа. Компонент владеет
 * только contenteditable-узлом и управлением выделением (Range), экспонируя
 * getHtml()/setHtml(). Логика диалога, формы и сохранения остаётся в родителе
 * (DocumentsView) — перенос 1:1 без изменения поведения.
 */
defineProps<{
  fieldOptions: { label: string; value: string; disabled?: boolean }[]
}>()

const editorRef = ref<HTMLElement | null>(null)
const fieldToInsert = ref<string | null>(null)
let savedRange: Range | null = null

const saveSelection = () => {
  const sel = window.getSelection()
  if (sel && sel.rangeCount > 0 && editorRef.value?.contains(sel.anchorNode)) {
    savedRange = sel.getRangeAt(0).cloneRange()
  }
}

const restoreSelection = () => {
  if (savedRange) {
    const sel = window.getSelection()
    sel?.removeAllRanges()
    sel?.addRange(savedRange)
  }
}

const editorCmd = (cmd: string, value?: string) => {
  document.execCommand(cmd, false, value)
  editorRef.value?.focus()
}

const insertTable = () => {
  const tableHtml = '<table style="width:100%;border-collapse:collapse">'
    + '<tr><td style="border:1px solid #ccc;padding:6px">Ячейка 1</td><td style="border:1px solid #ccc;padding:6px">Ячейка 2</td></tr>'
    + '<tr><td style="border:1px solid #ccc;padding:6px">Ячейка 3</td><td style="border:1px solid #ccc;padding:6px">Ячейка 4</td></tr>'
    + '</table><p></p>'
  document.execCommand('insertHTML', false, tableHtml)
  editorRef.value?.focus()
}

const insertDealField = () => {
  if (!fieldToInsert.value || fieldToInsert.value.startsWith('_h_')) return
  const tag = `{{ ${fieldToInsert.value} }}`
  restoreSelection()
  editorRef.value?.focus()
  document.execCommand(
    'insertHTML',
    false,
    `<span class="field-tag" contenteditable="false">${tag}</span>&nbsp;`,
  )
  fieldToInsert.value = null
  saveSelection()
}

const onEditorInput = () => { /* content tracked via editorRef */ }

const onEditorPaste = (e: ClipboardEvent) => {
  e.preventDefault()
  const text = e.clipboardData?.getData('text/html') || e.clipboardData?.getData('text/plain') || ''
  document.execCommand('insertHTML', false, text)
}

const getHtml = (): string => editorRef.value?.innerHTML || ''
const setHtml = (html: string) => {
  if (editorRef.value) editorRef.value.innerHTML = html
}

defineExpose({ getHtml, setHtml })
</script>

<style scoped>
.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
  color: var(--p-text-color);
}

.editor-toolbar {
  display: flex;
  gap: 2px;
  align-items: center;
  padding: 6px 8px;
  border: 1px solid var(--p-content-border-color);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  background: var(--p-surface-50);
  flex-wrap: wrap;
}

.toolbar-sep {
  width: 1px;
  height: 20px;
  background: var(--p-content-border-color);
  margin: 0 4px;
}

.visual-editor {
  min-height: 300px;
  max-height: 500px;
  overflow-y: auto;
  padding: 16px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 0 0 8px 8px;
  background: var(--p-surface-0);
  font-size: 14px;
  line-height: 1.6;
  outline: none;
}

.visual-editor :deep(.field-tag) {
  background: var(--p-primary-color);
  color: var(--p-primary-contrast-color);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
  font-family: monospace;
  cursor: default;
}
</style>
