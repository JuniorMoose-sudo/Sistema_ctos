# Manual do Técnico de Campo — App CTOs Lotadas

Guia de uso do **Portal do Técnico**, do login ao cadastro da ocorrência.
Use o celular (de preferência) ou computador. Em campo, ative o GPS do aparelho.

---

## 1. Acessando o sistema

No navegador do celular, abra:

```
https://sistema.3.147.33.126.nip.io/tecnico/
```

> Dica: no Android/iOS, toque em **"Adicionar à tela inicial"** (menu do navegador) para
> criar um atalho com ícone, como um app. O acesso por HTTPS é obrigatório para o GPS funcionar.

---

## 2. Login

- **Usuário:** seu nome de acesso (ex.: `joao.silva`), fornecido pela coordenação.
- **Senha:** a senha inicial fornecida pela coordenação.

Toque em **Entrar no Sistema**.

Se digitar errado, aparece o aviso *"Usuário ou senha inválidos"* — confira e tente de novo.

> A senha inicial é a mesma para todos no primeiro acesso. A coordenação pode alterá-la
> a qualquer momento no painel administrativo. Não compartilhe sua senha.

---

## 3. Tela inicial

Depois do login, o app mostra a tela com duas opções:

1. **Usar minha localização** → encontra as CTOs mais próximas pelo GPS (recomendado).
2. **Buscar CTO pelo nome** → digita o nome da CTO para achá-la manualmente.

---

## 4. Cadastro pela localização (GPS)

1. Toque em **"Usar minha localização"** e **permita o acesso à localização** quando o navegador pedir.
2. Aguarde a mensagem de status. Conforme o GPS melhora, o app mostra a **precisão**:
   - *"Localização obtida (±85m). Ajustando o GPS..."* → ainda imprecisa.
   - *"Localização precisa (±12m)"* → ideal para registrar. **Espere chegar nessa mensagem** quando estiver ao ar livre.
3. A lista mostra as **3 CTOs mais próximas** com: nome, bairro, distância e situação (🟢 Normal, 🟡 Próxima da lotação, 🔴 Lotada, 🟣 Danificada).
4. Toque na CTO correta.
5. Na tela de **Confirmação**, confira nome, bairro e distância e toque em **"Sim, continuar"**.
   (Se não for essa, toque em **"Não, voltar"**.)

---

## 5. Cadastro pela busca pelo nome

1. Toque em **"Buscar CTO pelo nome"**.
2. Digite o nome (ex.: `AGO-8.7`) e confirme.
3. A lista mostra os resultados — toque na CTO certa.
4. Toque em **"Sim, continuar"** na tela de confirmação.

> Use a busca manual quando o GPS estiver indisponível (ex.: dentro de prédio, sem sinal).

---

## 6. Preenchendo a ocorrência

Preencha os campos do formulário:

**Situação da CTO (obrigatório)** — marque a que descreve a CTO na hora da vistoria:
- 🟢 **Normal** — tudo certo.
- 🟡 **Próxima lotação** — ainda tem vaga, mas está quase cheia.
- 🔴 **Lotada** — sem portas livres.
- 🟣 **Danificada** — avariada/quebrada.

**Motivo (obrigatório se NÃO for Normal)** — o motivo do problema:
- Sem porta livre · Sem splitter · Porta rompida · Fibra rompida · Caixa quebrada
- Poste interditado · Sem energia · CTO inexistente · CTO muito distante · Outro

**Portas usadas / Portas livres (opcional)** — quantidade atual de portas ocupadas e disponíveis.

**Foto da CTO (opcional)** — tire uma foto pela câmera ou anexe uma imagem (ajuda muito no diagnóstico).

**Observação (opcional)** — qualquer informação extra relevante.

---

## 7. Enviando

Toque em **"Enviar ocorrência"**.

- Sucesso: aparece a tela **"Ocorrência enviada!"** → toque em **"Nova ocorrência"** para registrar outra.
- Erro: aparece a mensagem em vermelho no topo do formulário — corrija e envie de novo.

> O registro é **anexo permanente** (histórico da CTO): cada vistoria vira um registro novo.
> A situação exibida na busca reflete a **última** ocorrência registrada.

---

## 8. Dicas de campo

- **Ao ar livre e com o GPS do celular ligado**, espere a mensagem *"Localização precisa"* para garantir as CTOs certas.
- Se a lista não mostrar CTOs próximas, verifique se a localização está ativada e tente **"Reiniciar"**.
- Em locais sem GPS, use a **busca pelo nome**.
- Tire a foto sempre que possível — é a principal evidência para a equipe de manutenção.
- Mantenha o celular conectado à internet (Wi-Fi ou dados móveis).

---

## 9. Problemas comuns

| Problema | Causa provável | Solução |
|---|---|---|
| "Usuário ou senha inválidos" | Dados errados | Confira o usuário/senha com a coordenação |
| "Permissão de localização negada" | GPS bloqueado no navegador | Ative a permissão de localização (configurações do navegador) |
| "Tempo esgotado ao buscar localização" | Sem GPS/sinal | Saia para área aberta, reative o GPS ou use a busca pelo nome |
| "GPS indisponível" | Localização do aparelho desligada | Ative a localização/GPS nas configurações do celular |
| "Erro ao buscar CTOs" | Sessão expirada | Vá ao login e entre de novo |
| "Nenhuma CTO encontrada" | Nome errado ou fora da cobertura | Confira o nome (ex.: `AGO-8.7`) |

---

**Coordenação:** para criar técnicos, alterar senhas ou consultar as ocorrências, use o
painel administrativo em `https://sistema.3.147.33.126.nip.io/admin`.
