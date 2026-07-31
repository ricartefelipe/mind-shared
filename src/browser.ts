import { setupWorker, type SetupWorker } from 'msw/browser'
import { createMindHandlers, type MindHandlerOptions } from './msw.js'

export function createMindWorker(options: MindHandlerOptions = {}): SetupWorker {
  return setupWorker(...createMindHandlers(options))
}
