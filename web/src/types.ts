export type {
  Contradiction,
  DocumentRow,
  Evidence,
  FeedbackLabel,
  GraphSnapshot,
  GroundingStatus,
  PlanKind,
  PlanStep,
  QueryResult,
  Verification,
  Workspace,
} from '@ricartefelipe/mind-wallet-shared/archive/types'

export {
  entityTypeLabel,
  formatScore,
  groundingLabel,
  hopLabel,
  planKindLabel,
} from '@ricartefelipe/mind-wallet-shared/archive/types'

export type ViewId = 'consulta' | 'arquivo' | 'grafo'

export function viewLabel(view: ViewId): string {
  switch (view) {
    case 'consulta':
      return 'Consulta'
    case 'arquivo':
      return 'Arquivo'
    case 'grafo':
      return 'Grafo'
    default: {
      const unreachable: never = view
      return unreachable
    }
  }
}
