<script lang="ts">
  export type IconName =
    | 'home'
    | 'podcast'
    | 'settings'
    | 'plus'
    | 'back'
    | 'captions'
    | 'pin'
    | 'explain'
    | 'repeat'
    | 'speed'
    | 'play'
    | 'pause'
    | 'people'
    | 'mic'
    | 'auto-echo'
    | 'list'

  let {
    name,
    size = 22,
    stroke = 1.7,
  }: {
    name: IconName
    size?: number
    stroke?: number
  } = $props()
</script>

<svg
  class="icon"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  aria-hidden="true"
>
  {#if name === 'home'}
    <path
      d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5Z"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linejoin="round"
    />
  {:else if name === 'podcast'}
    <path
      d="M12 14a3 3 0 0 0 3-3V7a3 3 0 1 0-6 0v4a3 3 0 0 0 3 3Z"
      stroke="currentColor"
      stroke-width={stroke}
    />
    <path
      d="M7 11a5 5 0 0 0 10 0M12 16v3"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linecap="round"
    />
  {:else if name === 'settings'}
    <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width={stroke} />
    <path
      d="M12 3.5v2.2M12 18.3v2.2M3.5 12h2.2M18.3 12h2.2M6.1 6.1l1.6 1.6M16.3 16.3l1.6 1.6M17.9 6.1l-1.6 1.6M7.7 16.3l-1.6 1.6"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linecap="round"
    />
  {:else if name === 'plus'}
    <path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width={stroke} stroke-linecap="round" />
  {:else if name === 'back'}
    <path
      d="M15 5 8 12l7 7"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  {:else if name === 'captions'}
    <rect x="3" y="5" width="18" height="14" rx="3" stroke="currentColor" stroke-width={stroke} />
    <path d="M7 10h6M7 14h10" stroke="currentColor" stroke-width={stroke} stroke-linecap="round" />
  {:else if name === 'pin'}
    <path
      d="M15 4.5 9.5 10l-2 5.5L13 13.5 18.5 8"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linecap="round"
      stroke-linejoin="round"
    />
    <path d="m9.5 15.5-3 4" stroke="currentColor" stroke-width={stroke} stroke-linecap="round" />
    <path d="M12.5 7.5 16 11" stroke="currentColor" stroke-width={stroke} stroke-linecap="round" />
  {:else if name === 'explain'}
    <path
      d="M6 18.5V8.2A3.2 3.2 0 0 1 9.2 5h5.6A3.2 3.2 0 0 1 18 8.2v5.1A3.2 3.2 0 0 1 14.8 16.5H9.5L6 18.5Z"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linejoin="round"
    />
    <path d="M12 8.2v4.2M9.9 10.3h4.2" stroke="currentColor" stroke-width={stroke} stroke-linecap="round" />
  {:else if name === 'repeat'}
    <path
      d="M17 2.8v4.2h-4.2M7 21.2v-4.2h4.2"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linecap="round"
      stroke-linejoin="round"
    />
    <path
      d="M17 7a7 7 0 0 0-11.5 2.5M7 17a7 7 0 0 0 11.5-2.5"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linecap="round"
    />
  {:else if name === 'speed'}
    <path
      d="M5.5 17.5a8 8 0 1 1 13 0"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linecap="round"
    />
    <path d="M12 14.5 15.5 9" stroke="currentColor" stroke-width={stroke} stroke-linecap="round" />
    <circle cx="12" cy="14.5" r="1.2" fill="currentColor" />
  {:else if name === 'play'}
    <path
      d="M9 7.2v9.6L17 12 9 7.2Z"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linejoin="round"
    />
  {:else if name === 'pause'}
    <path
      d="M8 6.5v11M16 6.5v11"
      stroke="currentColor"
      stroke-width={stroke + 0.4}
      stroke-linecap="round"
    />
  {:else if name === 'people'}
    <circle cx="9" cy="9" r="3" stroke="currentColor" stroke-width={stroke} />
    <circle cx="16" cy="10" r="2.5" stroke="currentColor" stroke-width={stroke} />
    <path
      d="M4 18c.8-2.4 2.6-3.6 5-3.6s4.2 1.2 5 3.6M13.5 18c.4-1.4 1.4-2.2 2.8-2.2 1.2 0 2.1.6 2.7 1.8"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linecap="round"
    />
  {:else if name === 'mic'}
    <path
      d="M12 14a3 3 0 0 0 3-3V7a3 3 0 1 0-6 0v4a3 3 0 0 0 3 3Z"
      stroke="currentColor"
      stroke-width={stroke}
    />
    <path
      d="M7 11a5 5 0 0 0 10 0M12 16v3"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linecap="round"
    />
  {:else if name === 'auto-echo'}
    <path
      d="M20 12a8 8 0 1 1-2.2-5.5"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linecap="round"
    />
    <path
      d="M20 5.5V9h-3.5"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  {:else if name === 'list'}
    <path
      d="M8 7h12M8 12h12M8 17h8"
      stroke="currentColor"
      stroke-width={stroke}
      stroke-linecap="round"
    />
    <circle cx="4.5" cy="7" r="1" fill="currentColor" />
    <circle cx="4.5" cy="12" r="1" fill="currentColor" />
    <circle cx="4.5" cy="17" r="1" fill="currentColor" />
  {/if}
</svg>

<style>
  .icon {
    display: block;
    flex-shrink: 0;
  }
</style>
