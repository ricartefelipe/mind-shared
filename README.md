# Mind Wallet Shared

Contrato OpenAPI e mocks MSW compartilhados pelas aplicações Mind Wallet.

## Instalação local

Em cada frontend:

```json
{
  "devDependencies": {
    "@ricartefelipe/mind-wallet-shared": "file:../mind-shared"
  }
}
```

Depois execute `npm install` no frontend. Para publicar o pacote, remova `private`
e substitua a dependência local pela versão publicada.

## MSW

Cada aplicação mantém seu próprio `browser.ts` e `mockServiceWorker.js`.
O arquivo de handlers cria a configuração com o slug do sistema:

```ts
import { createMindHandlers } from '@ricartefelipe/mind-wallet-shared/msw'

export const handlers = createMindHandlers({
  apiBasePath: '/api/v1',
  systemSlug: 'vuemind',
})
```

O login mock (MSW) valida as credenciais demo locais (`demo@vuemind.dev` /
`demo123`). Em Pages (`build:pages`), MSW fica desligado e o frontend aponta
para a SpringMind Wallet API live — autenticação nativa `/auth/login`.
TotalRecall só provisiona usuários nessa API; não é modo de login do produto.

## Contrato

O contrato canônico é exportado por `@ricartefelipe/mind-wallet-shared/openapi`
e permanece copiado em `docs/contracts/` de cada frontend, para preservar os
deploys estáticos no GitHub Pages.

Após alterar o contrato, execute:

```bash
npm run sync:apps
```
