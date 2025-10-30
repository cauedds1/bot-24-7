# analysts/shots_analyzer.py
from analysts.context_analyzer import verificar_veto_mercado, ajustar_confianca_por_script

def analisar_mercado_finalizacoes(stats_casa, stats_fora, odds=None, master_data=None, script_name=None):
    """
    Analisa o mercado de Finalizações (Shots on Target) para um jogo.
    Como odds de finalizações raramente estão disponíveis, gera palpites baseados nas médias.
    
    PHOENIX V2.0: Agora com sistema de VETO e ajuste de confiança por script.
    """
    print(f"  🔍 FINALIZAÇÕES: Verificando dados... stats_casa={bool(stats_casa)}, stats_fora={bool(stats_fora)}")
    if not stats_casa or not stats_fora:
        print(f"  ⚠️ FINALIZAÇÕES: Retornando None (faltam stats)")
        return None

    # Extrair estatísticas de finalizações
    finalizacoes_casa = stats_casa['casa'].get('finalizacoes', 0)
    finalizacoes_fora = stats_fora['fora'].get('finalizacoes', 0)
    finalizacoes_gol_casa = stats_casa['casa'].get('finalizacoes_no_gol', 0)
    finalizacoes_gol_fora = stats_fora['fora'].get('finalizacoes_no_gol', 0)

    print(f"\n  🔍 DEBUG FINALIZAÇÕES - DADOS RECEBIDOS:")
    print(f"     Casa: {finalizacoes_casa:.1f} total ({finalizacoes_gol_casa:.1f} no gol)")
    print(f"     Fora: {finalizacoes_fora:.1f} total ({finalizacoes_gol_fora:.1f} no gol)")

    # BLOQUEIO: Se não houver dados de finalizações E finalizações no gol, não gerar palpites
    if (finalizacoes_casa == 0 and finalizacoes_fora == 0 and 
        finalizacoes_gol_casa == 0 and finalizacoes_gol_fora == 0):
        print("  ❌ FINALIZAÇÕES BLOQUEADO: Dados insuficientes (todos 0.0)")
        return None

    # Calcular médias esperadas
    media_exp_total = finalizacoes_casa + finalizacoes_fora
    media_exp_no_gol = finalizacoes_gol_casa + finalizacoes_gol_fora

    palpites = []

    # --- TOTAL DE FINALIZAÇÕES ---
    # Linhas comuns: 15.5, 18.5, 21.5, 24.5
    # ⚡ REDUZIDO: Confiança máxima limitada (sem odds = menor prioridade)
    if media_exp_total >= 21.5:
        tipo_palpite = "Over 21.5 Finalizações"
        confianca = min(round(5.0 + (media_exp_total - 21.5) * 0.2, 1), 7.0)  # Max 7.0
        
        # LAYER 3 & 4: VETO e ajuste de confiança
        if script_name:
            is_vetado, razao_veto = verificar_veto_mercado(tipo_palpite, script_name)
            if is_vetado:
                print(f"  🚫 VETO: {tipo_palpite} vetado por {script_name}")
            else:
                confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                if confianca >= 5.5:
                    palpites.append({
                        "tipo": tipo_palpite + " (Total)",
                        "confianca": confianca,
                        "odd": "N/A",
                        "time": "Total"
                    })
        elif confianca >= 5.5:
            palpites.append({
                "tipo": tipo_palpite + " (Total)",
                "confianca": confianca,
                "odd": "N/A",
                "time": "Total"
            })

    # ⚡ REDUZIDO: Confiança máxima limitada
    if media_exp_total >= 18.5:
        tipo_palpite = "Over 18.5 Finalizações"
        confianca = min(round(5.0 + (media_exp_total - 18.5) * 0.25, 1), 7.0)  # Max 7.0
        
        # LAYER 3 & 4: VETO e ajuste de confiança
        if script_name:
            is_vetado, razao_veto = verificar_veto_mercado(tipo_palpite, script_name)
            if not is_vetado:
                confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                if confianca >= 5.5:
                    palpites.append({
                        "tipo": tipo_palpite + " (Total)",
                        "confianca": confianca,
                        "odd": "N/A",
                        "time": "Total"
                    })
        elif confianca >= 5.5:
            palpites.append({
                "tipo": tipo_palpite + " (Total)",
                "confianca": confianca,
                "odd": "N/A",
                "time": "Total"
            })

    # ⚡ REDUZIDO: Confiança máxima limitada
    if media_exp_total <= 16.5:
        tipo_palpite = "Under 18.5 Finalizações"
        confianca = min(round(5.0 + (16.5 - media_exp_total) * 0.25, 1), 7.0)  # Max 7.0
        
        # LAYER 3 & 4: VETO e ajuste de confiança
        if script_name:
            is_vetado, razao_veto = verificar_veto_mercado(tipo_palpite, script_name)
            if not is_vetado:
                confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                if confianca >= 5.5:
                    palpites.append({
                        "tipo": tipo_palpite + " (Total)",
                        "confianca": confianca,
                        "odd": "N/A",
                        "time": "Total"
                    })
        elif confianca >= 5.5:
            palpites.append({
                "tipo": tipo_palpite + " (Total)",
                "confianca": confianca,
                "odd": "N/A",
                "time": "Total"
            })

    # --- FINALIZAÇÕES NO GOL (Shots on Target) ---
    if media_exp_no_gol >= 9.5:
        tipo_palpite = "Over 9.5 Finalizações no Gol"
        confianca = min(round(5.0 + (media_exp_no_gol - 9.5) * 0.3, 1), 6.8)
        if script_name:
            is_vetado, _ = verificar_veto_mercado(tipo_palpite, script_name)
            if not is_vetado:
                confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                if confianca >= 5.5:
                    palpites.append({"tipo": tipo_palpite + " (Total)", "confianca": confianca, "odd": "N/A", "time": "Total"})
        elif confianca >= 5.5:
            palpites.append({"tipo": tipo_palpite + " (Total)", "confianca": confianca, "odd": "N/A", "time": "Total"})

    if media_exp_no_gol <= 6.5:
        tipo_palpite = "Under 7.5 Finalizações no Gol"
        confianca = min(round(5.0 + (6.5 - media_exp_no_gol) * 0.3, 1), 6.8)
        if script_name:
            is_vetado, _ = verificar_veto_mercado(tipo_palpite, script_name)
            if not is_vetado:
                confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                if confianca >= 5.5:
                    palpites.append({"tipo": tipo_palpite + " (Total)", "confianca": confianca, "odd": "N/A", "time": "Total"})
        elif confianca >= 5.5:
            palpites.append({"tipo": tipo_palpite + " (Total)", "confianca": confianca, "odd": "N/A", "time": "Total"})

    # --- FINALIZAÇÕES POR TIME ---
    if finalizacoes_casa >= 11.5:
        tipo_palpite = "Over 11.5 Finalizações Casa"
        confianca = min(round(5.0 + (finalizacoes_casa - 11.5) * 0.25, 1), 6.8)
        if script_name:
            is_vetado, _ = verificar_veto_mercado(tipo_palpite, script_name)
            if not is_vetado:
                confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                if confianca >= 5.5:
                    palpites.append({"tipo": "Over 11.5 Finalizações (Casa)", "confianca": confianca, "odd": "N/A", "time": "Casa"})
        elif confianca >= 5.5:
            palpites.append({"tipo": "Over 11.5 Finalizações (Casa)", "confianca": confianca, "odd": "N/A", "time": "Casa"})

    if finalizacoes_fora >= 11.5:
        tipo_palpite = "Over 11.5 Finalizações Fora"
        confianca = min(round(5.0 + (finalizacoes_fora - 11.5) * 0.25, 1), 6.8)
        if script_name:
            is_vetado, _ = verificar_veto_mercado(tipo_palpite, script_name)
            if not is_vetado:
                confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                if confianca >= 5.5:
                    palpites.append({"tipo": "Over 11.5 Finalizações (Fora)", "confianca": confianca, "odd": "N/A", "time": "Fora"})
        elif confianca >= 5.5:
            palpites.append({"tipo": "Over 11.5 Finalizações (Fora)", "confianca": confianca, "odd": "N/A", "time": "Fora"})

    if finalizacoes_casa <= 7.5:
        tipo_palpite = "Under 8.5 Finalizações Casa"
        confianca = min(round(5.0 + (7.5 - finalizacoes_casa) * 0.25, 1), 6.8)
        if script_name:
            is_vetado, _ = verificar_veto_mercado(tipo_palpite, script_name)
            if not is_vetado:
                confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                if confianca >= 5.5:
                    palpites.append({"tipo": "Under 8.5 Finalizações (Casa)", "confianca": confianca, "odd": "N/A", "time": "Casa"})
        elif confianca >= 5.5:
            palpites.append({"tipo": "Under 8.5 Finalizações (Casa)", "confianca": confianca, "odd": "N/A", "time": "Casa"})

    if finalizacoes_fora <= 7.5:
        tipo_palpite = "Under 8.5 Finalizações Fora"
        confianca = min(round(5.0 + (7.5 - finalizacoes_fora) * 0.25, 1), 6.8)
        if script_name:
            is_vetado, _ = verificar_veto_mercado(tipo_palpite, script_name)
            if not is_vetado:
                confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                if confianca >= 5.5:
                    palpites.append({"tipo": "Under 8.5 Finalizações (Fora)", "confianca": confianca, "odd": "N/A", "time": "Fora"})
        elif confianca >= 5.5:
            palpites.append({"tipo": "Under 8.5 Finalizações (Fora)", "confianca": confianca, "odd": "N/A", "time": "Fora"})

    if palpites:
        suporte = (f"   - <b>Expectativa Finalizações:</b> {round(media_exp_total, 1)} total ({round(media_exp_no_gol, 1)} no gol)\n"
                   f"   - <b>Casa:</b> {finalizacoes_casa:.1f} finalizações/jogo ({finalizacoes_gol_casa:.1f} no gol)\n"
                   f"   - <b>Fora:</b> {finalizacoes_fora:.1f} finalizações/jogo ({finalizacoes_gol_fora:.1f} no gol)\n"
                   f"   - <i>⚠️ Odds raramente disponíveis - análise baseada em médias históricas</i>\n")
        return {"mercado": "Finalizações", "palpites": palpites, "dados_suporte": suporte}

    return None
