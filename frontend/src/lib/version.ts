/** Injected at build time from package.json via vite.config.ts */
declare const __APP_VERSION__: string

export const APP_VERSION = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : 'dev'
