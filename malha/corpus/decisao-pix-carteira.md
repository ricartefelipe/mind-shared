# Decisão de produto DEC-2024-11 — PIX na Carteira Mind

**DEC-2024-11** é a decisão de produto que eleva o contrato da **Carteira Mind** para a versão 2.0 do OpenAPI compartilhado.

A decisão substitui o fluxo de transferência genérico pelo PIX com validação de chave (CPF, CNPJ, e-mail, telefone e EVP) e payload de QR demonstrativo. A Carteira Mind depende de um contrato canônico copiado nos frontends para deploys estáticos.

DEC-2024-11 cita P-ACESSO-01: chaves PIX de produção não entram em mocks. Os handlers MSW da carteira usam beneficiários fictícios da Cooperativa Atlas Norte.

A decisão é responsável por paginação de extrato, expansão de saldo e notificações PIX. Qualquer alteração de contrato exige `npm run sync:apps` nos repositórios consumidores.

O espaço de tenancy `demo` pode exibir QR e chaves de exemplo. O espaço `producao` recusa payload demonstrativo.
