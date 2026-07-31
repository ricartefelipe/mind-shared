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
  totalRecallUrl: totalRecallBaseUrl(),
})
```

`totalRecallUrl` é opcional. Quando presente, o login consulta o TotalRecall
por até 4 segundos; se a consulta falhar ou expirar, o mock local continua
disponível.

## Contrato

O contrato canônico é exportado por `@ricartefelipe/mind-wallet-shared/openapi`
e permanece copiado em `docs/contracts/` de cada frontend, para preservar os
deploys estáticos no GitHub Pages.

Após alterar o contrato, execute:

```bash
npm run sync:apps
```
