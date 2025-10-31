# analysts/cards_analyzer.py
"""
PHOENIX V3.0 - CARDS ANALYZER (REFATORADO)
==========================================
UNIFIED CONFIDENCE SYSTEM: Usa exclusivamente confidence_calculator.py
para todos os cálculos de confiança.

ARQUITETURA:
1. Calcular probabilidade estatística de cada mercado de cartões
2. Chamar calculate_final_confidence para obter confiança final
3. Usar breakdown para evidências e transparência
"""

from config import ODD_MINIMA_DE_VALOR, MIN_CONFIANCA_CARTOES
from analysts.confidence_calculator import (
    calculate_statistical_probability_cards_over,
    calculate_final_confidence
)


def analisar_mercado_cartoes(stats_casa, stats_fora, odds, master_data=None, script_name=None):
    """
    Analisa mercado de cartões usando o sistema unificado de confiança.
    
    PHOENIX V3.0 REFACTORING:
    - ✅ USA confidence_calculator.py para TODOS os cálculos
    - ✅ Calcula probabilidade estatística primeiro
    - ✅ Aplica modificadores contextuais via calculate_final_confidence
    - ✅ Retorna breakdown para transparência
    
    Args:
        stats_casa: Estatísticas do time da casa
        stats_fora: Estatísticas do time visitante
        odds: Dicionário de odds disponíveis
        master_data: Dados do master_analyzer (tactical script)
        script_name: Nome do script tático
    
    Returns:
        dict: Análise de cartões com palpites ou None
    """
    print(f"  🔍 CARTÕES: Verificando dados disponíveis...")
    
    if not stats_casa or not stats_fora:
        print(f"  ⚠️ CARTÕES: Faltam estatísticas")
        return None

    # ✅ STEP 1: EXTRAIR MÉTRICAS DE CARTÕES
    cartoes_amarelos_casa = stats_casa.get('casa', {}).get('cartoes_amarelos', 0.0)
    cartoes_vermelhos_casa = stats_casa.get('casa', {}).get('cartoes_vermelhos', 0.0)
    cartoes_amarelos_fora = stats_fora.get('fora', {}).get('cartoes_amarelos', 0.0)
    cartoes_vermelhos_fora = stats_fora.get('fora', {}).get('cartoes_vermelhos', 0.0)

    cartoes_casa = cartoes_amarelos_casa + cartoes_vermelhos_casa
    cartoes_fora = cartoes_amarelos_fora + cartoes_vermelhos_fora

    # 🛡️ SHIELD RULE: Dados insuficientes
    if (cartoes_amarelos_casa == 0.0 and cartoes_vermelhos_casa == 0.0 and 
        cartoes_amarelos_fora == 0.0 and cartoes_vermelhos_fora == 0.0):
        print("  ❌ CARTÕES BLOQUEADO: Dados insuficientes (todos 0.0)")
        return None

    print(f"\n  📊 CARTÕES - Dados:")
    print(f"     Casa: {cartoes_casa:.1f} total ({cartoes_amarelos_casa:.1f}A + {cartoes_vermelhos_casa:.1f}V)")
    print(f"     Fora: {cartoes_fora:.1f} total ({cartoes_amarelos_fora:.1f}A + {cartoes_vermelhos_fora:.1f}V)")

    # ✅ STEP 2: CALCULAR MÉDIAS ESPERADAS
    media_exp_total = (cartoes_casa + cartoes_fora) / 2
    media_casa = cartoes_casa
    media_fora = cartoes_fora

    print(f"  📊 Médias esperadas: Total={media_exp_total:.1f}, Casa={media_casa:.1f}, Fora={media_fora:.1f}")

    palpites = []

    # ✅ STEP 3: VERIFICAR ODDS DISPONÍVEIS
    if not odds:
        print(f"  ⚠️ CARTÕES: Sem odds - partindo para análise tática")
        # TODO: Análise tática sem odds
        return None

    # ✅ STEP 4: ANALISAR MERCADOS DINAMICAMENTE
    
    # --- TOTAL (Full Time) OVER ---
    linhas_over_total = [2.5, 3.5, 4.5, 5.5]
    for linha in linhas_over_total:
        odd_key = f"cartoes_over_{linha}"
        if odd_key in odds:
            odd_value = odds[odd_key]
            
            # ✅ REFATORADO: Calcular probabilidade estatística
            prob_pct = calculate_statistical_probability_cards_over(
                weighted_cards_avg=media_exp_total,
                line=linha
            )
            
            # ✅ REFATORADO: Calcular confiança final via confidence_calculator
            bet_type = f"Over {linha} Cartões"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name,
                value_score_pct=0.0,
                odd=odd_value
            )
            
            print(f"     {bet_type}: Prob={prob_pct:.1f}% → Conf={conf_final:.1f} (odd={odd_value:.2f})")
            
            # ✅ Filtros de qualidade
            if odd_value >= ODD_MINIMA_DE_VALOR and conf_final >= MIN_CONFIANCA_CARTOES:
                palpites.append({
                    "tipo": f"Over {linha}",
                    "confianca": conf_final,
                    "odd": odd_value,
                    "time": "Total",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })

    # --- TOTAL (Full Time) UNDER ---
    linhas_under_total = [5.5, 4.5, 3.5]
    for linha in linhas_under_total:
        odd_key = f"cartoes_under_{linha}"
        if odd_key in odds:
            odd_value = odds[odd_key]
            
            # ✅ Probabilidade de UNDER = 100% - Probabilidade de OVER
            prob_over = calculate_statistical_probability_cards_over(
                weighted_cards_avg=media_exp_total,
                line=linha
            )
            prob_under = 100.0 - prob_over
            
            # ✅ Confiança final
            bet_type = f"Under {linha} Cartões"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name,
                value_score_pct=0.0,
                odd=odd_value
            )
            
            print(f"     {bet_type}: Prob={prob_under:.1f}% → Conf={conf_final:.1f} (odd={odd_value:.2f})")
            
            if odd_value >= ODD_MINIMA_DE_VALOR and conf_final >= MIN_CONFIANCA_CARTOES:
                palpites.append({
                    "tipo": f"Under {linha}",
                    "confianca": conf_final,
                    "odd": odd_value,
                    "time": "Total",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })

    # --- CASA (Home Cards) OVER/UNDER ---
    linhas_casa = [1.5, 2.5, 3.5]
    for linha in linhas_casa:
        # OVER
        odd_key_over = f"cartoes_casa_over_{linha}"
        if odd_key_over in odds:
            odd_value = odds[odd_key_over]
            
            prob_pct = calculate_statistical_probability_cards_over(
                weighted_cards_avg=media_casa,
                line=linha
            )
            
            bet_type = f"Over {linha} Cartões Casa"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name,
                value_score_pct=0.0,
                odd=odd_value
            )
            
            if odd_value >= ODD_MINIMA_DE_VALOR and conf_final >= MIN_CONFIANCA_CARTOES:
                palpites.append({
                    "tipo": f"Over {linha} Casa",
                    "confianca": conf_final,
                    "odd": odd_value,
                    "time": "Casa",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })
        
        # UNDER
        odd_key_under = f"cartoes_casa_under_{linha}"
        if odd_key_under in odds:
            odd_value = odds[odd_key_under]
            
            prob_over = calculate_statistical_probability_cards_over(
                weighted_cards_avg=media_casa,
                line=linha
            )
            prob_under = 100.0 - prob_over
            
            bet_type = f"Under {linha} Cartões Casa"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name,
                value_score_pct=0.0,
                odd=odd_value
            )
            
            if odd_value >= ODD_MINIMA_DE_VALOR and conf_final >= MIN_CONFIANCA_CARTOES:
                palpites.append({
                    "tipo": f"Under {linha} Casa",
                    "confianca": conf_final,
                    "odd": odd_value,
                    "time": "Casa",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })

    # --- FORA (Away Cards) OVER/UNDER ---
    linhas_fora = [1.5, 2.5, 3.5]
    for linha in linhas_fora:
        # OVER
        odd_key_over = f"cartoes_fora_over_{linha}"
        if odd_key_over in odds:
            odd_value = odds[odd_key_over]
            
            prob_pct = calculate_statistical_probability_cards_over(
                weighted_cards_avg=media_fora,
                line=linha
            )
            
            bet_type = f"Over {linha} Cartões Fora"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name,
                value_score_pct=0.0,
                odd=odd_value
            )
            
            if odd_value >= ODD_MINIMA_DE_VALOR and conf_final >= MIN_CONFIANCA_CARTOES:
                palpites.append({
                    "tipo": f"Over {linha} Fora",
                    "confianca": conf_final,
                    "odd": odd_value,
                    "time": "Fora",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })
        
        # UNDER
        odd_key_under = f"cartoes_fora_under_{linha}"
        if odd_key_under in odds:
            odd_value = odds[odd_key_under]
            
            prob_over = calculate_statistical_probability_cards_over(
                weighted_cards_avg=media_fora,
                line=linha
            )
            prob_under = 100.0 - prob_over
            
            bet_type = f"Under {linha} Cartões Fora"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name,
                value_score_pct=0.0,
                odd=odd_value
            )
            
            if odd_value >= ODD_MINIMA_DE_VALOR and conf_final >= MIN_CONFIANCA_CARTOES:
                palpites.append({
                    "tipo": f"Under {linha} Fora",
                    "confianca": conf_final,
                    "odd": odd_value,
                    "time": "Fora",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })

    # ✅ RETORNO FINAL
    print(f"  ✅ CARTÕES: {len(palpites)} palpites gerados")
    
    if palpites:
        suporte = (f"   - <b>Expectativa Cartões Total:</b> {media_exp_total:.1f}\n"
                   f"   - <b>Casa:</b> {media_casa:.1f} cartões/jogo\n"
                   f"   - <b>Fora:</b> {media_fora:.1f} cartões/jogo\n")
        
        return {"mercado": "Cartões", "palpites": palpites, "dados_suporte": suporte}
    
    # Fallback: Análise tática sem odds (TODO)
    print(f"  ❌ CARTÕES: Nenhum palpite passou nos filtros de qualidade")
    return None
