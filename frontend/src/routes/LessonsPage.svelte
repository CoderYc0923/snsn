<script lang="ts">
  import { compareLessonsRecent, lessons, openLesson } from '../lib/nav'
  import type { Lesson } from '../lib/demo'
  import BottomNav from '../components/BottomNav.svelte'
  import LessonCard from '../components/LessonCard.svelte'

  function grouped(items: Lesson[]) {
    const map = new Map<string, Lesson[]>()
    for (const lesson of items) {
      const list = map.get(lesson.date) ?? []
      list.push(lesson)
      map.set(lesson.date, list)
    }
    return [...map.entries()]
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([date, list]) => [date, [...list].sort(compareLessonsRecent)] as const)
  }

  const groups = $derived(grouped($lessons))
</script>

<main class="page lessons">
  <header class="page-pad head">
    <h1>课列表</h1>
    <p class="muted">按日期浏览全部课程</p>
  </header>

  <div class="page-body page-pad feed">
    {#if $lessons.length === 0}
      <section class="empty">
        <p>还没有课程</p>
        <p class="hint muted">去首页点右上角 + 导入材料</p>
      </section>
    {:else}
      {#each groups as [date, items] (date)}
        <section class="group">
          <h2>{date}</h2>
          {#each items as lesson (lesson.id)}
            <LessonCard {lesson} onclick={() => openLesson(lesson.id)} />
          {/each}
        </section>
      {/each}
    {/if}
  </div>

  <div class="page-footer">
    <BottomNav />
  </div>
</main>

<style>
  .head {
    flex-shrink: 0;
  }

  .head h1 {
    margin: 12px 0 6px;
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: -0.04em;
  }

  .head p {
    margin: 0 0 12px;
  }

  .feed {
    display: flex;
    flex-direction: column;
    gap: 18px;
    padding-top: 4px;
    padding-bottom: 12px;
  }

  .group h2 {
    margin: 0 0 10px;
    font-size: 0.92rem;
    font-weight: 700;
    color: var(--ink-soft);
  }

  .empty {
    border-radius: var(--radius-lg);
    background: var(--bg-sage);
    padding: 48px 16px;
    text-align: center;
    color: var(--ink-soft);
    font-weight: 650;
  }

  .empty p {
    margin: 0;
  }

  .hint {
    margin-top: 8px !important;
    font-size: 0.88rem;
    font-weight: 600;
  }
</style>
