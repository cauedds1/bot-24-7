# main.py
import os
import logging
import random
import asyncio
import signal
from dotenv import load_dotenv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

import cache_manager
from db_manager import DatabaseManager
from config import JOGOS_POR_PAGINA, ODD_MINIMA_DE_VALOR
from api_client import (buscar_jogos_do_dia, buscar_estatisticas_gerais_time, buscar_classificacao_liga, 
                        buscar_odds_do_jogo, buscar_ligas_disponiveis_hoje, buscar_jogos_por_liga, NOMES_LIGAS_PT,
                        buscar_ultimos_jogos_time, buscar_todas_ligas_suportadas, ORDEM_PAISES)
from analysts.master_analyzer import generate_match_analysis
from analysts.goals_analyzer_v2 import analisar_mercado_gols
from analysts.match_result_analyzer_v2 import analisar_mercado_resultado_final
from analysts.corners_analyzer import analisar_mercado_cantos
from analysts.btts_analyzer import analisar_mercado_btts
from analysts.cards_analyzer import analisar_mercado_cartoes
from analysts.shots_analyzer import analisar_mercado_finalizacoes
from analysts.handicaps_analyzer import analisar_mercado_handicaps
from analysts.context_analyzer import filtrar_mercados_por_contexto, get_quality_scores
from analysts.value_detector import detectar_valor_contextual, calculate_value_score, format_value_percentage, get_value_rating
from analysts.justification_generator import generate_persuasive_justification
import job_queue
import pagination_helpers

load_dotenv()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()

LIGAS_POR_PAGINA = 10

# Dicionário global para armazenar análises processadas em background
analises_em_background = {}

# Inicializar gerenciador de banco de dados
db_manager = DatabaseManager()

# Rate Limiting - Previne abuso de comandos
user_command_timestamps = {}
RATE_LIMIT_COMMANDS_PER_MINUTE = 10
RATE_LIMIT_WINDOW_SECONDS = 60

def check_rate_limit(user_id: int) -> bool:
    """
    Verifica se o usuário excedeu o rate limit de comandos.
    
    Rate Limit: 10 comandos por minuto por usuário.
    
    Returns:
        True se dentro do limite, False se excedeu
    """
    now = datetime.now()
    
    if user_id not in user_command_timestamps:
        user_command_timestamps[user_id] = []
    
    cutoff_time = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    user_command_timestamps[user_id] = [
        ts for ts in user_command_timestamps[user_id]
        if ts > cutoff_time
    ]
    
    if len(user_command_timestamps[user_id]) >= RATE_LIMIT_COMMANDS_PER_MINUTE:
        logging.warning(f"⚠️ Rate limit excedido para user {user_id}")
        return False
    
    user_command_timestamps[user_id].append(now)
    return True

def get_rodada_atual(jogo):
    try:
        return int(''.join(filter(str.isdigit, jogo['league']['round'])))
    except (ValueError, TypeError):
        return 0

def validate_suggestions(main_suggestion, alternative_suggestions):
    """
    Valida e remove sugestões alternativas que conflitam com a sugestão principal.
    
    Regras de conflito:
    - Se principal é "Casa Vence (1)", remove Draw/Fora/Dupla X2
    - Se principal é "Fora Vence (2)", remove Draw/Casa/Dupla 1X
    - Se principal é "Draw (X)", remove Casa/Fora
    - Se principal é "Over X.5 HT", remove Under (X-1).5 FT ou menor
    - Se principal é "BTTS - Não", remove sugestões que requerem ambos marcarem
    - Etc.
    """
    if not main_suggestion or not alternative_suggestions:
        return alternative_suggestions
    
    main_tipo = main_suggestion.get('tipo', '').lower()
    main_mercado = main_suggestion.get('mercado', '').lower()
    main_periodo = main_suggestion.get('periodo', 'FT')
    
    validated = []
    
    for alt in alternative_suggestions:
        alt_tipo = alt.get('tipo', '').lower()
        alt_mercado = alt.get('mercado', '').lower()
        alt_periodo = alt.get('periodo', 'FT')
        
        conflito = False
        motivo = ""
        
        # CONFLITO 1: Resultado Final (1X2)
        if 'resultado' in main_mercado or 'resultado' in alt_mercado:
            if ('casa vence' in main_tipo or 'home win' in main_tipo or '1 ' in main_tipo):
                if any(x in alt_tipo for x in ['empate', 'draw', 'x ', 'fora vence', 'away win', '2 ', 'dupla x2', 'double x2']):
                    conflito = True
                    motivo = f"Conflito: Principal sugere Casa vencer, alternativa sugere '{alt['tipo']}'"
            
            elif ('fora vence' in main_tipo or 'away win' in main_tipo or '2 ' in main_tipo):
                if any(x in alt_tipo for x in ['empate', 'draw', 'x ', 'casa vence', 'home win', '1 ', 'dupla 1x', 'double 1x']):
                    conflito = True
                    motivo = f"Conflito: Principal sugere Fora vencer, alternativa sugere '{alt['tipo']}'"
            
            elif ('empate' in main_tipo or 'draw' in main_tipo or 'x ' in main_tipo):
                if any(x in alt_tipo for x in ['casa vence', 'home win', '1 ', 'fora vence', 'away win', '2 ']):
                    conflito = True
                    motivo = f"Conflito: Principal sugere Empate, alternativa sugere '{alt['tipo']}'"
        
        # CONFLITO 2: Over/Under Gols (HT vs FT)
        if ('gol' in main_mercado or 'goal' in main_mercado) and ('gol' in alt_mercado or 'goal' in alt_mercado):
            # Se principal é "Over 1.5 HT", remover "Under 2.5 FT" ou menor
            if 'over' in main_tipo and main_periodo == 'HT':
                try:
                    main_linha = float([x for x in main_tipo.split() if '.' in x][0])
                    if 'under' in alt_tipo and alt_periodo == 'FT':
                        alt_linha = float([x for x in alt_tipo.split() if '.' in x][0])
                        # Over 1.5 HT (2+ gols no HT) conflita com Under 2.5 FT (max 2 gols FT)
                        if alt_linha <= main_linha + 1.0:
                            conflito = True
                            motivo = f"Conflito lógico: Over {main_linha} HT vs Under {alt_linha} FT é muito arriscado"
                except (IndexError, ValueError):
                    pass
        
        # CONFLITO 3: BTTS (Ambos Marcam)
        if 'btts' in main_mercado or 'btts' in alt_mercado:
            if 'não' in main_tipo or 'no' in main_tipo:
                # BTTS Não conflita com qualquer mercado que exige ambos marcarem
                if any(x in alt_tipo for x in ['btts - sim', 'btts - yes', 'ambos marcam']):
                    conflito = True
                    motivo = f"Conflito: Principal sugere BTTS Não, alternativa sugere ambos marcarem"
            elif 'sim' in main_tipo or 'yes' in main_tipo:
                if any(x in alt_tipo for x in ['btts - não', 'btts - no']):
                    conflito = True
                    motivo = f"Conflito: Principal sugere BTTS Sim, alternativa sugere não marcarem"
        
        # CONFLITO 4: Over/Under no mesmo mercado e período
        if main_mercado == alt_mercado and main_periodo == alt_periodo:
            if 'over' in main_tipo and 'under' in alt_tipo:
                conflito = True
                motivo = f"Conflito: Over e Under no mesmo mercado/período"
            elif 'under' in main_tipo and 'over' in alt_tipo:
                conflito = True
                motivo = f"Conflito: Under e Over no mesmo mercado/período"
        
        if conflito:
            print(f"  ⚠️  VALIDAÇÃO: Removendo sugestão conflitante: {motivo}")
        else:
            validated.append(alt)
    
    return validated

def analisar_contexto_jogo(classificacao, time_casa_nome, time_fora_nome, rodada_atual):
    if not classificacao or rodada_atual == 0:
        return ""

    time_casa_info = None
    time_fora_info = None
    total_times = len(classificacao)

    for time_info in classificacao:
        if time_info['team']['name'] == time_casa_nome:
            time_casa_info = time_info
        if time_info['team']['name'] == time_fora_nome:
            time_fora_info = time_info

    if not time_casa_info or not time_fora_info:
        return ""

    pos_casa = time_casa_info['rank']
    pos_fora = time_fora_info['rank']
    forma_casa = time_casa_info.get('form', 'N/A')
    forma_fora = time_fora_info.get('form', 'N/A')

    narrativa_motivacao = ""
    if rodada_atual > (total_times * 0.6):
        if pos_casa <= 4 and pos_fora <= 4:
            narrativa_motivacao = "Jogo de alta tensão na briga pelo título."
        elif pos_casa >= total_times - 3 and pos_fora >= total_times - 3:
            narrativa_motivacao = "Confronto direto crucial na luta contra o rebaixamento."

    contexto_rodada = f"Jogo da {rodada_atual}ª rodada."
    base = f"<b>📝 Contexto:</b> {narrativa_motivacao or contexto_rodada}\n   - <b>Forma Casa:</b> {forma_casa} | <b>Forma Fora:</b> {forma_fora}\n"
    return base

import random

def formatar_historico_jogos(ultimos_jogos, time_id, time_nome, mercado, periodo='FT'):
    """
    Formata o histórico dos últimos jogos mostrando a métrica específica do mercado.
    """
    if not ultimos_jogos:
        return ""

    historico = f"\n<b>📋 Histórico {time_nome} ({periodo}):</b>\n"

    for jogo in ultimos_jogos[:4]:  # Últimas 4 partidas
        stats = jogo.get('statistics', {})

        # Determinar se o time jogou em casa ou fora
        eh_casa = jogo['home_team'] == time_nome
        team_key = 'home' if eh_casa else 'away'
        oponente = jogo['away_team'] if eh_casa else jogo['home_team']
        local = "🏠" if eh_casa else "✈️"

        # Extrair métrica específica baseada no mercado
        valor_metrica = None
        unidade = ""

        if mercado == 'Gols':
            if periodo == 'FT':
                valor_metrica = jogo['home_goals'] if eh_casa else jogo['away_goals']
                unidade = "gol" if valor_metrica == 1 else "gols"
            elif periodo == 'HT':
                # Pegar gols do primeiro tempo
                ht_score = jogo.get('score', {}).get('halftime', {})
                valor_metrica = ht_score.get('home' if eh_casa else 'away', 0)
                unidade = "gol HT" if valor_metrica == 1 else "gols HT"

        elif mercado == 'Cantos':
            # API fornece "Corner Kicks" nas estatísticas
            cantos = stats.get(team_key, {}).get('Corner Kicks', 0)
            valor_metrica = int(cantos) if cantos else 0
            unidade = "escanteio" if valor_metrica == 1 else "escanteios"

        elif mercado == 'Cartões':
            # Somar Yellow Cards + Red Cards
            amarelos = stats.get(team_key, {}).get('Yellow Cards', 0)
            vermelhos = stats.get(team_key, {}).get('Red Cards', 0)

            amarelos = int(amarelos) if amarelos else 0
            vermelhos = int(vermelhos) if vermelhos else 0

            valor_metrica = amarelos + vermelhos
            unidade = "cartão" if valor_metrica == 1 else "cartões"

        elif mercado == 'Finalizações':
            # VERSÃO PAGA: "Shots on Goal" ou "Total Shots"
            if periodo == 'HT':
                # API não separa shots por tempo, usar metade como estimativa
                shots = stats.get(team_key, {}).get('Shots on Goal', 0)
                shots = int(shots) if shots else 0
                valor_metrica = shots // 2  # Estimativa HT
                unidade = f"final. HT" if valor_metrica == 1 else f"finais. HT"
            else:
                shots = stats.get(team_key, {}).get('Shots on Goal', 0)
                valor_metrica = int(shots) if shots else 0
                unidade = "finalização" if valor_metrica == 1 else "finalizações"

        # Formatar linha do histórico
        if valor_metrica is not None:
            historico += f"  {local} <b>{valor_metrica}</b> {unidade} vs {oponente}\n"

    return historico + "\n"


def gerar_justificativa_real(sugestoes_principais, stats_casa, stats_fora, nome_casa, nome_fora, classificacao, time_casa_id, time_fora_id):
    """
    Gera justificativa REAL e CONVINCENTE baseada em dados estatísticos dos últimos 4 jogos.
    Mostra dados específicos para cada mercado (cantos, cartões, chutes, gols).
    """
    if not sugestoes_principais:
        return ""

    # Importar helper de justificativas
    from analysts.justificativas_helper import gerar_justificativa_ultimos_jogos
    
    # Pegar sugestão principal
    palpite_principal = sugestoes_principais[0]
    mercado = palpite_principal['mercado']
    
    # Mapear mercado para tipo usado na função
    mapa_mercados = {
        'Gols': 'gols',
        'Cantos': 'cantos',
        'Cartões': 'cartoes',
        'Finalizações': 'chutes'
    }
    
    mercado_tipo = mapa_mercados.get(mercado)
    
    if not mercado_tipo:
        # Mercados sem justificativa detalhada
        return "✅ CONCLUSÃO: Estatísticas MUITO FAVORÁVEIS. Os dados indicam alta probabilidade de acerto.\n"
    
    # Gerar justificativa com dados dos últimos 4 jogos
    return gerar_justificativa_ultimos_jogos(time_casa_id, time_fora_id, mercado_tipo, palpite_principal) + "\n"


def gerar_narrativa_palpite(sugestao, stats_casa, stats_fora, nome_casa, nome_fora):
    if not sugestao:
        return ""

    tipo = sugestao['tipo']
    mercado = sugestao['mercado']
    confianca = sugestao.get('confianca', 0)

    narrativas = {
        'Gols': {
            'Over': [
                f"💥 {nome_casa} tem sido uma MÁQUINA de gols em casa ({stats_casa['casa']['gols_marcados']:.1f} por jogo), enquanto {nome_fora} também contribui ofensivamente quando joga fora ({stats_fora['fora']['gols_marcados']:.1f} por jogo). Espere um jogo MOVIMENTADO!",
                f"🔥 Defensas frágeis de AMBOS os lados! {nome_casa} sofre {stats_casa['casa']['gols_sofridos']:.1f} gols/jogo em casa e a combinação de ataques produtivos pode gerar um FESTIVAL DE GOLS!",
                f"⚡ Este confronto tem TUDO para ser eletrizante! {nome_casa} marca consistentemente em casa ({stats_casa['casa']['gols_marcados']:.1f}) e {nome_fora} não fica atrás quando visita ({stats_fora['fora']['gols_marcados']:.1f}). Prepare a pipoca!"
            ],
            'Under': [
                f"🛡️ Duas MURALHAS se enfrentam! {nome_casa} tem uma das defesas mais SÓLIDAS em casa (apenas {stats_casa['casa']['gols_sofridos']:.1f} gols sofridos/jogo). Jogo TRUNCADO à vista!",
                f"🔒 Ataques APAGADOS neste confronto! {nome_casa} mal consegue balançar as redes em casa ({stats_casa['casa']['gols_marcados']:.1f}) e {nome_fora} também patina quando joga fora ({stats_fora['fora']['gols_marcados']:.1f}). Gols vão ser RAROS!",
                f"⚔️ Batalha TÁTICA esperada! Com defesas organizadas e ataques sem inspiração, este jogo tem cara de 0x0 ou 1x0. POUCOS gols no radar!"
            ]
        },
        'Cantos': {
            'Over': [
                f"🚩 CHUVA DE ESCANTEIOS à vista! {nome_casa} força em média {stats_casa['casa']['cantos_feitos']:.1f} cantos por jogo em casa, e {nome_fora} também pressiona quando visita ({stats_fora['fora']['cantos_feitos']:.1f}). Jogo com MUITO volume!",
                f"📍 Times OFENSIVOS que pressionam MUITO! Espere um jogo com ALTA intensidade nas laterais e muitas bolas na área. Bandeirinhas vão trabalhar!",
                f"⚡ Estilos de jogo que GERAM escanteios! Ambos gostam de atacar pelas pontas e cruzar na área. Prepare-se para MUITOS corners!"
            ],
            'Under': [
                f"🎯 Jogo pelo MEIO! Ambas equipes jogam de forma mais DIRETA, sem abusar das laterais. {nome_casa} tem apenas {stats_casa['casa']['cantos_feitos']:.1f} cantos/jogo em casa. POUCOS escanteios esperados!",
                f"🔄 Estilos CONSERVADORES! Times que não arriscam muito e preferem controlar o jogo. Poucas jogadas de linha de fundo previstas!"
            ]
        },
        'BTTS': {
            'Sim': [
                f"⚽⚽ AMBOS VÃO BALANÇAR AS REDES! {nome_casa} marca em CASA ({stats_casa['casa']['gols_marcados']:.1f}/jogo) e {nome_fora} também tem SANGUE NOS OLHOS quando visita ({stats_fora['fora']['gols_marcados']:.1f}/jogo). Defesas não são o forte aqui!",
                f"🎯 Ataques AFIADOS dos dois lados! Com capacidade ofensiva comprovada, é MUITO PROVÁVEL que ambos marquem. Jogo ABERTO e perigoso!",
                f"💪 Times que SABEM FAZER GOLS! Estatísticas não mentem: quando jogam nessas condições, AMBOS costumam marcar. Alta probabilidade!"
            ],
            'Não': [
                f"🚫 Pelo menos UM vai passar em BRANCO! {nome_casa} tem dificuldades em casa ({stats_casa['casa']['gols_marcados']:.1f} gols/jogo) OU {nome_fora} não consegue produzir fora ({stats_fora['fora']['gols_marcados']:.1f}). Apostaria que SÓ UM marca!",
                f"🛡️ Defesa VAI PREVALECER! Com pelo menos uma equipe tendo SÉRIAS dificuldades ofensivas, é BEM PROVÁVEL que apenas um time marque neste jogo!",
                f"🔒 Ataque TRAVADO! Os números mostram que pelo menos uma equipe tem grandes chances de FICAR SEM MARCAR. Confiamos nisso!"
            ]
        },
        'Resultado': {
            'Vitória': [
                f"🏠 MANDO DE CAMPO PESANDO! {nome_casa} é MUITO FORTE em seus domínios e encara um adversário que não consegue se impor fora. VITÓRIA CLARA à vista!",
                f"💪 SUPERIORIDADE EVIDENTE! Estatísticas, momento e fator casa apontam para uma vitória CONVINCENTE!",
                f"⚡ NÃO PERDE ESTA! O favoritismo é CLARO e os números confirmam!"
            ]
        },
        'Cartões': {
            'Over': [
                f"🟨 CHUVA DE CARTÕES à vista! Este jogo tem TUDO para ser QUENTE! Times com histórico de muitas faltas e árbitro rigoroso. Prepare-se para ver MUITOS amarelos!",
                f"⚠️ CONFRONTO TENSO esperado! Ambas equipes jogam com INTENSIDADE e não economizam nas faltas. Cartões NÃO vão faltar!",
                f"🔥 Jogo FÍSICO e DISPUTADO! Estatísticas mostram alta média de cartões. Árbitro vai trabalhar MUITO neste jogo!"
            ],
            'Under': [
                f"🕊️ Jogo LIMPO esperado! Times jogam com DISCIPLINA e têm baixo histórico de cartões. Árbitro pode ficar DESOCUPADO!",
                f"✅ Confronto TÉCNICO previsto! Equipes que RESPEITAM o jogo e evitam faltas desnecessárias. POUCOS cartões no radar!",
                f"🎯 Partida CONTROLADA! Estatísticas de disciplina são EXCELENTES em ambos os lados. Jogo limpo é o mais provável!"
            ]
        }
    }

    try:
        tipo_base = tipo.split()[0]  # Pega só "Over", "Under", "Sim", "Não", "Vitória"
        opcoes = narrativas.get(mercado, {}).get(tipo_base, [])
        if not opcoes and mercado == 'Resultado':
            opcoes = narrativas['Resultado']['Vitória']

        if opcoes:
            narrativa = random.choice(opcoes)
        else:
            narrativa = f"Os dados estatísticos apontam FORTEMENTE para esta opção. Confiança {confianca}/10!"
    except Exception as e:
        logging.warning(f"⚠️ Erro ao gerar narrativa persuasiva para {mercado}/{tipo}: {e}")
        narrativa = f"A análise técnica indica esta aposta com {confianca}/10 de confiança!"

    return f"📖 <b>Análise:</b> {narrativa}\n"


async def gerar_analise_completa_todos_mercados(jogo):
    """
    🧠 NEW ARCHITECTURE: Gera análise COMPLETA usando Master Analyzer.
    Master Analyzer cria análise centralizada, analyzers especializados consomem o output.
    """
    print("--- 🧠 MASTER ANALYZER WORKFLOW: STARTING ---")
    id_jogo = jogo['fixture']['id']
    id_liga = jogo['league']['id']
    
    # 1️⃣ CHAMAR MASTER ANALYZER - CÉREBRO CENTRAL
    print("--- 🧠 CALLING MASTER ANALYZER ---")
    analysis_packet = await generate_match_analysis(jogo)
    
    if 'error' in analysis_packet:
        print(f"--- ❌ MASTER ANALYZER ERROR: {analysis_packet['error']} ---")
        return None
    
    print(f"--- ✅ MASTER ANALYZER COMPLETE - Script: {analysis_packet['analysis_summary']['selected_script']} ---")
    
    # 2️⃣ BUSCAR DADOS ADICIONAIS (odds, classificação)
    odds = await buscar_odds_do_jogo(id_jogo)
    classificacao = await buscar_classificacao_liga(id_liga)
    
    # Extrair posições da classificação
    pos_casa = "N/A"
    pos_fora = "N/A"
    if classificacao:
        for time_info in classificacao:
            if time_info['team']['name'] == jogo['teams']['home']['name']:
                pos_casa = time_info['rank']
            if time_info['team']['name'] == jogo['teams']['away']['name']:
                pos_fora = time_info['rank']
    
    # 3️⃣ ANALYZERS ESPECIALIZADOS CONSOMEM O MASTER PACKET
    print("--- 📊 SPECIALIST ANALYZERS EXTRACTING DATA ---")
    
    # Extrair script ANTES de chamar analyzers (para passar como parâmetro)
    script = analysis_packet['analysis_summary']['selected_script']
    
    # Analyzers refatorados (Phoenix V2.0) - recebem analysis_packet diretamente
    analise_gols = analisar_mercado_gols(analysis_packet, odds)
    print("--- ✅ GOALS ANALYZER DONE ---")
    
    analise_resultado = analisar_mercado_resultado_final(analysis_packet, odds)
    print("--- ✅ MATCH RESULT ANALYZER DONE ---")
    
    # Analyzers legacy - recebem stats + script_name para VETO
    stats_casa = analysis_packet['raw_data']['home_stats']
    stats_fora = analysis_packet['raw_data']['away_stats']
    
    analise_cantos = analisar_mercado_cantos(stats_casa, stats_fora, odds, classificacao, pos_casa, pos_fora, analysis_packet, script)
    print("--- ✅ CORNERS ANALYZER DONE ---")
    
    analise_btts = analisar_mercado_btts(stats_casa, stats_fora, odds, script)
    print("--- ✅ BTTS ANALYZER DONE ---")
    
    analise_cartoes = analisar_mercado_cartoes(stats_casa, stats_fora, odds, analysis_packet, script)
    print("--- ✅ CARDS ANALYZER DONE ---")
    
    analise_finalizacoes = analisar_mercado_finalizacoes(stats_casa, stats_fora, odds, analysis_packet, script)
    print("--- ✅ SHOTS ANALYZER DONE ---")
    
    analise_handicaps = analisar_mercado_handicaps(stats_casa, stats_fora, odds, classificacao, pos_casa, pos_fora, script)
    print("--- ✅ HANDICAPS ANALYZER DONE ---")
    
    # 4️⃣ EXTRAIR INFORMAÇÕES DO MASTER PACKET
    reasoning = analysis_packet['analysis_summary']['reasoning']
    power_home = analysis_packet['analysis_summary']['power_score_home']
    power_away = analysis_packet['analysis_summary']['power_score_away']
    
    # Legacy context detection
    alerta_contexto = detectar_diferenca_tecnica(jogo, classificacao, pos_casa, pos_fora)
    
    # Informações do jogo
    time_casa_nome = jogo['teams']['home']['name']
    time_fora_nome = jogo['teams']['away']['name']
    liga_info = NOMES_LIGAS_PT.get(id_liga)
    nome_liga = liga_info[0] if liga_info else jogo['league']['name']
    
    # Converter horário UTC → BRT (America/Sao_Paulo)
    data_jogo_utc = datetime.fromisoformat(jogo['fixture']['date'].replace('Z', '+00:00'))
    data_jogo_brt = data_jogo_utc.astimezone(ZoneInfo("America/Sao_Paulo"))
    horario_formatado = data_jogo_brt.strftime("%d/%m/%Y %H:%M")
    
    # ========== 🎯 PRIORIZAÇÃO GLOBAL POR VALUE SCORE ==========
    print("--- 🎯 GLOBAL VALUE PRIORITIZATION STARTED ---")
    
    # Coletar TODOS os palpites de TODOS os mercados com Value Score
    todos_palpites_com_value = []
    
    mercados_analise = [
        ('Gols', '⚽', analise_gols),
        ('Cantos', '🚩', analise_cantos),
        ('BTTS', '🎲', analise_btts),
        ('Resultado', '🏁', analise_resultado),
        ('Cartões', '🟨', analise_cartoes),
        ('Finalizações', '🎯', analise_finalizacoes),
        ('Handicaps', '⚖️', analise_handicaps)
    ]
    
    for mercado_nome, mercado_emoji, analise in mercados_analise:
        if not analise or not analise.get('palpites'):
            continue
        
        for palpite in analise['palpites'][:3]:  # Pegar top 3 de cada mercado
            # ========== DIVERGENT LOGIC: Check if Tactical Tip ==========
            is_tactical = palpite.get('is_tactical', False)
            
            if is_tactical:
                # TACTICAL TIP: Exempt from odd validation
                print(f"  🧠 Tactical Tip detectado: {mercado_nome} - {palpite.get('tipo')} (Conf: {palpite.get('confianca')}/10)")
                
                # Use confiança como métrica de prioridade (normalizada para escala similar ao value_score)
                # Confiança 10/10 = value_score equivalente de ~0.5 (médio-alto)
                # Isso permite que tactical tips de alta confiança compitam com bets de value médio
                tactical_priority = palpite.get('confianca', 5) / 20.0  # 10/10 -> 0.5, 8/10 -> 0.4
                
                todos_palpites_com_value.append({
                    'mercado_nome': mercado_nome,
                    'mercado_emoji': mercado_emoji,
                    'palpite': palpite,
                    'value_score': tactical_priority,
                    'bot_probability': palpite.get('confianca', 0) / 10.0,
                    'is_tactical': True
                })
                continue  # Pular validação de odds
            
            # REGULAR BET: Validate odd and calculate value
            odd = palpite.get('odd')
            if odd is None or odd == 'N/A' or odd == '':
                print(f"  ⚠️ Palpite ignorado (odd inválida): {mercado_nome} - {palpite.get('tipo')}")
                continue
            
            # Validar que odd é numérica
            try:
                odd_float = float(odd)
                if odd_float <= 1.0:
                    print(f"  ⚠️ Palpite ignorado (odd <= 1.0): {mercado_nome} - {palpite.get('tipo')} @{odd}")
                    continue
            except (ValueError, TypeError):
                print(f"  ⚠️ Palpite ignorado (odd não numérica): {mercado_nome} - {palpite.get('tipo')} @{odd}")
                continue
            
            # Calcular Value Score
            bot_prob = palpite.get('probabilidade', palpite.get('confianca', 0) * 10) / 100.0
            value_score = calculate_value_score(bot_prob, odd_float)
            
            # Adicionar à lista global
            todos_palpites_com_value.append({
                'mercado_nome': mercado_nome,
                'mercado_emoji': mercado_emoji,
                'palpite': palpite,
                'value_score': value_score,
                'bot_probability': bot_prob,
                'is_tactical': False
            })
    
    # Ordenar por Value Score (maior primeiro)
    todos_palpites_com_value.sort(key=lambda x: x['value_score'], reverse=True)
    
    print(f"  📊 Total de {len(todos_palpites_com_value)} palpites analisados")
    if todos_palpites_com_value:
        print(f"  🏆 Melhor Value: {todos_palpites_com_value[0]['value_score']:.3f} ({todos_palpites_com_value[0]['mercado_nome']})")
    
    # Separar TOP PICKS (3 melhores) e Sugestões Alternativas
    # FILTRAR: Sugestões alternativas devem ter value >= 0 (sem value negativo)
    top_picks = todos_palpites_com_value[:3]
    sugestoes_alternativas = [p for p in todos_palpites_com_value[3:8] if p['value_score'] >= 0]
    
    # ========== CONSTRUIR MENSAGEM ==========
    mensagem = f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    mensagem += f"🏆 <b>{nome_liga}</b>\n"
    mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    mensagem += f"⚽ <b>{time_casa_nome}</b> <i>({pos_casa}º)</i> <b>vs</b> <b>{time_fora_nome}</b> <i>({pos_fora}º)</i>\n"
    mensagem += f"🕐 <b>Horário:</b> {horario_formatado} (Brasília)\n\n"
    
    # 🚨 ALERTA DE CONTEXTO
    if alerta_contexto:
        mensagem += f"{alerta_contexto}\n\n"
    
    # ========== ROTEIRO TÁTICO ==========
    mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    mensagem += f"🎬 <b>ROTEIRO TÁTICO</b>\n"
    mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    mensagem += f"📜 <b>Script:</b> {script.replace('SCRIPT_', '').replace('_', ' ')}\n"
    mensagem += f"💡 {reasoning}\n\n"
    
    # Só mostrar Power Score se não for valor padrão (50 vs 50 = sem dados)
    if not (power_home == 50 and power_away == 50):
        mensagem += f"📊 Power: Casa {power_home} | Fora {power_away}\n\n"
    
    # ========== TOP PICKS (MELHORES MERCADOS) ==========
    if top_picks:
        mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        mensagem += f"💎 <b>TOP PICKS (MAIOR VALOR)</b>\n"
        mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for idx, item in enumerate(top_picks, 1):
            p = item['palpite']
            value_score = item['value_score']
            value_pct = format_value_percentage(value_score)
            rating, emoji = get_value_rating(value_score)
            
            mensagem += f"{item['mercado_emoji']} <b>#{idx} - {item['mercado_nome']}</b>\n"
            
            odd_str = f" <b>@{p['odd']}</b>" if p.get('odd') and p.get('odd') > 0 else " <i>(Oportunidade Tática)</i>"
            mensagem += f"  📌 <b>{p['tipo']}</b> ({p.get('periodo', 'FT')}){odd_str}\n"
            mensagem += f"  💎 <b>Value:</b> {emoji} {value_pct} ({rating})\n"
            mensagem += f"  🎯 <b>Probabilidade:</b> {item['bot_probability']:.0%} | <b>Confiança:</b> {p.get('confianca', 'N/A')}/10\n\n"
        
        mensagem += "\n"
    
    # ========== SUGESTÕES ALTERNATIVAS ==========
    if sugestoes_alternativas:
        mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        mensagem += f"💡 <b>SUGESTÕES ALTERNATIVAS</b>\n"
        mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for item in sugestoes_alternativas:
            p = item['palpite']
            value_score = item['value_score']
            value_pct = format_value_percentage(value_score)
            rating, emoji = get_value_rating(value_score)
            
            odd_str = f" @{p['odd']}" if p.get('odd') and p.get('odd') > 0 else " (Tática)"
            mensagem += f"{item['mercado_emoji']} <b>{item['mercado_nome']}:</b> {p['tipo']} ({p.get('periodo', 'FT')}){odd_str} - {emoji} {value_pct}\n"
        
        mensagem += "\n"
    
    mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    # ========== AVISO: MERCADOS SEM ODDS ==========
    # Informar quais mercados não tinham odds disponíveis na API
    mercados_sem_odds = []
    if not analise_cantos or not analise_cantos.get('palpites'):
        mercados_sem_odds.append("Escanteios")
    if not analise_cartoes or not analise_cartoes.get('palpites'):
        mercados_sem_odds.append("Cartões")
    if not analise_finalizacoes or not analise_finalizacoes.get('palpites'):
        mercados_sem_odds.append("Finalizações")
    if not analise_handicaps or not analise_handicaps.get('palpites'):
        mercados_sem_odds.append("Handicaps")
    
    if mercados_sem_odds:
        mensagem += f"\n⚠️ <b>Mercados sem odds disponíveis na API:</b>\n"
        mensagem += f"   {', '.join(mercados_sem_odds)}\n"
        mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    print("--- SURVIVAL CHECK 12: MESSAGE FORMATTING DONE ---")
    print(f"--- SURVIVAL CHECK 13: RETURNING MESSAGE (Length: {len(mensagem)} chars) ---")
    
    return mensagem


def detectar_diferenca_tecnica(jogo, classificacao, pos_casa, pos_fora):
    """
    Detecta diferença técnica GIGANTE entre times.
    Exemplos: 
    - Time da Premier League vs time da 3ª divisão
    - 1º colocado vs lanterna
    - Copa: time grande vs time pequeno
    """
    alerta = None
    id_liga = jogo['league']['id']
    nome_liga = jogo['league']['name'].lower()
    time_casa = jogo['teams']['home']['name']
    time_fora = jogo['teams']['away']['name']
    
    # Ligas de elite (tier 1)
    LIGAS_ELITE = [
        39, 140, 61, 78, 135,  # Premier, La Liga, Ligue 1, Bundesliga, Serie A
        94, 71, 2, 3,  # Primeira Liga PT, Serie A BR, Champions, Europa League
    ]
    
    # Copas nacionais onde times de divisões diferentes jogam
    COPAS_NACIONAIS = [
        48, 556, 66, 81, 137,  # Copa del Rey, Taça PT, Coupe de France, DFB Pokal, Coppa Italia
        73, 960,  # Copa do Brasil, FA Cup
    ]
    
    # 1. COPA: Time grande vs time pequeno
    if id_liga in COPAS_NACIONAIS:
        # Tentar detectar pela classificação (se um time não tem posição, é de divisão inferior)
        if pos_casa != "N/A" and pos_fora == "N/A":
            alerta = (
                f"🚨 <b>ALERTA - DIFERENÇA TÉCNICA!</b>\n"
                f"⚠️ <b>{time_casa}</b> (liga principal) enfrenta <b>{time_fora}</b> (divisão inferior)\n"
                f"💡 <b>CONTEXTO:</b> Times grandes costumam DOMINAR nestas partidas!\n"
                f"📊 Espere: MUITOS gols, escanteios, finalizações do favorito."
            )
        elif pos_fora != "N/A" and pos_casa == "N/A":
            alerta = (
                f"🚨 <b>ALERTA - DIFERENÇA TÉCNICA!</b>\n"
                f"⚠️ <b>{time_fora}</b> (liga principal) enfrenta <b>{time_casa}</b> (divisão inferior)\n"
                f"💡 <b>CONTEXTO:</b> Times grandes costumam DOMINAR nestas partidas!\n"
                f"📊 Espere: MUITOS gols, escanteios, finalizações do favorito."
            )
    
    # 2. DIFERENÇA BRUTAL NA TABELA (1º-3º vs últimos 3)
    if classificacao and pos_casa != "N/A" and pos_fora != "N/A":
        try:
            pos_casa_num = int(pos_casa)
            pos_fora_num = int(pos_fora)
            total_times = len(classificacao)
            
            # Casa no topo (1º-3º) vs Fora nos 3 últimos
            if pos_casa_num <= 3 and pos_fora_num >= (total_times - 2):
                alerta = (
                    f"🚨 <b>ALERTA - DESEQUILÍBRIO!</b>\n"
                    f"⚠️ <b>{time_casa}</b> ({pos_casa}º) é MUITO SUPERIOR a <b>{time_fora}</b> ({pos_fora}º)\n"
                    f"💡 <b>CONTEXTO:</b> Líder costuma DOMINAR lanternas!\n"
                    f"📊 Espere: Pressão ofensiva, escanteios, goleada possível."
                )
            # Fora no topo vs Casa nos 3 últimos
            elif pos_fora_num <= 3 and pos_casa_num >= (total_times - 2):
                alerta = (
                    f"🚨 <b>ALERTA - DESEQUILÍBRIO!</b>\n"
                    f"⚠️ <b>{time_fora}</b> ({pos_fora}º) é MUITO SUPERIOR a <b>{time_casa}</b> ({pos_casa}º)\n"
                    f"💡 <b>CONTEXTO:</b> Líder visitante pode MASSACRAR lanterna!\n"
                    f"📊 Espere: Visitante pressionando, muitos cantos e finalizações."
                )
        except Exception as e:
            logging.warning(f"⚠️ Erro ao analisar desequilíbrio na tabela: {e}")
    
    return alerta


async def gerar_palpite_completo(jogo, filtro_mercado=None, filtro_tipo_linha=None):
    id_jogo = jogo['fixture']['id']
    id_liga = jogo['league']['id']
    usar_cache_otimizado = False

    # Cache de análise completa do jogo (economiza MUITO processamento!)
    cache_key = f"analise_jogo_{id_jogo}_{filtro_mercado}_{filtro_tipo_linha}"
    cached_analise = cache_manager.get(cache_key)
    if cached_analise:
        return cached_analise

    # 🎯 VERIFICAR BANCO DE DADOS PRIMEIRO (análise completa sem filtros)
    if not filtro_mercado and not filtro_tipo_linha:
        analise_db = db_manager.buscar_analise(id_jogo, max_idade_horas=12)
        if analise_db:
            usar_cache_otimizado = True
            print(f"💾 CACHE OTIMIZADO: Usando análise salva do Fixture #{id_jogo}")

            # Reconstruir listas de análises a partir do banco
            analises_brutas = []
            if analise_db.get('analise_gols'):
                analises_brutas.append(analise_db['analise_gols'])
            if analise_db.get('analise_cantos'):
                analises_brutas.append(analise_db['analise_cantos'])
            if analise_db.get('analise_btts'):
                analises_brutas.append(analise_db['analise_btts'])
            if analise_db.get('analise_resultado'):
                analises_brutas.append(analise_db['analise_resultado'])
            if analise_db.get('analise_cartoes'):
                analises_brutas.append(analise_db['analise_cartoes'])
            if analise_db.get('analise_finalizacoes'):
                analises_brutas.append(analise_db['analise_finalizacoes'])
            if analise_db.get('analise_handicaps'):
                analises_brutas.append(analise_db['analise_handicaps'])

            analises_encontradas = [a for a in analises_brutas if a]
            stats_casa = analise_db['stats_casa']
            stats_fora = analise_db['stats_fora']
            classificacao = analise_db['classificacao']

            # Extrair posições da classificação
            pos_casa = "N/A"
            pos_fora = "N/A"
            if classificacao:
                for time_info in classificacao:
                    if time_info['team']['name'] == jogo['teams']['home']['name']:
                        pos_casa = time_info['rank']
                    if time_info['team']['name'] == jogo['teams']['away']['name']:
                        pos_fora = time_info['rank']

            # Pular direto para a geração da mensagem
            if analises_encontradas:
                total_palpites = sum(len(a.get('palpites', [])) for a in analises_encontradas)
                print(f"  ✅ DB CACHE: {len(analises_encontradas)} mercados com {total_palpites} palpites recuperados")
        else:
            analise_db = None
    else:
        analise_db = None

    # Se não achou no banco, fazer análise completa
    if not analise_db:
        stats_casa = await buscar_estatisticas_gerais_time(jogo['teams']['home']['id'], id_liga)
        stats_fora = await buscar_estatisticas_gerais_time(jogo['teams']['away']['id'], id_liga)
        odds = await buscar_odds_do_jogo(id_jogo)

        if not stats_casa or not stats_fora or not odds:
            if not stats_casa:
                print(f"⚠️  SEM STATS CASA: Jogo {id_jogo} - {jogo['teams']['home']['name']}")
            if not stats_fora:
                print(f"⚠️  SEM STATS FORA: Jogo {id_jogo} - {jogo['teams']['away']['name']}")
            if not odds:
                print(f"⚠️  SEM ODDS: Jogo {id_jogo}")
            return None

        classificacao = await buscar_classificacao_liga(id_liga)
        pos_casa = "N/A"
        pos_fora = "N/A"

        if classificacao:
            for time_info in classificacao:
                if time_info['team']['name'] == jogo['teams']['home']['name']:
                    pos_casa = time_info['rank']
                if time_info['team']['name'] == jogo['teams']['away']['name']:
                    pos_fora = time_info['rank']

        # 💎 DETECÇÃO DE VALOR CONTEXTUAL
        # Identifica se odds "baixas" (1.50-2.50) têm valor baseado no contexto do jogo
        contextos_valor = detectar_valor_contextual(stats_casa, stats_fora, jogo, classificacao)

        if any(contextos_valor.values()):
            contextos_ativos = [k for k, v in contextos_valor.items() if v]
            print(f"  💎 VALOR CONTEXTUAL DETECTADO: {', '.join(contextos_ativos)}")
            print(f"     → Bot aceita odds menores (1.50+) para favoritos/clássicos/jogos decisivos")

        # 📜 CALCULAR GAME SCRIPT antes de criar análises
        time_casa_id = jogo['teams']['home']['id']
        time_fora_id = jogo['teams']['away']['id']
        home_quality, away_quality = get_quality_scores(time_casa_id, time_fora_id)
        game_script = "EQUILIBRADO"  # Default
        quality_difference = abs(home_quality - away_quality)
        if quality_difference > 20:
            game_script = "DOMINIO_CASA" if home_quality > away_quality else "DOMINIO_VISITANTE"
        elif quality_difference > 10:
            game_script = "FAVORITISMO_CASA" if home_quality > away_quality else "FAVORITISMO_VISITANTE"

        # Buscar análise master para contexto tático
        analysis_packet = await generate_match_analysis(jogo)
        
        analises_brutas = [
            analisar_mercado_gols(stats_casa, stats_fora, odds, classificacao, pos_casa, pos_fora, game_script),
            analisar_mercado_cantos(stats_casa, stats_fora, odds, classificacao, pos_casa, pos_fora, analysis_packet),
            analisar_mercado_btts(stats_casa, stats_fora, odds),
            analisar_mercado_resultado_final(stats_casa, stats_fora, odds, classificacao, pos_casa, pos_fora),
            analisar_mercado_cartoes(stats_casa, stats_fora, odds, analysis_packet),
            analisar_mercado_finalizacoes(stats_casa, stats_fora, odds),
            analisar_mercado_handicaps(stats_casa, stats_fora, odds, classificacao, pos_casa, pos_fora)
        ]

        print(f"  DEBUG Jogo {id_jogo}: Gols={bool(analises_brutas[0])}, Cantos={bool(analises_brutas[1])}, BTTS={bool(analises_brutas[2])}, Resultado={bool(analises_brutas[3])}, Cartões={bool(analises_brutas[4])}, Finalizações={bool(analises_brutas[5])}, Handicaps={bool(analises_brutas[6])}")

        # 🎯 FILTRO INTELIGENTE POR CONTEXTO DA PARTIDA
        # Analisa o perfil do jogo e descarta mercados que NÃO fazem sentido contextualmente
        # EXCETO quando usuário pede mercado específico (Cantos, Cartões, etc)
        if filtro_mercado:
            # Usuário pediu mercado específico - NÃO filtrar por contexto
            analises_encontradas = [a for a in analises_brutas if a]
            print(f"  ⚠️ MODO ESPECÍFICO: Ignorando filtro de contexto (usuário pediu '{filtro_mercado}')")
        else:
            # Análise geral - aplicar filtro de contexto
            analises_filtradas, perfil_partida, game_script_filtered = filtrar_mercados_por_contexto(analises_brutas, stats_casa, stats_fora, time_casa_id, time_fora_id)
            analises_encontradas = analises_filtradas

        if analises_encontradas:
            total_palpites = sum(len(a.get('palpites', [])) for a in analises_encontradas)
            print(f"  DEBUG Jogo {id_jogo}: {len(analises_encontradas)} mercados com {total_palpites} palpites totais")

            # 💾 SALVAR ANÁLISE COMPLETA NO BANCO DE DADOS
            if not filtro_mercado and not filtro_tipo_linha:
                data_jogo_str = jogo['fixture']['date'].split('T')[0]
                liga_info = NOMES_LIGAS_PT.get(jogo['league']['id'])
                nome_liga = liga_info[0] if liga_info else jogo['league']['name']

                dados_jogo = {
                    'data_jogo': data_jogo_str,
                    'liga': nome_liga,
                    'time_casa': jogo['teams']['home']['name'],
                    'time_fora': jogo['teams']['away']['name']
                }

                analises_dict = {}
                for a in analises_brutas:
                    if a:
                        mercado_lower = a['mercado'].lower()
                        if 'gol' in mercado_lower and 'btts' not in mercado_lower:
                            analises_dict['gols'] = a
                        elif 'canto' in mercado_lower or 'escanteio' in mercado_lower:
                            analises_dict['cantos'] = a
                        elif 'btts' in mercado_lower or 'ambas' in mercado_lower:
                            analises_dict['btts'] = a
                        elif 'resultado' in mercado_lower:
                            analises_dict['resultado'] = a
                        elif 'cart' in mercado_lower:
                            analises_dict['cartoes'] = a
                        elif 'finaliza' in mercado_lower or 'shot' in mercado_lower:
                            analises_dict['finalizacoes'] = a
                        elif 'handicap' in mercado_lower:
                            analises_dict['handicaps'] = a

                stats_dict = {
                    'stats_casa': stats_casa,
                    'stats_fora': stats_fora,
                    'classificacao': classificacao
                }

                db_manager.salvar_analise(id_jogo, dados_jogo, analises_dict, stats_dict)

    if filtro_mercado:
        print(f"DEBUG: Filtro mercado = '{filtro_mercado}'")
        print(f"DEBUG: Mercados encontrados antes do filtro: {[a['mercado'] for a in analises_encontradas]}")
        analises_encontradas = [a for a in analises_encontradas if a['mercado'].lower() == filtro_mercado.lower()]
        print(f"DEBUG: Mercados após filtro: {[a['mercado'] for a in analises_encontradas]}")

    if filtro_tipo_linha == 'over_only':
        for analise in analises_encontradas:
            analise['palpites'] = [p for p in analise['palpites'] if 'Over' in p.get('tipo', '')]

    analises_encontradas = [a for a in analises_encontradas if a.get('palpites')]

    if not analises_encontradas:
        print(f"⚠️  SEM VALUE BETS: Jogo {id_jogo} - Nenhuma análise de valor encontrada")
        return None

    # Coletar TODOS os palpites e ordenar por VALOR
    todos_palpites = []
    for analise in analises_encontradas:
        for palpite in analise['palpites']:
            todos_palpites.append({
                **palpite,
                'mercado': analise['mercado'],
                'dados_suporte': analise.get('dados_suporte', '')
            })

    # NOVA ORDENAÇÃO INTELIGENTE:
    # 1. Prioriza mercados com odds reais (não "N/A")
    # 2. Depois ordena por confiança
    def calcular_prioridade(palpite):
        confianca = palpite['confianca']
        odd_raw = palpite.get('odd', 'N/A')  # Mantém valor original (string ou float)
        
        # Verificar se odd é string "N/A" ou numérica
        tem_odd_real = odd_raw != 'N/A' and odd_raw != "N/A" and str(odd_raw) != 'N/A'
        
        # FORTE BONUS para mercados com odds reais
        # PENALIDADE para mercados sem odds (N/A)
        if tem_odd_real:
            bonus_odd = 3.0  # Bonus para mercados com odds reais
        else:
            bonus_odd = -2.0  # PENALIDADE para mercados sem odds (N/A)
        
        prioridade_final = confianca + bonus_odd
        
        # DEBUG: Log dos primeiros 5 palpites
        if len(todos_palpites) <= 5 or palpite == todos_palpites[0]:
            print(f"  📊 DEBUG PRIORIDADE: {palpite['tipo']} | Conf={confianca:.1f} | Odd={odd_raw} | Bonus={bonus_odd:+.1f} | PRIORIDADE={prioridade_final:.1f}")
        
        # Score total = confiança + bonus/penalidade
        return prioridade_final
    
    todos_palpites.sort(key=calcular_prioridade, reverse=True)

    # Separar: TOP 1 = Principal (maior confiança), Resto = Alternativas
    sugestoes_principais = todos_palpites[:1] if len(todos_palpites) >= 1 else todos_palpites
    palpites_secundarios = todos_palpites[1:] if len(todos_palpites) > 1 else []
    
    # 🎯 VALIDAÇÃO DE CONFLITOS: Remover sugestões alternativas contraditórias
    if sugestoes_principais and palpites_secundarios:
        print(f"\n🔍 VALIDAÇÃO DE CONFLITOS: Analisando {len(palpites_secundarios)} sugestões alternativas...")
        palpites_secundarios = validate_suggestions(sugestoes_principais[0], palpites_secundarios)
        print(f"✅ VALIDAÇÃO COMPLETA: {len(palpites_secundarios)} sugestões alternativas válidas restantes\n")

    time_casa_nome = jogo['teams']['home']['name']
    time_fora_nome = jogo['teams']['away']['name']
    time_casa_id = jogo['teams']['home']['id']
    time_fora_id = jogo['teams']['away']['id']

    # Obter nome da liga com bandeira (NOMES_LIGAS_PT retorna tupla)
    liga_id = jogo['league']['id']
    liga_info = NOMES_LIGAS_PT.get(liga_id)
    nome_liga = liga_info[0] if liga_info else jogo['league']['name']

    # DEBUG: SEMPRE mostrar ID e nome da liga
    liga_real = jogo['league']['name']
    pais_real = jogo['league']['country']
    print(f"🔍 LIGA: ID={liga_id} | Nome API='{liga_real}' ({pais_real}) | Nome Bot='{nome_liga}'")

    # Converter horário para Brasília
    data_utc = datetime.strptime(jogo['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z')
    data_brasilia = data_utc.astimezone(ZoneInfo("America/Sao_Paulo"))
    horario_formatado = data_brasilia.strftime('%H:%M')

    # ========== NOVA ESTRUTURA ==========
    mensagem = f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    mensagem += f"🏆 <b>{nome_liga}</b>\n"
    mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # Buscar posições e forma dos times na classificação
    pos_casa = "N/A"
    pos_fora = "N/A"
    forma_casa = "N/A"
    forma_fora = "N/A"

    if classificacao:
        for time_info in classificacao:
            if time_info['team']['name'] == time_casa_nome:
                pos_casa = time_info.get('rank', 'N/A')
                forma_casa = time_info.get('form', 'N/A')
            if time_info['team']['name'] == time_fora_nome:
                pos_fora = time_info.get('rank', 'N/A')
                forma_fora = time_info.get('form', 'N/A')

    mensagem += f"⚽ <b>{time_casa_nome}</b> <i>({pos_casa}º)</i> <b>vs</b> <b>{time_fora_nome}</b> <i>({pos_fora}º)</i>\n"
    mensagem += f"🕐 <b>Horário:</b> {horario_formatado} (Brasília)\n\n"

    # Rodada e Forma
    rodada_atual = get_rodada_atual(jogo)
    if classificacao:
        mensagem += f"📊 <b>Rodada {rodada_atual}</b> | Forma: {time_casa_nome} <code>{forma_casa}</code> | {time_fora_nome} <code>{forma_fora}</code>\n\n"

    # ========== SUGESTÕES PRINCIPAIS ==========
    mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    mensagem += f"💎 <b>SUGESTÕES PRINCIPAIS</b>\n"
    mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    for idx, palpite in enumerate(sugestoes_principais, 1):
        periodo = palpite.get('periodo', 'FT')
        periodo_str = f" ({periodo})"  # SEMPRE mostrar período (FT, HT, ST)
        time_str = ""

        # Adicionar "Total/Casa/Fora" para mercados com linhas (Gols, Cantos, Cartões)
        if palpite['mercado'] in ['Gols', 'Cantos', 'Cartões', 'Finalizações']:
            time_tipo = palpite.get('time', 'Total')
            if time_tipo == 'Total':
                time_str = ""  # Total é padrão, não precisa mostrar
            else:
                time_str = f" ({time_tipo})"  # Mostrar (Casa) ou (Fora)

        # Formatar tipo do palpite
        tipo_formatado = palpite['tipo']

        odd_str = f" @{palpite['odd']}" if palpite.get('odd') and palpite.get('odd') > 0 else ""
        mensagem += f"<b>{idx}.</b> <b>{tipo_formatado} {palpite['mercado']}{time_str}{periodo_str}</b>{odd_str} "
        mensagem += f"<i>(Confiança: {palpite['confianca']}/10)</i>\n"

    # ========== JUSTIFICATIVA DETALHADA ==========
    mensagem += f"\n📖 <b>JUSTIFICATIVA:</b>\n"

    # Gerar justificativa REAL baseada em dados COM HISTÓRICO DE JOGOS
    justificativa = gerar_justificativa_real(sugestoes_principais, stats_casa, stats_fora, time_casa_nome, time_fora_nome, classificacao, time_casa_id, time_fora_id)
    mensagem += justificativa

    # ========== SUGESTÕES ALTERNATIVAS (MÁXIMO 5) ==========
    if palpites_secundarios:
        mensagem += f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        mensagem += f"📋 <b>SUGESTÕES ALTERNATIVAS</b>\n"
        mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # Limitar para máximo 5 sugestões alternativas
        for palpite in palpites_secundarios[:5]:
            periodo = palpite.get('periodo', 'FT')
            periodo_str = f" ({periodo})"  # SEMPRE mostrar período (FT, HT, ST)
            time_str = ""

            # Adicionar "Total/Casa/Fora" para mercados com linhas
            if palpite['mercado'] in ['Gols', 'Cantos', 'Cartões', 'Finalizações']:
                time_tipo = palpite.get('time', 'Total')
                if time_tipo == 'Total':
                    time_str = ""  # Total é padrão, não precisa mostrar
                else:
                    time_str = f" ({time_tipo})"  # Mostrar (Casa) ou (Fora)

            tipo_formatado = palpite['tipo']

            confianca_emoji = "🟢" if palpite['confianca'] >= 7.5 else "🟡" if palpite['confianca'] >= 6.5 else "🔵"
            odd_str = f" @{palpite['odd']}" if palpite.get('odd') and palpite.get('odd') > 0 else ""
            mensagem += f"{confianca_emoji} <b>{tipo_formatado} {palpite['mercado']}{time_str}{periodo_str}</b>{odd_str} <i>({palpite['confianca']}/10)</i>\n"

    # Indicador de cache otimizado
    if usar_cache_otimizado:
        mensagem += f"\n\n<i>✅ Resultado entregue via cache otimizado: nenhuma nova consulta na API foi necessária.</i>"

    mensagem_final = mensagem + "\n"

    # Guardar análise completa no cache (120 minutos = 2 horas)
    cache_manager.set(cache_key, mensagem_final)

    return mensagem_final

async def coletar_todos_palpites_disponiveis():
    """
    Coleta TODOS os palpites de TODOS os jogos e TODOS os mercados.
    Retorna lista de dicts com: {jogo, palpite, time_casa, time_fora, liga, horario}
    """
    jogos = await buscar_jogos_do_dia()
    if not jogos:
        return []

    todos_palpites_globais = []

    for jogo in jogos:
        fixture_id = jogo['fixture']['id']

        # Buscar cache de análise do banco
        analise_db = db_manager.buscar_analise(fixture_id, max_idade_horas=12)

        if analise_db:
            # Usar análise do cache
            stats_casa = analise_db.get('stats_casa', {})
            stats_fora = analise_db.get('stats_fora', {})
            classificacao = analise_db.get('classificacao', [])
        else:
            # Buscar dados frescos
            time_casa_id = jogo['teams']['home']['id']
            time_fora_id = jogo['teams']['away']['id']
            liga_id = jogo['league']['id']

            stats_casa = await buscar_estatisticas_gerais_time(time_casa_id, liga_id)
            stats_fora = await buscar_estatisticas_gerais_time(time_fora_id, liga_id)
            classificacao = await buscar_classificacao_liga(liga_id)

        # Buscar odds do jogo
        odds = await buscar_odds_do_jogo(fixture_id)

        if not stats_casa or not stats_fora or not odds:
            continue

        # Obter posições na classificação
        pos_casa = "N/A"
        pos_fora = "N/A"
        if classificacao:
            for time_info in classificacao:
                if time_info['team']['name'] == jogo['teams']['home']['name']:
                    pos_casa = time_info['rank']
                if time_info['team']['name'] == jogo['teams']['away']['name']:
                    pos_fora = time_info['rank']

        # 📜 CALCULAR GAME SCRIPT
        home_quality, away_quality = get_quality_scores(time_casa_id, time_fora_id)
        game_script = "EQUILIBRADO"
        quality_difference = abs(home_quality - away_quality)
        if quality_difference > 20:
            game_script = "DOMINIO_CASA" if home_quality > away_quality else "DOMINIO_VISITANTE"
        elif quality_difference > 10:
            game_script = "FAVORITISMO_CASA" if home_quality > away_quality else "FAVORITISMO_VISITANTE"

        # Buscar análise master para contexto tático
        analysis_packet = await generate_match_analysis(jogo)
        
        # Analisar todos os mercados COM OS PARÂMETROS CORRETOS
        analise_gols = analisar_mercado_gols(stats_casa, stats_fora, odds, classificacao, pos_casa, pos_fora, game_script)
        analise_cantos = analisar_mercado_cantos(stats_casa, stats_fora, odds, classificacao, pos_casa, pos_fora, analysis_packet)
        analise_btts = analisar_mercado_btts(stats_casa, stats_fora, odds)
        analise_resultado = analisar_mercado_resultado_final(stats_casa, stats_fora, odds, classificacao, pos_casa, pos_fora)
        analise_cartoes = analisar_mercado_cartoes(stats_casa, stats_fora, odds, analysis_packet)
        analise_finalizacoes = analisar_mercado_finalizacoes(stats_casa, stats_fora, odds)
        analise_handicaps = analisar_mercado_handicaps(stats_casa, stats_fora, odds, classificacao, pos_casa, pos_fora)

        # Coletar palpites
        for analise in [analise_gols, analise_cantos, analise_btts, analise_resultado, analise_cartoes, analise_finalizacoes, analise_handicaps]:
            if analise and 'palpites' in analise:
                mercado_nome = analise.get('mercado', '')
                for palpite in analise['palpites']:
                    # Converter odd para float de forma segura
                    odd_raw = palpite.get('odd', 0)
                    try:
                        odd_float = float(odd_raw) if odd_raw not in [None, "N/A", ""] else 0
                    except (ValueError, TypeError):
                        odd_float = 0

                    if odd_float >= ODD_MINIMA_DE_VALOR:
                        todos_palpites_globais.append({
                            'jogo': jogo,
                            'palpite': palpite,
                            'mercado': mercado_nome,  # Adicionar mercado aqui
                            'time_casa': jogo['teams']['home']['name'],
                            'time_fora': jogo['teams']['away']['name'],
                            'liga': jogo['league']['name'],
                            'horario': jogo['fixture']['date']
                        })

    # DIAGNÓSTICO: Log de produtividade
    print(f"\n📊 RELATÓRIO DE GERAÇÃO DE PALPITES:")
    print(f"   Total de jogos analisados: {len(jogos)}")
    print(f"   Total de palpites gerados: {len(todos_palpites_globais)}")
    print(f"   Taxa de produtividade: {(len(todos_palpites_globais) / max(len(jogos), 1)):.1f} palpites/jogo")
    
    return todos_palpites_globais

def converter_odd_para_float(odd_raw):
    """
    Converte odd (que pode ser string, float ou None) para float de forma segura.
    TASK 4: Fallback mudado de 1.0 para 0.0 para descartar odds inválidas.
    """
    try:
        return float(odd_raw) if odd_raw not in [None, "N/A", "", 0] else 0.0
    except (ValueError, TypeError):
        return 0.0

def calcular_valor_palpite(palpite_data):
    """
    Calcula o 'valor' de um palpite baseado em confiança, odd e coerência.
    Quanto maior o score, melhor o palpite.
    """
    palpite = palpite_data['palpite']
    confianca = palpite.get('confianca', 0)
    odd = converter_odd_para_float(palpite.get('odd', 1.0))

    # Fórmula de valor: prioriza alta confiança com odds razoáveis
    # Penaliza odds muito baixas (<1.30) e muito altas (>3.5)
    if odd < 1.30:
        penalidade_odd = 0.7  # Odd muito baixa
    elif odd > 3.5:
        penalidade_odd = 0.8  # Odd muito alta (risco)
    elif 1.50 <= odd <= 2.20:
        penalidade_odd = 1.2  # Sweet spot: boas odds com valor
    else:
        penalidade_odd = 1.0

    # Score = confiança * penalidade * (odd normalizada)
    valor = confianca * penalidade_odd * min(odd / 1.5, 2.0)

    return valor

async def gerar_aposta_simples():
    """
    Gera UMA ÚNICA aposta de alta confiança de TODOS os jogos/mercados.
    Usa sistema de pontuação de VALOR (não aleatório).
    """
    todos_palpites = await coletar_todos_palpites_disponiveis()

    if not todos_palpites:
        return None

    # Filtrar apenas palpites com confiança >= 6.0 (recalibrado para capturar mais oportunidades)
    palpites_alta_confianca = [p for p in todos_palpites if p['palpite'].get('confianca', 0) >= 6.0]

    if not palpites_alta_confianca:
        # Fallback: relaxar para 5.5 se não houver palpites >= 6.0
        palpites_alta_confianca = [p for p in todos_palpites if p['palpite'].get('confianca', 0) >= 5.5]
    
    if not palpites_alta_confianca:
        palpites_alta_confianca = todos_palpites  # Último fallback: usar todos

    # Calcular valor de cada palpite
    palpites_com_valor = []
    for p in palpites_alta_confianca:
        valor = calcular_valor_palpite(p)
        palpites_com_valor.append((p, valor))

    # Ordenar por valor (maior primeiro)
    palpites_com_valor.sort(key=lambda x: x[1], reverse=True)

    # Escolher entre os TOP 10 com maior valor (adiciona alguma aleatoriedade)
    top_palpites = palpites_com_valor[:min(10, len(palpites_com_valor))]
    escolhido = random.choice(top_palpites)[0]

    return escolhido

async def gerar_multipla_inteligente(min_jogos, max_jogos):
    """
    Gera múltipla com N jogos usando seleções coerentes e de alta confiança.
    Prioriza palpites com MELHOR VALOR (relação confiança/odd).
    """
    todos_palpites = await coletar_todos_palpites_disponiveis()

    if not todos_palpites:
        return []

    # Filtrar apenas palpites com confiança >= 5.5 (recalibrado)
    palpites_bons = [p for p in todos_palpites if p['palpite'].get('confianca', 0) >= 5.5]

    if len(palpites_bons) < min_jogos:
        # Relaxar para 5.0 se não houver jogos suficientes
        palpites_bons = [p for p in todos_palpites if p['palpite'].get('confianca', 0) >= 5.0]

    # Agrupar por jogo (evitar múltiplos palpites do mesmo jogo)
    jogos_disponiveis = {}
    for p in palpites_bons:
        fixture_id = p['jogo']['fixture']['id']
        if fixture_id not in jogos_disponiveis:
            jogos_disponiveis[fixture_id] = []
        jogos_disponiveis[fixture_id].append(p)

    # Selecionar 1 palpite por jogo usando SISTEMA DE VALOR
    palpites_selecionados = []
    for fixture_id, palpites_jogo in jogos_disponiveis.items():
        # Calcular valor de cada palpite do jogo
        palpites_com_valor = []
        for p in palpites_jogo:
            valor = calcular_valor_palpite(p)
            palpites_com_valor.append((p, valor))

        # Escolher o de MAIOR VALOR (não necessariamente maior confiança)
        melhor_palpite = max(palpites_com_valor, key=lambda x: x[1])[0]
        palpites_selecionados.append(melhor_palpite)

    # Ordenar por valor e pegar os melhores
    palpites_ordenados = []
    for p in palpites_selecionados:
        valor = calcular_valor_palpite(p)
        palpites_ordenados.append((p, valor))

    palpites_ordenados.sort(key=lambda x: x[1], reverse=True)

    # ALEATORIEDADE: Escolher entre os TOP candidatos (não sempre os mesmos)
    num_jogos = random.randint(min_jogos, min(max_jogos, len(palpites_ordenados)))

    # Pegar 2x o número necessário dos melhores e embaralhar
    pool_size = min(num_jogos * 2, len(palpites_ordenados))
    pool_candidatos = palpites_ordenados[:pool_size]

    # Embaralhar e pegar N jogos aleatórios do pool
    random.shuffle(pool_candidatos)

    return [p[0] for p in pool_candidatos[:num_jogos]]

async def gerar_bingo_odd_alta(odd_min, odd_max):
    """
    Gera múltipla com odd total entre odd_min e odd_max.
    ESTRATÉGIA INTELIGENTE:
    - Prioriza VALOR (alta confiança com odds razoáveis)
    - NÃO escolhe odds @5, @6 desesperadamente
    - Prefere VOLUME com valor (muitos jogos @1.30-1.80)
    - Usa algoritmo de otimização para melhor combinação
    """
    todos_palpites = await coletar_todos_palpites_disponiveis()

    if not todos_palpites:
        return []

    # Filtrar palpites com confiança >= 5.5 E odd <= 3.0 (evita odds absurdas) - recalibrado
    palpites_validos = [p for p in todos_palpites 
                        if p['palpite'].get('confianca', 0) >= 5.5 
                        and converter_odd_para_float(p['palpite'].get('odd', 1.0)) <= 3.0]

    # Se não tem palpites suficientes, relaxa o filtro de odd
    if len(palpites_validos) < 10:
        palpites_validos = [p for p in todos_palpites 
                            if p['palpite'].get('confianca', 0) >= 5.0
                            and converter_odd_para_float(p['palpite'].get('odd', 1.0)) <= 4.0]

    # Agrupar por jogo (1 palpite por jogo)
    jogos_disponiveis = {}
    for p in palpites_validos:
        fixture_id = p['jogo']['fixture']['id']
        if fixture_id not in jogos_disponiveis:
            jogos_disponiveis[fixture_id] = []
        jogos_disponiveis[fixture_id].append(p)

    # Selecionar melhor palpite de cada jogo usando SISTEMA DE VALOR
    palpites_disponiveis = []
    for fixture_id, palpites_jogo in jogos_disponiveis.items():
        palpites_com_valor = []
        for p in palpites_jogo:
            valor = calcular_valor_palpite(p)
            palpites_com_valor.append((p, valor))

        melhor_palpite = max(palpites_com_valor, key=lambda x: x[1])[0]
        palpites_disponiveis.append(melhor_palpite)

    # Ordenar por VALOR (melhores primeiro)
    palpites_ordenados = []
    for p in palpites_disponiveis:
        valor = calcular_valor_palpite(p)
        palpites_ordenados.append((p, valor))

    palpites_ordenados.sort(key=lambda x: x[1], reverse=True)

    # ESTRATÉGIA: Priorizar odds médias (@1.30-2.00) para construir odd alta com volume
    multipla_final = []
    odd_acumulada = 1.0

    # Separar palpites por faixa de odd
    odds_baixas = [p for p, v in palpites_ordenados if 1.30 <= converter_odd_para_float(p['palpite'].get('odd', 1.0)) <= 1.60]
    odds_medias = [p for p, v in palpites_ordenados if 1.60 < converter_odd_para_float(p['palpite'].get('odd', 1.0)) <= 2.20]
    odds_altas = [p for p, v in palpites_ordenados if 2.20 < converter_odd_para_float(p['palpite'].get('odd', 1.0)) <= 3.0]

    # ALEATORIEDADE: Embaralhar cada faixa para gerar múltiplas diferentes
    random.shuffle(odds_baixas)
    random.shuffle(odds_medias)
    random.shuffle(odds_altas)

    # Estratégia: começar com odds baixas/médias (volume com valor)
    pool = odds_baixas + odds_medias + odds_altas

    for palpite in pool:
        if len(multipla_final) >= 20:
            break

        odd_palpite = converter_odd_para_float(palpite['palpite'].get('odd', 1.0))
        nova_odd = odd_acumulada * odd_palpite

        # Continua adicionando se não atingiu o mínimo
        if nova_odd < odd_min:
            multipla_final.append(palpite)
            odd_acumulada = nova_odd
        # Se está no range ideal, adiciona e PODE parar (mas verifica se pode melhorar)
        elif odd_min <= nova_odd <= odd_max:
            multipla_final.append(palpite)
            odd_acumulada = nova_odd
            # Se está próximo do meio do range, para
            if nova_odd >= (odd_min + odd_max) / 2:
                break
        # Se ultrapassou um pouco, adiciona e para
        elif nova_odd <= odd_max * 1.3:
            multipla_final.append(palpite)
            odd_acumulada = nova_odd
            break
        # Se ultrapassou muito, pula este palpite
        else:
            continue

    # Se ainda não atingiu mínimo, adiciona mais palpites
    if odd_acumulada < odd_min and len(multipla_final) < 20:
        for palpite in pool:
            if palpite in multipla_final:
                continue

            odd_palpite = converter_odd_para_float(palpite['palpite'].get('odd', 1.0))
            nova_odd = odd_acumulada * odd_palpite

            multipla_final.append(palpite)
            odd_acumulada = nova_odd

            if odd_acumulada >= odd_min or len(multipla_final) >= 20:
                break

    return multipla_final

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    if not check_rate_limit(user_id):
        await update.message.reply_text(
            "⚠️ <b>Limite de Requisições Excedido</b>\n\n"
            "Você está enviando comandos muito rapidamente.\n"
            f"Por favor, aguarde alguns segundos antes de tentar novamente. (Limite: {RATE_LIMIT_COMMANDS_PER_MINUTE} comandos/{RATE_LIMIT_WINDOW_SECONDS}s)",
            parse_mode='HTML'
        )
        return
    
    # Menu organizado em grid 2x3 + NOVOS MÓDULOS + linha de configurações
    keyboard = [
        [InlineKeyboardButton("🎯 Análise Completa", callback_data='analise_completa'), 
         InlineKeyboardButton("🔍 Buscar Jogo", callback_data='buscar_jogo')],
        [InlineKeyboardButton("⚽ Over Gols", callback_data='analise_over_gols'), 
         InlineKeyboardButton("🚩 Escanteios", callback_data='analise_escanteios')],
        [InlineKeyboardButton("🎲 BTTS", callback_data='analise_btts'), 
         InlineKeyboardButton("🏁 Resultado", callback_data='analise_resultado')],
        [InlineKeyboardButton("💰 Aposta Simples", callback_data='aposta_simples'),
         InlineKeyboardButton("🎰 Criar Múltipla", callback_data='criar_multipla'),
         InlineKeyboardButton("🎯 Bingo", callback_data='bingo')],
        [InlineKeyboardButton("📅 Jogos do Dia", callback_data='stats_dia'),
         InlineKeyboardButton("🏆 Por Liga", callback_data='analise_por_liga')],
        [InlineKeyboardButton("⚙️ Configurações", callback_data='configuracoes')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Mensagem de boas-vindas mais visual
    await update.message.reply_html(
        f"👋 Olá, {update.effective_user.mention_html()}!\n\n"
        f"🤖 Eu sou o <b>AnalytipsBot</b> - Seu assistente de análise de apostas esportivas!\n\n"
        f"📈 <b>Escolha uma opção abaixo:</b>",
        reply_markup=reply_markup
    )

async def limpar_cache_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    if not check_rate_limit(user_id):
        await update.message.reply_text(
            "⚠️ <b>Limite de Requisições Excedido</b>\n\n"
            "Você está enviando comandos muito rapidamente.\n"
            f"Por favor, aguarde alguns segundos antes de tentar novamente.",
            parse_mode='HTML'
        )
        return
    
    cache_manager.clear()
    await update.message.reply_text("✅ Memória de análise (cache) foi limpa com sucesso!")

async def getlog_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /getlog - Exporta as últimas 500 linhas do log do bot"""
    user_id = update.effective_user.id
    
    if not check_rate_limit(user_id):
        await update.message.reply_text(
            "⚠️ <b>Limite de Requisições Excedido</b>\n\n"
            "Você está enviando comandos muito rapidamente.\n"
            f"Por favor, aguarde alguns segundos antes de tentar novamente.",
            parse_mode='HTML'
        )
        return
    
    import glob
    import os
    import re
    
    try:
        # Encontrar o arquivo de log mais recente em /tmp/logs/
        log_files = glob.glob("/tmp/logs/Bot_Telegram_*.log")
        
        if not log_files:
            await update.message.reply_text("❌ Nenhum arquivo de log encontrado.")
            return
        
        # Pegar o arquivo mais recente
        latest_log = max(log_files, key=os.path.getmtime)
        
        # Ler o arquivo XML completo
        with open(latest_log, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Extrair o conteúdo dentro das tags <logs>
        match = re.search(r'<logs>(.*?)</logs>', content, re.DOTALL)
        
        if not match:
            await update.message.reply_text("❌ Formato de log não reconhecido.")
            return
        
        # Pegar apenas o conteúdo dentro das tags <logs>
        log_content_full = match.group(1).strip()
        
        # Dividir em linhas e pegar as últimas 500
        lines = log_content_full.split('\n')
        last_lines = lines[-500:]
        log_content = "\n".join(last_lines)
        
        # Informar o usuário
        total_lines = len(lines)
        await update.message.reply_text(
            f"📋 <b>Exportando Log do Bot</b>\n\n"
            f"📁 Arquivo: <code>{os.path.basename(latest_log)}</code>\n"
            f"📊 Total de linhas: <b>{total_lines}</b>\n"
            f"📤 Enviando: <b>últimas {len(last_lines)} linhas</b>",
            parse_mode='HTML'
        )
        
        # Telegram tem limite de 4096 caracteres por mensagem
        # Usar blocos de código Markdown para evitar parsing de entidades especiais
        # Limite: 4096 - 6 (para ``` no início e fim) = 4090 caracteres úteis
        MAX_CHUNK_SIZE = 4090
        
        if len(log_content) > MAX_CHUNK_SIZE:
            for i in range(0, len(log_content), MAX_CHUNK_SIZE):
                chunk = log_content[i:i+MAX_CHUNK_SIZE]
                # Enviar cada chunk em um bloco de código Markdown
                await update.message.reply_text(f"```\n{chunk}\n```", parse_mode='Markdown')
        else:
            # Enviar tudo em um único bloco de código Markdown
            await update.message.reply_text(f"```\n{log_content}\n```", parse_mode='Markdown')
        
        await update.message.reply_text("✅ Log exportado com sucesso!")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao ler arquivo de log: {str(e)}")

async def processar_um_jogo(jogo, idx_total, filtro_mercado, filtro_tipo_linha):
    """Processa um único jogo (async) - verifica cache primeiro"""
    cache_key = f"analise_jogo_{jogo['fixture']['id']}_{filtro_mercado}_{filtro_tipo_linha}"
    analise_cached = cache_manager.get(cache_key)

    if analise_cached:
        print(f"✅ CACHE HIT: Jogo {idx_total} (ID {jogo['fixture']['id']})")
        return analise_cached if analise_cached else None

    print(f"⚙️  PROCESSANDO: Jogo {idx_total} (ID {jogo['fixture']['id']})")
    # Executar gerar_palpite_completo diretamente (já é async)
    palpite = await gerar_palpite_completo(jogo, filtro_mercado, filtro_tipo_linha)
    return palpite if palpite else None

async def processar_analises_em_background(sessao_id, jogos, filtro_mercado, filtro_tipo_linha):
    """
    Processa análises EM PARALELO (lotes de 10) em background.
    Continua processando enquanto o usuário recebe os primeiros resultados.
    """
    print(f"🔄 BACKGROUND: Iniciando processamento PARALELO de {len(jogos)} jogos (sessão {sessao_id})")
    analises_processadas = []
    LOTE_PARALELO = 10  # Processar 10 jogos ao mesmo tempo

    # Processar em lotes paralelos
    for i in range(0, len(jogos), LOTE_PARALELO):
        lote = jogos[i:i+LOTE_PARALELO]

        # Processar este lote em paralelo
        tasks = [
            processar_um_jogo(jogo, i+idx+1, filtro_mercado, filtro_tipo_linha) 
            for idx, jogo in enumerate(lote)
        ]
        resultados = await asyncio.gather(*tasks, return_exceptions=True)

        # Adicionar resultados válidos
        for resultado in resultados:
            if resultado and not isinstance(resultado, Exception):
                analises_processadas.append(resultado)

        # Atualizar progresso no dicionário global
        analises_em_background[sessao_id] = {
            'analises': analises_processadas.copy(),
            'processados': min(i + LOTE_PARALELO, len(jogos)),
            'total': len(jogos),
            'completo': (i + LOTE_PARALELO) >= len(jogos)
        }

        print(f"📊 PROGRESSO: {len(analises_processadas)} análises prontas ({min(i+LOTE_PARALELO, len(jogos))}/{len(jogos)} jogos processados)")

    print(f"✅ BACKGROUND: Finalizado! {len(analises_processadas)} análises prontas (sessão {sessao_id})")
    return analises_processadas

async def analisar_e_enviar_proximo_lote(query, context: ContextTypes.DEFAULT_TYPE):
    chat_id = query.message.chat_id
    user_data = context.user_data

    jogos_nao_analisados = user_data.get('lista_de_jogos', [])
    indice_atual = user_data.get('proximo_indice_jogo', 0)
    filtro_mercado = user_data.get('filtro_mercado', None)
    filtro_tipo_linha = user_data.get('filtro_tipo_linha', None)

    # ID único para esta sessão de análise
    sessao_id = user_data.get('sessao_analise_id')

    # Primeira vez? Iniciar processamento em background
    if indice_atual == 0:
        # LIMPAR dados de sessões anteriores
        user_data['analises_processadas'] = []

        sessao_id = f"{chat_id}_{random.randint(1000,9999)}"
        user_data['sessao_analise_id'] = sessao_id

        # Iniciar tarefa em background (não aguarda completar!)
        asyncio.create_task(processar_analises_em_background(
            sessao_id, jogos_nao_analisados, filtro_mercado, filtro_tipo_linha
        ))

        await query.edit_message_text(text=f"⚡ Analisando {len(jogos_nao_analisados)} jogos...\n💾 Cache inteligente ativado!")
        await asyncio.sleep(2)  # Dar tempo para processar primeiros jogos

    # Buscar análises: primeiro em user_data (mais rápido), depois em background
    todas_analises = user_data.get('analises_processadas', [])

    if not todas_analises:
        # Buscar do background se ainda não está em user_data
        progresso_bg = analises_em_background.get(sessao_id, {'analises': [], 'processados': 0, 'total': len(jogos_nao_analisados)})
        todas_analises = progresso_bg['analises']
        processados = progresso_bg['processados']
    else:
        # Análises já no user_data, buscar progresso atualizado
        progresso_bg = analises_em_background.get(sessao_id, {'analises': todas_analises, 'processados': len(todas_analises), 'completo': True})

    # Aguardar até ter pelo menos 5 análises (OU processamento completo)
    tentativas = 0
    while len(todas_analises) < min(indice_atual + JOGOS_POR_PAGINA, len(jogos_nao_analisados)) and tentativas < 60:
        progresso_bg = analises_em_background.get(sessao_id, {'analises': [], 'processados': 0, 'completo': False})

        # Se processamento completou, sair imediatamente (mesmo com menos análises)
        if progresso_bg.get('completo', False):
            todas_analises = progresso_bg['analises']
            break

        await asyncio.sleep(1)
        todas_analises = progresso_bg['analises']
        tentativas += 1

        # Atualizar progresso (com tratamento de timeout)
        if tentativas % 5 == 0:
            try:
                await query.edit_message_text(text=f"⏳ Processando... {len(todas_analises)} análises prontas")
            except Exception:
                pass  # Ignorar erros de timeout do Telegram

    # Armazenar análises completas em user_data para reutilização rápida
    user_data['analises_processadas'] = todas_analises

    # Pegar próximo lote
    palpites_deste_lote = todas_analises[indice_atual:indice_atual + JOGOS_POR_PAGINA]
    novo_indice = indice_atual + len(palpites_deste_lote)
    user_data['proximo_indice_jogo'] = novo_indice

    if not palpites_deste_lote:
        # DIAGNÓSTICO: Log para debug (não deve mais acontecer com novo modelo)
        print(f"⚠️ AVISO: Nenhum palpite gerado no lote. Total de análises disponíveis: {len(todas_analises)}")
        print(f"   Índice atual: {indice_atual}, Jogos processados: {processados}")
        
        keyboard = [[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='voltar_menu')]]
        # Mensagem mais informativa
        msg_debug = (
            f"📊 Processamento concluído!\n\n"
            f"✅ {len(todas_analises)} análises foram geradas para os jogos disponíveis.\n"
            f"💡 Se não há mais palpites neste momento, aguarde novos jogos ou ajuste os filtros.\n\n"
            f"🔄 <i>O bot está otimizado e gerando mais oportunidades com o novo modelo de confiança.</i>"
        )
        await context.bot.send_message(chat_id, msg_debug, 
                                       reply_markup=InlineKeyboardMarkup(keyboard),
                                       parse_mode='HTML')
        await query.delete_message()
        # Limpar sessão
        if sessao_id in analises_em_background:
            del analises_em_background[sessao_id]
        return

    await query.delete_message()

    # Enviar análises
    for palpite in palpites_deste_lote:
        await context.bot.send_message(chat_id, palpite, parse_mode='HTML')

    # Ainda tem mais análises?
    if novo_indice < len(todas_analises) or not progresso_bg.get('completo', False):
        processados_atual = progresso_bg.get('processados', 0)
        callback_suffix = f"{filtro_mercado}_{filtro_tipo_linha}" if filtro_mercado or filtro_tipo_linha else "None"
        keyboard = [
            [InlineKeyboardButton(f"📊 Gerar Mais Análises ({processados_atual}/{len(jogos_nao_analisados)} processados)", callback_data=f'carregar_mais_{callback_suffix}')],
            [InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='voltar_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id, "✅ Próximo lote pronto!", reply_markup=reply_markup)
    else:
        keyboard = [[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='voltar_menu')]]
        await context.bot.send_message(chat_id, 
                                       f"🎯 <b>Fim da Análise!</b>\n\n"
                                       f"✅ Total de {len(todas_analises)} análises encontradas.\n"
                                       f"💾 Tudo salvo no cache para próximas consultas!",
                                       reply_markup=InlineKeyboardMarkup(keyboard),
                                       parse_mode='HTML')
        # Limpar sessão
        if sessao_id in analises_em_background:
            del analises_em_background[sessao_id]

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    
    if not check_rate_limit(user_id):
        await query.answer(
            "⚠️ Você está enviando comandos muito rapidamente. Por favor, aguarde alguns segundos.",
            show_alert=True
        )
        return
    
    await query.answer()
    data = query.data

    logging.info(f"🔵 BUTTON HANDLER: User {user_id} - callback_data = '{data}'")

    if data == 'analise_completa':
        try:
            print("🔵 INICIANDO: Análise Completa")
            context.user_data['filtro_mercado'] = None
            context.user_data['filtro_tipo_linha'] = None

            await query.edit_message_text(text="Buscando a lista de jogos do dia...")
            print("🔵 CHAMANDO: buscar_jogos_do_dia()")

            jogos_encontrados = await buscar_jogos_do_dia()

            print(f"🔵 RESULTADO: {len(jogos_encontrados) if jogos_encontrados else 0} jogos encontrados")

            if not jogos_encontrados:
                await query.edit_message_text(text="Não encontrei jogos para hoje.")
                return

            random.shuffle(jogos_encontrados)
            context.user_data['lista_de_jogos'] = jogos_encontrados
            context.user_data['proximo_indice_jogo'] = 0

            print("🔵 CHAMANDO: analisar_e_enviar_proximo_lote()")
            await analisar_e_enviar_proximo_lote(query, context)
            print("🔵 CONCLUÍDO: analisar_e_enviar_proximo_lote()")
        except Exception as e:
            print(f"❌ ERRO CRÍTICO em analise_completa: {e}")
            import traceback
            traceback.print_exc()
            await context.bot.send_message(query.message.chat_id, f"❌ Erro: {str(e)}")

    elif data == 'analise_por_liga':
        await query.edit_message_text(text="📋 Carregando ligas suportadas...")
        ligas = await asyncio.to_thread(buscar_todas_ligas_suportadas)

        if not ligas:
            await query.edit_message_text(text="❌ Erro ao carregar ligas.")
            return

        context.user_data['ligas_disponiveis'] = ligas
        context.user_data['pagina_liga_atual'] = 0
        await mostrar_pagina_ligas(query, context)

    elif data.startswith('liga_'):
        liga_id = int(data.split('_')[1])

        await query.edit_message_text(text="Buscando jogos da liga...")
        jogos_liga = await buscar_jogos_por_liga(liga_id)

        if not jogos_liga:
            await query.edit_message_text(text="Não encontrei jogos desta liga para hoje.")
            return

        random.shuffle(jogos_liga)
        context.user_data['lista_de_jogos'] = jogos_liga
        context.user_data['proximo_indice_jogo'] = 0
        context.user_data['filtro_mercado'] = None
        context.user_data['filtro_tipo_linha'] = None
        await analisar_e_enviar_proximo_lote(query, context)

    elif data == 'proxima_pagina_ligas':
        context.user_data['pagina_liga_atual'] += 1
        await mostrar_pagina_ligas(query, context)

    elif data == 'pagina_anterior_ligas':
        context.user_data['pagina_liga_atual'] -= 1
        await mostrar_pagina_ligas(query, context)
    
    elif data == 'pag_prox_buscar_jogo':
        context.user_data['pagina_buscar_jogo'] += 1
        await mostrar_ligas_buscar_jogo(query, context)
    
    elif data == 'pag_ant_buscar_jogo':
        context.user_data['pagina_buscar_jogo'] -= 1
        await mostrar_ligas_buscar_jogo(query, context)

    elif data == 'analise_over_gols':
        user_id = query.from_user.id
        await query.edit_message_text(text="⚽ Adicionando análise Over Gols à fila...\n\n⏳ Processando em background. Aguarde alguns instantes...")
        
        job_id = await job_queue.add_analysis_job(user_id, 'goals_only')
        
        if job_id is None:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="⚠️ <b>Sistema Temporariamente Sobrecarregado</b>\n\n"
                     "Estou processando um grande número de análises no momento.\n\n"
                     "Por favor, tente novamente em alguns minutos. 🙏",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="voltar_menu")]])
            )
            return
        
        await asyncio.sleep(2)
        
        paginated = pagination_helpers.get_paginated_analyses(db_manager, user_id, 'goals_only', 0)
        
        if paginated['analyses']:
            from analysts.dossier_formatter import format_phoenix_dossier
            
            for analysis_row in paginated['analyses']:
                dossier = pagination_helpers.parse_dossier_from_analysis(analysis_row)
                formatted_msg = format_phoenix_dossier(dossier)
                await context.bot.send_message(chat_id=query.message.chat_id, text=formatted_msg, parse_mode='HTML')
            
            keyboard = pagination_helpers.create_pagination_keyboard(0, paginated['has_more'], 'goals_only', paginated['total_pages'])
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"📊 Mostrando {len(paginated['analyses'])} de {paginated['total']} análises",
                reply_markup=keyboard
            )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="⏳ Análises sendo processadas. Use o menu para checar novamente em alguns segundos.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="voltar_menu")]])
            )

    elif data == 'analise_escanteios':
        user_id = query.from_user.id
        await query.edit_message_text(text="🚩 Adicionando análise de Escanteios à fila...\n\n⏳ Processando em background. Aguarde alguns instantes...")
        
        job_id = await job_queue.add_analysis_job(user_id, 'corners_only')
        
        if job_id is None:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="⚠️ <b>Sistema Temporariamente Sobrecarregado</b>\n\n"
                     "Estou processando um grande número de análises no momento.\n\n"
                     "Por favor, tente novamente em alguns minutos. 🙏",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="voltar_menu")]])
            )
            return
        
        await asyncio.sleep(2)
        
        paginated = pagination_helpers.get_paginated_analyses(db_manager, user_id, 'corners_only', 0)
        
        if paginated['analyses']:
            from analysts.dossier_formatter import format_phoenix_dossier
            
            for analysis_row in paginated['analyses']:
                dossier = pagination_helpers.parse_dossier_from_analysis(analysis_row)
                formatted_msg = format_phoenix_dossier(dossier)
                await context.bot.send_message(chat_id=query.message.chat_id, text=formatted_msg, parse_mode='HTML')
            
            keyboard = pagination_helpers.create_pagination_keyboard(0, paginated['has_more'], 'corners_only', paginated['total_pages'])
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"📊 Mostrando {len(paginated['analyses'])} de {paginated['total']} análises",
                reply_markup=keyboard
            )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="⏳ Análises sendo processadas. Use o menu para checar novamente em alguns segundos.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="voltar_menu")]])
            )

    elif data == 'analise_btts':
        user_id = query.from_user.id
        await query.edit_message_text(text="🎲 Adicionando análise BTTS à fila...\n\n⏳ Processando em background. Aguarde alguns instantes...")
        
        job_id = await job_queue.add_analysis_job(user_id, 'btts_only')
        
        if job_id is None:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="⚠️ <b>Sistema Temporariamente Sobrecarregado</b>\n\n"
                     "Estou processando um grande número de análises no momento.\n\n"
                     "Por favor, tente novamente em alguns minutos. 🙏",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="voltar_menu")]])
            )
            return
        
        await asyncio.sleep(2)
        
        paginated = pagination_helpers.get_paginated_analyses(db_manager, user_id, 'btts_only', 0)
        
        if paginated['analyses']:
            from analysts.dossier_formatter import format_phoenix_dossier
            
            for analysis_row in paginated['analyses']:
                dossier = pagination_helpers.parse_dossier_from_analysis(analysis_row)
                formatted_msg = format_phoenix_dossier(dossier)
                await context.bot.send_message(chat_id=query.message.chat_id, text=formatted_msg, parse_mode='HTML')
            
            keyboard = pagination_helpers.create_pagination_keyboard(0, paginated['has_more'], 'btts_only', paginated['total_pages'])
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"📊 Mostrando {len(paginated['analyses'])} de {paginated['total']} análises",
                reply_markup=keyboard
            )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="⏳ Análises sendo processadas. Use o menu para checar novamente em alguns segundos.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="voltar_menu")]])
            )

    elif data == 'analise_resultado':
        user_id = query.from_user.id
        await query.edit_message_text(text="🏁 Adicionando análise de Resultado à fila...\n\n⏳ Processando em background. Aguarde alguns instantes...")
        
        job_id = await job_queue.add_analysis_job(user_id, 'result_only')
        
        if job_id is None:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="⚠️ <b>Sistema Temporariamente Sobrecarregado</b>\n\n"
                     "Estou processando um grande número de análises no momento.\n\n"
                     "Por favor, tente novamente em alguns minutos. 🙏",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="voltar_menu")]])
            )
            return
        
        await asyncio.sleep(2)
        
        paginated = pagination_helpers.get_paginated_analyses(db_manager, user_id, 'result_only', 0)
        
        if paginated['analyses']:
            from analysts.dossier_formatter import format_phoenix_dossier
            
            for analysis_row in paginated['analyses']:
                dossier = pagination_helpers.parse_dossier_from_analysis(analysis_row)
                formatted_msg = format_phoenix_dossier(dossier)
                await context.bot.send_message(chat_id=query.message.chat_id, text=formatted_msg, parse_mode='HTML')
            
            keyboard = pagination_helpers.create_pagination_keyboard(0, paginated['has_more'], 'result_only', paginated['total_pages'])
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"📊 Mostrando {len(paginated['analyses'])} de {paginated['total']} análises",
                reply_markup=keyboard
            )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="⏳ Análises sendo processadas. Use o menu para checar novamente em alguns segundos.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="voltar_menu")]])
            )

    elif data == 'buscar_jogo':
        await query.edit_message_text(text="🔍 Carregando ligas disponíveis...")
        ligas = await buscar_ligas_disponiveis_hoje()
        
        if not ligas:
            keyboard = [[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='voltar_menu')]]
            await query.edit_message_text(
                text="❌ Não encontrei ligas com jogos para hoje.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # Armazenar ligas no contexto do usuário para paginação
        context.user_data['ligas_buscar_jogo'] = ligas
        context.user_data['pagina_buscar_jogo'] = 0
        
        await mostrar_ligas_buscar_jogo(query, context)
    
    elif data == 'stats_dia':
        await query.edit_message_text(text="📅 Carregando jogos do dia...")
        jogos = await buscar_jogos_do_dia()

        if not jogos:
            await query.edit_message_text(text="❌ Não encontrei jogos para hoje.")
            return

        # Agrupar jogos por liga com informações de país para ordenação
        ligas_dict = {}
        for jogo in jogos:
            liga_id = jogo['league']['id']
            liga_info = NOMES_LIGAS_PT.get(liga_id)
            
            if liga_info:
                liga_nome, pais = liga_info
                ordem_pais = ORDEM_PAISES.get(pais, 999)
                
                if liga_id not in ligas_dict:
                    ligas_dict[liga_id] = {
                        'nome': liga_nome,
                        'pais': pais,
                        'ordem_pais': ordem_pais,
                        'count': 0
                    }
                ligas_dict[liga_id]['count'] += 1

        # Ordenar ligas por país (ordem personalizada) e depois por número de jogos
        ligas_ordenadas = sorted(
            ligas_dict.values(),
            key=lambda x: (x['ordem_pais'], -x['count'], x['nome'])
        )

        mensagem = f"📅 <b>Jogos do Dia</b>\n\n"
        mensagem += f"⚽ <b>Total de Jogos:</b> {len(jogos)}\n"
        mensagem += f"🏆 <b>Total de Ligas:</b> {len(ligas_dict)}\n\n"
        mensagem += f"📋 <b>Jogos por Liga:</b>\n"

        for liga in ligas_ordenadas:
            count = liga['count']
            mensagem += f"• {liga['nome']}: {count} jogo{'s' if count > 1 else ''}\n"

        keyboard = [[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='voltar_menu')]]
        await query.edit_message_text(text=mensagem, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data == 'configuracoes':
        # Obter configurações atuais do usuário (ou padrões)
        odd_minima = context.user_data.get('odd_minima', ODD_MINIMA_DE_VALOR)
        confianca_minima = context.user_data.get('confianca_minima', 6.0)

        mensagem = (
            f"⚙️ <b>Configurações</b>\n\n"
            f"📊 <b>Configurações Atuais:</b>\n"
            f"  • Odd Mínima: {odd_minima}\n"
            f"  • Confiança Mínima: {confianca_minima}/10\n\n"
            f"🔧 Escolha o que deseja ajustar:"
        )

        keyboard = [
            [InlineKeyboardButton("📈 Odd Mínima", callback_data='config_odd_minima'),
             InlineKeyboardButton("🎯 Confiança Mínima", callback_data='config_confianca')],
            [InlineKeyboardButton("🔄 Restaurar Padrões", callback_data='config_resetar')],
            [InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='voltar_menu')]
        ]
        await query.edit_message_text(text=mensagem, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data == 'config_odd_minima':
        keyboard = [
            [InlineKeyboardButton("1.30", callback_data='set_odd_1.30'), 
             InlineKeyboardButton("1.50", callback_data='set_odd_1.50')],
            [InlineKeyboardButton("1.70", callback_data='set_odd_1.70'), 
             InlineKeyboardButton("2.00", callback_data='set_odd_2.00')],
            [InlineKeyboardButton("🔙 Voltar", callback_data='configuracoes')]
        ]
        await query.edit_message_text(
            text="📈 <b>Selecione a Odd Mínima</b>\n\nApenas apostas com odd igual ou superior serão mostradas:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

    elif data.startswith('set_odd_'):
        odd_valor = float(data.split('_')[2])
        context.user_data['odd_minima'] = odd_valor
        await query.answer(f"✅ Odd mínima alterada para {odd_valor}")
        await query.edit_message_text(
            text=f"✅ <b>Configuração Salva!</b>\n\nOdd mínima agora é {odd_valor}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data='configuracoes')]]),
            parse_mode='HTML'
        )

    elif data == 'config_confianca':
        keyboard = [
            [InlineKeyboardButton("5.0", callback_data='set_conf_5.0'), 
             InlineKeyboardButton("6.0", callback_data='set_conf_6.0')],
            [InlineKeyboardButton("7.0", callback_data='set_conf_7.0'), 
             InlineKeyboardButton("8.0", callback_data='set_conf_8.0')],
            [InlineKeyboardButton("🔙 Voltar", callback_data='configuracoes')]
        ]
        await query.edit_message_text(
            text="🎯 <b>Selecione a Confiança Mínima</b>\n\nApenas palpites com confiança igual ou superior serão mostrados:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

    elif data.startswith('set_conf_'):
        conf_valor = float(data.split('_')[2])
        context.user_data['confianca_minima'] = conf_valor
        await query.answer(f"✅ Confiança mínima alterada para {conf_valor}/10")
        await query.edit_message_text(
            text=f"✅ <b>Configuração Salva!</b>\n\nConfiança mínima agora é {conf_valor}/10",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data='configuracoes')]]),
            parse_mode='HTML'
        )

    elif data == 'config_resetar':
        context.user_data['odd_minima'] = ODD_MINIMA_DE_VALOR
        context.user_data['confianca_minima'] = 6.0
        await query.answer("✅ Configurações restauradas!")
        await query.edit_message_text(
            text=f"✅ <b>Configurações Restauradas!</b>\n\nOdd mínima: {ODD_MINIMA_DE_VALOR}\nConfiança mínima: 6.0/10",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data='configuracoes')]]),
            parse_mode='HTML'
        )

    elif data == 'aposta_simples':
        await query.edit_message_text(text="🎲 Gerando aposta simples...")
        aposta = await gerar_aposta_simples()

        if not aposta:
            await query.edit_message_text(text="❌ Não encontrei jogos disponíveis para gerar aposta simples.")
            return

        palpite = aposta['palpite']
        jogo = aposta['jogo']

        data_utc = datetime.strptime(jogo['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z')
        data_brasilia = data_utc.astimezone(ZoneInfo("America/Sao_Paulo"))
        horario = data_brasilia.strftime('%H:%M')

        periodo = palpite.get('periodo', 'FT')
        periodo_str = f" ({periodo})"  # SEMPRE mostrar período (FT, HT, ST)

        # Pegar mercado do item ao invés do palpite
        mercado = aposta.get('mercado', palpite.get('mercado', ''))

        mensagem = f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        mensagem += f"💰 <b>APOSTA SIMPLES</b>\n"
        mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        mensagem += f"🏆 {aposta['liga']}\n"
        mensagem += f"⚽ <b>{aposta['time_casa']}</b> vs <b>{aposta['time_fora']}</b>\n"
        mensagem += f"🕐 {horario} (Brasília)\n\n"
        mensagem += f"🎯 <b>{palpite['tipo']} {mercado}{periodo_str}</b>\n"
        
        if palpite.get('odd') and palpite.get('odd') > 0:
            mensagem += f"📊 Odd: <b>@{palpite['odd']}</b>\n"
        
        mensagem += f"💎 Confiança: <b>{palpite['confianca']}/10</b>\n"

        keyboard = [
            [InlineKeyboardButton("🔄 Gerar Nova Aposta", callback_data='aposta_simples')],
            [InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='voltar_menu')]
        ]
        await query.edit_message_text(text=mensagem, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data == 'criar_multipla':
        keyboard = [
            [InlineKeyboardButton("2-4 Jogos", callback_data='multipla_2_4')],
            [InlineKeyboardButton("4-6 Jogos", callback_data='multipla_4_6')],
            [InlineKeyboardButton("5-9 Jogos", callback_data='multipla_5_9')],
            [InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='voltar_menu')]
        ]
        await query.edit_message_text(
            text="🎰 <b>Criar Múltipla</b>\n\nEscolha quantos jogos deseja na múltipla:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

    elif data.startswith('multipla_'):
        parts = data.split('_')
        min_jogos = int(parts[1])
        max_jogos = int(parts[2])

        await query.edit_message_text(text=f"🎰 Montando múltipla com {min_jogos}-{max_jogos} jogos...")
        multipla = await gerar_multipla_inteligente(min_jogos, max_jogos)

        if not multipla:
            await query.edit_message_text(text="❌ Não encontrei jogos suficientes para criar a múltipla.")
            return

        odd_total = 1.0
        for item in multipla:
            odd_total *= item['palpite'].get('odd', 1.0)

        mensagem = f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        mensagem += f"🎰 <b>MÚLTIPLA ({len(multipla)} JOGOS)</b>\n"
        mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        for idx, item in enumerate(multipla, 1):
            jogo = item['jogo']
            palpite = item['palpite']
            mercado = item.get('mercado', '')

            data_utc = datetime.strptime(jogo['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z')
            data_brasilia = data_utc.astimezone(ZoneInfo("America/Sao_Paulo"))
            horario = data_brasilia.strftime('%H:%M')

            periodo_str = f" ({palpite.get('periodo', 'FT')})" if palpite.get('periodo') != 'FT' else ""

            mensagem += f"<b>{idx}.</b> {item['time_casa']} vs {item['time_fora']}\n"
            
            odd_str = f" @{palpite['odd']}" if palpite.get('odd') and palpite.get('odd') > 0 else ""
            mensagem += f"   🎯 <b>{mercado}: {palpite['tipo']}{periodo_str}</b>{odd_str}\n"
            mensagem += f"   🕐 {horario} | 💎 {palpite['confianca']}/10\n\n"

        mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        mensagem += f"💰 <b>ODD TOTAL: @{odd_total:.2f}</b>\n"

        keyboard = [
            [InlineKeyboardButton("🔄 Gerar Nova Múltipla", callback_data=f'multipla_{min_jogos}_{max_jogos}')],
            [InlineKeyboardButton("🔙 Voltar", callback_data='criar_multipla')]
        ]
        await query.edit_message_text(text=mensagem, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data == 'bingo':
        keyboard = [
            [InlineKeyboardButton("Odd 15-25", callback_data='bingo_15_25')],
            [InlineKeyboardButton("Odd 30-40", callback_data='bingo_30_40')],
            [InlineKeyboardButton("Odd 60-80", callback_data='bingo_60_80')],
            [InlineKeyboardButton("Odd 100+", callback_data='bingo_100_150')],
            [InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='voltar_menu')]
        ]
        await query.edit_message_text(
            text="🎯 <b>BINGO - Múltipla de Odd Alta</b>\n\nEscolha o range de odd desejado:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

    elif data.startswith('bingo_'):
        parts = data.split('_')
        odd_min = int(parts[1])
        odd_max = int(parts[2])

        await query.edit_message_text(text=f"🎯 Montando BINGO com odd {odd_min}-{odd_max}...")
        bingo = await gerar_bingo_odd_alta(odd_min, odd_max)

        if not bingo:
            await query.edit_message_text(text="❌ Não encontrei jogos suficientes para criar o bingo.")
            return

        odd_total = 1.0
        for item in bingo:
            odd_total *= item['palpite'].get('odd', 1.0)

        mensagem = f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        mensagem += f"🎯 <b>BINGO ({len(bingo)} JOGOS)</b>\n"
        mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        for idx, item in enumerate(bingo, 1):
            jogo = item['jogo']
            palpite = item['palpite']
            mercado = item.get('mercado', '')

            data_utc = datetime.strptime(jogo['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z')
            data_brasilia = data_utc.astimezone(ZoneInfo("America/Sao_Paulo"))
            horario = data_brasilia.strftime('%H:%M')

            periodo_str = f" ({palpite.get('periodo', 'FT')})" if palpite.get('periodo') != 'FT' else ""

            mensagem += f"<b>{idx}.</b> {item['time_casa']} vs {item['time_fora']}\n"
            
            odd_str = f" @{palpite['odd']}" if palpite.get('odd') and palpite.get('odd') > 0 else ""
            mensagem += f"   🎯 <b>{mercado}: {palpite['tipo']}{periodo_str}</b>{odd_str}\n"
            mensagem += f"   🕐 {horario} | 💎 {palpite['confianca']}/10\n\n"

        mensagem += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        mensagem += f"🚀 <b>ODD TOTAL: @{odd_total:.2f}</b>\n"

        if odd_total < odd_min:
            mensagem += f"\n⚠️ <i>Odd ficou abaixo do target ({odd_min}), mas é a melhor combinação disponível.</i>"

        keyboard = [
            [InlineKeyboardButton("🔄 Gerar Novo Bingo", callback_data=f'bingo_{odd_min}_{odd_max}')],
            [InlineKeyboardButton("🔙 Voltar", callback_data='bingo')]
        ]
        await query.edit_message_text(text=mensagem, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('page_'):
        parts = data.split('_')
        analysis_type = parts[1]
        page = int(parts[2])
        user_id = query.from_user.id
        
        paginated = pagination_helpers.get_paginated_analyses(
            db_manager, user_id, analysis_type, page
        )
        
        if not paginated['analyses']:
            await query.edit_message_text(
                text="Nenhuma análise encontrada. Use o menu principal para iniciar uma análise.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="voltar_menu")
                ]])
            )
            return
        
        from analysts.dossier_formatter import format_phoenix_dossier
        
        for analysis_row in paginated['analyses']:
            dossier = pagination_helpers.parse_dossier_from_analysis(analysis_row)
            formatted_msg = format_phoenix_dossier(dossier)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=formatted_msg,
                parse_mode='HTML'
            )
        
        keyboard = pagination_helpers.create_pagination_keyboard(
            paginated['current_page'],
            paginated['has_more'],
            analysis_type,
            paginated['total_pages']
        )
        
        status_msg = f"📊 Mostrando {len(paginated['analyses'])} de {paginated['total']} análises"
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=status_msg,
            reply_markup=keyboard
        )
    
    elif data == 'noop':
        await query.answer()
    
    elif data == 'voltar_menu':
        keyboard = [
            [InlineKeyboardButton("🎯 Análise Completa", callback_data='analise_completa'), 
             InlineKeyboardButton("🔍 Buscar Jogo", callback_data='buscar_jogo')],
            [InlineKeyboardButton("⚽ Over Gols", callback_data='analise_over_gols'), 
             InlineKeyboardButton("🚩 Escanteios", callback_data='analise_escanteios')],
            [InlineKeyboardButton("🎲 BTTS", callback_data='analise_btts'), 
             InlineKeyboardButton("🏁 Resultado", callback_data='analise_resultado')],
            [InlineKeyboardButton("💰 Aposta Simples", callback_data='aposta_simples'),
             InlineKeyboardButton("🎰 Criar Múltipla", callback_data='criar_multipla'),
             InlineKeyboardButton("🎯 Bingo", callback_data='bingo')],
            [InlineKeyboardButton("📅 Jogos do Dia", callback_data='stats_dia'),
             InlineKeyboardButton("🏆 Por Liga", callback_data='analise_por_liga')],
            [InlineKeyboardButton("⚙️ Configurações", callback_data='configuracoes')]
        ]
        await query.edit_message_text(
            text="🤖 <b>AnalytipsBot</b> - Menu Principal\n\n📈 Escolha uma opção:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

    elif data.startswith('carregar_mais_'):
        parts = data.split('_', 2)
        if len(parts) == 3:
            info = parts[2].split('_', 1)
            if info[0] != 'None':
                context.user_data['filtro_mercado'] = info[0]
            if len(info) > 1 and info[1] != 'None':
                context.user_data['filtro_tipo_linha'] = info[1]

        await analisar_e_enviar_proximo_lote(query, context)
    
    elif data.startswith('buscar_jogo_liga_'):
        liga_id = int(data.replace('buscar_jogo_liga_', ''))
        await query.edit_message_text(text="⏳ Carregando jogos da liga...")
        
        # Buscar todos os jogos do dia e filtrar pela liga
        jogos = await buscar_jogos_do_dia()
        jogos_liga = [j for j in jogos if j['league']['id'] == liga_id]
        
        if not jogos_liga:
            keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data='buscar_jogo')]]
            await query.edit_message_text(
                text="❌ Nenhum jogo encontrado para esta liga.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # Armazenar jogos e mostrar
        context.user_data['jogos_buscar_jogo'] = jogos_liga
        context.user_data['liga_selecionada_id'] = liga_id
        await mostrar_jogos_da_liga_buscar(query, context)
    
    elif data.startswith('analisar_jogo_'):
        jogo_id = int(data.replace('analisar_jogo_', ''))
        
        # Buscar jogo específico
        jogos_salvos = context.user_data.get('jogos_buscar_jogo', [])
        jogo = next((j for j in jogos_salvos if j['fixture']['id'] == jogo_id), None)
        
        if not jogo:
            keyboard = [[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='voltar_menu')]]
            await query.edit_message_text(
                text="❌ Jogo não encontrado.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # Mensagem detalhada de progresso
        time_casa = jogo['teams']['home']['name']
        time_fora = jogo['teams']['away']['name']
        await query.edit_message_text(
            text=f"🔍 <b>Analisando partida selecionada...</b>\n\n"
                 f"⚽ {time_casa} vs {time_fora}\n\n"
                 f"📊 Processando TODOS os mercados:\n"
                 f"   • Gols (FT & HT)\n"
                 f"   • Resultado Final\n"
                 f"   • BTTS\n"
                 f"   • Escanteios\n"
                 f"   • Cartões\n"
                 f"   • Handicaps\n"
                 f"   • Finalizações\n\n"
                 f"⏳ Aguarde...",
            parse_mode='HTML'
        )
        
        # Realizar análise COMPLETA com TODOS os mercados (APENAS deste jogo)
        print(f"--- 🎯 BUSCAR JOGO: Analisando APENAS Fixture #{jogo_id} ---")
        analise_completa = await gerar_analise_completa_todos_mercados(jogo)
        print(f"--- ✅ BUSCAR JOGO: Análise retornada (sucesso: {bool(analise_completa)}) ---")
        
        if analise_completa:
            # Anexar botões diretamente à mensagem de análise
            keyboard = [
                [InlineKeyboardButton("🔍 Analisar Outro Jogo", callback_data='buscar_jogo')],
                [InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='voltar_menu')]
            ]
            await context.bot.send_message(
                query.message.chat_id,
                analise_completa,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        else:
            keyboard = [
                [InlineKeyboardButton("🔍 Tentar Outro Jogo", callback_data='buscar_jogo')],
                [InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='voltar_menu')]
            ]
            await context.bot.send_message(
                query.message.chat_id,
                "❌ Não foi possível gerar análise para este jogo.\n"
                "Pode não haver odds suficientes disponíveis.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        await query.delete_message()

async def mostrar_ligas_buscar_jogo(query, context: ContextTypes.DEFAULT_TYPE):
    """Mostra ligas disponíveis para buscar jogo específico"""
    ligas = context.user_data.get('ligas_buscar_jogo', [])
    pagina_atual = context.user_data.get('pagina_buscar_jogo', 0)
    
    LIGAS_POR_PAGINA = 10
    inicio = pagina_atual * LIGAS_POR_PAGINA
    fim = inicio + LIGAS_POR_PAGINA
    ligas_pagina = ligas[inicio:fim]
    
    keyboard = []
    for liga in ligas_pagina:
        keyboard.append([InlineKeyboardButton(
            liga['nome'], 
            callback_data=f"buscar_jogo_liga_{liga['id']}"
        )])
    
    # Botões de navegação
    nav_buttons = []
    if pagina_atual > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Anterior", callback_data='pag_ant_buscar_jogo'))
    if fim < len(ligas):
        nav_buttons.append(InlineKeyboardButton("Próxima ▶️", callback_data='pag_prox_buscar_jogo'))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='voltar_menu')])
    
    mensagem = (
        f"🔍 <b>Buscar Jogo Específico</b>\n\n"
        f"Selecione a liga:\n\n"
        f"📄 Página {pagina_atual + 1} de {(len(ligas) - 1) // LIGAS_POR_PAGINA + 1}"
    )
    await query.edit_message_text(
        text=mensagem, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='HTML'
    )

async def mostrar_jogos_da_liga_buscar(query, context: ContextTypes.DEFAULT_TYPE):
    """Mostra jogos de uma liga específica para seleção"""
    jogos = context.user_data.get('jogos_buscar_jogo', [])
    liga_id = context.user_data.get('liga_selecionada_id')
    
    if not jogos:
        keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data='buscar_jogo')]]
        await query.edit_message_text(
            text="❌ Nenhum jogo encontrado.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Obter nome da liga
    liga_info = NOMES_LIGAS_PT.get(liga_id, ("Liga", "País"))
    liga_nome = liga_info[0] if isinstance(liga_info, tuple) else liga_info
    
    keyboard = []
    for jogo in jogos[:15]:  # Limitar a 15 jogos
        fixture = jogo['fixture']
        teams = jogo['teams']
        
        # Formatar horário - Converter para Brasília
        data_jogo = datetime.fromisoformat(fixture['date'].replace('Z', '+00:00'))
        data_jogo_brasilia = data_jogo.astimezone(ZoneInfo("America/Sao_Paulo"))
        horario = data_jogo_brasilia.strftime("%H:%M")
        
        jogo_texto = f"{horario} | {teams['home']['name']} vs {teams['away']['name']}"
        keyboard.append([InlineKeyboardButton(
            jogo_texto, 
            callback_data=f"analisar_jogo_{fixture['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data='buscar_jogo')])
    
    mensagem = (
        f"⚽ <b>{liga_nome}</b>\n\n"
        f"Selecione o jogo para análise completa:\n"
        f"(Mostrando até 15 jogos)"
    )
    await query.edit_message_text(
        text=mensagem, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='HTML'
    )

async def mostrar_pagina_ligas(query, context: ContextTypes.DEFAULT_TYPE):
    ligas = context.user_data.get('ligas_disponiveis', [])
    pagina_atual = context.user_data.get('pagina_liga_atual', 0)

    inicio = pagina_atual * LIGAS_POR_PAGINA
    fim = inicio + LIGAS_POR_PAGINA
    ligas_pagina = ligas[inicio:fim]

    keyboard = []
    for liga in ligas_pagina:
        # Nome já inclui a bandeira, não precisa adicionar país
        keyboard.append([InlineKeyboardButton(liga['nome'], callback_data=f"liga_{liga['id']}")])

    nav_buttons = []
    if pagina_atual > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Anterior", callback_data='pagina_anterior_ligas'))
    if fim < len(ligas):
        nav_buttons.append(InlineKeyboardButton("Próxima ▶️", callback_data='proxima_pagina_ligas'))

    if nav_buttons:
        keyboard.append(nav_buttons)

    # Adicionar botão voltar ao menu
    keyboard.append([InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='voltar_menu')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    mensagem = f"<b>🏆 Selecione uma Liga</b>\n\nPágina {pagina_atual + 1} de {(len(ligas) - 1) // LIGAS_POR_PAGINA + 1}"
    await query.edit_message_text(text=mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def startup_validation():
    """
    Valida secrets e conexões externas antes de iniciar o bot.
    Previne que o bot inicie com configurações inválidas.
    
    Verifica:
    - Telegram Bot Token (via get_me)
    - API-Football Key (via chamada de teste)
    - PostgreSQL Connection (via health check)
    
    Raises:
        SystemExit: Se alguma validação falhar
    """
    print("🔍 Validando configurações e secrets...")
    
    from telegram import Bot
    import api_client
    
    validation_failed = False
    
    if not TELEGRAM_TOKEN:
        print("❌ FALHA CRÍTICA: TELEGRAM_BOT_TOKEN não encontrado nas variáveis de ambiente")
        validation_failed = True
    else:
        try:
            bot = Bot(token=TELEGRAM_TOKEN)
            bot_info = await bot.get_me()
            print(f"✅ Telegram Token válido - Bot: @{bot_info.username}")
        except Exception as e:
            print(f"❌ FALHA CRÍTICA: Telegram Token inválido ou erro de conexão: {e}")
            validation_failed = True
    
    api_key = os.getenv("API_FOOTBALL_KEY")
    if not api_key:
        print("❌ FALHA CRÍTICA: API_FOOTBALL_KEY não encontrado nas variáveis de ambiente")
        validation_failed = True
    else:
        try:
            response = await api_client.api_request_with_retry(
                "GET",
                f"{api_client.API_URL}status",
                params={}
            )
            if response.status_code == 200:
                print(f"✅ API-Football Key válida - Conexão estabelecida")
            else:
                print(f"❌ FALHA CRÍTICA: API-Football retornou status {response.status_code}")
                validation_failed = True
        except Exception as e:
            print(f"❌ FALHA CRÍTICA: Erro ao validar API-Football: {e}")
            validation_failed = True
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("⚠️ DATABASE_URL não encontrado - Cache de análises será desabilitado")
    else:
        try:
            with db_manager._get_connection() as conn:
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    print(f"✅ PostgreSQL Connection válida - Database conectado")
                else:
                    print("⚠️ PostgreSQL não disponível - Cache de análises desabilitado")
        except Exception as e:
            print(f"❌ FALHA CRÍTICA: Erro ao validar PostgreSQL: {e}")
            validation_failed = True
    
    if validation_failed:
        print("\n❌❌❌ STARTUP VALIDATION FAILED ❌❌❌")
        print("O bot não pode iniciar com secrets inválidos.")
        print("Por favor, verifique suas variáveis de ambiente e tente novamente.")
        raise SystemExit(1)
    
    print("✅✅✅ Todas as validações passaram! Bot pronto para iniciar.\n")

async def post_init(application: Application) -> None:
    """Função executada após inicialização do bot para iniciar background workers"""
    # Criar e registrar cliente HTTP no contexto do Application
    print("🔌 Criando cliente HTTP assíncrono...")
    import api_client
    http_client = api_client.create_http_client()
    api_client.set_http_client(http_client)
    application.bot_data['http_client'] = http_client
    print("✅ Cliente HTTP criado e registrado!")
    
    print("🚀 Iniciando background analysis worker...")
    asyncio.create_task(job_queue.background_analysis_worker(db_manager))
    print("✅ Background worker iniciado!")
    
    print("🔄 Iniciando cache saver periódico...")
    asyncio.create_task(cache_manager.periodic_cache_saver())
    print("✅ Cache saver iniciado!")

async def post_shutdown(application: Application) -> None:
    """
    Hook oficial do python-telegram-bot executado no shutdown.
    Garante que todos os recursos assíncronos sejam fechados na ordem correta.
    
    ORDEM CRÍTICA:
    1. Salvar cache (dados em memória)
    2. Fechar cliente HTTP assíncrono (httpx.AsyncClient)
    3. Fechar connection pool do banco de dados
    
    Esta função é chamada automaticamente pelo Application quando:
    - application.stop() é chamado
    - Um signal (SIGINT/SIGTERM) é recebido
    - O bot é encerrado normalmente
    """
    print("🛑 POST_SHUTDOWN: Iniciando limpeza de recursos...")
    
    try:
        print("💾 Salvando cache final...")
        await asyncio.to_thread(cache_manager.save_cache_to_disk)
        print("✅ Cache salvo com sucesso!")
    except Exception as e:
        print(f"⚠️ Erro ao salvar cache: {e}")
    
    try:
        print("🔌 Fechando cliente HTTP assíncrono...")
        import api_client
        http_client = application.bot_data.get('http_client')
        if http_client:
            await api_client.close_http_client(http_client)
            print("✅ Cliente HTTP fechado com sucesso!")
        else:
            print("⚠️ Cliente HTTP não encontrado no bot_data")
    except Exception as e:
        print(f"⚠️ Erro ao fechar cliente HTTP: {e}")
    
    try:
        print("🗄️ Fechando connection pool do PostgreSQL...")
        db_manager.close_pool()
        print("✅ Connection pool fechado com sucesso!")
    except Exception as e:
        print(f"⚠️ Erro ao fechar connection pool: {e}")
    
    print("✅ POST_SHUTDOWN: Limpeza de recursos concluída!")

def setup_signal_handlers(application: Application) -> None:
    """
    Configura handlers para sinais do OS (SIGINT/SIGTERM).
    
    CORREÇÃO CRÍTICA:
    - Signal handlers devem ser SÍNCRONOS
    - Não usar asyncio.create_task() dentro de signal handlers
    - Apenas solicitar que o Application pare (stop()) de forma síncrona
    - O próprio Application chamará post_shutdown() automaticamente
    
    Esta abordagem evita o RuntimeError: Event loop is closed
    """
    def signal_handler(signum, frame):
        signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
        print(f"\n🛑 Sinal {signal_name} recebido! Solicitando shutdown gracioso...")
        
        # Solicitar parada do bot de forma síncrona
        # O Application executará post_shutdown() automaticamente
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(application.stop)
        else:
            print("⚠️ Event loop não está rodando, encerrando diretamente...")
            os._exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    print("✅ Signal handlers configurados (SIGINT, SIGTERM)")

def main() -> None:
    asyncio.run(startup_validation())

    cache_manager.load_cache_from_disk()

    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    
    setup_signal_handlers(application)
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("limpar_cache", limpar_cache_command))
    application.add_handler(CommandHandler("getlog", getlog_command))
    application.add_handler(CallbackQueryHandler(button_handler))

    print(f"AnalytipsBot iniciado! Escutando...")
    application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
