# analysts/btts_analyzer.py
from config import (ODD_MINIMA_DE_VALOR, BTTS_PROB_THRESHOLD_SIM, BTTS_PROB_THRESHOLD_NAO,
                    MIN_CONFIANCA_BTTS_SIM, MIN_CONFIANCA_BTTS_NAO)
from analysts.context_analyzer import verificar_veto_mercado, ajustar_confianca_por_script

def analisar_mercado_btts(stats_casa, stats_fora, odds, script_name=None):
    """
    Analisa o mercado de Ambas Marcam (BTTS - Both Teams To Score).
    
    PHOENIX V2.0: Agora com sistema de VETO e ajuste de confiança por script.
    """
    if not stats_casa or not stats_fora or not odds:
        return None

    prob_casa_marcar = min(stats_casa['casa']['gols_marcados'] / 2.5, 0.95)
    prob_fora_marcar = min(stats_fora['fora']['gols_marcados'] / 2.5, 0.95)
    prob_ambas_marcam = prob_casa_marcar * prob_fora_marcar

    palpites_btts = []
    
    # LAYER 3 & 4: VETO e ajuste de confiança por script

    if 'btts_yes' in odds and odds['btts_yes'] >= ODD_MINIMA_DE_VALOR:
        if prob_ambas_marcam >= BTTS_PROB_THRESHOLD_SIM:
            tipo = "BTTS Sim"
            confianca = min(round(5.0 + (prob_ambas_marcam - BTTS_PROB_THRESHOLD_SIM) * 10, 1), 9.5)
            
            # Verificar veto se script disponível
            if script_name:
                is_vetado, razao_veto = verificar_veto_mercado(tipo, script_name)
                if is_vetado:
                    print(f"  🚫 VETO: {tipo} vetado por {script_name} - {razao_veto}")
                    confianca = 0  # Zerar confiança para não adicionar
                else:
                    confianca = ajustar_confianca_por_script(confianca, tipo, script_name)
            
            if confianca >= MIN_CONFIANCA_BTTS_SIM:
                palpites_btts.append({
                    "tipo": "Sim",
                    "confianca": confianca,
                    "odd": odds['btts_yes']
                })

    if 'btts_no' in odds and odds['btts_no'] >= ODD_MINIMA_DE_VALOR:
        if prob_ambas_marcam < BTTS_PROB_THRESHOLD_NAO:
            tipo = "BTTS Não"
            confianca = min(round(5.0 + (BTTS_PROB_THRESHOLD_NAO - prob_ambas_marcam) * 10, 1), 9.5)
            
            # Verificar veto se script disponível
            if script_name:
                is_vetado, razao_veto = verificar_veto_mercado(tipo, script_name)
                if is_vetado:
                    print(f"  🚫 VETO: {tipo} vetado por {script_name} - {razao_veto}")
                    confianca = 0  # Zerar confiança para não adicionar
                else:
                    confianca = ajustar_confianca_por_script(confianca, tipo, script_name)
            
            if confianca >= MIN_CONFIANCA_BTTS_NAO:
                palpites_btts.append({
                    "tipo": "Não",
                    "confianca": confianca,
                    "odd": odds['btts_no']
                })

    if palpites_btts:
        dados_suporte = (f"   - <b>Probabilidade Ambas Marcam:</b> {round(prob_ambas_marcam * 100, 1)}%\n"
                        f"   - <b>Casa marcar:</b> {round(prob_casa_marcar * 100, 1)}% | <b>Fora marcar:</b> {round(prob_fora_marcar * 100, 1)}%\n"
                        f"   - <b>Média Gols Casa:</b> {stats_casa['casa']['gols_marcados']} | <b>Média Gols Fora:</b> {stats_fora['fora']['gols_marcados']}\n")

        return {
            "mercado": "BTTS",
            "palpites": palpites_btts,
            "dados_suporte": dados_suporte
        }

    return None


