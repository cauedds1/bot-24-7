# Bot de Análise de Apostas Esportivas - Telegram

## Overview
Este projeto é um bot sofisticado e modular para o Telegram, focado na análise estatística de partidas de futebol. Ele se integra à API-Football (API-Sports) para coletar dados em tempo real e históricos de jogos, gerando análises detalhadas e palpites para apostas esportivas. O objetivo é fornecer aos usuários insights aprofundados para decisões de apostas mais informadas, utilizando métricas avançadas e ajustadas por contexto.

## User Preferences
Eu, como usuário, prefiro um estilo de comunicação direto e objetivo. Gosto de ver o impacto das mudanças e melhorias de forma clara e concisa. Priorizo o desenvolvimento iterativo e a resolução de problemas críticos que afetam a funcionalidade principal. Não desejo que o agente faça alterações nos arquivos `.env` ou em qualquer configuração de variáveis de ambiente diretamente, a menos que explicitamente instruído.

## System Architecture
O bot é construído com uma arquitetura modular e production-ready, permitindo fácil expansão e manutenção.
- **Ponto de Entrada:** `main.py`
- **Comunicação API:** `api_client.py` gerencia a interação com a API-Football.
- **Configuração:** `config.py` centraliza as configurações do projeto.
- **Gerenciamento de Dados:**
    - `cache_manager.py` implementa um sistema de cache em memória e arquivo para otimizar o uso da API e o desempenho.
    - `db_manager.py` gerencia a persistência de dados utilizando PostgreSQL, com uma tabela `analises_jogos` para cache de análises complexas.
- **Módulos de Análise (Pure Analyst Protocol):** O diretório `analysts/` contém módulos especializados para diferentes mercados de apostas, orquestrados por um `master_analyzer.py`. Todos os analisadores usam um sistema unificado de confiança (`confidence_calculator.py`) baseado exclusivamente em probabilidades estatísticas, independente de odds de mercado. Inclui análises para gols, resultado final, escanteios, ambos marcam, cartões, finalizações, handicaps e análise contextual (`context_analyzer.py`).
- **UI/UX:** O bot interage com o usuário através de comandos do Telegram, apresentando análises de forma clara e concisa. As mensagens são formatadas para serem consistentes e evitar redundância.
- **Testes:** Diretório `tests/` contém testes unitários para validação de funcionalidades críticas.

## Decisões Técnicas
### Core Features
- **QSC Dinâmico (Quality Score Composite):** Implementado em `context_analyzer.py`, calcula um score de qualidade composto baseado em reputação estática, posição na tabela, saldo de gols e forma recente, ponderando a importância de cada componente.
- **SoS (Strength of Schedule) & Weighted Metrics:** Em `master_analyzer.py`, analisa a força dos adversários recentes e pondera estatísticas (como cantos e finalizações) pela dificuldade dos oponentes, fornecendo métricas ajustadas.
- **Detecção Dinâmica de Temporada:** `api_client.py` inclui lógica para detectar automaticamente a temporada ativa de uma liga através da API, com fallback inteligente, suportando calendários não-padrão e eliminando a necessidade de lógica de data hardcoded.
- **Gerenciamento de Fuso Horário:** Horários dos jogos são convertidos para `America/Sao_Paulo` (Brasília) usando `ZoneInfo` para exibir informações corretas ao usuário.
- **Tratamento de Tactical Tips:** Dicas táticas sem odds são processadas e priorizadas corretamente, sem serem descartadas por falta de odd.
- **Calibração de Cache TTLs:** Os tempos de vida (TTL) do cache são diferenciados por tipo de dado, otimizando a atualização de dados sensíveis ao tempo (odds) e economizando créditos da API para dados mais estáveis.

### Pure Analyst Protocol - 2025-10-31
**Paradigma Shift:** O bot foi completamente refatorado para focar em análise estatística pura, eliminando toda dependência de market odds (valor de apostas).

- **Sistema Unificado de Confiança:** Todos os analisadores agora usam `confidence_calculator.py` com assinatura simplificada: `calculate_final_confidence(statistical_probability_pct, bet_type, tactical_script)`.
- **Remoção de Filtragem por Odds:** Eliminados todos os checks de `ODD_MINIMA_DE_VALOR` em 8 módulos de análise (goals, corners, cards, shots, btts, handicaps, match_result).
- **Priorização por Confiança:** Análises são ordenadas e filtradas exclusivamente por níveis de confiança estatística (0-10), não por "valor de mercado".
- **Interface Pure Analyst:** Output formatado mostra "ANÁLISE PRINCIPAL" e "OUTRAS TENDÊNCIAS" baseado em confiança, mantendo odds apenas para referência informativa.
- **Módulos Removidos:** `value_detector.py` (detecção de valor de mercado), funções de modificação de score por odd.
- **Arquitetura Validada:** Todos os analisadores testados e aprovados pelo sistema de revisão arquitetural, sem regressões detectadas.

### Production Hardening (SRE) - 2025-10-31
- **API Resilience:** Todas as chamadas HTTP externas agora têm retry automático com exponential backoff (até 5 tentativas) usando a biblioteca `tenacity`. Previne crashes por falhas temporárias de rede ou API (502, 503, timeouts).
- **Startup Secret Validation:** Função `startup_validation()` valida Telegram Token, API-Football Key e PostgreSQL Connection antes de iniciar o bot. Bot recusa iniciar se algum secret estiver inválido, prevenindo crashes tardios.
- **Graceful Shutdown:** Signal handlers (SIGINT, SIGTERM) executam shutdown limpo salvando cache, fechando conexões HTTP e DB pool. Garante zero perda de dados em shutdowns abruptos.
- **Bounded Job Queue:** Fila de análises tem limite máximo de 1000 jobs, prevenindo memory exhaustion sob alta carga. Rejeita graciosamente novos jobs quando cheia, informando o usuário.
- **Rate Limiting:** Proteção contra abuso com limite de 10 comandos/minuto por usuário usando sliding window. Aplicado em todos os comandos e callbacks.
- **Production Readiness Score:** 9/10 (upgrade de 4/10 após hardening)

## External Dependencies
- **Telegram Bot API:** Utilizado através da biblioteca `python-telegram-bot` para interação com os usuários.
- **API-Football (API-Sports):** Principal fonte de dados para estatísticas e informações de jogos, acessada via `httpx` com retry automático.
- **PostgreSQL:** Banco de dados relacional utilizado para persistência de dados e cache de análises, conectado via `psycopg2-binary`. O Replit provê uma instância Neon serverless.
- **python-dotenv:** Usado para gerenciar variáveis de ambiente.
- **tenacity:** Framework de retry para resiliência de chamadas HTTP externas.
- **numpy/scipy:** Bibliotecas científicas para cálculos estatísticos avançados.

## Deployment
- **Procfile:** Configurado para deployment em plataformas PaaS (Heroku, Fly.io, Railway, Render).
- **Environment Variables Requeridas:**
  - `TELEGRAM_BOT_TOKEN` - Token do bot do Telegram
  - `API_FOOTBALL_KEY` - Chave da API-Football
  - `DATABASE_URL` - URL de conexão PostgreSQL (opcional, mas recomendado)

## Recent Changes (2025-10-31)
### Pure Analyst Protocol Implementation
Refatoração arquitetural completa transformando o bot de um modelo "tipster" (focado em valor de mercado) para um "Pure Analyst" (análise estatística independente de odds). Todos os 8 módulos de análise foram atualizados para usar o sistema unificado de confiança sem filtragem por odds.

### Production Hardening
Veja `SRE_AFTER_ACTION_REPORT.md` para detalhes completos da missão de Production Hardening.