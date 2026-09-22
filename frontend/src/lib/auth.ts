import { writable } from 'svelte/store'

const ACCESS_KEY = 'snsn-access-verified'
const TOKEN_KEY = 'snsn-api-token'

export const authUnlocked = writable(false)

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStorage(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // ignore quota / private mode
  }
}

function removeStorage(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    // ignore
  }
}

export function initAuth(): void {
  authUnlocked.set(readStorage(ACCESS_KEY) === '1')
}

export function persistAuth(token: string): void {
  writeStorage(ACCESS_KEY, '1')
  if (token && token !== 'ok') {
    writeStorage(TOKEN_KEY, token)
  } else {
    removeStorage(TOKEN_KEY)
  }
  authUnlocked.set(true)
}

export function getApiToken(): string | undefined {
  const stored = readStorage(TOKEN_KEY)
  if (stored) return stored
  return import.meta.env.VITE_SNSN_API_TOKEN as string | undefined
}
