# Carta de tenancy e espaços

A **Cooperativa Atlas Norte** organiza a memória compartilhada em espaços de tenancy. Cada espaço tem slug, permissões e índice próprio.

O **Espaço Atlas** (`atlas-norte`) é o arquivo vivo de políticas, decisões e incidentes. Ele aponta para os espaços `demo`, `homolog` e `producao` da **Carteira Mind**.

Tenancy requer isolamento de embeddings, termos BM25 e grafo. Um trecho ingerido em `homolog` não entra na recuperação de `producao`.

A carta de tenancy cita P-ACESSO-01 e N-EVID-02. Operadores do espaço `producao` precisam de `ledger.admin` ou `security.officer`. Operadores de `demo` podem ingerir corpus de exemplo sem ticket.

A memória coletiva acumula correções humanas: evidência marcada como útil sobe no ranking; evidência marcada como errada desce. Essa correção vive no espaço onde foi feita e não atravessa a tenancy.
