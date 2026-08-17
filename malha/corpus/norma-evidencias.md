# Norma de evidências N-EVID-02

**N-EVID-02** é a norma de evidências da **Cooperativa Atlas Norte**. Ela substitui o hábito de responder de memória em incidentes da **Carteira Mind**.

Toda afirmação operacional exige: fonte (documento), trecho (chunk com ordinal), score de recuperação e, quando houver travessia, o caminho de entidades no grafo.

N-EVID-02 cita P-ACESSO-01 e INC-2025-04. A norma é responsável por recusar síntese quando o score fundido fica abaixo do limiar ou quando nenhum termo da pergunta aparece nas evidências.

Humanos marcam evidência como útil ou errada. O ranking híbrido (BM25 + denso + grafo) aprende com esse feedback dentro do espaço de tenancy.

Não se inventa saldo, chave PIX, responsável ou data. Se o arquivo não contém o trecho, a resposta é recusa explícita.
