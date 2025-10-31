"""
Analisador de Gols V2 - PHOENIX V2.0 FINAL STAGE

NOVO MODELO DE CONFIANÇA BASEADO EM PROBABILIDADES ESTATÍSTICAS:
- Usa probabilidades do Master Analyzer como base
- Aplica novo cálculo de confiança em 4 passos
- Garante que confiança reflete probabilidade real do evento

PHOENIX V2.0: Sistema de VETO + Confiança Calibrada
"""

from config import (ODD_MINIMA_DE_VALOR, MIN_CONFIANCA_GOLS_OVER_UNDER,
                    MIN_CONFIANCA_GOLS_OVER_1_5, MIN_CONFIANCA_GOLS_OVER_3_5)
# DEPRECATED: from analysts.context_analyzer import verificar_veto_mercado
from analysts.confidence_calculator import calculate_final_confidence


def extract_goals_suggestions(analysis_packet, odds):
    """
    Extrai sugestões de gols do pacote de análise do Master Analyzer.
    
    Args:
        analysis_packet: Pacote completo gerado por master_analyzer.generate_match_analysis()
        odds: Dicionário com odds disponíveis
    
    Returns:
        dict: Sugestões formatadas para o mercado de gols
    """
    if 'error' in analysis_packet:
        return None
    
    probabilities = analysis_packet['calculated_probabilities']
    script = analysis_packet['analysis_summary']['selected_script']
    reasoning = analysis_packet['analysis_summary']['reasoning']
    
    over_2_5_prob = probabilities['goals_over_under_2_5']['over_2_5_prob']
    under_2_5_prob = probabilities['goals_over_under_2_5']['under_2_5_prob']
    
    palpites = []
    
    # LAYER 3: Verificar VETO antes de adicionar cada palpite
    # LAYER 4: Ajustar confiança baseado em coerência com script
    
    if 'gols_ft_over_2.5' in odds and odds['gols_ft_over_2.5'] >= ODD_MINIMA_DE_VALOR:
        tipo = "Over 2.5"
        # NOVO MODELO: Calcular confiança baseada em probabilidade estatística
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=over_2_5_prob,
            bet_type=tipo,
            tactical_script=script,
            value_score_pct=0.0,
            odd=odds['gols_ft_over_2.5']
        )
        print(f"  📊 NOVO MODELO GOLS: {tipo} - Prob:{over_2_5_prob:.0f}% -> Conf:{confianca:.1f}/10 (Base:{breakdown['confianca_base']:.1f}, Mods:{breakdown['modificador_script']:+.1f})")
        if confianca >= 5.0:
            palpites.append({
                "tipo": tipo,
                "confianca": confianca,
                "odd": odds['gols_ft_over_2.5'],
                "periodo": "FT",
                "time": "Total",
                "probabilidade": over_2_5_prob,
                "confidence_breakdown": breakdown
            })
    
    if 'gols_ft_under_2.5' in odds and odds['gols_ft_under_2.5'] >= ODD_MINIMA_DE_VALOR:
        tipo = "Under 2.5"
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=under_2_5_prob,
            bet_type=tipo,
            tactical_script=script,
            value_score_pct=0.0,
            odd=odds['gols_ft_under_2.5']
        )
        print(f"  📊 NOVO MODELO GOLS: {tipo} - Prob:{under_2_5_prob:.0f}% -> Conf:{confianca:.1f}/10")
        if confianca >= 5.0:
            palpites.append({
                "tipo": tipo,
                "confianca": confianca,
                "odd": odds['gols_ft_under_2.5'],
                "periodo": "FT",
                "time": "Total",
                "probabilidade": under_2_5_prob,
                "confidence_breakdown": breakdown
            })
    
    if 'gols_ft_over_1.5' in odds and odds['gols_ft_over_1.5'] >= ODD_MINIMA_DE_VALOR:
        tipo = "Over 1.5"
        over_1_5_prob = min(over_2_5_prob + 15, 90)
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=over_1_5_prob,
            bet_type=tipo,
            tactical_script=script,
            value_score_pct=0.0,
            odd=odds['gols_ft_over_1.5']
        )
        print(f"  📊 NOVO MODELO GOLS: {tipo} - Prob:{over_1_5_prob:.0f}% -> Conf:{confianca:.1f}/10")
        if confianca >= 5.5:
            palpites.append({
                "tipo": tipo,
                "confianca": confianca,
                "odd": odds['gols_ft_over_1.5'],
                "periodo": "FT",
                "time": "Total",
                "probabilidade": over_1_5_prob,
                "confidence_breakdown": breakdown
            })
    
    if 'gols_ft_over_3.5' in odds and odds['gols_ft_over_3.5'] >= ODD_MINIMA_DE_VALOR:
        tipo = "Over 3.5"
        if script == 'SCRIPT_OPEN_HIGH_SCORING_GAME':
            over_3_5_prob = max(over_2_5_prob - 20, 30)
            confianca, breakdown = calculate_final_confidence(
                statistical_probability_pct=over_3_5_prob,
                bet_type=tipo,
                tactical_script=script,
                value_score_pct=0.0,
                odd=odds['gols_ft_over_3.5']
            )
            print(f"  📊 NOVO MODELO GOLS: {tipo} - Prob:{over_3_5_prob:.0f}% -> Conf:{confianca:.1f}/10")
            if confianca >= 5.0:
                palpites.append({
                    "tipo": tipo,
                    "confianca": confianca,
                    "odd": odds['gols_ft_over_3.5'],
                    "periodo": "FT",
                    "time": "Total",
                    "probabilidade": over_3_5_prob,
                    "confidence_breakdown": breakdown
                })
    
    if not palpites:
        return None
    
    palpites_sorted = sorted(palpites, key=lambda x: x['confianca'], reverse=True)
    
    contexto = f"💡 {reasoning}"
    
    return {
        "mercado": "Gols",
        "palpites": palpites_sorted,
        "dados_suporte": contexto,
        "script": script
    }


def _convert_probability_to_confidence(probability_pct):
    """
    Converte probabilidade (%) para escala de confiança (0-10).
    
    Args:
        probability_pct: Probabilidade em porcentagem (0-100)
    
    Returns:
        float: Confiança na escala 0-10
    """
    if probability_pct >= 70:
        return 9.0
    elif probability_pct >= 65:
        return 8.5
    elif probability_pct >= 60:
        return 8.0
    elif probability_pct >= 55:
        return 7.5
    elif probability_pct >= 50:
        return 7.0
    elif probability_pct >= 45:
        return 6.5
    elif probability_pct >= 40:
        return 6.0
    elif probability_pct >= 35:
        return 5.5
        return 5.0


def analisar_mercado_gols(analysis_packet, odds):
    """
    Função principal compatível com interface antiga.
    Wrapper para extract_goals_suggestions().
    
    Args:
        analysis_packet: Pacote do Master Analyzer
        odds: Odds disponíveis
    
    Returns:
        dict: Análise formatada do mercado de gols
    """
    return extract_goals_suggestions(analysis_packet, odds)
