/**
 * Lightweight scoped logger.
 *
 * In dev (Vite `import.meta.env.DEV`) all levels print to console.
 * In production builds, only `warn` and `error` are emitted — `debug` and
 * `info` calls become no-ops so that the production console stays quiet.
 *
 * Usage:
 *   import { createLogger } from '@/utils/logger'
 *   const log = createLogger('notifications')
 *   log.debug('WS message', payload)
 *   log.error('WS failed', err)
 */
const isDev = Boolean(import.meta.env?.DEV)

interface Logger {
  debug(...args: unknown[]): void
  info(...args: unknown[]): void
  warn(...args: unknown[]): void
  error(...args: unknown[]): void
}

export function createLogger(scope: string): Logger {
  const prefix = `[${scope}]`
  return {
    debug(...args: unknown[]) {
      if (isDev) console.debug(prefix, ...args)
    },
    info(...args: unknown[]) {
      if (isDev) console.info(prefix, ...args)
    },
    warn(...args: unknown[]) {
      console.warn(prefix, ...args)
    },
    error(...args: unknown[]) {
      console.error(prefix, ...args)
    },
  }
}
