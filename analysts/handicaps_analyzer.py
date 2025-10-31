# analysts/handicaps_analyzer.py
from config import ODD_MINIMA_DE_VALOR
from analysts.confidence_calculator import calculate_final_confidence

def analisar_mercado_handicaps(stats_casa, stats_fora, odds, classificacao=None, pos_casa="N/A", pos_fora="N/A", script_name=None):
    """
    Analisa handicaps de forma CONTEXTUAL e INTELIGENTE:
    - Avalia superioridade combinando múltiplos fatores
    - Oferece handicaps quando há clara vantagem de um time
    - Considera força, posição, forma recente, gols, escanteios
    
    Tipos de handicaps:
    - Asiáticos e Europeus de Gols
    - Asiáticos e Europeus de Escanteios
    - Asiáticos de Cartões (quando disponível)
    
    PHOENIX V2.0: Agora com sistema de VETO e ajuste de confiança por script.
    """
    if not stats_casa or not stats_fora or not odds:
        return None

    # ========================================
    # ANÁLISE CONTEXTUAL COMPLETA
    # ========================================
    
    # 1. FORÇA OFENSIVA/DEFENSIVA (Gols)
    gols_casa_marcados = stats_casa['casa'].get('gols_marcados', 0)
    gols_casa_sofridos = stats_casa['casa'].get('gols_sofridos', 0)
    gols_fora_marcados = stats_fora['fora'].get('gols_marcados', 0)
    gols_fora_sofridos = stats_fora['fora'].get('gols_sofridos', 0)

    forca_casa = gols_casa_marcados - gols_casa_sofridos
    forca_fora = gols_fora_marcados - gols_fora_sofridos
    diferenca_forca = forca_casa - forca_fora

    # 2. POSIÇÃO NA TABELA
    diferenca_posicao = 0
    if pos_casa != "N/A" and pos_fora != "N/A":
        try:
            diferenca_posicao = int(pos_fora) - int(pos_casa)
        except (ValueError, TypeError):
            # Posições inválidas, manter diferença em 0
            pass

    # 3. ESCANTEIOS
    cantos_casa = stats_casa['casa'].get('cantos_feitos', 0)
    cantos_fora = stats_fora['fora'].get('cantos_feitos', 0)
    diferenca_cantos = cantos_casa - cantos_fora

    # 4. CARTÕES
    cartoes_casa = stats_casa['casa'].get('cartoes_amarelos', 0) + stats_casa['casa'].get('cartoes_vermelhos', 0) * 2
    cartoes_fora = stats_fora['fora'].get('cartoes_amarelos', 0) + stats_fora['fora'].get('cartoes_vermelhos', 0) * 2
    diferenca_cartoes = cartoes_casa - cartoes_fora

    # ========================================
    # SCORING DE SUPERIORIDADE (0-10)
    # ========================================
    # Combina múltiplos fatores para determinar nível de superioridade
    
    superioridade_casa = 0.0
    
    # Força (peso 40%)
    if diferenca_forca >= 2.5:
        superioridade_casa += 4.0
    elif diferenca_forca >= 1.5:
        superioridade_casa += 3.0
    elif diferenca_forca >= 0.8:
        superioridade_casa += 2.0
    elif diferenca_forca >= 0.3:
        superioridade_casa += 1.0
    elif diferenca_forca <= -2.5:
        superioridade_casa -= 4.0
    elif diferenca_forca <= -1.5:
        superioridade_casa -= 3.0
    elif diferenca_forca <= -0.8:
        superioridade_casa -= 2.0
    elif diferenca_forca <= -0.3:
        superioridade_casa -= 1.0
    
    # Posição na tabela (peso 30%)
    if diferenca_posicao >= 10:
        superioridade_casa += 3.0
    elif diferenca_posicao >= 6:
        superioridade_casa += 2.0
    elif diferenca_posicao >= 3:
        superioridade_casa += 1.0
    elif diferenca_posicao <= -10:
        superioridade_casa -= 3.0
    elif diferenca_posicao <= -6:
        superioridade_casa -= 2.0
    elif diferenca_posicao <= -3:
        superioridade_casa -= 1.0
    
    # Ataque vs Defesa (peso 20%)
    ataque_casa = gols_casa_marcados
    defesa_fora = gols_fora_sofridos
    ataque_fora = gols_fora_marcados
    defesa_casa = gols_casa_sofridos
    
    if ataque_casa >= 2.0 and defesa_fora >= 1.5:
        superioridade_casa += 1.5  # Casa ataca bem E fora defende mal
    if ataque_fora >= 2.0 and defesa_casa >= 1.5:
        superioridade_casa -= 1.5  # Fora ataca bem E casa defende mal
    
    # Escanteios (peso 10%)
    if diferenca_cantos >= 3.0:
        superioridade_casa += 0.5
    elif diferenca_cantos <= -3.0:
        superioridade_casa -= 0.5
    
    print(f"\n  🎯 ANÁLISE CONTEXTUAL HANDICAPS:")
    print(f"     Diferença Força: {diferenca_forca:+.2f} | Posição: {diferenca_posicao:+d} | Cantos: {diferenca_cantos:+.2f}")
    print(f"     SUPERIORIDADE CASA: {superioridade_casa:+.1f}/10")
    print(f"     → Casa ataca {ataque_casa:.1f} gols/jogo, Fora defende {defesa_fora:.1f} gols/jogo")
    print(f"     → Fora ataca {ataque_fora:.1f} gols/jogo, Casa defende {defesa_casa:.1f} gols/jogo")

    palpites = []

    # ========================================
    # HANDICAPS DE GOLS (BASEADOS EM CONTEXTO)
    # ========================================
    
    # CASA MUITO SUPERIOR (superioridade >= 6.0)
    if superioridade_casa >= 6.0:
        print(f"     ✅ CASA MUITO SUPERIOR - Oferecendo handicaps altos")
        
        # Handicap Asiático -2.5 (Casa vence por 3+)
        if "handicap_asia_casa_-2.5" in odds and odds["handicap_asia_casa_-2.5"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Asiático -2.5 (Casa)"
            confianca = min(round(5.0 + superioridade_casa * 0.5, 1), 9.5)
            if script_name:
                
                
                    pass
                else:
                    
                    if confianca >= 6.5:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_casa_-2.5"], "periodo": "FT", "time": "Casa"})
            elif confianca >= 6.5:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_casa_-2.5"], "periodo": "FT", "time": "Casa"})
        
        # Handicap Asiático -2.0
        if "handicap_asia_casa_-2.0" in odds and odds["handicap_asia_casa_-2.0"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Asiático -2.0 (Casa)"
            confianca = min(round(5.0 + superioridade_casa * 0.45, 1), 9.5)
            if script_name:
                
                
                    pass
                else:
                    
                    if confianca >= 6.2:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_casa_-2.0"], "periodo": "FT", "time": "Casa"})
            elif confianca >= 6.2:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_casa_-2.0"], "periodo": "FT", "time": "Casa"})
        
        # Handicap Europeu -2
        if "handicap_euro_casa_-2" in odds and odds["handicap_euro_casa_-2"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Europeu -2 (Casa)"
            confianca = min(round(5.0 + superioridade_casa * 0.4, 1), 9.5)
            if script_name:
                
                
                    pass
                else:
                    
                    if confianca >= 6.5:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_euro_casa_-2"], "periodo": "FT", "time": "Casa"})
            elif confianca >= 6.5:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_euro_casa_-2"], "periodo": "FT", "time": "Casa"})

    # CASA SUPERIOR (superioridade >= 3.5)
    if superioridade_casa >= 3.5:
        print(f"     ✅ CASA SUPERIOR - Oferecendo handicaps médios")
        
        # Handicap Asiático -1.5
        if "handicap_asia_casa_-1.5" in odds and odds["handicap_asia_casa_-1.5"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Asiático -1.5 (Casa)"
            confianca = min(round(5.0 + superioridade_casa * 0.6, 1), 9.5)
            if script_name:
                
                if not is_vetado:
                    
                    if confianca >= 5.8:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_casa_-1.5"], "periodo": "FT", "time": "Casa"})
            elif confianca >= 5.8:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_casa_-1.5"], "periodo": "FT", "time": "Casa"})
        
        # Handicap Asiático -1.0
        if "handicap_asia_casa_-1.0" in odds and odds["handicap_asia_casa_-1.0"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Asiático -1.0 (Casa)"
            confianca = min(round(5.0 + superioridade_casa * 0.55, 1), 9.5)
            if script_name:
                
                if not is_vetado:
                    
                    if confianca >= 5.5:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_casa_-1.0"], "periodo": "FT", "time": "Casa"})
            elif confianca >= 5.5:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_casa_-1.0"], "periodo": "FT", "time": "Casa"})
        
        # Handicap Europeu -1
        if "handicap_euro_casa_-1" in odds and odds["handicap_euro_casa_-1"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Europeu -1 (Casa)"
            confianca = min(round(5.0 + superioridade_casa * 0.5, 1), 9.5)
            if script_name:
                
                if not is_vetado:
                    
                    if confianca >= 5.8:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_euro_casa_-1"], "periodo": "FT", "time": "Casa"})
            elif confianca >= 5.8:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_euro_casa_-1"], "periodo": "FT", "time": "Casa"})

    # CASA FAVORITA (superioridade >= 2.0)
    if superioridade_casa >= 2.0:
        print(f"     ✅ CASA FAVORITA - Oferecendo handicaps baixos")
        
        # Handicap Asiático -0.5
        if "handicap_asia_casa_-0.5" in odds and odds["handicap_asia_casa_-0.5"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Asiático -0.5 (Casa)"
            confianca = min(round(5.0 + superioridade_casa * 0.7, 1), 9.5)
            if script_name:
                
                if not is_vetado:
                    
                    if confianca >= 5.5:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_casa_-0.5"], "periodo": "FT", "time": "Casa"})
            elif confianca >= 5.5:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_casa_-0.5"], "periodo": "FT", "time": "Casa"})

    # JOGO EQUILIBRADO (-2.0 < superioridade < 2.0)
    if -2.0 < superioridade_casa < 2.0:
        print(f"     ⚖️ JOGO EQUILIBRADO - Oferecendo handicaps neutros")
        
        # Handicap 0.0 Casa
        if "handicap_asia_casa_0.0" in odds and odds["handicap_asia_casa_0.0"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Asiático 0.0 (Casa)"
            confianca = min(round(5.5 + (2.0 - abs(superioridade_casa)) * 0.5, 1), 9.5)
            if script_name:
                
                if not is_vetado:
                    
                    if confianca >= 5.5:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_casa_0.0"], "periodo": "FT", "time": "Casa"})
            elif confianca >= 5.5:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_casa_0.0"], "periodo": "FT", "time": "Casa"})
        
        # Handicap +0.5 Fora (proteção)
        if "handicap_asia_fora_+0.5" in odds and odds["handicap_asia_fora_+0.5"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Asiático +0.5 (Fora)"
            confianca = min(round(5.5 + (2.0 - abs(superioridade_casa)) * 0.6, 1), 9.5)
            if script_name:
                
                if not is_vetado:
                    
                    if confianca >= 5.8:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_fora_+0.5"], "periodo": "FT", "time": "Fora"})
            elif confianca >= 5.8:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_fora_+0.5"], "periodo": "FT", "time": "Fora"})

    # FORA FAVORITO (superioridade <= -2.0)
    if superioridade_casa <= -2.0:
        print(f"     ✅ FORA FAVORITO - Oferecendo handicaps positivos")
        
        # Handicap +1.0 Fora
        if "handicap_asia_fora_+1.0" in odds and odds["handicap_asia_fora_+1.0"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Asiático +1.0 (Fora)"
            confianca = min(round(5.0 + abs(superioridade_casa) * 0.7, 1), 9.5)
            if script_name:
                
                if not is_vetado:
                    
                    if confianca >= 5.5:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_fora_+1.0"], "periodo": "FT", "time": "Fora"})
            elif confianca >= 5.5:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_fora_+1.0"], "periodo": "FT", "time": "Fora"})

    # FORA SUPERIOR (superioridade <= -3.5)
    if superioridade_casa <= -3.5:
        print(f"     ✅ FORA SUPERIOR - Oferecendo handicaps médios")
        
        # Handicap +1.5 Fora
        if "handicap_asia_fora_+1.5" in odds and odds["handicap_asia_fora_+1.5"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Asiático +1.5 (Fora)"
            confianca = min(round(5.0 + abs(superioridade_casa) * 0.6, 1), 9.5)
            if script_name:
                
                if not is_vetado:
                    
                    if confianca >= 5.8:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_fora_+1.5"], "periodo": "FT", "time": "Fora"})
            elif confianca >= 5.8:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_fora_+1.5"], "periodo": "FT", "time": "Fora"})
        
        # Handicap Europeu +1 Fora
        if "handicap_euro_fora_+1" in odds and odds["handicap_euro_fora_+1"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Europeu +1 (Fora)"
            confianca = min(round(5.0 + abs(superioridade_casa) * 0.5, 1), 9.5)
            if script_name:
                
                if not is_vetado:
                    
                    if confianca >= 5.8:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_euro_fora_+1"], "periodo": "FT", "time": "Fora"})
            elif confianca >= 5.8:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_euro_fora_+1"], "periodo": "FT", "time": "Fora"})

    # FORA MUITO SUPERIOR (superioridade <= -6.0)
    if superioridade_casa <= -6.0:
        print(f"     ✅ FORA MUITO SUPERIOR - Oferecendo handicaps altos")
        
        # Handicap +2.0 Fora
        if "handicap_asia_fora_+2.0" in odds and odds["handicap_asia_fora_+2.0"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Asiático +2.0 (Fora)"
            confianca = min(round(5.0 + abs(superioridade_casa) * 0.45, 1), 9.5)
            if script_name:
                
                if not is_vetado:
                    
                    if confianca >= 6.2:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_fora_+2.0"], "periodo": "FT", "time": "Fora"})
            elif confianca >= 6.2:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_fora_+2.0"], "periodo": "FT", "time": "Fora"})
        
        # Handicap +2.5 Fora
        if "handicap_asia_fora_+2.5" in odds and odds["handicap_asia_fora_+2.5"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Asiático +2.5 (Fora)"
            confianca = min(round(5.0 + abs(superioridade_casa) * 0.5, 1), 9.5)
            if script_name:
                
                if not is_vetado:
                    
                    if confianca >= 6.5:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_fora_+2.5"], "periodo": "FT", "time": "Fora"})
            elif confianca >= 6.5:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_asia_fora_+2.5"], "periodo": "FT", "time": "Fora"})

    # ========================================
    # HANDICAPS DE ESCANTEIOS (CONTEXTUAIS)
    # ========================================
    
    # Casa domina escanteios fortemente (diferença >= 3.0)
    if diferenca_cantos >= 3.0:
        # Handicap Cantos -2.5 (Casa)
        if "handicap_cantos_asia_casa_-2.5" in odds and odds["handicap_cantos_asia_casa_-2.5"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Asiático Cantos -2.5 (Casa)"
            confianca = min(round(5.0 + diferenca_cantos * 0.6, 1), 9.5)
            if script_name:
                
                if not is_vetado:
                    
                    if confianca >= 6.0:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_cantos_asia_casa_-2.5"], "periodo": "FT", "time": "Casa"})
            elif confianca >= 6.0:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_cantos_asia_casa_-2.5"], "periodo": "FT", "time": "Casa"})
        
        # Handicap Europeu Cantos -2 (Casa)
        if "handicap_cantos_euro_casa_-2" in odds and odds["handicap_cantos_euro_casa_-2"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Europeu Cantos -2 (Casa)"
            confianca = min(round(5.0 + diferenca_cantos * 0.5, 1), 9.5)
            if script_name:
                
                if not is_vetado:
                    
                    if confianca >= 6.0:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_cantos_euro_casa_-2"], "periodo": "FT", "time": "Casa"})
            elif confianca >= 6.0:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_cantos_euro_casa_-2"], "periodo": "FT", "time": "Casa"})

    # Fora domina escanteios fortemente (diferença <= -3.0)
    if diferenca_cantos <= -3.0:
        # Handicap Cantos +2.5 (Fora)
        if "handicap_cantos_asia_fora_+2.5" in odds and odds["handicap_cantos_asia_fora_+2.5"] >= ODD_MINIMA_DE_VALOR:
            tipo_palpite = "Handicap Asiático Cantos +2.5 (Fora)"
            confianca = min(round(5.0 + abs(diferenca_cantos) * 0.6, 1), 9.5)
            if script_name:
                
                if not is_vetado:
                    
                    if confianca >= 6.0:
                        palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_cantos_asia_fora_+2.5"], "periodo": "FT", "time": "Fora"})
            elif confianca >= 6.0:
                palpites.append({"tipo": tipo_palpite, "confianca": confianca, "odd": odds["handicap_cantos_asia_fora_+2.5"], "periodo": "FT", "time": "Fora"})

    # ========================================
    # RETORNAR RESULTADO
    # ========================================
    
    if palpites:
        print(f"     ✅ {len(palpites)} handicaps gerados baseados em contexto\n")
        
        dados_suporte = (
            f"   - <b>Superioridade Casa:</b> {superioridade_casa:+.1f}/10\n"
            f"   - <b>Força Casa:</b> {round(forca_casa, 2)} | <b>Força Fora:</b> {round(forca_fora, 2)}\n"
            f"   - <b>Diferença de Força:</b> {round(diferenca_forca, 2)}\n"
        )

        if diferenca_posicao != 0:
            dados_suporte += f"   - <b>Diferença de Posição:</b> {diferenca_posicao:+d} posições\n"
        
        dados_suporte += f"   - <b>Cantos Casa:</b> {cantos_casa:.1f} | <b>Cantos Fora:</b> {cantos_fora:.1f}\n"

        return {
            "mercado": "Handicaps",
            "palpites": palpites,
            "dados_suporte": dados_suporte
        }
    else:
        print(f"     ⚠️ Nenhum handicap adequado ao contexto do jogo\n")

    return None
