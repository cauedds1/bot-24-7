# analysts/context_analyzer.py

from config import QUALITY_SCORES, LEAGUE_WEIGHTING_FACTOR, MERCADOS_VETADOS_POR_SCRIPT


def calculate_dynamic_qsc(team_stats, team_id, classificacao=None, team_name=None, league_id=None, rodada_atual=0):
    """
    LAYER 1 - PHOENIX V2.0: Calcula Quality Score Composto e Dinâmico (QSC).
    
    O QSC é uma média ponderada de 4 componentes:
    1. Base QS (Reputation) - 25% peso - do dicionário QUALITY_SCORES
    2. Position QS (Table) - 30% peso - posição na tabela
    3. Goal Difference QS - 25% peso - saldo de gols
    4. Recent Form QS - 20% peso - últimos 5 jogos
    
    NOVIDADES PHOENIX V2.0:
    - League Weighting Factor: Multiplica QSC final pelo peso da liga
    - Season Start Adjustment: Primeiras 5 rodadas usam blend 50/50 entre table-based e reputation
    
    Args:
        team_stats: Estatísticas gerais do time
        team_id: ID do time
        classificacao: Tabela de classificação da liga
        team_name: Nome do time (para buscar na classificação)
        league_id: ID da liga (para League Weighting Factor)
        rodada_atual: Rodada atual da liga (para Season Start Adjustment)
    
    Returns:
        int: QSC Dynamic (0-100)
    """
    DEFAULT_BASE_QS = 70
    DEFAULT_LEAGUE_WEIGHT = 0.70
    
    # 1. BASE QS (REPUTATION) - 25% peso
    base_qs = QUALITY_SCORES.get(team_id, DEFAULT_BASE_QS)
    
    # 2. POSITION QS (TABLE) - 30% peso
    position_qs = 50  # Neutro
    if classificacao and team_name:
        for team_info in classificacao:
            if team_info['team']['name'] == team_name:
                rank = team_info['rank']
                total_teams = len(classificacao)
                # 1º lugar = 100, Último = 50
                position_qs = 100 - ((rank - 1) / (total_teams - 1)) * 50 if total_teams > 1 else 75
                break
    
    # 3. GOAL DIFFERENCE QS - 25% peso
    goal_diff_qs = 50  # Neutro
    goals = team_stats.get('goals', {})
    goals_for = goals.get('for', {}).get('total', {}).get('total', 0)
    goals_against = goals.get('against', {}).get('total', {}).get('total', 0)
    goal_diff = goals_for - goals_against
    
    # Saldo >= +20 = 100, Saldo <= -20 = 0
    if goal_diff >= 20:
        goal_diff_qs = 100
    elif goal_diff <= -20:
        goal_diff_qs = 0
    else:
        goal_diff_qs = 50 + (goal_diff / 20) * 50
    
    # 4. RECENT FORM QS - 20% peso
    form_qs = 50  # Neutro
    form_string = team_stats.get('form', '')
    if form_string:
        recent_form = form_string[-5:]  # Últimos 5 jogos
        wins = recent_form.count('W')
        draws = recent_form.count('D')
        losses = recent_form.count('L')
        
        # 5W = 100, 5L = 0
        if wins == 5:
            form_qs = 100
        elif wins == 4:
            form_qs = 85
        elif wins == 3:
            form_qs = 70
        elif wins == 2:
            form_qs = 60
        elif wins == 1:
            form_qs = 52
        elif losses == 5:
            form_qs = 0
        elif losses == 4:
            form_qs = 15
        elif losses == 3:
            form_qs = 30
        else:
            form_qs = 50
    
    # --- SEASON START ADJUSTMENT (PRIMEIRAS 5 RODADAS) ---
    # Nas primeiras 5 rodadas, a tabela não é confiável
    # Usar blend 50/50 entre Position QS e Base QS (reputation)
    if rodada_atual > 0 and rodada_atual <= 5:
        position_qs_original = position_qs
        position_qs = (position_qs * 0.5) + (base_qs * 0.5)
        print(f"    🔄 SEASON START ADJUSTMENT (Rodada {rodada_atual}): Position QS ajustado de {int(position_qs_original)} para {int(position_qs)}")
    
    # MÉDIA PONDERADA
    qsc = (
        base_qs * 0.25 +
        position_qs * 0.30 +
        goal_diff_qs * 0.25 +
        form_qs * 0.20
    )
    
    # --- LEAGUE WEIGHTING FACTOR ---
    # Multiplicar QSC pelo peso da liga
    league_weight = LEAGUE_WEIGHTING_FACTOR.get(league_id, DEFAULT_LEAGUE_WEIGHT) if league_id else DEFAULT_LEAGUE_WEIGHT
    qsc_before_league_weight = qsc
    qsc = qsc * league_weight
    
    qsc_final = int(round(qsc))
    
    print(f"    🧠 QSC DINÂMICO ({team_name}): {qsc_final}/100")
    print(f"       Base QS: {base_qs} | Position QS: {int(position_qs)} | Goal Diff QS: {int(goal_diff_qs)} | Form QS: {int(form_qs)}")
    if league_id:
        print(f"       ⚖️ League Weight: {league_weight:.2f} (QSC antes: {int(qsc_before_league_weight)}, depois: {qsc_final})")
    
    return qsc_final


def get_quality_scores(home_team_id: int, away_team_id: int):
    """
    Retorna os quality scores ESTÁTICOS (qualidade técnica) dos times.
    NOTA: Esta função está deprecada. Use calculate_dynamic_qsc() para QSC dinâmico.
    
    Args:
        home_team_id: ID do time da casa
        away_team_id: ID do time visitante
    
    Returns:
        tuple: (home_quality, away_quality) - Scores de 1 a 100
               Times não encontrados recebem score padrão de 70
    """
    DEFAULT_QUALITY = 70
    
    home_quality = QUALITY_SCORES.get(home_team_id, DEFAULT_QUALITY)
    away_quality = QUALITY_SCORES.get(away_team_id, DEFAULT_QUALITY)
    
    return home_quality, away_quality


def analisar_compatibilidade_ofensiva_defensiva(stats_casa, stats_fora):
    """
    Analisa se o ataque de um time se encaixa bem contra a defesa do outro.
    Retorna insights sobre a dinâmica do confronto.
    """
    insights = []

    # Gols: Casa ataca muito E Fora defende mal?
    if stats_casa['casa']['gols_marcados'] >= 1.8 and stats_fora['fora']['gols_sofridos'] >= 1.5:
        insights.append({
            'tipo': 'gols_casa_favoravel',
            'descricao': f"⚔️ ATAQUE CASA vs DEFESA FRÁGIL FORA! Casa marca {stats_casa['casa']['gols_marcados']:.1f} gols/jogo enquanto Fora sofre {stats_fora['fora']['gols_sofridos']:.1f}. Cenário IDEAL para gols da casa!",
            'fator_multiplicador': 1.3
        })

    # Gols: Fora ataca muito E Casa defende mal?
    if stats_fora['fora']['gols_marcados'] >= 1.3 and stats_casa['casa']['gols_sofridos'] >= 1.3:
        insights.append({
            'tipo': 'gols_fora_favoravel',
            'descricao': f"💥 VISITANTE OFENSIVO vs CASA VULNERÁVEL! Fora marca {stats_fora['fora']['gols_marcados']:.1f} quando visita e Casa sofre {stats_casa['casa']['gols_sofridos']:.1f} em casa. Gols do visitante PROVÁVEIS!",
            'fator_multiplicador': 1.25
        })

    # Ambos ataques fortes E ambas defesas fracas = Festival de gols
    if (stats_casa['casa']['gols_marcados'] >= 1.5 and stats_fora['fora']['gols_marcados'] >= 1.2 and
        stats_casa['casa']['gols_sofridos'] >= 1.2 and stats_fora['fora']['gols_sofridos'] >= 1.2):
        insights.append({
            'tipo': 'festival_gols',
            'descricao': f"🎆 EXPLOSÃO DE GOLS ESPERADA! Ambos atacam bem (Casa {stats_casa['casa']['gols_marcados']:.1f}, Fora {stats_fora['fora']['gols_marcados']:.1f}) E ambos defendem mal. Prepare a pipoca!",
            'fator_multiplicador': 1.4
        })

    # Ambas defesas SÓLIDAS = Jogo truncado
    if stats_casa['casa']['gols_sofridos'] <= 0.8 and stats_fora['fora']['gols_sofridos'] <= 0.8:
        insights.append({
            'tipo': 'jogo_truncado',
            'descricao': f"🛡️ BATALHA DE MURALHAS! Casa sofre apenas {stats_casa['casa']['gols_sofridos']:.1f} gols/jogo e Fora {stats_fora['fora']['gols_sofridos']:.1f}. Jogo TRAVADO esperado!",
            'fator_multiplicador': 0.7
        })

    # Cantos: Casa força muito E Fora sofre muitos cantos
    cantos_casa = stats_casa['casa'].get('cantos_feitos', 0)
    cantos_fora_sofre = stats_fora['fora'].get('cantos_sofridos', 0)

    if cantos_casa >= 5.5 and cantos_fora_sofre >= 5.0:
        insights.append({
            'tipo': 'cantos_casa_favoravel',
            'descricao': f"🚩 PRESSÃO OFENSIVA DA CASA! Time da casa força {cantos_casa:.1f} cantos/jogo e visitante costuma ceder {cantos_fora_sofre:.1f}. MUITOS escanteios para a casa!",
            'fator_multiplicador': 1.25
        })

    return insights


def analisar_importancia_jogo(classificacao, pos_casa, pos_fora, rodada_atual, total_rodadas=38):
    """
    Avalia a importância e motivação do jogo baseado em contexto da temporada.
    """
    if not classificacao or pos_casa == "N/A" or pos_fora == "N/A":
        return None

    total_times = len(classificacao)
    progresso_temporada = rodada_atual / total_rodadas

    # Reta final da temporada (últimas 25% das rodadas)
    reta_final = progresso_temporada >= 0.75

    contextos = []

    # Derby/Clássico (times próximos na tabela e posições altas)
    if abs(pos_casa - pos_fora) <= 3 and pos_casa <= 6 and pos_fora <= 6:
        contextos.append({
            'tipo': 'confronto_direto_topo',
            'descricao': f"⭐ CONFRONTO DIRETO NO TOPO! {pos_casa}º vs {pos_fora}º - Pontos diretos na briga por classificação!",
            'intensidade': 'ALTA',
            'efeito': 'Jogo mais ABERTO e AGRESSIVO. Ambos vão buscar a vitória.'
        })

    # Luta contra rebaixamento
    zona_rebaixamento = total_times - 3
    if pos_casa >= zona_rebaixamento or pos_fora >= zona_rebaixamento:
        if reta_final:
            contextos.append({
                'tipo': 'batalha_sobrevivencia',
                'descricao': f"🆘 JOGO DE SEIS PONTOS! Reta final e pelo menos um time na zona de rebaixamento. DECISIVO!",
                'intensidade': 'EXTREMA',
                'efeito': 'Jogo TRUNCADO e NERVOSO. Equipes podem se FECHAR mais.'
            })
        else:
            contextos.append({
                'tipo': 'preocupacao_rebaixamento',
                'descricao': f"⚠️ Time(s) em posição delicada na tabela. Necessidade de pontuar URGENTE!",
                'intensidade': 'MÉDIA-ALTA',
                'efeito': 'Time mandante pode pressionar mais, visitante pode se FECHAR.'
            })

    # Time pequeno vs gigante (diferença > 10 posições)
    if abs(pos_casa - pos_fora) >= 10:
        if pos_casa < pos_fora:
            contextos.append({
                'tipo': 'favorito_claro_casa',
                'descricao': f"🏠 FAVORITO ABSOLUTO em casa! Diferença de {abs(pos_casa - pos_fora)} posições na tabela.",
                'intensidade': 'MÉDIA',
                'efeito': 'Casa deve DOMINAR. Visitante pode se FECHAR e jogar no contra-ataque.'
            })
        else:
            contextos.append({
                'tipo': 'zebra_possivel',
                'descricao': f"🎲 Time menor recebe gigante! Casa jogando em seus domínios pode SURPREENDER.",
                'intensidade': 'MÉDIA',
                'efeito': 'Casa MOTIVADA pelo desafio. Jogo pode ser mais EQUILIBRADO do que parece.'
            })

    # Meio de tabela tranquilo (nenhum objetivo claro)
    if (8 <= pos_casa <= total_times - 5 and 8 <= pos_fora <= total_times - 5 and 
        not reta_final):
        contextos.append({
            'tipo': 'jogo_morno',
            'descricao': f"😴 Times no meio da tabela sem objetivos claros. Jogo pode ser BUROCRÁTICO.",
            'intensidade': 'BAIXA',
            'efeito': 'Ritmo MODERADO. Menos intensidade que jogos decisivos.'
        })

    return contextos if contextos else None


def analisar_estilo_jogo(stats_casa, stats_fora):
    """
    Identifica estilos de jogo e dinâmicas de confronto.
    """
    estilos = []

    # Time que começa devagar (poucos gols no 1º tempo)
    # Estimativa: se marca poucos gols no geral, provavelmente começa devagar
    if stats_casa['casa']['gols_marcados'] <= 1.0:
        estilos.append({
            'time': 'casa',
            'estilo': 'COMEÇA DEVAGAR',
            'descricao': f"🐌 Casa é time que ESQUENTA aos poucos (apenas {stats_casa['casa']['gols_marcados']:.1f} gols/jogo). Primeiro tempo pode ser MORNO."
        })

    if stats_fora['fora']['gols_marcados'] <= 0.8:
        estilos.append({
            'time': 'fora',
            'estilo': 'POUCO OFENSIVO FORA',
            'descricao': f"🔒 Visitante muito CAUTELOSO quando joga fora ({stats_fora['fora']['gols_marcados']:.1f} gols/jogo). Tende a se FECHAR."
        })

    # Time agressivo (muitos gols e cantos)
    cantos_casa = stats_casa['casa'].get('cantos_feitos', 0)
    if stats_casa['casa']['gols_marcados'] >= 2.0 and cantos_casa >= 6.0:
        estilos.append({
            'time': 'casa',
            'estilo': 'ULTRA OFENSIVO',
            'descricao': f"⚡ Casa é MÁQUINA OFENSIVA! {stats_casa['casa']['gols_marcados']:.1f} gols e {cantos_casa:.1f} cantos por jogo. Pressão CONSTANTE!"
        })

    # Time equilibrado (defende e ataca bem)
    if (1.3 <= stats_casa['casa']['gols_marcados'] <= 1.8 and 
        stats_casa['casa']['gols_sofridos'] <= 1.0):
        estilos.append({
            'time': 'casa',
            'estilo': 'EQUILIBRADO',
            'descricao': f"⚖️ Casa é time SÓLIDO e EQUILIBRADO. Marca {stats_casa['casa']['gols_marcados']:.1f} e sofre apenas {stats_casa['casa']['gols_sofridos']:.1f}."
        })

    return estilos if estilos else None


def gerar_analise_contextual_completa(stats_casa, stats_fora, classificacao, pos_casa, pos_fora, rodada_atual):
    """
    Combina todas as análises contextuais em um relatório completo.
    """
    relatorio = {
        'compatibilidade': analisar_compatibilidade_ofensiva_defensiva(stats_casa, stats_fora),
        'importancia': analisar_importancia_jogo(classificacao, pos_casa, pos_fora, rodada_atual),
        'estilos': analisar_estilo_jogo(stats_casa, stats_fora)
    }

    return relatorio


def definir_perfil_partida(stats_casa, stats_fora):
    """
    Define o PERFIL da partida analisando o CONTEXTO, não apenas números.
    Retorna o perfil e quais mercados fazem SENTIDO para este jogo.

    Perfis possíveis:
    - OFENSIVO: Jogo aberto, muitos gols esperados
    - DEFENSIVO: Jogo truncado, poucas chances
    - EQUILIBRADO: Jogo disputado, resultado incerto
    - PRESSÃO_CASA: Casa domina, visitante se fecha
    - VISITANTE_PERIGOSO: Visitante forte, casa vulnerável
    """
    gols_casa_marcados = stats_casa['casa']['gols_marcados']
    gols_casa_sofridos = stats_casa['casa']['gols_sofridos']
    gols_fora_marcados = stats_fora['fora']['gols_marcados']
    gols_fora_sofridos = stats_fora['fora']['gols_sofridos']

    cantos_casa = stats_casa['casa'].get('cantos_feitos', 0)
    cantos_fora = stats_fora['fora'].get('cantos_feitos', 0)

    cartoes_casa = stats_casa['casa'].get('cartoes_amarelos', 0) + stats_casa['casa'].get('cartoes_vermelhos', 0)
    cartoes_fora = stats_fora['fora'].get('cartoes_amarelos', 0) + stats_fora['fora'].get('cartoes_vermelhos', 0)

    # Análise do perfil
    perfil = {
        'tipo': None,
        'descricao': '',
        'mercados_prioritarios': [],
        'mercados_secundarios': [],
        'mercados_evitar': []
    }

    # PERFIL 1: FESTIVAL DE GOLS (ambos atacam bem E defendem mal)
    if (gols_casa_marcados >= 1.6 and gols_fora_marcados >= 1.2 and 
        gols_casa_sofridos >= 1.2 and gols_fora_sofridos >= 1.2):
        perfil['tipo'] = 'FESTIVAL_GOLS'
        perfil['descricao'] = '🎆 JOGO OFENSIVO - Ambos atacam e defendem mal. Muitos gols esperados!'
        perfil['mercados_prioritarios'] = ['gols', 'btts']
        perfil['mercados_secundarios'] = ['cantos', 'finalizações', 'cartões']
        perfil['mercados_evitar'] = []

    # PERFIL 2: JOGO TRAVADO (ambas defesas sólidas)
    elif gols_casa_sofridos <= 0.9 and gols_fora_sofridos <= 0.9:
        perfil['tipo'] = 'JOGO_TRAVADO'
        perfil['descricao'] = '🛡️ JOGO DEFENSIVO - Defesas sólidas. Poucos gols esperados.'
        perfil['mercados_prioritarios'] = ['gols']  # Apenas under gols
        perfil['mercados_secundarios'] = ['resultado', 'cantos', 'finalizações', 'cartões']
        perfil['mercados_evitar'] = ['btts']  # Evita apenas BTTS (ambos marcarem é improvável)

    # PERFIL 3: CASA DOMINANTE (casa forte, fora fraco)
    elif gols_casa_marcados >= 1.8 and gols_fora_marcados <= 1.0 and cantos_casa >= 5.5:
        perfil['tipo'] = 'PRESSAO_CASA'
        perfil['descricao'] = '⚔️ PRESSÃO DA CASA - Casa domina e pressiona. Visitante se fecha.'
        perfil['mercados_prioritarios'] = ['gols', 'cantos', 'resultado']
        perfil['mercados_secundarios'] = ['finalizações', 'cartões']
        perfil['mercados_evitar'] = ['btts']  # Visitante dificilmente marca

    # PERFIL 4: VISITANTE PERIGOSO (fora forte, casa vulnerável)
    elif gols_fora_marcados >= 1.3 and gols_casa_sofridos >= 1.4:
        perfil['tipo'] = 'VISITANTE_PERIGOSO'
        perfil['descricao'] = '💥 VISITANTE OFENSIVO - Fora marca bem, casa sofre. Gols de ambos prováveis.'
        perfil['mercados_prioritarios'] = ['gols', 'btts']
        perfil['mercados_secundarios'] = ['resultado', 'finalizações', 'cartões']
        perfil['mercados_evitar'] = []

    # PERFIL 5: JOGO EQUILIBRADO (forças similares)
    elif abs(gols_casa_marcados - gols_fora_marcados) <= 0.4:
        perfil['tipo'] = 'EQUILIBRADO'
        perfil['descricao'] = '⚖️ JOGO EQUILIBRADO - Forças similares. Resultado imprevisível.'
        perfil['mercados_prioritarios'] = ['gols', 'resultado']
        perfil['mercados_secundarios'] = ['btts', 'finalizações', 'cartões']
        perfil['mercados_evitar'] = []

    # PERFIL 6: JOGO COM MUITOS CARTÕES (times violentos)
    elif cartoes_casa >= 3.0 and cartoes_fora >= 2.5:
        perfil['tipo'] = 'JOGO_QUENTE'
        perfil['descricao'] = '🔥 JOGO QUENTE - Muita intensidade física. Cartões esperados.'
        perfil['mercados_prioritarios'] = ['cartoes']
        perfil['mercados_secundarios'] = ['gols', 'resultado', 'finalizações']
        perfil['mercados_evitar'] = []

    # PERFIL PADRÃO (se não se encaixa em nenhum)
    else:
        perfil['tipo'] = 'PADRAO'
        perfil['descricao'] = '⚽ JOGO PADRÃO - Análise numérica sem padrão claro.'
        perfil['mercados_prioritarios'] = ['gols']
        perfil['mercados_secundarios'] = ['resultado', 'btts', 'finalizações', 'cartões']
        perfil['mercados_evitar'] = []

    return perfil


def filtrar_mercados_por_contexto(analises_brutas, stats_casa, stats_fora, time_casa_id=None, time_fora_id=None):
    """
    Filtra os mercados sugeridos baseado no CONTEXTO da partida.
    NÃO força múltiplos mercados só porque os números batem.

    Args:
        analises_brutas: Lista de análises geradas por todos os analyzers
        stats_casa, stats_fora: Estatísticas dos times
        time_casa_id, time_fora_id: IDs dos times (opcional)

    Returns:
        Lista filtrada de análises que fazem SENTIDO contextual
    """
    # 🧠 QUALITY SCORES: Avaliar qualidade técnica dos times
    game_script = "EQUILIBRADO"  # Default script
    if time_casa_id and time_fora_id:
        home_quality, away_quality = get_quality_scores(time_casa_id, time_fora_id)
        print(f"🧠 CONTEXT_ANALYZER - Quality Score - Home: {home_quality} | Away: {away_quality}")
        
        # --- NEW: Game Script Logic ---
        quality_difference = abs(home_quality - away_quality)
        
        if quality_difference > 20:  # Threshold for significant difference
            if home_quality > away_quality:
                game_script = "DOMINIO_CASA"
            else:
                game_script = "DOMINIO_VISITANTE"
        elif quality_difference > 10:  # Threshold for moderate difference
            if home_quality > away_quality:
                game_script = "FAVORITISMO_CASA"
            else:
                game_script = "FAVORITISMO_VISITANTE"
        
        print(f"📜 ROTEIRO DE JOGO - Quality Score: {game_script} (Diff: {quality_difference})")
        # -----------------------------
    
    perfil = definir_perfil_partida(stats_casa, stats_fora)

    analises_filtradas = []

    for analise in analises_brutas:
        if not analise:
            continue

        mercado = analise['mercado'].lower()

        # Verificar se o mercado está na lista de evitar
        if any(m in mercado for m in perfil['mercados_evitar']):
            print(f"  ⚠️ CONTEXTO: Mercado '{analise['mercado']}' NÃO FAZ SENTIDO para perfil {perfil['tipo']}. DESCARTADO!")
            continue

        # Priorizar mercados principais e secundários
        if any(m in mercado for m in perfil['mercados_prioritarios']):
            analises_filtradas.append(analise)
            print(f"  ✅ CONTEXTO: Mercado '{analise['mercado']}' FAZ SENTIDO para perfil {perfil['tipo']} (PRIORITÁRIO)")
        elif any(m in mercado for m in perfil['mercados_secundarios']):
            analises_filtradas.append(analise)
            print(f"  ✅ CONTEXTO: Mercado '{analise['mercado']}' FAZ SENTIDO para perfil {perfil['tipo']} (SECUNDÁRIO)")
        elif not perfil['mercados_prioritarios'] and not perfil['mercados_secundarios']:
            # Se não há filtros específicos, aceita tudo
            analises_filtradas.append(analise)

    # LOG do perfil identificado
    print(f"\n📊 PERFIL DA PARTIDA: {perfil['tipo']}")
    print(f"   {perfil['descricao']}")
    print(f"   Mercados prioritários: {perfil['mercados_prioritarios']}")
    print(f"   Mercados secundários: {perfil['mercados_secundarios']}")
    print(f"   Mercados a evitar: {perfil['mercados_evitar']}")
    print(f"   Análises aceitas: {len(analises_filtradas)}/{len([a for a in analises_brutas if a])}\n")

    return analises_filtradas, perfil, game_script


# DEPRECATED: Funções obsoletas removidas - agora usa confidence_calculator.py
# verificar_veto_mercado() -> Veto logic integrado em calculate_final_confidence()
# ajustar_confianca_por_script() -> Script modifiers integrados em apply_tactical_script_modifier()
# definir_perfil_partida() -> Ainda em uso mas pode ser simplificado
# filtrar_mercados_por_contexto() -> Ainda em uso mas pode ser simplificado
