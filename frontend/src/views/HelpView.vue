<template>
  <section class="help-page">
    <h1 class="page-title brand-heading">Помощь</h1>

    <div class="help-layout">
      <aside class="help-sidebar surface-card">
        <div class="help-search">
          <PInputText v-model="search" placeholder="Поиск по разделам…" size="small" />
        </div>
        <nav class="help-nav">
          <button
            v-for="article in filteredArticles"
            :key="article.slug"
            :class="['help-nav-item', { active: activeSlug === article.slug }]"
            @click="selectArticle(article.slug)"
          >
            {{ article.title }}
          </button>
          <div v-if="!filteredArticles.length" class="help-empty">Ничего не найдено</div>
        </nav>
      </aside>

      <article class="help-article surface-card">
        <div v-if="activeArticle" class="help-article-body markdown-body" v-html="renderedHtml" />
        <div v-else class="help-empty">Выберите статью слева</div>
      </article>

      <aside v-if="tocItems.length" class="help-toc surface-card">
        <div class="help-toc-title">На этой странице</div>
        <a
          v-for="item in tocItems"
          :key="item.slug"
          :href="'#' + item.slug"
          :class="['help-toc-item', 'level-' + item.level]"
          @click.prevent="scrollTo(item.slug)"
        >
          {{ item.text }}
        </a>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { renderMarkdown, type MarkdownHeading } from '@/utils/markdown'

const modules = import.meta.glob('@/docs/user-guide/*.md', {
  query: '?raw',
  import: 'default',
  eager: true
}) as Record<string, string>

interface Article {
  slug: string
  title: string
  order: number
  source: string
}

const articles = computed<Article[]>(() => {
  const list: Article[] = []
  for (const [path, source] of Object.entries(modules)) {
    const fileName = path.split('/').pop() || ''
    const slug = fileName.replace(/\.md$/, '')
    if (slug === 'README') continue
    const titleMatch = source.match(/^\s*#\s+(.+)$/m)
    const title = titleMatch ? titleMatch[1].trim() : slug
    const orderMatch = slug.match(/^(\d+)/)
    const order = orderMatch ? parseInt(orderMatch[1], 10) : 999
    list.push({ slug, title, order, source })
  }
  list.sort((a, b) => a.order - b.order)
  return list
})

const route = useRoute()
const router = useRouter()

const search = ref('')
const activeSlug = ref('')

const filteredArticles = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return articles.value
  return articles.value.filter(a =>
    a.title.toLowerCase().includes(q) || a.source.toLowerCase().includes(q)
  )
})

const activeArticle = computed(() =>
  articles.value.find(a => a.slug === activeSlug.value) || null
)

const rendered = computed(() => {
  if (!activeArticle.value) return { html: '', headings: [] as MarkdownHeading[] }
  return renderMarkdown(activeArticle.value.source)
})

const renderedHtml = computed(() => rendered.value.html)

const tocItems = computed(() =>
  rendered.value.headings.filter(h => h.level >= 2 && h.level <= 3)
)

const selectArticle = (slug: string) => {
  activeSlug.value = slug
  if (route.query.article !== slug) {
    router.replace({ query: { ...route.query, article: slug } })
  }
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const scrollTo = (slug: string) => {
  const el = document.getElementById(slug)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

const syncFromRoute = () => {
  const qs = typeof route.query.article === 'string' ? route.query.article : ''
  const found = articles.value.find(a => a.slug === qs)
  activeSlug.value = found ? found.slug : articles.value[0]?.slug || ''
}

watch(() => route.query.article, syncFromRoute)

onMounted(syncFromRoute)
</script>

<style scoped>
.help-page {
  max-width: 100%;
}

.help-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) 220px;
  gap: 14px;
  align-items: flex-start;
}

.help-sidebar,
.help-article,
.help-toc {
  padding: 14px;
}

.help-sidebar {
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 60px);
  overflow-y: auto;
}

.help-search {
  margin-bottom: 10px;
}

.help-search :deep(input) {
  width: 100%;
}

.help-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.help-nav-item {
  text-align: left;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  font-size: 13.5px;
  line-height: 1.35;
  transition: 0.15s ease;
}

.help-nav-item:hover {
  background: var(--surface-alt);
}

.help-nav-item.active {
  background: var(--primary-lighter);
  color: var(--brand);
  font-weight: 600;
}

.help-article {
  min-height: 400px;
}

.help-toc {
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 60px);
  overflow-y: auto;
}

.help-toc-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 8px;
  letter-spacing: 0.04em;
}

.help-toc-item {
  display: block;
  padding: 4px 6px;
  font-size: 13px;
  line-height: 1.35;
  color: var(--text);
  text-decoration: none;
  border-radius: 6px;
}

.help-toc-item:hover {
  background: var(--surface-alt);
}

.help-toc-item.level-3 {
  padding-left: 16px;
  color: var(--text-muted);
}

.help-empty {
  padding: 20px;
  color: var(--text-muted);
  text-align: center;
}

.markdown-body {
  font-size: 14.5px;
  line-height: 1.65;
  color: var(--text);
}

.markdown-body :deep(h1) {
  font-size: 1.7em;
  margin: 0 0 14px;
  font-weight: 700;
}

.markdown-body :deep(h2) {
  font-size: 1.3em;
  margin: 24px 0 10px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--line);
  font-weight: 700;
}

.markdown-body :deep(h3) {
  font-size: 1.1em;
  margin: 20px 0 8px;
  font-weight: 700;
}

.markdown-body :deep(h4) {
  font-size: 1em;
  margin: 16px 0 6px;
  font-weight: 700;
}

.markdown-body :deep(p) {
  margin: 0 0 10px;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0 0 12px;
  padding-left: 24px;
}

.markdown-body :deep(li) {
  margin: 4px 0;
}

.markdown-body :deep(code) {
  background: var(--bg);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 0.9em;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.markdown-body :deep(a) {
  color: var(--brand);
  text-decoration: underline;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--line);
  margin: 20px 0;
}

.markdown-body :deep(strong) {
  font-weight: 700;
}

@media (max-width: 1100px) {
  .help-layout {
    grid-template-columns: 240px minmax(0, 1fr);
  }
  .help-toc {
    display: none;
  }
}

@media (max-width: 720px) {
  .help-layout {
    grid-template-columns: 1fr;
  }
  .help-sidebar {
    position: static;
    max-height: none;
  }
}
</style>
