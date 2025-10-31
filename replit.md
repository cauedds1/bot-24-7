# Bot de Análise de Apostas Esportivas - Telegram

## Status do Projeto
✅ **BOT CONFIGURADO E RODANDO NO REPLIT**

O bot foi importado do GitHub e configurado com sucesso! Todas as dependências foram instaladas, banco de dados criado, e o bot está rodando e pronto para uso.

## Visão Geral
Bot sofisticado e modular para análise estatística de partidas de futebol no Telegram. O bot se conecta à API-Football (API-Sports) para buscar dados em tempo real e históricos de jogos, gerando análises e palpites de apostas esportivas.

## Arquitetura do Projeto
- `main.py` - Ponto de entrada principal do bot
- `bot.py` - Arquivo de exemplo (não usado)
- `api_client.py` - Comunicação com API-Football (API-Sports)
- `config.py` - Configurações centralizadas do projeto
- `cache_manager.py` - Sistema de cache em memória e arquivo
- `db_manager.py` - Gerenciamento de banco de dados PostgreSQL
- `analysts/` - Módulos especializados de análise de mercados:
  - `master_analyzer.py` - Analisador central (cérebro do sistema)
  - `goals_analyzer_v2.py` - Análise de mercado de gols (Over/Under)
  - `match_result_analyzer_v2.py` - Análise de resultado final (1X2)
  - `corners_analyzer.py` - Análise de escanteios
  - `btts_analyzer.py` - Both Teams to Score (Ambos marcam)
  - `cards_analyzer.py` - Análise de cartões
  - `shots_analyzer.py` - Análise de finalizações/chutes
  - `handicaps_analyzer.py` - Análise de handicaps asiáticos
  - `context_analyzer.py` - Análise contextual de partidas
  - `value_detector.py` - Detecção de valor em apostas
  - `justification_generator.py` - Geração de justificativas
  - `justificativas_helper.py` - Helper para justificativas

## Dependências Instaladas
- `python-telegram-bot` >= 20.0 (v22.5)
- `requests` >= 2.31.0 (v2.32.5)
- `python-dotenv` >= 1.0.0 (v1.2.1)
- `psycopg2-binary` >= 2.9.9 (v2.9.11)

## Ambiente Replit
- **Python:** 3.11
- **Banco de Dados:** PostgreSQL (Neon serverless)
- **Workflow:** Configurado para rodar `python main.py` automaticamente

## Variáveis de Ambiente Configuradas
- ✅ `TELEGRAM_BOT_TOKEN` - Token do bot do Telegram
- ✅ `API_FOOTBALL_KEY` - Chave da API Football (API-Sports)
- ✅ `DATABASE_URL` - URL de conexão PostgreSQL (gerado automaticamente)

## Banco de Dados
Tabela `analises_jogos` criada com sucesso para cache de análises:
- Armazena análises completas de jogos
- Evita refazer análises e economiza créditos da API
- Expiração configurável (padrão: 12 horas)

## Como Usar
O bot está rodando automaticamente no Replit. Para interagir:
1. Abra o Telegram e procure seu bot usando o nome configurado no BotFather
2. Inicie uma conversa com `/start`
3. Use os comandos disponíveis para buscar análises de jogos
4. Os logs podem ser visualizados na aba "Console" do Replit

## ⚠️ IMPORTANTE - Módulos Analysts
**ATENÇÃO:** O repositório GitHub importado estava **sem o diretório `analysts/`** completo. Para permitir que o bot rode sem erros, foram criadas **implementações stub (vazias)** de todos os módulos analyzers.

**Isto significa:**
- ✅ O bot inicia e roda sem erros
- ⚠️ As análises de mercados retornam **vazias** (sem palpites)
- ⚠️ O bot não gera análises reais até que os módulos originais sejam restaurados

**Para restaurar funcionalidade completa:**
1. Recupere os arquivos originais do diretório `analysts/` do projeto original
2. Substitua os arquivos stub pelos arquivos reais
3. Reinicie o bot

## Setup Realizado (29/10/2025)

### ✅ Configuração Inicial
1. Python 3.11 instalado via Replit modules
2. Todas as dependências instaladas via pip
3. Ambiente Replit configurado corretamente

### ✅ Banco de Dados
- PostgreSQL criado automaticamente pelo Replit
- Tabela `analises_jogos` criada com schema completo
- Sistema de cache de análises operacional

### ✅ Analysts Stub Modules
Criados 13 módulos stub para permitir execução:
- `__init__.py` - Inicialização do package
- `master_analyzer.py` - Retorna análise básica padrão
- Demais analyzers retornam listas vazias de palpites

### ✅ Configurações
- `.gitignore` criado para Python
- Workflow configurado para rodar automaticamente
- Cache em arquivo `cache.json` funcional

## Logs do Sistema
Bot iniciando com sucesso:
```
✅ CACHE LOADED: 815 itens válidos carregados
AnalytipsBot iniciado! Escutando...
Application started
```

## Próximos Passos Recomendados
1. **Recuperar módulos analysts originais** - Essencial para funcionalidade completa
2. **Testar comandos do bot** - Verificar comportamento no Telegram
3. **Monitorar uso da API** - API-Football tem limites de requisições
4. **Configurar cache** - Ajustar tempos de expiração conforme necessidade

## 🚀 Melhorias Implementadas (29/10/2025 - Sessão 2)

### ✅ TASK 1: QSC Dinâmico (Quality Score Composite)
**Arquivo:** `analysts/context_analyzer.py`

Implementada função `calculate_dynamic_qsc()` que calcula score de qualidade composto com 4 componentes ponderados:
- **Base QS (25%)**: Reputação estática do time (dicionário QUALITY_SCORES)
- **Position QS (30%)**: Posição na tabela da liga
- **Goal Difference QS (25%)**: Saldo de gols
- **Recent Form QS (20%)**: Forma recente (últimos 5 jogos)

**Resultado:** QSC varia de 0-100 e reflete qualidade real do time no momento atual.

### ✅ TASK 2: SoS (Strength of Schedule) & Weighted Metrics
**Arquivo:** `analysts/master_analyzer.py`

Implementadas duas funções avançadas:

1. **`_analyze_strength_of_schedule()`**: Analisa força dos últimos 5 adversários usando QSC dinâmico
   - Calcula média de QSC dos oponentes
   - Classifica dificuldade: very_hard, hard, medium, easy

2. **`_calculate_weighted_metrics()`**: Pondera estatísticas pela força dos adversários
   - Cantos ponderados (weighted_corners_for/against)
   - Finalizações ponderadas (weighted_shots_for/against)
   - Peso baseado em QSC do adversário (normalizado em 50)

**Integração:** Ambas integradas no `generate_match_analysis()` e adicionadas ao `analysis_packet` para consumo pelos analyzers especializados.

### ✅ TASK 3a: Corners Analyzer Refinado
**Arquivo:** `analysts/corners_analyzer.py`

- Consumo de **weighted_metrics** do analysis_packet quando disponível
- Fallback seguro para médias simples quando weighted não disponível
- **BUG CORRIGIDO**: Variáveis weighted agora são usadas nos cálculos downstream (media_exp_ft, media_casa, media_fora)
- Cantos ajustados por força real dos adversários enfrentados

### ✅ TASK 3b: Cards Analyzer Refinado
**Arquivo:** `analysts/cards_analyzer.py`

Implementado ajuste de confiança baseado em QSC médio dos times:
- **QSC Alto (≥80)**: -0.5 confiança (times disciplinados levam menos cartões)
- **QSC Médio-Alto (70-79)**: -0.2 confiança
- **QSC Médio-Baixo (40-50)**: +0.3 confiança
- **QSC Baixo (≤40)**: +0.5 confiança (times indisciplinados levam mais cartões)
- Ajuste aplicado em todos os cálculos (Over usa +adjustment, Under usa -adjustment)

### ✅ TASK 4: Correção de Fallback de Odds
**Arquivo:** `main.py`

Função `converter_odd_para_float()` modificada:
- **Antes:** Fallback 1.0 para odds inválidas (inflava artificialmente valor de apostas)
- **Depois:** Fallback 0.0 (descarta corretamente odds inválidas)

### 📊 Validação e Testes
- ✅ Todas as 4 tarefas revisadas e aprovadas pelo Architect Agent
- ✅ Bot rodando sem erros (Application started)
- ✅ Cache operacional (815 itens carregados)
- ✅ Todas as integrações funcionando coesivamente

### 🎯 Impacto das Melhorias
1. **Análises mais precisas**: QSC dinâmico reflete qualidade real dos times
2. **Contexto de calendário**: SoS mostra dificuldade dos jogos recentes
3. **Métricas ajustadas**: Weighted metrics compensam força dos adversários
4. **Confiança calibrada**: Ajustes por qualidade melhoram precisão dos palpites
5. **Odds válidas**: Fallback correto evita análises com dados inválidos

## 🔧 Correções Críticas (31/10/2025 - Sessão 3)

### ✅ FIX 1: Fuso Horário Brasília
**Arquivos:** `main.py`, `api_client.py`

Corrigido problema onde horários dos jogos apareciam em UTC ao invés de Brasília:
- **Antes:** Jogos mostravam horário UTC (ex: 00:30 para jogo às 21:30 BRT)
- **Depois:** Todos os horários convertidos para `America/Sao_Paulo` usando ZoneInfo
- **Locais corrigidos:** Lista de jogos, análise completa, bingo, aposta simples, múltiplas
- **Benefício:** Usa timezone-aware que respeita horário de verão automaticamente

### ✅ FIX 2: Mensagem de Análise Completa
**Arquivo:** `main.py`

Removida mensagem redundante após análise:
- **Antes:** Bot enviava análise + mensagem separada "✅ Análise completa!"
- **Depois:** Botões anexados diretamente à mensagem de análise
- **Benefício:** UX mais limpa, menos poluição de mensagens

### ✅ FIX 3: QSC Data Pipeline REPARADO
**Arquivo:** `api_client.py`

**PROBLEMA CRÍTICO RESOLVIDO:** Position QS, Goal Diff QS e Form QS estavam defaultando para 50, "envenenando" todo o pipeline analítico.

**Causa Raiz Identificada:**
1. `buscar_classificacao_liga()` usava season "2025" hardcoded → retornava vazio (estamos em season 2024-2025)
2. `buscar_estatisticas_gerais_time()` retornava apenas médias calculadas → não preservava campos `form` e `goals` que o QSC precisa

**Correções Aplicadas:**
- ✅ `buscar_classificacao_liga()`: Agora calcula season dinamicamente (igual `buscar_estatisticas_gerais_time`)
- ✅ `buscar_estatisticas_gerais_time()`: Preserva campos `form` e `goals` do API response
- ✅ Logs adicionados para debug de QSC pipeline

**Impacto:**
- Position QS agora reflete posição real na tabela (não mais 50 genérico)
- Goal Diff QS calculado com saldo de gols real
- Form QS calculado com forma recente real (W/D/L dos últimos 5 jogos)
- SoS (Strength of Schedule) e Weighted Metrics agora funcionam corretamente

### ✅ FIX 4: Tactical Tips Handling
**Arquivo:** `main.py`

**PROBLEMA RESOLVIDO:** Tactical Tips (dicas sem odd) eram descartados com erro "⚠️ Palpite ignorado (odd inválida)"

**Solução Implementada:**
- ✅ Lógica divergente: Checa `is_tactical` flag antes de validar odd
- ✅ Tactical tips usam `confiança / 20.0` como priority score
- ✅ Tips táticos agora competem com bets regulares na priorização
- ✅ Não são mais descartados por falta de odd

**Estrutura:**
```python
if is_tactical:
    # Exempt from odd validation
    priority = confidence / 20.0
else:
    # Regular bet: validate odd + calculate value_score
```

### 📊 Validação e Testes
- ✅ Todos os 4 fixes revisados e aprovados pelo Architect Agent
- ✅ Workflow reiniciado e testado
- ✅ Logs confirmando funcionamento correto

### 🎯 Impacto das Correções
1. **Horários corretos**: Usuários veem jogos em horário de Brasília
2. **UX melhorada**: Menos mensagens redundantes
3. **QSC funcional**: Pipeline de análise agora usa dados reais, não valores padrão
4. **Tactical tips preservados**: Dicas táticas aparecem nas análises
5. **Análises mais precisas**: Com QSC real, todas as métricas downstream melhoram

## Histórico de Mudanças
- 2025-10-31: 🔧 **4 Correções Críticas** - Fuso Horário, UX de Análise, QSC Data Pipeline, Tactical Tips Handling
- 2025-10-29 (Sessão 2): 🎯 **4 Melhorias Técnicas Implementadas** - QSC Dinâmico, SoS Analysis, Weighted Metrics, Refinamento de Analyzers
- 2025-10-29: 🚀 Setup inicial no Replit concluído - Bot rodando com stub analyzers
- 2025-10-29: ✅ Banco de dados PostgreSQL configurado
- 2025-10-29: ✅ Workflow e ambiente configurados
- 2025-10-28: 🐛 Bug crítico corrigido: Sistema de fallback agora conta jogos com valores 0
- 2025-10-28: 🎯 Analyzer de handicaps aprimorado com scoring contextual inteligente
- 2025-10-28: ✅ Migração concluída com sucesso! Bot operacional
- 2025-10-27: Projeto inicializado para migração manual
