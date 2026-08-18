# Postmortem INC-2025-04 — autenticação na Carteira Mind

**INC-2025-04** ocorreu quando o login mock da **Carteira Mind** foi confundido com o login nativo de **SpringMind**.

O incidente aponta para uma falha de evidência: a documentação interna afirmou que **TotalRecall** autenticava o usuário. TotalRecall só provisiona usuários na API; não é modo de login do produto.

A Cooperativa Atlas Norte registrou o incidente no **Espaço Atlas**. A correção depende de P-ACESSO-01 e de N-EVID-02: cada afirmação sobre autenticação deve citar o contrato OpenAPI ou o trecho do handbook.

Durante INC-2025-04, um operador marcou como errada a evidência que ligava TotalRecall ao login. O ranking do arquivo deve penalizar esse trecho em consultas futuras sobre autenticação.

Mitigação: o handbook agora declara as credenciais demo apenas para MSW local (`demo@vuemind.dev`). Em Pages, MSW fica desligado e o frontend aponta para a SpringMind Wallet API live.
