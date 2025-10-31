# analysts/corners_analyzer.py
from config import ODD_MINIMA_DE_VALOR, ODD_MINIMA_PENALIDADE, MIN_CONFIANCA_CANTOS, MIN_CONFIANCA_CANTOS_UNDER
from analysts.context_analyzer import analisar_compatibilidade_ofensiva_defensiva
from analysts.confidence_calculator import calculate_statistical_probability_corners_over, calculate_final_confidence

def ajustar_confianca_por_odd(confianca_base, odd):
    """Ajusta a confiança baseado na odd: penaliza odds muito altas."""
    if odd < ODD_MINIMA_PENALIDADE:
        return max(confianca_base - 1.0, MIN_CONFIANCA_CANTOS)
    elif odd <= 2.5:
        return confianca_base
    elif odd <= 3.5:
        return max(confianca_base - 0.5, MIN_CONFIANCA_CANTOS_UNDER)
    elif odd <= 5.0:
        return max(confianca_base - 1.5, MIN_CONFIANCA_CANTOS_UNDER)
    else:
        # Odds muito altas (> 5.0): penalização severa
        return max(confianca_base - 2.5, MIN_CONFIANCA_CANTOS)

def analisar_mercado_cantos(stats_casa, stats_fora, odds, classificacao=None, pos_casa="N/A", pos_fora="N/A", master_data=None, script_name=None):
    """
    Analisa mercado de cantos:
    1. PRIORIDADE: Buscar odds com valor (apostas rentáveis)
    2. FALLBACK: Gerar sugestão tática quando não há odds disponíveis
    PHOENIX V2.0: Agora com sistema de VETO e ajuste de confiança por script.
    """
    if not stats_casa or not stats_fora:
        return None

    # Inicializar variáveis (para evitar erros LSP de unbound)
    cantos_casa_feitos = 0.0
    cantos_casa_sofridos = 0.0
    cantos_fora_feitos = 0.0
    cantos_fora_sofridos = 0.0

    # ✅ TASK 3a: USAR WEIGHTED METRICS SE DISPONÍVEL (ponderado por força do adversário)
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

    # 🛡️ SHIELD RULE: Se TODOS os valores são 0.0, retornar None imediatamente
    if (cantos_casa_feitos == 0.0 and cantos_casa_sofridos == 0.0 and 
        cantos_fora_feitos == 0.0 and cantos_fora_sofridos == 0.0):
        print(f"  ❌ CANTOS BLOQUEADO: Dados insuficientes (todos 0.0) - API não retornou stats")
        return None

    # Contexto: pressão ofensiva favorece cantos
    insights = analisar_compatibilidade_ofensiva_defensiva(stats_casa, stats_fora)
    fator_cantos = 1.0
    contexto_insights = []

    for insight in insights:
        if insight['tipo'] == 'cantos_casa_favoravel':
            fator_cantos *= insight['fator_multiplicador']
            contexto_insights.append(insight['descricao'])
        elif insight['tipo'] == 'festival_gols':
            fator_cantos *= 1.2  # Jogos com muitos gols tendem a ter muitos cantos
            contexto_insights.append("⚡ Jogo ofensivo tende a gerar MAIS cantos!")

    # ✅ TASK 3a FIX: Usar as variáveis já preenchidas (weighted ou simples)
    media_exp_ft = (cantos_casa_feitos + cantos_fora_sofridos + 
                    cantos_fora_feitos + cantos_casa_sofridos) / 2
    media_exp_ft_ajustada = media_exp_ft * fator_cantos
    media_exp_ht = media_exp_ft_ajustada * 0.48
    media_casa = cantos_casa_feitos * (fator_cantos if fator_cantos > 1.0 else 1.0)
    media_fora = cantos_fora_feitos

    palpites = []

    # 🔍 DEBUG: Mostrar quais odds de cantos estão disponíveis
    odds_cantos_disponiveis = [k for k in odds.keys() if 'cantos' in k or 'corner' in k.lower()] if odds else []
    print(f"  📊 DEBUG CANTOS - Odds disponíveis: {odds_cantos_disponiveis if odds_cantos_disponiveis else 'NENHUMA'}")
    
    if not odds or len(odds_cantos_disponiveis) == 0:
        print(f"  ⚠️ CANTOS: Sem odds disponíveis na API - partindo para análise tática")

    # --- FT (Full Time) Total ---
    # BUSCAR DINAMICAMENTE as linhas que EXISTEM na API (ao invés de linhas fixas)
    if odds:
        for odd_key, odd_value in odds.items():
            if odd_key.startswith("cantos_ft_over_"):
                try:
                    linha = float(odd_key.replace("cantos_ft_over_", ""))
                    requisito = linha + 0.3
                    if media_exp_ft_ajustada >= requisito and odd_value >= ODD_MINIMA_DE_VALOR:
                        tipo_palpite = f"Over {linha} Cantos"
                        conf_base = min(round(5.0 + (media_exp_ft_ajustada - requisito) * 2.0, 1), 9.5)
                        conf = ajustar_confianca_por_odd(conf_base, odd_value)
                        
                        # LAYER 3 & 4: VETO e ajuste de confiança
                        if script_name:
                            
                            
                                continue
                        
                        if conf >= 5.0:
                            palpites.append({"tipo": f"Over {linha}", "confianca": conf, "odd": odd_value, "periodo": "FT", "time": "Total"})
                except ValueError:
                    continue

        # Under dinâmico (BLOQUEIO: Under < 7.5 não faz sentido para FT Total)
        for odd_key, odd_value in odds.items():
            if odd_key.startswith("cantos_ft_under_"):
                try:
                    linha = float(odd_key.replace("cantos_ft_under_", ""))
                    if linha < 7.5:
                        continue
                    requisito = linha - 0.3
                    if media_exp_ft_ajustada < requisito and odd_value >= ODD_MINIMA_DE_VALOR:
                        tipo_palpite = f"Under {linha} Cantos"
                        conf_base = min(round(5.0 + (requisito - media_exp_ft_ajustada) * 2.0, 1), 9.5)
                        conf = ajustar_confianca_por_odd(conf_base, odd_value)
                        
                        # LAYER 3 & 4: VETO e ajuste de confiança
                        if script_name:
                            
                            
                                continue
                        
                        if conf >= 5.5:
                            palpites.append({"tipo": f"Under {linha}", "confianca": conf, "odd": odd_value, "periodo": "FT", "time": "Total"})
                except ValueError:
                    continue

        # --- HT (Half Time) Total - DINÂMICO ---
        for odd_key, odd_value in odds.items():
            if odd_key.startswith("cantos_ht_over_"):
                try:
                    linha = float(odd_key.replace("cantos_ht_over_", ""))
                    requisito = linha + 0.3
                    if media_exp_ht >= requisito and odd_value >= ODD_MINIMA_DE_VALOR:
                        tipo_palpite = f"Over {linha} Cantos HT"
                        conf_base = min(round(5.0 + (media_exp_ht - requisito) * 2.0, 1), 9.5)
                        conf = ajustar_confianca_por_odd(conf_base, odd_value)
                        if script_name:
                            
                            
                                continue
                        if conf >= 5.0:
                            palpites.append({"tipo": f"Over {linha}", "confianca": conf, "odd": odd_value, "periodo": "HT", "time": "Total"})
                except ValueError:
                    continue

        for odd_key, odd_value in odds.items():
            if odd_key.startswith("cantos_ht_under_"):
                try:
                    linha = float(odd_key.replace("cantos_ht_under_", ""))
                    requisito = linha - 0.3
                    if media_exp_ht < requisito and odd_value >= ODD_MINIMA_DE_VALOR:
                        tipo_palpite = f"Under {linha} Cantos HT"
                        conf_base = min(round(5.0 + (requisito - media_exp_ht) * 2.0, 1), 9.5)
                        conf = ajustar_confianca_por_odd(conf_base, odd_value)
                        if script_name:
                            
                            
                                continue
                        if conf >= 5.5:
                            palpites.append({"tipo": f"Under {linha}", "confianca": conf, "odd": odd_value, "periodo": "HT", "time": "Total"})
                except ValueError:
                    continue

        # --- CASA (Home Corners) - DINÂMICO ---
        for odd_key, odd_value in odds.items():
            if odd_key.startswith("cantos_casa_over_"):
                try:
                    linha = float(odd_key.replace("cantos_casa_over_", ""))
                    requisito = linha + 0.3
                    if media_casa >= requisito and odd_value >= ODD_MINIMA_DE_VALOR:
                        tipo_palpite = f"Over {linha} Cantos Casa"
                        conf_base = min(round(5.0 + (media_casa - requisito) * 2.0, 1), 9.5)
                        conf = ajustar_confianca_por_odd(conf_base, odd_value)
                        if script_name:
                            
                            
                                continue
                        if conf >= 5.0:
                            palpites.append({"tipo": f"Over {linha}", "confianca": conf, "odd": odd_value, "periodo": "FT", "time": "Casa"})
                except ValueError:
                    continue

            elif odd_key.startswith("cantos_casa_under_"):
                try:
                    linha = float(odd_key.replace("cantos_casa_under_", ""))
                    requisito = linha - 0.3
                    if media_casa < requisito and odd_value >= ODD_MINIMA_DE_VALOR:
                        tipo_palpite = f"Under {linha} Cantos Casa"
                        conf_base = min(round(5.0 + (requisito - media_casa) * 2.0, 1), 9.5)
                        conf = ajustar_confianca_por_odd(conf_base, odd_value)
                        if script_name:
                            
                            
                                continue
                        if conf >= 5.5:
                            palpites.append({"tipo": f"Under {linha}", "confianca": conf, "odd": odd_value, "periodo": "FT", "time": "Casa"})
                except ValueError:
                    continue

        # --- FORA (Away Corners) - DINÂMICO ---
        for odd_key, odd_value in odds.items():
            if odd_key.startswith("cantos_fora_over_"):
                try:
                    linha = float(odd_key.replace("cantos_fora_over_", ""))
                    requisito = linha + 0.3
                    if media_fora >= requisito and odd_value >= ODD_MINIMA_DE_VALOR:
                        tipo_palpite = f"Over {linha} Cantos Fora"
                        conf_base = min(round(5.0 + (media_fora - requisito) * 2.0, 1), 9.5)
                        conf = ajustar_confianca_por_odd(conf_base, odd_value)
                        if script_name:
                            
                            
                                continue
                        if conf >= 5.0:
                            palpites.append({"tipo": f"Over {linha}", "confianca": conf, "odd": odd_value, "periodo": "FT", "time": "Fora"})
                except ValueError:
                    continue

            elif odd_key.startswith("cantos_fora_under_"):
                try:
                    linha = float(odd_key.replace("cantos_fora_under_", ""))
                    requisito = linha - 0.3
                    if media_fora < requisito and odd_value >= ODD_MINIMA_DE_VALOR:
                        tipo_palpite = f"Under {linha} Cantos Fora"
                        conf_base = min(round(5.0 + (requisito - media_fora) * 2.0, 1), 9.5)
                        conf = ajustar_confianca_por_odd(conf_base, odd_value)
                        if script_name:
                            
                            
                                continue
                        if conf >= 5.5:
                            palpites.append({"tipo": f"Under {linha}", "confianca": conf, "odd": odd_value, "periodo": "FT", "time": "Fora"})
                except ValueError:
                    continue

    print(f"  DEBUG CANTOS FINAL: {len(palpites)} palpites encontrados. Media_exp={media_exp_ft_ajustada:.1f}, Media_casa={media_casa:.1f}, Media_fora={media_fora:.1f}")

    if palpites:
        print(f"  ✅ CANTOS: Retornando {len(palpites)} palpites com odds")
        contexto_str = ""
        if contexto_insights:
            contexto_str = f"   - <b>💡 Contexto:</b> {contexto_insights[0][:120]}...\n" if len(contexto_insights[0]) > 120 else f"   - <b>💡 Contexto:</b> {contexto_insights[0]}\n"

        suporte = (f"   - <b>Expectativa Total:</b> {round(media_exp_ft, 2)} → {round(media_exp_ft_ajustada, 2)} (ajustada)\n"
                   f"   - <b>Casa:</b> {stats_casa['casa']['cantos_feitos']:.1f} → {media_casa:.1f} cantos/jogo\n"
                   f"{contexto_str}")
        return {"mercado": "Cantos", "palpites": palpites, "dados_suporte": suporte}
    
    if master_data:
        print(f"  🧠 CANTOS: Sem odds, gerando SUGESTÃO TÁTICA baseada em análise contextual")
        from analysts.contextual_analyzer import ContextualAnalyzer
        
        analista = ContextualAnalyzer(master_data)
        insight = analista.analisar_cantos_contextual()
        
        palpite_tatico = {
            "tipo": insight.sugestao,
            "confianca": insight.confianca,
            "odd": None,
            "periodo": "FT",
            "time": "Total",
            "narrativa_tatica": insight.narrativa,
            "evidencias": insight.evidencias
        }
        
        suporte = (f"   - <b>🧠 Análise Tática (sem odd disponível):</b>\n"
                   f"{insight.narrativa}\n\n"
                   f"   - <b>Evidências:</b>\n" + "\n".join([f"      {e}" for e in insight.evidencias]))
        
        return {"mercado": "Cantos", "palpites": [palpite_tatico], "dados_suporte": suporte, "tatico_apenas": True}
    
    print(f"  ❌ CANTOS: Sem odds e sem master_data para análise tática")
    return None
