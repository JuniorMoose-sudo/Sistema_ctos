# Especificação Técnica — Sistema de Monitoramento de CTOs Lotadas

> Este documento é uma especificação completa para desenvolvimento do zero. Segue-a na íntegra, na ordem apresentada, sem pular etapas de dados (Fase 0) — o projeto não funciona sem elas.

---

## 1. Contexto e objetivo

Empresa de telecom/ISP na unidade de Campina Grande - PB. O objetivo é substituir o registro informal de "CTO lotada" (ligação/mensagem em grupo) por um sistema que:

1. Deixa o técnico registrar a situação de uma CTO em campo em menos de 20 segundos, via celular, sem digitar dados que já existem no cadastro.
2. Dá ao gestor um dashboard em tempo real com mapa de calor, ranking por bairro e exportação em CSV.
3. Gera, com o tempo, uma lista de priorização de expansão de rede baseada em dado real (ocorrências + tentativas de instalação bloqueadas), não em percepção.

---

## 2. Fonte de dados original (input do projeto)

Arquivo: `Campina_Grande_-_PB_5743.kmz` (formato KML compactado).

**Estrutura real confirmada (não assumir mais do que isto):**
- 1 único `<Folder>` contendo **5.743 `<Placemark>`**.
- Cada Placemark tem **apenas**: `<name>` (texto livre, formato inconsistente) e `<Point><coordinates>longitude,latitude,0</coordinates></Point>`.
- **Não existe** `<ExtendedData>`, bairro, rua, capacidade, splitter ou status no arquivo. Qualquer campo desse tipo tem que ser gerado pelo sistema, não extraído do KMZ.
- Padrões de nome observados (não confiáveis como fonte de bairro, apenas como referência de zona/rede):
  - `CTO-SJM-B2-25` (~502 ocorrências)
  - `CGEF-R39-CT2` (~278 ocorrências)
  - `TA3654049` (~79 ocorrências)
  - `CGE-TO 1-15-146`, `cto_120`, `reserva-03` (~4.500 variações soltas, sem padrão único)

**Implicação de arquitetura:** o bairro de cada CTO precisa ser derivado por geocodificação reversa (lat/long → bairro), não extraído do arquivo. Isso é a Fase 0 e é bloqueante para todo o resto.

---

## 3. Stack

| Camada | Tecnologia |
|---|---|
| Backend / API | Django + Django REST Framework |
| Banco de dados | PostgreSQL |
| App do técnico | Django templates mobile-first (ou HTML/JS puro consumindo a API REST) |
| Dashboard do gestor | Streamlit + Plotly (mapa de calor) |
| Geocodificação | Script Python usando Nominatim (grátis) ou Google Geocoding API |
| Cálculo de distância | Fórmula de Haversine em Python puro (sem dependência externa) |
| Exportação CSV | pandas (`to_csv`) + `st.download_button` |
| Deploy | AWS EC2, Nginx, systemd, gunicorn (Django) + processo separado para Streamlit |

---

## 4. Fase 0 — Pipeline de preparação de dados (bloqueante)

**Script standalone** (`scripts/importar_kmz.py`), roda uma única vez (e depois sob demanda, se o KMZ for atualizado):

1. Extrai `doc.kml` do `.kmz` (é um zip).
2. Faz parse de todos os `<Placemark>`, extraindo `name` e `coordinates` (atenção: KML usa `longitude,latitude`, ordem invertida em relação ao padrão comum lat/long).
3. Para cada ponto, chama a API de geocodificação reversa e extrai o campo de bairro (`suburb`/`neighbourhood` no Nominatim). Implementar:
   - Rate limiting (Nominatim: 1 req/segundo).
   - Cache local (não geocodificar a mesma CTO duas vezes).
   - Tratamento de falha (bairro nulo é aceitável — não travar o pipeline).
4. Gera um CSV intermediário: `nome, latitude, longitude, bairro`.
5. Carrega esse CSV no Postgres via management command Django (`import_ctos`), fazendo upsert por nome (evita duplicar se rodar de novo).

**Critério de aceite:** as 5.743 CTOs devem existir na tabela `CTO` com bairro preenchido (ou nulo, se a geocodificação falhar para aquele ponto — não é bloqueante item a item, só o pipeline como um todo).

---

## 5. Modelagem de dados

### 5.1 Model `CTO` (cadastro fixo — praticamente imutável após a carga inicial)

| Campo | Tipo | Observação |
|---|---|---|
| `id` | PK | |
| `nome` | CharField, unique | Como veio do KMZ |
| `latitude` | DecimalField | |
| `longitude` | DecimalField | |
| `bairro` | CharField, nullable | Preenchido na Fase 0 |
| `capacidade` | IntegerField, nullable | Preenchido manualmente depois, se disponível |
| `splitter` | CharField, nullable | Ex: "1x16" |
| `status_atual` | CharField (choices: normal, proxima_lotacao, lotada, danificada) | **Nunca editado diretamente** — sempre recalculado a partir da última `Ocorrencia` |
| `ativa` | BooleanField, default True | Para desativar CTOs sem apagar histórico |
| `criado_em` | DateTimeField auto | |

### 5.2 Model `Ocorrencia` (log append-only — nunca é editado ou apagado)

| Campo | Tipo | Observação |
|---|---|---|
| `id` | PK | |
| `cto` | ForeignKey(CTO) | |
| `tecnico` | ForeignKey(User) | |
| `situacao` | CharField (mesmas choices de status_atual) | |
| `motivo` | CharField (choices: sem_porta_livre, sem_splitter, porta_rompida, fibra_rompida, caixa_quebrada, poste_interditado, sem_energia, cto_inexistente, cto_muito_distante, outro), nullable | Obrigatório apenas quando `situacao` != normal |
| `portas_usadas` | IntegerField, nullable | |
| `portas_livres` | IntegerField, nullable | |
| `foto` | ImageField, nullable | |
| `observacao` | TextField, nullable | |
| `latitude_registro` | DecimalField | GPS do técnico no momento do envio (pode divergir da CTO) |
| `longitude_registro` | DecimalField | |
| `criado_em` | DateTimeField auto | |

**Regra de negócio central:** todo `save()` de uma nova `Ocorrencia` dispara a atualização de `CTO.status_atual` para o valor de `situacao` dessa ocorrência (via signal ou override de `save`). O histórico em `Ocorrencia` nunca é alterado — é a fonte de verdade para "quantas vezes lotou", "tempo médio até expansão", etc.

---

## 6. API (Django REST Framework)

| Endpoint | Método | Descrição |
|---|---|---|
| `/api/ctos/proximas/?lat=&lon=` | GET | Retorna as 3 CTOs mais próximas do ponto informado, calculado via Haversine, ordenado por distância crescente |
| `/api/ctos/buscar/?q=` | GET | Busca por nome (fallback quando GPS falha) |
| `/api/ctos/<id>/` | GET | Detalhe da CTO: cadastro + última ocorrência + histórico resumido |
| `/api/ocorrencias/` | POST | Cria uma nova ocorrência (autenticado como técnico) |
| `/api/ocorrencias/?cto=&bairro=&data_inicio=&data_fim=&situacao=` | GET | Lista filtrável, usada pelo dashboard e pela exportação CSV |

Autenticação: token simples do DRF (`TokenAuthentication`) é suficiente — não há necessidade de OAuth para uso interno.

---

## 7. App do técnico (mobile-first)

Fluxo obrigatório, nesta ordem:

1. Captura geolocalização via `navigator.geolocation.getCurrentPosition`.
2. Chama `/api/ctos/proximas/` e exibe até 3 opções com distância em metros.
3. Se GPS falhar ou usuário não confirmar nenhuma opção: campo de busca por nome (`/api/ctos/buscar/`) ou seleção manual (mapa).
4. Tela de confirmação antes do formulário: "Você está registrando CTO {nome}, {distância}m — confirmar?".
5. Formulário: situação (radio), motivo (radio, condicional a situação ≠ normal), portas usadas/livres (numérico), foto (upload de câmera do celular), observação (texto livre).
6. Envio via `POST /api/ocorrencias/`, gravando automaticamente técnico (usuário logado), data/hora, e GPS do momento do envio.

Não bloquear o técnico em nenhuma etapa — sempre ter um caminho de fallback manual.

---

## 8. Dashboard do gestor (Streamlit)

### 8.1 KPIs (topo da tela)
Cards com: total de CTOs cadastradas, lotadas, quase lotadas, danificadas, atualizadas hoje. Calculados sobre `CTO.status_atual`.

### 8.2 Filtros (sidebar)
Bairro, técnico, período (data início/fim), situação.

### 8.3 Mapa de calor
Plotly (`density_mapbox` ou equivalente) agregando `CTO.latitude/longitude` por `status_atual = lotada`, colorido por densidade de bairro.

### 8.4 Ranking
Tabela ordenada de bairros por contagem de CTOs lotadas.

### 8.5 Exportação CSV — **requisito obrigatório do projeto**
Botão de download (`st.download_button`) que:
- Respeita todos os filtros ativos na tela no momento do clique.
- Gera o CSV via `pandas.DataFrame.to_csv(index=False)`.
- Colunas obrigatórias, nesta ordem: `nome_cto, bairro, latitude, longitude, situacao, motivo, portas_usadas, portas_livres, tecnico, data_hora_registro, observacao`.
- Encoding UTF-8, separador `,` (ajustar para `;` se for aberto em Excel PT-BR e apresentar acentuação quebrada).

### 8.6 Evolução histórica
Gráfico de linha: contagem de ocorrências por mês, por status. Usado para mostrar tendência de crescimento de saturação.

---

## 9. Inteligência e priorização (fase avançada, não bloqueante para o MVP)

1. Cruzar `Ocorrencia` (situacao = lotada/motivo relacionado a falta de porta) com a base de protocolos/OS já existente (pipeline de recorrência), casando por proximidade geográfica ou endereço do cliente.
2. Gerar uma tabela de priorização: `cto, numero_ocorrencias, numero_tentativas_instalacao_bloqueadas, data_primeira_ocorrencia, dias_em_lotacao`.
3. Exportar essa tabela também em CSV, mesmo padrão do item 8.5.

---

## 10. Estrutura de pastas sugerida

```
sistema_ctos/
├── backend/                  # Django
│   ├── manage.py
│   ├── ctos/                 # app: models CTO, Ocorrencia
│   ├── api/                  # app: serializers, views DRF
│   └── config/                # settings, urls
├── dashboard/                 # Streamlit
│   └── app.py
├── scripts/
│   └── importar_kmz.py        # Fase 0
├── data/
│   └── Campina_Grande_-_PB_5743.kmz
└── requirements.txt
```

---

## 11. Critérios de aceite do MVP

- [ ] As 5.743 CTOs do KMZ estão carregadas no Postgres com bairro preenchido.
- [ ] Técnico consegue registrar uma ocorrência via celular em menos de 20 segundos, sem digitar nome de CTO manualmente (no caminho feliz com GPS).
- [ ] `CTO.status_atual` reflete sempre a última `Ocorrencia`, e o histórico completo continua acessível.
- [ ] Dashboard mostra KPIs, mapa de calor e ranking em tempo real (sem cache manual).
- [ ] Exportação CSV funciona com os filtros ativos e contém todas as colunas especificadas no item 8.5.

---

## 11.1 Decisões de projeto (fechadas)

| Decisão | Valor |
|---|---|
| Geocodificação | Nominatim (rate limit de 1 req/s — pipeline da Fase 0 demora ~1h40 para as 5.743 CTOs) |
| Banco de dados | Neon (Postgres serverless) — conexão via `DATABASE_URL` com `sslmode=require` obrigatório |
| Armazenamento de fotos | Local no EC2 (`MEDIA_ROOT`), servido via Nginx. Monitorar disco — sem S3 por enquanto |
| Threshold "quase lotada" | Baseado em portas livres, não em percentual fixo, pra generalizar entre splitters de capacidades diferentes (1x8, 1x16, 1x32): **`portas_livres <= 2` → quase_lotada; `portas_livres == 0` → lotada**. (Equivale ao exemplo de 16 vagas / atenção em 14 usadas.) |
| Lista de técnicos | Importada de um arquivo `tecnicos.json` (usuário + senha) via management command, senha hasheada no import — nunca fica em texto puro no banco |
| Capacidade/splitter | Inicia **zerado** para todas as 5.743 CTOs. Preenchido organicamente pelas equipes em campo, no momento em que se depararem com aquela CTO — não é um cadastro prévio manual |

## 12. Fora de escopo do MVP (mencionar mas não implementar agora)

- Integração com o sistema de ativações da empresa (cruzamento de tentativas de instalação x CTO lotada) — planejado para a fase de inteligência (item 9).
- App nativo (iOS/Android) — o app web mobile-first atende ao caso de uso.
- OAuth/SSO corporativo — token simples é suficiente para uso interno.
