# analysts/cards_analyzer.py
from config import ODD_MINIMA_DE_VALOR, MIN_CONFIANCA_CARTOES, MIN_CONFIANCA_CANTOS_UNDER
from analysts.context_analyzer import verificar_veto_mercado, ajustar_confianca_por_script

def analisar_mercado_cartoes(stats_casa, stats_fora, odds, master_data=None, script_name=None):
    """
    Analisa o mercado de Cartões (Over/Under Total/Casa/Fora) para um jogo.
    Gera sugestão tática MESMO SEM ODDS quando master_data disponível.
    
    PHOENIX V2.0: Agora com sistema de VETO e ajuste de confiança por script.
    """
    print(f"  🔍 CARTÕES: Verificando dados... stats_casa={bool(stats_casa)}, stats_fora={bool(stats_fora)}, odds={bool(odds)}, master_data={bool(master_data)}")
    if not stats_casa or not stats_fora:
        print(f"  ⚠️ CARTÕES: Retornando None (faltam stats)")
        return None

    # ✅ USAR LÓGICA DE PARSING FUNCIONAL
    # Extrair dados usando as chaves corretas da estrutura retornada por buscar_estatisticas_gerais_time
    cartoes_amarelos_casa = stats_casa.get('casa', {}).get('cartoes_amarelos', 0.0)
    cartoes_vermelhos_casa = stats_casa.get('casa', {}).get('cartoes_vermelhos', 0.0)
    cartoes_amarelos_fora = stats_fora.get('fora', {}).get('cartoes_amarelos', 0.0)
    cartoes_vermelhos_fora = stats_fora.get('fora', {}).get('cartoes_vermelhos', 0.0)

    cartoes_casa = cartoes_amarelos_casa + cartoes_vermelhos_casa
    cartoes_fora = cartoes_amarelos_fora + cartoes_vermelhos_fora

    # 🛡️ SHIELD RULE: Se TODOS os valores são 0.0, retornar None imediatamente  
    if (cartoes_amarelos_casa == 0.0 and cartoes_vermelhos_casa == 0.0 and 
        cartoes_amarelos_fora == 0.0 and cartoes_vermelhos_fora == 0.0):
        print("  ❌ CARTÕES BLOQUEADO: Dados insuficientes (todos 0.0) - API não retornou stats")
        return None

    print(f"\n  🔍 DEBUG CARTÕES - DADOS RECEBIDOS:")
    print(f"     Casa: {cartoes_casa:.1f} total ({cartoes_amarelos_casa:.1f} amarelos + {cartoes_vermelhos_casa:.1f} vermelhos)")
    print(f"     Fora: {cartoes_fora:.1f} total ({cartoes_amarelos_fora:.1f} amarelos + {cartoes_vermelhos_fora:.1f} vermelhos)")

    # ✅ TASK 3b: AJUSTE DE CONFIANÇA BASEADO EM QSC DINÂMICO
    qsc_adjustment = 0.0
    if master_data and 'analysis_summary' in master_data:
        qsc_home = master_data['analysis_summary'].get('qsc_home', 50)
        qsc_away = master_data['analysis_summary'].get('qsc_away', 50)
        qsc_avg = (qsc_home + qsc_away) / 2
        
        # Times de maior qualidade (QSC alto) tendem a ser mais disciplinados
        # Times de menor qualidade (QSC baixo) tendem a levar mais cartões
        # QSC 80+ = -0.5 confiança (times disciplinados)
        # QSC 50-70 = neutro
        # QSC <40 = +0.5 confiança (times indisciplinados)
        if qsc_avg >= 80:
            qsc_adjustment = -0.5
        elif qsc_avg >= 70:
            qsc_adjustment = -0.2
        elif qsc_avg <= 40:
            qsc_adjustment = +0.5
        elif qsc_avg <= 50:
            qsc_adjustment = +0.3
        
        print(f"     🧠 QSC Médio: {qsc_avg:.1f} → Ajuste confiança: {qsc_adjustment:+.1f}")

    media_exp_total = (cartoes_casa + cartoes_fora) / 2
    media_casa = cartoes_casa
    media_fora = cartoes_fora

    palpites = []

    # ⚠️ PROTEÇÃO: Só buscar odds se estiverem disponíveis
    if odds:
        # --- TOTAL (Full Time) ---
        # ⚡ AJUSTADO: Requisitos reduzidos para capturar mais oportunidades
        linhas_over_total = {2.5: 2.8, 3.5: 3.8, 4.5: 4.8, 5.5: 5.8}
        for linha, req in linhas_over_total.items():
            odd_key = f"cartoes_over_{linha}"
            if media_exp_total >= req and odd_key in odds and odds[odd_key] >= ODD_MINIMA_DE_VALOR:
                confianca = min(round(5.0 + (media_exp_total - req) * 2.0 + qsc_adjustment, 1), 9.5)
                
                # LAYER 3 & 4: VETO e ajuste de confiança
                tipo_palpite = f"Over {linha} Cartões"
                if script_name:
                    is_vetado, razao_veto = verificar_veto_mercado(tipo_palpite, script_name)
                    if is_vetado:
                        print(f"  🚫 VETO: {tipo_palpite} vetado por {script_name} - {razao_veto}")
                        continue
                    confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                
                # ⚡ AJUSTADO: Threshold reduzido de 5.5 para 5.0
                if confianca >= 5.0:
                    palpites.append({
                        "tipo": f"Over {linha}",
                        "confianca": confianca,
                        "odd": odds[odd_key],
                        "time": "Total"
                    })

        # Under Total
        linhas_under_total = {5.5: 4.7, 4.5: 3.7, 3.5: 2.7}
        for linha, req in linhas_under_total.items():
            odd_key = f"cartoes_under_{linha}"
            if media_exp_total < req and odd_key in odds and odds[odd_key] >= ODD_MINIMA_DE_VALOR:
                tipo_palpite = f"Under {linha} Cartões"
                confianca = min(round(5.0 + (req - media_exp_total) * 2.0 - qsc_adjustment, 1), 9.5)
                if script_name:
                    is_vetado, _ = verificar_veto_mercado(tipo_palpite, script_name)
                    if is_vetado:
                        continue
                    confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                if confianca >= 5.5:
                    palpites.append({"tipo": f"Under {linha}", "confianca": confianca, "odd": odds[odd_key], "time": "Total"})

        # Casa Over/Under
        linhas_casa = {1.5: 1.8, 2.5: 2.8, 3.5: 3.8}
        for linha, req in linhas_casa.items():
            odd_key_over = f"cartoes_casa_over_{linha}"
            if media_casa >= req and odd_key_over in odds and odds[odd_key_over] >= ODD_MINIMA_DE_VALOR:
                tipo_palpite = f"Over {linha} Cartões Casa"
                confianca = min(round(5.0 + (media_casa - req) * 2.0 + qsc_adjustment, 1), 9.5)
                if script_name:
                    is_vetado, _ = verificar_veto_mercado(tipo_palpite, script_name)
                    if is_vetado:
                        continue
                    confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                if confianca >= 5.0:
                    palpites.append({"tipo": f"Over {linha}", "confianca": confianca, "odd": odds[odd_key_over], "time": "Casa"})

            odd_key_under = f"cartoes_casa_under_{linha}"
            if media_casa < (req - 0.3) and odd_key_under in odds and odds[odd_key_under] >= ODD_MINIMA_DE_VALOR:
                tipo_palpite = f"Under {linha} Cartões Casa"
                confianca = min(round(5.0 + (req - media_casa) * 2.0 - qsc_adjustment, 1), 9.5)
                if script_name:
                    is_vetado, _ = verificar_veto_mercado(tipo_palpite, script_name)
                    if is_vetado:
                        continue
                    confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                if confianca >= 5.5:
                    palpites.append({"tipo": f"Under {linha}", "confianca": confianca, "odd": odds[odd_key_under], "time": "Casa"})

        # Fora Over/Under
        linhas_fora = {1.5: 1.8, 2.5: 2.8, 3.5: 3.8}
        for linha, req in linhas_fora.items():
            odd_key_over = f"cartoes_fora_over_{linha}"
            if media_fora >= req and odd_key_over in odds and odds[odd_key_over] >= ODD_MINIMA_DE_VALOR:
                tipo_palpite = f"Over {linha} Cartões Fora"
                confianca = min(round(5.0 + (media_fora - req) * 2.0 + qsc_adjustment, 1), 9.5)
                if script_name:
                    is_vetado, _ = verificar_veto_mercado(tipo_palpite, script_name)
                    if is_vetado:
                        continue
                    confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                if confianca >= 5.0:
                    palpites.append({"tipo": f"Over {linha}", "confianca": confianca, "odd": odds[odd_key_over], "time": "Fora"})

            odd_key_under = f"cartoes_fora_under_{linha}"
            if media_fora < (req - 0.3) and odd_key_under in odds and odds[odd_key_under] >= ODD_MINIMA_DE_VALOR:
                tipo_palpite = f"Under {linha} Cartões Fora"
                confianca = min(round(5.0 + (req - media_fora) * 2.0 - qsc_adjustment, 1), 9.5)
                if script_name:
                    is_vetado, _ = verificar_veto_mercado(tipo_palpite, script_name)
                    if is_vetado:
                        continue
                    confianca = ajustar_confianca_por_script(confianca, tipo_palpite, script_name)
                if confianca >= 5.5:
                    palpites.append({"tipo": f"Under {linha}", "confianca": confianca, "odd": odds[odd_key_under], "time": "Fora"})
    
    # Retornar palpites com odds se encontrados
    if palpites:
        suporte = (f"   - <b>Expectativa Cartões Total:</b> {round(media_exp_total, 2)}\n"
                   f"   - <b>Casa:</b> {media_casa:.1f} cartões/jogo | <b>Fora:</b> {media_fora:.1f} cartões/jogo\n")
        return {"mercado": "Cartões", "palpites": palpites, "dados_suporte": suporte}
    
    if master_data:
        print(f"  🧠 CARTÕES: Sem odds, gerando SUGESTÃO TÁTICA baseada em análise contextual")
        from analysts.contextual_analyzer import ContextualAnalyzer
        
        analista = ContextualAnalyzer(master_data)
        insight = analista.analisar_cartoes_contextual()
        
        palpite_tatico = {
            "tipo": insight.sugestao,
            "confianca": insight.confianca,
            "odd": None,
            "time": "Total",
            "narrativa_tatica": insight.narrativa,
            "evidencias": insight.evidencias
        }
        
        suporte = (f"   - <b>🧠 Análise Tática (sem odd disponível):</b>\n"
                   f"{insight.narrativa}\n\n"
                   f"   - <b>Evidências:</b>\n" + "\n".join([f"      {e}" for e in insight.evidencias]))
        
        return {"mercado": "Cartões", "palpites": [palpite_tatico], "dados_suporte": suporte, "tatico_apenas": True}
    
    print(f"  ❌ CARTÕES: Sem odds e sem master_data para análise tática")
    return None
