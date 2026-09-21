<script lang="ts">
  import {
    dismissImportTask,
    IMPORT_STAGES,
    retryImport,
    type ImportTask,
  } from '../lib/importJob'

  let { task }: { task: ImportTask } = $props()
</script>

<article class="card" class:failed={task.status === 'failed'} aria-live="polite">
  <div class="top">
    <div class="badge">{task.kind === 'video' ? '视频' : '音频'}</div>
    <button
      class="x"
      type="button"
      aria-label={task.status === 'running' ? '取消导入' : '关闭'}
      onclick={() => dismissImportTask(task.localId)}
    >
      ×
    </button>
  </div>

  <h3>{task.title}</h3>

  {#if task.status === 'failed'}
    <p class="err">{task.error || '导入失败'}</p>
    <div class="actions">
      <button type="button" onclick={() => retryImport(task.localId)}>重试</button>
      <button class="ghost" type="button" onclick={() => dismissImportTask(task.localId)}>关闭</button>
    </div>
  {:else}
    <p class="hint">
      {IMPORT_STAGES[task.stageIndex] ?? '处理中'}中 · 可继续浏览其它页面
    </p>
    <div class="bar" aria-hidden="true">
      <span style={`width: ${Math.max(8, Math.round(task.progress * 100))}%`}></span>
    </div>
    <ol class="steps">
      {#each IMPORT_STAGES as label, index}
        <li
          class:done={task.stageIndex > index}
          class:current={task.stageIndex === index}
        >
          {label}
        </li>
      {/each}
    </ol>
  {/if}
</article>

<style>
  .card {
    border-radius: var(--radius-lg);
    padding: 14px 14px 12px;
    margin-bottom: 12px;
    background: linear-gradient(135deg, #eef6dc 0%, #f7f3e8 55%, #e8f0dc 100%);
    box-shadow: var(--shadow-card);
  }

  .card.failed {
    background: #fff6f4;
  }

  .top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 8px;
  }

  .badge {
    font-size: 0.7rem;
    font-weight: 750;
    padding: 3px 8px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.75);
    color: var(--accent-ink);
  }

  .x {
    width: 28px;
    height: 28px;
    border-radius: 999px;
    display: grid;
    place-items: center;
    color: var(--ink-soft);
    background: rgba(255, 255, 255, 0.55);
  }

  h3 {
    margin: 0 0 8px;
    font-size: 0.98rem;
    font-weight: 800;
    line-height: 1.35;
  }

  .hint {
    margin: 0 0 10px;
    font-size: 0.8rem;
    font-weight: 650;
    color: var(--ink-soft);
  }

  .err {
    margin: 0 0 10px;
    font-size: 0.85rem;
    font-weight: 650;
    color: #b42318;
  }

  .bar {
    height: 6px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.7);
    overflow: hidden;
    margin-bottom: 10px;
  }

  .bar span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: var(--accent);
    transition: width 0.35s ease;
  }

  .steps {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 4px;
  }

  .steps li {
    text-align: center;
    font-size: 0.68rem;
    font-weight: 700;
    color: var(--ink-faint);
  }

  .steps li.done {
    color: var(--accent-deep);
  }

  .steps li.current {
    color: var(--accent-ink);
  }

  .actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .actions button {
    min-height: 38px;
    border-radius: 10px;
    background: var(--accent);
    color: var(--accent-ink);
    font-weight: 750;
    font-size: 0.82rem;
  }

  .actions button.ghost {
    background: rgba(255, 255, 255, 0.7);
    color: var(--ink-soft);
  }
</style>
