# analysts/btts_analyzer.py
from config import ODD_MINIMA_DE_VALOR, MIN_CONFIANCA_BTTS_SIM, MIN_CONFIANCA_BTTS_NAO
from analysts.confidence_calculator import calculate_statistical_probability_btts, calculate_final_confidence

def analisar_mercado_btts(stats_casa, stats_fora, odds, script_name=None):
    """
    Analisa o mercado de Ambas Marcam (BTTS - Both Teams To Score).
    
    PHOENIX V3.0 - UNIFIED CONFIDENCE MODEL:
    - Usa confidence_calculator.py centralizado para cálculo de confiança
    - Probabilidades estatísticas baseadas em dados reais
    - Modificadores contextuais (script tático, value, odd) aplicados de forma consistente
    """
    if not stats_casa or not stats_fora or not odds:
        return None

    home_scoring_rate = min(stats_casa['casa']['gols_marcados'] / 2.5, 0.95)
    away_scoring_rate = min(stats_fora['fora']['gols_marcados'] / 2.5, 0.95)
    
    prob_btts_pct = calculate_statistical_probability_btts(home_scoring_rate, away_scoring_rate)
    prob_no_btts_pct = 100 - prob_btts_pct

    palpites_btts = []

    if 'btts_yes' in odds and odds['btts_yes'] >= ODD_MINIMA_DE_VALOR:
        odd_btts_yes = odds['btts_yes']
        
        value_score = ((1 / odd_btts_yes) - (prob_btts_pct / 100)) / (prob_btts_pct / 100) * 100 if prob_btts_pct > 0 else 0
        
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob_btts_pct,
            bet_type="BTTS Sim",
            tactical_script=script_name,
            value_score_pct=value_score,
            odd=odd_btts_yes
        )
        
        if confianca >= MIN_CONFIANCA_BTTS_SIM:
            palpites_btts.append({
                "tipo": "Sim",
                "confianca": confianca,
                "odd": odd_btts_yes,
                "breakdown": breakdown
            })

    if 'btts_no' in odds and odds['btts_no'] >= ODD_MINIMA_DE_VALOR:
        odd_btts_no = odds['btts_no']
        
        value_score = ((1 / odd_btts_no) - (prob_no_btts_pct / 100)) / (prob_no_btts_pct / 100) * 100 if prob_no_btts_pct > 0 else 0
        
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob_no_btts_pct,
            bet_type="BTTS Não",
            tactical_script=script_name,
            value_score_pct=value_score,
            odd=odd_btts_no
        )
        
        if confianca >= MIN_CONFIANCA_BTTS_NAO:
            palpites_btts.append({
                "tipo": "Não",
                "confianca": confianca,
                "odd": odd_btts_no,
                "breakdown": breakdown
            })

    if palpites_btts:
        dados_suporte = (f"   - <b>Probabilidade Ambas Marcam:</b> {round(prob_btts_pct, 1)}%\n"
                        f"   - <b>Casa marcar:</b> {round(home_scoring_rate * 100, 1)}% | <b>Fora marcar:</b> {round(away_scoring_rate * 100, 1)}%\n"
                        f"   - <b>Média Gols Casa:</b> {stats_casa['casa']['gols_marcados']} | <b>Média Gols Fora:</b> {stats_fora['fora']['gols_marcados']}\n")

        return {
            "mercado": "BTTS",
            "palpites": palpites_btts,
            "dados_suporte": dados_suporte
        }

    return None


