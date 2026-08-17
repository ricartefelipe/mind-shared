# Política de acesso a dados

**P-ACESSO-01** vigora na **Cooperativa Atlas Norte** e regula quem lê dados de produção da **Carteira Mind**.

A Carteira Mind depende de **SpringMind** para autenticação nativa. O provisionamento de contas aponta para **TotalRecall**, que não é modo de login do produto.

Somente operadores com papel `ledger.admin` ou `security.officer` podem acessar dados de produção da carteira. Consultas de homologação vivem no **Espaço Atlas** de tenancy `homolog`, isolado do espaço `producao`.

A política de acesso a dados requer registro de evidência em cada sessão: identificador do operador, trecho consultado e motivo. P-ACESSO-01 cita a **Norma de evidências** **N-EVID-02**.

Acesso sem evidência é incidente. Qualquer extração de saldo, chave PIX ou identificador de beneficiário em produção exige ticket e permanece no arquivo por 24 meses.
