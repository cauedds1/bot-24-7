# analysts/corners_analyzer.py
"""
PHOENIX V3.0 - CORNERS ANALYZER (REFATORADO)
============================================
UNIFIED CONFIDENCE SYSTEM: Usa exclusivamente confidence_calculator.py
para todos os cálculos de confiança.

ARQUITETURA:
1. Calcular probabilidade estatística de cada mercado de cantos
2. Chamar calculate_final_confidence para obter confiança final
3. Usar breakdown para evidências e transparência
"""

from config import ODD_MINIMA_DE_VALOR, MIN_CONFIANCA_CANTOS, MIN_CONFIANCA_CANTOS_UNDER
from analysts.context_analyzer import analisar_compatibilidade_ofensiva_defensiva
from analysts.confidence_calculator import (
    calculate_statistical_probability_corners_over,
    calculate_final_confidence
)


def analisar_mercado_cantos(stats_casa, stats_fora, odds, classificacao=None, pos_casa="N/A", pos_fora="N/A", master_data=None, script_name=None):
    """
    Analisa mercado de cantos usando o sistema unificado de confiança.
    
    PHOENIX V3.0 REFACTORING:
    - ✅ USA confidence_calculator.py para TODOS os cálculos
    - ✅ Calcula probabilidade estatística primeiro
    - ✅ Aplica modificadores contextuais via calculate_final_confidence
    - ✅ Retorna breakdown para transparência
    
    Args:
        stats_casa: Estatísticas do time da casa
        stats_fora: Estatísticas do time visitante
        odds: Dicionário de odds disponíveis
        classificacao: Tabela de classificação da liga
        pos_casa: Posição do time da casa
        pos_fora: Posição do time visitante
        master_data: Dados do master_analyzer (tactical script)
        script_name: Nome do script tático
    
    Returns:
        dict: Análise de cantos com palpites ou None
    """
    if not stats_casa or not stats_fora:
        return None

    # ✅ STEP 1: EXTRAIR MÉTRICAS DE CANTOS (weighted ou simples)
    cantos_casa_feitos = 0.0
    cantos_casa_sofridos = 0.0
    cantos_fora_feitos = 0.0
    cantos_fora_sofridos = 0.0

    use_weighted = False
    if master_data and 'analysis_summary' in master_data:
        weighted_home = master_data['analysis_summary'].get('weighted_metrics_home', {})
        weighted_away = master_data['analysis_summary'].get('weighted_metrics_away', {})
        
        if weighted_home and weighted_away:
            use_weighted = True
            cantos_casa_feitos = weighted_home.get('weighted_corners_for', 0.0)
            cantos_casa_sofridos = weighted_home.get('weighted_corners_against', 0.0)
            cantos_fora_feitos = weighted_away.get('weighted_corners_for', 0.0)
            cantos_fora_sofridos = weighted_away.get('weighted_corners_against', 0.0)
            print(f"\n  ⚖️ CANTOS: Usando WEIGHTED METRICS (ponderado por SoS)")
    
    # Fallback para médias simples
    if not use_weighted:
        cantos_casa_feitos = stats_casa.get('casa', {}).get('cantos_feitos', 0.0)
        cantos_casa_sofridos = stats_casa.get('casa', {}).get('cantos_sofridos', 0.0)
        cantos_fora_feitos = stats_fora.get('fora', {}).get('cantos_feitos', 0.0)
        cantos_fora_sofridos = stats_fora.get('fora', {}).get('cantos_sofridos', 0.0)
        print(f"\n  📊 CANTOS: Usando médias simples")
    
    print(f"     Casa: {cantos_casa_feitos:.1f} feitos / {cantos_casa_sofridos:.1f} sofridos")
    print(f"     Fora: {cantos_fora_feitos:.1f} feitos / {cantos_fora_sofridos:.1f} sofridos")

    # 🛡️ SHIELD RULE: Dados insuficientes
    if (cantos_casa_feitos == 0.0 and cantos_casa_sofridos == 0.0 and 
        cantos_fora_feitos == 0.0 and cantos_fora_sofridos == 0.0):
        print(f"  ❌ CANTOS BLOQUEADO: Dados insuficientes (todos 0.0)")
        return None

    # ✅ STEP 2: ANÁLISE CONTEXTUAL (insights que afetam cantos)
    insights = analisar_compatibilidade_ofensiva_defensiva(stats_casa, stats_fora)
    fator_cantos = 1.0
    contexto_insights = []

    for insight in insights:
        if insight['tipo'] == 'cantos_casa_favoravel':
            fator_cantos *= insight['fator_multiplicador']
            contexto_insights.append(insight['descricao'])
        elif insight['tipo'] == 'festival_gols':
            fator_cantos *= 1.2  # Jogos ofensivos geram mais cantos
            contexto_insights.append("⚡ Jogo ofensivo tende a gerar MAIS cantos!")

    # ✅ STEP 3: CALCULAR MÉDIAS ESPERADAS
    media_exp_ft = (cantos_casa_feitos + cantos_fora_sofridos + 
                    cantos_fora_feitos + cantos_casa_sofridos) / 2
    media_exp_ft_ajustada = media_exp_ft * fator_cantos
    media_exp_ht = media_exp_ft_ajustada * 0.48  # HT = ~48% dos cantos
    media_casa = cantos_casa_feitos * (fator_cantos if fator_cantos > 1.0 else 1.0)
    media_fora = cantos_fora_feitos

    print(f"  📊 Médias esperadas: FT={media_exp_ft_ajustada:.1f}, HT={media_exp_ht:.1f}, Casa={media_casa:.1f}, Fora={media_fora:.1f}")

    palpites = []

    # 🔍 DEBUG: Odds disponíveis
    odds_cantos_disponiveis = [k for k in odds.keys() if 'cantos' in k or 'corner' in k.lower()] if odds else []
    print(f"  📊 Odds de cantos disponíveis: {len(odds_cantos_disponiveis)}")
    
    if not odds or len(odds_cantos_disponiveis) == 0:
        print(f"  ⚠️ CANTOS: Sem odds - partindo para análise tática")
        # TODO: Análise tática sem odds
        return None

    # ✅ STEP 4: ANALISAR MERCADOS DINAMICAMENTE
    
    # --- FT (Full Time) OVER ---
    for odd_key, odd_value in odds.items():
        if odd_key.startswith("cantos_ft_over_"):
            try:
                linha = float(odd_key.replace("cantos_ft_over_", ""))
                
                # ✅ REFATORADO: Calcular probabilidade estatística
                prob_pct = calculate_statistical_probability_corners_over(
                    weighted_corners_avg=media_exp_ft_ajustada,
                    line=linha,
                    historical_frequency=None  # Pode adicionar frequência histórica no futuro
                )
                
                # ✅ REFATORADO: Calcular confiança final via confidence_calculator
                bet_type = f"Over {linha} Cantos"
                conf_final, breakdown = calculate_final_confidence(
                    statistical_probability_pct=prob_pct,
                    bet_type=bet_type,
                    tactical_script=script_name,
                    value_score_pct=0.0,  # Value score calculado externamente se necessário
                    odd=odd_value
                )
                
                print(f"     {bet_type}: Prob={prob_pct:.1f}% → Conf={conf_final:.1f} (odd={odd_value:.2f})")
                
                # ✅ Filtros de qualidade
                if odd_value >= ODD_MINIMA_DE_VALOR and conf_final >= MIN_CONFIANCA_CANTOS:
                    palpites.append({
                        "tipo": bet_type,
                        "confianca": conf_final,
                        "odd": odd_value,
                        "periodo": "FT",
                        "time": "Total",
                        "breakdown": breakdown,  # Transparência
                        "probabilidade_estatistica": prob_pct
                    })
                    
            except ValueError:
                continue

    # --- FT (Full Time) UNDER ---
    for odd_key, odd_value in odds.items():
        if odd_key.startswith("cantos_ft_under_"):
            try:
                linha = float(odd_key.replace("cantos_ft_under_", ""))
                
                # BLOQUEIO: Under < 7.5 não faz sentido para FT Total
                if linha < 7.5:
                    continue
                
                # ✅ Probabilidade de UNDER = 100% - Probabilidade de OVER
                prob_over = calculate_statistical_probability_corners_over(
                    weighted_corners_avg=media_exp_ft_ajustada,
                    line=linha,
                    historical_frequency=None
                )
                prob_under = 100.0 - prob_over
                
                # ✅ Confiança final
                bet_type = f"Under {linha} Cantos"
                conf_final, breakdown = calculate_final_confidence(
                    statistical_probability_pct=prob_under,
                    bet_type=bet_type,
                    tactical_script=script_name,
                    value_score_pct=0.0,
                    odd=odd_value
                )
                
                print(f"     {bet_type}: Prob={prob_under:.1f}% → Conf={conf_final:.1f} (odd={odd_value:.2f})")
                
                if odd_value >= ODD_MINIMA_DE_VALOR and conf_final >= MIN_CONFIANCA_CANTOS_UNDER:
                    palpites.append({
                        "tipo": bet_type,
                        "confianca": conf_final,
                        "odd": odd_value,
                        "periodo": "FT",
                        "time": "Total",
                        "breakdown": breakdown,
                        "probabilidade_estatistica": prob_under
                    })
                    
            except ValueError:
                continue

    # --- HT (Half Time) OVER ---
    for odd_key, odd_value in odds.items():
        if odd_key.startswith("cantos_ht_over_"):
            try:
                linha = float(odd_key.replace("cantos_ht_over_", ""))
                
                prob_pct = calculate_statistical_probability_corners_over(
                    weighted_corners_avg=media_exp_ht,
                    line=linha,
                    historical_frequency=None
                )
                
                bet_type = f"Over {linha} Cantos HT"
                conf_final, breakdown = calculate_final_confidence(
                    statistical_probability_pct=prob_pct,
                    bet_type=bet_type,
                    tactical_script=script_name,
                    value_score_pct=0.0,
                    odd=odd_value
                )
                
                if odd_value >= ODD_MINIMA_DE_VALOR and conf_final >= MIN_CONFIANCA_CANTOS:
                    palpites.append({
                        "tipo": f"Over {linha} HT",
                        "confianca": conf_final,
                        "odd": odd_value,
                        "periodo": "HT",
                        "time": "Total",
                        "breakdown": breakdown,
                        "probabilidade_estatistica": prob_pct
                    })
                    
            except ValueError:
                continue

    # --- HT (Half Time) UNDER ---
    for odd_key, odd_value in odds.items():
        if odd_key.startswith("cantos_ht_under_"):
            try:
                linha = float(odd_key.replace("cantos_ht_under_", ""))
                
                prob_over = calculate_statistical_probability_corners_over(
                    weighted_corners_avg=media_exp_ht,
                    line=linha,
                    historical_frequency=None
                )
                prob_under = 100.0 - prob_over
                
                bet_type = f"Under {linha} Cantos HT"
                conf_final, breakdown = calculate_final_confidence(
                    statistical_probability_pct=prob_under,
                    bet_type=bet_type,
                    tactical_script=script_name,
                    value_score_pct=0.0,
                    odd=odd_value
                )
                
                if odd_value >= ODD_MINIMA_DE_VALOR and conf_final >= MIN_CONFIANCA_CANTOS_UNDER:
                    palpites.append({
                        "tipo": f"Under {linha} HT",
                        "confianca": conf_final,
                        "odd": odd_value,
                        "periodo": "HT",
                        "time": "Total",
                        "breakdown": breakdown,
                        "probabilidade_estatistica": prob_under
                    })
                    
            except ValueError:
                continue

    # --- CASA (Home Corners) OVER/UNDER ---
    for odd_key, odd_value in odds.items():
        if odd_key.startswith("cantos_casa_over_"):
            try:
                linha = float(odd_key.replace("cantos_casa_over_", ""))
                
                prob_pct = calculate_statistical_probability_corners_over(
                    weighted_corners_avg=media_casa,
                    line=linha,
                    historical_frequency=None
                )
                
                bet_type = f"Over {linha} Cantos Casa"
                conf_final, breakdown = calculate_final_confidence(
                    statistical_probability_pct=prob_pct,
                    bet_type=bet_type,
                    tactical_script=script_name,
                    value_score_pct=0.0,
                    odd=odd_value
                )
                
                if odd_value >= ODD_MINIMA_DE_VALOR and conf_final >= MIN_CONFIANCA_CANTOS:
                    palpites.append({
                        "tipo": f"Over {linha} Casa",
                        "confianca": conf_final,
                        "odd": odd_value,
                        "periodo": "FT",
                        "time": "Casa",
                        "breakdown": breakdown,
                        "probabilidade_estatistica": prob_pct
                    })
                    
            except ValueError:
                continue
                
        elif odd_key.startswith("cantos_casa_under_"):
            try:
                linha = float(odd_key.replace("cantos_casa_under_", ""))
                
                prob_over = calculate_statistical_probability_corners_over(
                    weighted_corners_avg=media_casa,
                    line=linha,
                    historical_frequency=None
                )
                prob_under = 100.0 - prob_over
                
                bet_type = f"Under {linha} Cantos Casa"
                conf_final, breakdown = calculate_final_confidence(
                    statistical_probability_pct=prob_under,
                    bet_type=bet_type,
                    tactical_script=script_name,
                    value_score_pct=0.0,
                    odd=odd_value
                )
                
                if odd_value >= ODD_MINIMA_DE_VALOR and conf_final >= MIN_CONFIANCA_CANTOS_UNDER:
                    palpites.append({
                        "tipo": f"Under {linha} Casa",
                        "confianca": conf_final,
                        "odd": odd_value,
                        "periodo": "FT",
                        "time": "Casa",
                        "breakdown": breakdown,
                        "probabilidade_estatistica": prob_under
                    })
                    
            except ValueError:
                continue

    # --- FORA (Away Corners) OVER/UNDER ---
    for odd_key, odd_value in odds.items():
        if odd_key.startswith("cantos_fora_over_"):
            try:
                linha = float(odd_key.replace("cantos_fora_over_", ""))
                
                prob_pct = calculate_statistical_probability_corners_over(
                    weighted_corners_avg=media_fora,
                    line=linha,
                    historical_frequency=None
                )
                
                bet_type = f"Over {linha} Cantos Fora"
                conf_final, breakdown = calculate_final_confidence(
                    statistical_probability_pct=prob_pct,
                    bet_type=bet_type,
                    tactical_script=script_name,
                    value_score_pct=0.0,
                    odd=odd_value
                )
                
                if odd_value >= ODD_MINIMA_DE_VALOR and conf_final >= MIN_CONFIANCA_CANTOS:
                    palpites.append({
                        "tipo": f"Over {linha} Fora",
                        "confianca": conf_final,
                        "odd": odd_value,
                        "periodo": "FT",
                        "time": "Fora",
                        "breakdown": breakdown,
                        "probabilidade_estatistica": prob_pct
                    })
                    
            except ValueError:
                continue
                
        elif odd_key.startswith("cantos_fora_under_"):
            try:
                linha = float(odd_key.replace("cantos_fora_under_", ""))
                
                prob_over = calculate_statistical_probability_corners_over(
                    weighted_corners_avg=media_fora,
                    line=linha,
                    historical_frequency=None
                )
                prob_under = 100.0 - prob_over
                
                bet_type = f"Under {linha} Cantos Fora"
                conf_final, breakdown = calculate_final_confidence(
                    statistical_probability_pct=prob_under,
                    bet_type=bet_type,
                    tactical_script=script_name,
                    value_score_pct=0.0,
                    odd=odd_value
                )
                
                if odd_value >= ODD_MINIMA_DE_VALOR and conf_final >= MIN_CONFIANCA_CANTOS_UNDER:
                    palpites.append({
                        "tipo": f"Under {linha} Fora",
                        "confianca": conf_final,
                        "odd": odd_value,
                        "periodo": "FT",
                        "time": "Fora",
                        "breakdown": breakdown,
                        "probabilidade_estatistica": prob_under
                    })
                    
            except ValueError:
                continue

    # ✅ RETORNO FINAL
    print(f"  ✅ CANTOS: {len(palpites)} palpites gerados")
    
    if palpites:
        contexto_str = ""
        if contexto_insights:
            contexto_str = f"   - <b>💡 Contexto:</b> {contexto_insights[0]}\n"

        suporte = (f"   - <b>Expectativa Total:</b> {media_exp_ft:.1f} → {media_exp_ft_ajustada:.1f} (ajustada)\n"
                   f"   - <b>Casa:</b> {cantos_casa_feitos:.1f} cantos/jogo\n"
                   f"   - <b>Fora:</b> {cantos_fora_feitos:.1f} cantos/jogo\n"
                   f"{contexto_str}")
        
        return {"mercado": "Cantos", "palpites": palpites, "dados_suporte": suporte}
    
    # Fallback: Análise tática sem odds (TODO)
    print(f"  ❌ CANTOS: Nenhum palpite passou nos filtros de qualidade")
    return None
