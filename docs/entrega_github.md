# Entrega no GitHub — passo a passo

Roteiro do processo de entrega: bifurcar o repositório do professor, trabalhar
no seu próprio repositório e abrir a solicitação de integração ao final.

> Substitua `PROFESSOR/repositorio-base` e `SEU-USUARIO` pelos valores reais.

---

## 1. Bifurcar o repositório (fork)

1. Abra o repositório do professor no GitHub.
2. Clique em **Fork**, no canto superior direito.
3. Escolha a sua conta como destino e confirme.

Você passa a ter uma cópia em `github.com/SEU-USUARIO/repositorio-base`. Só um
integrante do grupo precisa fazer isso; os demais são adicionados como
colaboradores em **Settings → Collaborators**.

---

## 2. Clonar para a sua máquina

```bash
git clone https://github.com/SEU-USUARIO/repositorio-base.git
cd repositorio-base
```

Configure a sua identidade, se ainda não fez:

```bash
git config user.name "Seu Nome"
git config user.email "seu.email@exemplo.com"
```

Registre o repositório original como fonte, para conseguir trazer atualizações:

```bash
git remote add upstream https://github.com/PROFESSOR/repositorio-base.git
git remote -v
```

---

## 3. Trabalhar em um ramo

Evite trabalhar direto no ramo principal:

```bash
git checkout -b desenvolvimento
```

---

## 4. Confirmar o trabalho em partes

Faça confirmações pequenas e com mensagem que diga o que mudou e por quê. Uma
sequência que funciona bem para este projeto:

```bash
git add topologia.json simulador/rede.py
git commit -m "Adiciona topologia da Figura 1 e cálculo de rotas por menor custo"

git add simulador/pdu.py simulador/camadas.py
git commit -m "Implementa as sete camadas e o encapsulamento da unidade de dados"

git add simulador/motor.py simulador/registro.py
git commit -m "Implementa o motor de simulação e o registro textual numerado"

git add simulador/visual.py main.py
git commit -m "Adiciona a interface gráfica e o ponto de entrada"

git add tests/ ferramentas/
git commit -m "Adiciona a bateria de 91 testes automatizados"

git add README.md docs/
git commit -m "Escreve o README e a documentação técnica"
```

O que **não** deve entrar em confirmação: `__pycache__/`, `.venv/`, `build/`,
`dist/` e arquivos de editor. O `.gitignore` do projeto já cuida disso.

Envie para o seu repositório:

```bash
git push -u origin desenvolvimento
```

---

## 5. Manter-se atualizado

Se o professor alterar o repositório original:

```bash
git fetch upstream
git merge upstream/main
```

---

## 6. Abrir a solicitação de integração (pull request)

1. Abra o seu repositório no GitHub. Aparecerá o aviso *Compare & pull request*.
2. Confirme que o destino é `PROFESSOR/repositorio-base`, ramo `main`, e a
   origem é o seu ramo `desenvolvimento`.
3. Escreva o título e a descrição. Sugestão de descrição:

```markdown
## Simulador Visual do Modelo OSI

**Grupo:** Nome 1 (matrícula), Nome 2 (matrícula), Nome 3 (matrícula)

### O que foi entregue
- Simulador com interface gráfica em tkinter, sem dependências externas
- Os sete casos de demonstração exigidos (E1/C1 a E7/C7)
- 91 testes automatizados, todos aprovados
- README, documentação técnica e dois tutoriais em `docs/`
- Executável para Windows em `dist/SimuladorOSI.exe`

### Como executar
`python main.py` ou duplo clique em `SimuladorOSI.exe`

### Convenções adotadas
Estão declaradas na Seção 4 de `docs/documentacao_projeto.md`, incluindo os
custos dos enlaces e a separação entre limite de segmentação (48 octetos) e
tamanho do segmento (40 octetos).
```

4. Clique em **Create pull request**.

---

## 7. Conferência antes de entregar

- [ ] O fork está na conta de um integrante do grupo
- [ ] Todos os integrantes aparecem no histórico de confirmações
- [ ] As mensagens de confirmação descrevem o que foi feito
- [ ] Nenhum `__pycache__/`, `.venv/` ou `build/` foi enviado
- [ ] O README traz nomes, matrículas, disciplina e semestre preenchidos
- [ ] As capturas de tela foram inseridas nos documentos de `docs/`
- [ ] Os tutoriais foram exportados em PDF, se o professor pediu
- [ ] `python -m pytest` termina sem falha
- [ ] `python main.py` abre a janela em uma máquina limpa
- [ ] A solicitação de integração foi aberta e aponta para o repositório do professor
