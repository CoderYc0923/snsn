<script lang="ts">
  import { onMount } from 'svelte'
  import { verifyAccess } from '../lib/api'
  import { persistAuth } from '../lib/auth'

  const DIGITS = 6

  let digits = $state<string[]>(Array(DIGITS).fill(''))
  let busy = $state(false)
  let error = $state<string | null>(null)
  let shake = $state(false)
  let inputEl = $state<HTMLInputElement>()

  let code = $derived(digits.join(''))

  function resetDigits() {
    digits = Array(DIGITS).fill('')
    if (inputEl) inputEl.value = ''
  }

  function flashError(message: string) {
    error = message
    shake = true
    resetDigits()
    inputEl?.focus()
    setTimeout(() => {
      shake = false
    }, 420)
  }

  async function submit() {
    if (code.length !== DIGITS || busy) return
    busy = true
    error = null
    try {
      const result = await verifyAccess(code)
      persistAuth(result.token)
    } catch (e) {
      flashError(e instanceof Error ? e.message : '密码错误')
    } finally {
      busy = false
    }
  }

  function onInput(event: Event) {
    if (busy) return
    const raw = (event.currentTarget as HTMLInputElement).value.replace(/\D/g, '').slice(0, DIGITS)
    const next = Array(DIGITS).fill('')
    for (let i = 0; i < raw.length; i += 1) {
      next[i] = raw[i]
    }
    digits = next
    error = null
    if (raw.length === DIGITS) {
      void submit()
    }
  }

  onMount(() => {
    inputEl?.focus()
  })
</script>

<div class="gate" role="presentation">
  <div class="card" class:shake aria-live="polite">
    <h1>输入访问密码</h1>
    <p class="hint">6 位数字，验证通过后可使用</p>

    <div class="code-row" class:busy>
      {#each digits as digit, index (index)}
        <span class="cell" class:filled={!!digit} aria-hidden="true">{digit || '·'}</span>
      {/each}
      <input
        bind:this={inputEl}
        class="code-input"
        type="text"
        inputmode="numeric"
        autocomplete="one-time-code"
        maxlength={DIGITS}
        aria-label="6 位访问密码"
        disabled={busy}
        oninput={onInput}
      />
    </div>

    {#if error}
      <p class="err">{error}</p>
    {:else if busy}
      <p class="status">验证中…</p>
    {/if}
  </div>
</div>

<style>
  .gate {
    position: absolute;
    inset: 0;
    z-index: 100;
    display: grid;
    place-items: center;
    padding: 24px max(20px, var(--sar)) 24px max(20px, var(--sal));
    background:
      radial-gradient(120% 80% at 50% 0%, rgba(184, 232, 106, 0.28), transparent 55%),
      rgba(247, 248, 242, 0.96);
    backdrop-filter: blur(8px);
  }

  .card {
    width: min(100%, 320px);
    padding: 28px 22px 24px;
    border-radius: 28px;
    background: #fff;
    box-shadow: var(--shadow-float);
    text-align: center;
    animation: rise 0.28s ease-out both;
  }

  .card.shake {
    animation: shake 0.42s ease;
  }

  .brand {
    margin: 0 0 10px;
    font-family: var(--font-brand);
    font-size: 0.92rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    color: var(--accent-deep);
  }

  h1 {
    margin: 0;
    font-size: 1.35rem;
    font-weight: 800;
    letter-spacing: -0.03em;
  }

  .hint {
    margin: 8px 0 22px;
    font-size: 0.88rem;
    color: var(--ink-soft);
  }

  .code-row {
    position: relative;
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 8px;
  }

  .code-row.busy {
    opacity: 0.72;
  }

  .cell {
    aspect-ratio: 0.82;
    border-radius: 14px;
    background: var(--bg-sage);
    display: grid;
    place-items: center;
    font-size: 1.35rem;
    font-weight: 800;
    color: var(--ink-faint);
    transition:
      background 0.15s ease,
      color 0.15s ease,
      box-shadow 0.15s ease;
  }

  .cell.filled {
    color: var(--accent-ink);
    background: #fff;
    box-shadow: inset 0 0 0 2px var(--accent);
  }

  .code-input {
    position: absolute;
    inset: 0;
    opacity: 0;
    width: 100%;
    height: 100%;
    cursor: text;
  }

  .err {
    margin: 14px 0 0;
    font-size: 0.86rem;
    font-weight: 650;
    color: #b42318;
  }

  .status {
    margin: 14px 0 0;
    font-size: 0.86rem;
    font-weight: 650;
    color: var(--accent-deep);
  }

  @keyframes rise {
    from {
      opacity: 0;
      transform: translateY(12px) scale(0.98);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }

  @keyframes shake {
    0%,
    100% {
      transform: translateX(0);
    }
    20%,
    60% {
      transform: translateX(-6px);
    }
    40%,
    80% {
      transform: translateX(6px);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .card {
      animation: none;
    }

    .card.shake {
      animation: none;
    }
  }
</style>
