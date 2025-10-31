# analysts/shots_analyzer.py
"""
PHOENIX V3.0 - SHOTS ANALYZER (REFATORADO)
==========================================
UNIFIED CONFIDENCE SYSTEM: Usa exclusivamente confidence_calculator.py
para todos os cálculos de confiança.

ARQUITETURA:
1. Calcular probabilidade estatística de cada mercado de finalizações
2. Chamar calculate_final_confidence para obter confiança final
3. Usar breakdown para evidências e transparência
"""

from analysts.confidence_calculator import (
    calculate_statistical_probability_shots_over,
    calculate_final_confidence
)


def analisar_mercado_finalizacoes(stats_casa, stats_fora, odds=None, master_data=None, script_name=None):
    """
    Analisa mercado de finalizações usando o sistema unificado de confiança.
    
    PHOENIX V3.0 REFACTORING:
    - ✅ USA confidence_calculator.py para TODOS os cálculos
    - ✅ Calcula probabilidade estatística primeiro
    - ✅ Aplica modificadores contextuais via calculate_final_confidence
    - ✅ Retorna breakdown para transparência
    
    Args:
        stats_casa: Estatísticas do time da casa
        stats_fora: Estatísticas do time visitante
        odds: Dicionário de odds disponíveis (raramente disponível para shots)
        master_data: Dados do master_analyzer (tactical script)
        script_name: Nome do script tático
    
    Returns:
        dict: Análise de finalizações com palpites ou None
    """
    print(f"  🔍 FINALIZAÇÕES: Verificando dados disponíveis...")
    
    if not stats_casa or not stats_fora:
        print(f"  ⚠️ FINALIZAÇÕES: Faltam estatísticas")
        return None

    # ✅ STEP 1: EXTRAIR MÉTRICAS DE FINALIZAÇÕES
    finalizacoes_casa = stats_casa['casa'].get('finalizacoes', 0)
    finalizacoes_fora = stats_fora['fora'].get('finalizacoes', 0)
    finalizacoes_gol_casa = stats_casa['casa'].get('finalizacoes_no_gol', 0)
    finalizacoes_gol_fora = stats_fora['fora'].get('finalizacoes_no_gol', 0)

    print(f"\n  📊 FINALIZAÇÕES - Dados:")
    print(f"     Casa: {finalizacoes_casa:.1f} total ({finalizacoes_gol_casa:.1f} no gol)")
    print(f"     Fora: {finalizacoes_fora:.1f} total ({finalizacoes_gol_fora:.1f} no gol)")

    # 🛡️ SHIELD RULE: Dados insuficientes
    if (finalizacoes_casa == 0 and finalizacoes_fora == 0 and 
        finalizacoes_gol_casa == 0 and finalizacoes_gol_fora == 0):
        print("  ❌ FINALIZAÇÕES BLOQUEADO: Dados insuficientes (todos 0.0)")
        return None

    # ✅ STEP 2: CALCULAR MÉDIAS ESPERADAS
    media_exp_total = finalizacoes_casa + finalizacoes_fora
    media_exp_no_gol = finalizacoes_gol_casa + finalizacoes_gol_fora

    print(f"  📊 Médias esperadas: Total={media_exp_total:.1f}, No gol={media_exp_no_gol:.1f}")

    palpites = []

    # ✅ STEP 3: ANALISAR MERCADOS
    # Nota: Odds raramente disponíveis para finalizações, então odds geralmente será None
    
    # --- TOTAL DE FINALIZAÇÕES OVER ---
    linhas_over_total = [21.5, 18.5, 15.5]
    for linha in linhas_over_total:
        # ✅ REFATORADO: Calcular probabilidade estatística
        prob_pct = calculate_statistical_probability_shots_over(
            weighted_shots_avg=media_exp_total,
            line=linha
        )
        
        # ✅ REFATORADO: Calcular confiança final
        bet_type = f"Over {linha} Finalizações"
        conf_final, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob_pct,
            bet_type=bet_type,
            tactical_script=script_name,
            value_score_pct=0.0,
            odd=odds.get(f"shots_over_{linha}", 2.0) if odds else 2.0  # Default odd se não disponível
        )
        
        print(f"     {bet_type}: Prob={prob_pct:.1f}% → Conf={conf_final:.1f}")
        
        # Threshold mais alto para shots (menos confiável que outros mercados)
        if conf_final >= 5.5:
            palpites.append({
                "tipo": f"{bet_type} (Total)",
                "confianca": conf_final,
                "odd": None,  # Raramente disponível
                "time": "Total",
                "breakdown": breakdown,
                "probabilidade_estatistica": prob_pct
            })

    # --- TOTAL DE FINALIZAÇÕES UNDER ---
    linhas_under_total = [18.5, 15.5]
    for linha in linhas_under_total:
        prob_over = calculate_statistical_probability_shots_over(
            weighted_shots_avg=media_exp_total,
            line=linha
        )
        prob_under = 100.0 - prob_over
        
        bet_type = f"Under {linha} Finalizações"
        conf_final, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob_under,
            bet_type=bet_type,
            tactical_script=script_name,
            value_score_pct=0.0,
            odd=odds.get(f"shots_under_{linha}", 2.0) if odds else 2.0
        )
        
        if conf_final >= 5.5:
            palpites.append({
                "tipo": f"{bet_type} (Total)",
                "confianca": conf_final,
                "odd": None,
                "time": "Total",
                "breakdown": breakdown,
                "probabilidade_estatistica": prob_under
            })

    # --- FINALIZAÇÕES NO GOL (Shots on Target) OVER/UNDER ---
    if media_exp_no_gol > 0:
        # Over 9.5
        prob_pct = calculate_statistical_probability_shots_over(
            weighted_shots_avg=media_exp_no_gol,
            line=9.5
        )
        
        if prob_pct >= 45:  # Mínimo de probabilidade
            bet_type = "Over 9.5 Finalizações no Gol"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name,
                value_score_pct=0.0,
                odd=2.0
            )
            
            if conf_final >= 5.5:
                palpites.append({
                    "tipo": f"{bet_type} (Total)",
                    "confianca": conf_final,
                    "odd": None,
                    "time": "Total",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })
        
        # Under 7.5
        prob_over = calculate_statistical_probability_shots_over(
            weighted_shots_avg=media_exp_no_gol,
            line=7.5
        )
        prob_under = 100.0 - prob_over
        
        if prob_under >= 45:
            bet_type = "Under 7.5 Finalizações no Gol"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name,
                value_score_pct=0.0,
                odd=2.0
            )
            
            if conf_final >= 5.5:
                palpites.append({
                    "tipo": f"{bet_type} (Total)",
                    "confianca": conf_final,
                    "odd": None,
                    "time": "Total",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })

    # --- FINALIZAÇÕES POR TIME ---
    # Casa Over/Under
    if finalizacoes_casa > 0:
        # Over 11.5 Casa
        prob_pct = calculate_statistical_probability_shots_over(
            weighted_shots_avg=finalizacoes_casa,
            line=11.5
        )
        
        if prob_pct >= 45:
            bet_type = "Over 11.5 Finalizações Casa"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name,
                value_score_pct=0.0,
                odd=2.0
            )
            
            if conf_final >= 5.5:
                palpites.append({
                    "tipo": "Over 11.5 Finalizações (Casa)",
                    "confianca": conf_final,
                    "odd": None,
                    "time": "Casa",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })
        
        # Under 8.5 Casa
        prob_over = calculate_statistical_probability_shots_over(
            weighted_shots_avg=finalizacoes_casa,
            line=8.5
        )
        prob_under = 100.0 - prob_over
        
        if prob_under >= 45:
            bet_type = "Under 8.5 Finalizações Casa"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name,
                value_score_pct=0.0,
                odd=2.0
            )
            
            if conf_final >= 5.5:
                palpites.append({
                    "tipo": "Under 8.5 Finalizações (Casa)",
                    "confianca": conf_final,
                    "odd": None,
                    "time": "Casa",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })

    # Fora Over/Under
    if finalizacoes_fora > 0:
        # Over 11.5 Fora
        prob_pct = calculate_statistical_probability_shots_over(
            weighted_shots_avg=finalizacoes_fora,
            line=11.5
        )
        
        if prob_pct >= 45:
            bet_type = "Over 11.5 Finalizações Fora"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name,
                value_score_pct=0.0,
                odd=2.0
            )
            
            if conf_final >= 5.5:
                palpites.append({
                    "tipo": "Over 11.5 Finalizações (Fora)",
                    "confianca": conf_final,
                    "odd": None,
                    "time": "Fora",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })
        
        # Under 8.5 Fora
        prob_over = calculate_statistical_probability_shots_over(
            weighted_shots_avg=finalizacoes_fora,
            line=8.5
        )
        prob_under = 100.0 - prob_over
        
        if prob_under >= 45:
            bet_type = "Under 8.5 Finalizações Fora"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name,
                value_score_pct=0.0,
                odd=2.0
            )
            
            if conf_final >= 5.5:
                palpites.append({
                    "tipo": "Under 8.5 Finalizações (Fora)",
                    "confianca": conf_final,
                    "odd": None,
                    "time": "Fora",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })

    # ✅ RETORNO FINAL
    print(f"  ✅ FINALIZAÇÕES: {len(palpites)} palpites gerados")
    
    if palpites:
        suporte = (f"   - <b>Expectativa Finalizações:</b> {media_exp_total:.1f} total ({media_exp_no_gol:.1f} no gol)\n"
                   f"   - <b>Casa:</b> {finalizacoes_casa:.1f} finalizações/jogo ({finalizacoes_gol_casa:.1f} no gol)\n"
                   f"   - <b>Fora:</b> {finalizacoes_fora:.1f} finalizações/jogo ({finalizacoes_gol_fora:.1f} no gol)\n"
                   f"   - <i>⚠️ Odds raramente disponíveis - análise baseada em probabilidades estatísticas</i>\n")
        
        return {"mercado": "Finalizações", "palpites": palpites, "dados_suporte": suporte}

    print(f"  ❌ FINALIZAÇÕES: Nenhum palpite passou nos filtros de qualidade")
    return None
