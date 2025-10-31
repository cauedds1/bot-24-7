# analysts/cards_analyzer.py
"""
CARDS ANALYZER V3.0 - DEEP ANALYSIS PROTOCOL

BLUEPRINT IMPLEMENTATION:
- Retorna LISTA de múltiplas predições (~6 predições)
- Analisa submercados: Total Cards (Over/Under 3.5, 4.5, 5.5)
- Cada predição tem confiança calculada via confidence_calculator
- Implementa Script-Based Probability Modifier
"""

from config import MIN_CONFIANCA_CARTOES
from analysts.confidence_calculator import (
    calculate_statistical_probability_cards_over,
    calculate_final_confidence
)


def apply_script_modifier_to_probability_cards(base_prob_pct, bet_type, tactical_script):
    """
    Script-Based Probability Modifier para CARTÕES
    
    Aplica modificador de probabilidade baseado no script tático.
    Jogos tensos, rivais ou desesperados tendem a ter mais cartões.
    
    Args:
        base_prob_pct: Probabilidade base em % (0-100)
        bet_type: Tipo da aposta (ex: "Over 4.5 Cartões")
        tactical_script: Script tático selecionado
    
    Returns:
        float: Probabilidade modificada (0-100%)
    """
    if not tactical_script:
        return base_prob_pct
    
    modifier = 1.0
    
    # Jogos tensos/disputados/desesperados = mais cartões
    if "Over" in bet_type or "over" in bet_type:
        if tactical_script in ["SCRIPT_BALANCED_RIVALRY_CLASH", "SCRIPT_RELEGATION_BATTLE", 
                               "SCRIPT_CAGEY_TACTICAL_AFFAIR", "SCRIPT_TIGHT_LOW_SCORING"]:
            modifier = 1.25  # +25% na probabilidade
        elif tactical_script in ["SCRIPT_GIANT_VS_MINNOW", "SCRIPT_JOGO_DE_COMPADRES"]:
            modifier = 0.80  # -20% na probabilidade (jogo tranquilo)
    
    elif "Under" in bet_type or "under" in bet_type:
        if tactical_script in ["SCRIPT_GIANT_VS_MINNOW", "SCRIPT_JOGO_DE_COMPADRES"]:
            modifier = 1.25  # Jogos tranquilos = menos cartões
        elif tactical_script in ["SCRIPT_BALANCED_RIVALRY_CLASH", "SCRIPT_RELEGATION_BATTLE"]:
            modifier = 0.80
    
    modified_prob = base_prob_pct * modifier
    return min(max(modified_prob, 0.0), 100.0)


def analisar_mercado_cartoes(stats_casa, stats_fora, odds, master_data=None, script_name=None):
    """
    FUNÇÃO PRINCIPAL - Análise profunda do mercado de cartões.
    
    ACTION 1.3: Retorna LISTA de múltiplas predições (~6 predições) com submercados:
    - Total Cards FT: Over/Under 3.5, 4.5, 5.5
    
    Args:
        stats_casa: Estatísticas do time da casa
        stats_fora: Estatísticas do time visitante
        odds: Dicionário de odds disponíveis
        master_data: Dados do master_analyzer (tactical script)
        script_name: Nome do script tático
    
    Returns:
        dict: Análise com lista de predições ou None
    """
    print(f"\n  🔍 CARTÕES V3.0: Iniciando análise profunda...")
    
    if not stats_casa or not stats_fora:
        print(f"  ⚠️ CARTÕES: Faltam estatísticas")
        return None

    # STEP 1: EXTRAIR MÉTRICAS DE CARTÕES
    cartoes_amarelos_casa = stats_casa.get('casa', {}).get('cartoes_amarelos', 0.0)
    cartoes_vermelhos_casa = stats_casa.get('casa', {}).get('cartoes_vermelhos', 0.0)
    cartoes_amarelos_fora = stats_fora.get('fora', {}).get('cartoes_amarelos', 0.0)
    cartoes_vermelhos_fora = stats_fora.get('fora', {}).get('cartoes_vermelhos', 0.0)

    cartoes_casa = cartoes_amarelos_casa + cartoes_vermelhos_casa
    cartoes_fora = cartoes_amarelos_fora + cartoes_vermelhos_fora

    if (cartoes_amarelos_casa == 0.0 and cartoes_vermelhos_casa == 0.0 and 
        cartoes_amarelos_fora == 0.0 and cartoes_vermelhos_fora == 0.0):
        print("  ❌ CARTÕES BLOQUEADO: Dados insuficientes")
        return None

    print(f"  📊 CARTÕES - Dados:")
    print(f"     Casa: {cartoes_casa:.1f} total ({cartoes_amarelos_casa:.1f}A + {cartoes_vermelhos_casa:.1f}V)")
    print(f"     Fora: {cartoes_fora:.1f} total ({cartoes_amarelos_fora:.1f}A + {cartoes_vermelhos_fora:.1f}V)")
    print(f"     Script Tático: {script_name}")

    # STEP 2: CALCULAR MÉDIAS ESPERADAS
    media_exp_total = (cartoes_casa + cartoes_fora) / 2
    media_casa = cartoes_casa
    media_fora = cartoes_fora

    print(f"  📊 Médias esperadas: Total={media_exp_total:.1f}, Casa={media_casa:.1f}, Fora={media_fora:.1f}")

    all_predictions = []

    if not odds:
        print(f"  ⚠️ CARTÕES: Sem odds disponíveis")
        return None

    # ========== 1. TOTAL CARDS FULL TIME ==========
    
    linhas_total = [3.5, 4.5, 5.5]
    
    for linha in linhas_total:
        # Over
        odd_key_over = f"cartoes_over_{linha}"
        if odd_key_over in odds:
            prob_pct = calculate_statistical_probability_cards_over(
                weighted_cards_avg=media_exp_total,
                line=linha
            )
            
            prob_pct = apply_script_modifier_to_probability_cards(
                prob_pct, f"Over {linha} Cartões", script_name
            )
            
            bet_type = f"Over {linha} Cartões"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name,
            )
            
            if conf_final >= MIN_CONFIANCA_CARTOES:
                all_predictions.append({
                    "mercado": "Cartões",
                    "tipo": f"Over {linha}",
                    "confianca": conf_final,
                    "odd": odds[odd_key_over],
                    "time": "Total",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })
        
        # Under
        odd_key_under = f"cartoes_under_{linha}"
        if odd_key_under in odds:
            prob_over = calculate_statistical_probability_cards_over(
                weighted_cards_avg=media_exp_total,
                line=linha
            )
            prob_under = 100.0 - prob_over
            
            prob_under = apply_script_modifier_to_probability_cards(
                prob_under, f"Under {linha} Cartões", script_name
            )
            
            bet_type = f"Under {linha} Cartões"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name,
            )
            
            if conf_final >= MIN_CONFIANCA_CARTOES:
                all_predictions.append({
                    "mercado": "Cartões",
                    "tipo": f"Under {linha}",
                    "confianca": conf_final,
                    "odd": odds[odd_key_under],
                    "time": "Total",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })

    print(f"  ✅ CARTÕES V3.0: {len(all_predictions)} predições geradas (deep analysis)")
    
    if all_predictions:
        suporte = (f"Expectativa Cartões Total: {media_exp_total:.1f}\n"
                   f"Casa: {media_casa:.1f} cartões/jogo\n"
                   f"Fora: {media_fora:.1f} cartões/jogo\n")
        
        return {"mercado": "Cartões", "palpites": all_predictions, "dados_suporte": suporte}
    
    print(f"  ❌ CARTÕES: Nenhuma predição passou nos filtros")
    return None
